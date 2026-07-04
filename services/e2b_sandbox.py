"""services/e2b_sandbox.py — E2B Firecracker micro-VM sandbox session.

Implements the same ``async def call_tool(name, arguments) -> str`` contract as
:class:`agent.mcp_client.MCPClient`, so an :class:`E2BSandboxSession` is a
drop-in replacement for ``runner._mcp``. Attaching it makes every
``write_file`` / ``run_command`` / ``clone_repo`` / ``git_commit`` /
``git_push`` execute inside a fresh E2B micro-VM (boot ≈150 ms, no local
Docker, clean per-session isolation) without touching ``agent/tools.py``.

When the SDK is missing, the sandbox is unreachable, or the quota is exhausted,
every call raises :class:`agent.mcp_client.MCPUnavailableError` — and
``AgentRunner._dispatch_tool`` already catches that and falls back to local
``WorkspaceTools`` (write_file / run_command) or surfaces a clean error
(clone_repo / git_commit / git_push are MCP-only). So unavailability
automatically degrades to today's behaviour via the existing circuit-breaker
pattern.

The token-scrub logic mirrors :mod:`mcp_server.workspace` (clone / push
rewrite the origin URL with the GitHub token, then restore the clean URL so
the token is never persisted in ``.git/config``).
"""
from __future__ import annotations

import logging
import os
from typing import Any

from agent.mcp_client import MCPUnavailableError
from services.e2b_config import E2BConfig, e2b_enabled, is_e2b_sdk_importable, resolve_e2b_config

log = logging.getLogger("qwen-proxy")


def _scrub_token(text: str, token: str | None) -> str:
    """Best-effort scrub of ``token`` from ``text``.

    Used on stderr/stdout returned from in-sandbox git commands so a leaked
    token in a git error message never escapes the sandbox boundary. Mirrors
    ``mcp_server.workspace._run``'s ``err.replace(token, "***")`` pattern.
    """
    if not token:
        return text
    return text.replace(token, "***")


def _inject_token(repo_url: str, token: str | None) -> tuple[str, str | None]:
    """Return ``(authed_url, clean_url)`` for a GitHub repo URL.

    ``authed_url`` carries the token inline for the clone / push call.
    ``clean_url`` is the un-authed URL we restore to ``origin`` afterward so
    the token is never persisted in ``.git/config``. When no token is supplied
    or the URL is not a GitHub HTTPS URL, both are the original URL.
    """
    if not token:
        return repo_url, repo_url
    if not repo_url.startswith("https://github.com/"):
        return repo_url, repo_url
    authed = repo_url.replace("https://github.com/", f"https://{token}@github.com/")
    return authed, repo_url


class E2BSandboxSession:
    """Wraps the E2B async SDK to look like an MCP client to ``AgentRunner``.

    Lifecycle:
      * ``await session.open()`` → ``AsyncSandbox.create(api_key=..., timeout=...)``
      * ``await session.call_tool(name, args)`` → file/command/git ops inside
        the sandbox
      * ``await session.close()`` → ``sandbox.kill()`` (idempotent)

    All public methods raise :class:`MCPUnavailableError` on SDK / network /
    quota failures so the caller (``AgentRunner._dispatch_tool``) falls back
    to local tools via the existing pattern.
    """

    def __init__(self, config: E2BConfig | None = None) -> None:
        self._config = config or resolve_e2b_config()
        if self._config is None:
            raise MCPUnavailableError("E2B_API_KEY not set; cannot open sandbox")
        self._sandbox: Any = None  # e2b_code_interpreter.AsyncSandbox
        self._closed = False

    @property
    def is_open(self) -> bool:
        return self._sandbox is not None and not self._closed

    async def open(self) -> "E2BSandboxSession":
        """Create the sandbox. Raises :class:`MCPUnavailableError` on failure."""
        if self._sandbox is not None:
            return self
        if not is_e2b_sdk_importable():
            raise MCPUnavailableError(
                "e2b-code-interpreter SDK not installed; cannot use E2B sandbox"
            )
        try:
            # Import inside the function so the module loads cleanly when the
            # SDK is absent (deploy without the optional dep).
            from e2b_code_interpreter import AsyncSandbox
        except ImportError as exc:
            raise MCPUnavailableError(
                f"e2b-code-interpreter import failed: {exc}"
            ) from exc

        try:
            self._sandbox = await AsyncSandbox.create(
                api_key=self._config.api_key,
                timeout=self._config.timeout_sec,
                # The E2B SDK accepts a ``template`` kwarg on create; we pass
                # it so operators can pin a custom template via E2B_TEMPLATE.
                # If a future SDK renames this kwarg, the import guard + the
                # MCPUnavailableError fallback ensure no crash.
                **({"template": self._config.template} if self._config.template else {}),
                **({"metadata": self._config.metadata} if self._config.metadata else {}),
            )
        except Exception as exc:
            # Quota / auth / network failures all surface as plain exceptions
            # from the SDK; normalise to MCPUnavailableError so the agent's
            # fallback engages.
            raise MCPUnavailableError(f"E2B sandbox create failed: {exc}") from exc
        return self

    async def close(self) -> None:
        """Kill the sandbox. Idempotent; never raises (best-effort cleanup)."""
        if self._closed:
            return
        self._closed = True
        sb = self._sandbox
        self._sandbox = None
        if sb is None:
            return
        try:
            await sb.kill()
        except Exception as exc:  # pragma: no cover - best-effort
            log.debug("E2B sandbox kill failed (best-effort): %s", exc)

    # ── MCP-compatible call_tool seam ──────────────────────────────────────

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Route an MCP-style tool call into the E2B sandbox.

        Mirrors the names used by :mod:`mcp_server.workspace` so this is a
        drop-in for ``runner._mcp``: ``write_file``, ``read_file``,
        ``run_command``, ``clone_repo``, ``git_commit``, ``git_push``,
        ``git_diff``.
        """
        if not self.is_open:
            raise MCPUnavailableError("E2B sandbox not open")
        sb = self._sandbox
        try:
            if name == "write_file":
                return await self._write_file(sb, arguments)
            if name == "read_file":
                return await self._read_file(sb, arguments)
            if name == "run_command":
                return await self._run_command(sb, arguments)
            if name == "clone_repo":
                return await self._clone_repo(sb, arguments)
            if name == "git_commit":
                return await self._git_commit(sb, arguments)
            if name == "git_push":
                return await self._git_push(sb, arguments)
            if name == "git_diff":
                return await self._git_diff(sb, arguments)
            raise MCPUnavailableError(f"E2B sandbox does not implement tool: {name}")
        except MCPUnavailableError:
            raise
        except Exception as exc:
            # Any unexpected SDK error is treated as "sandbox unavailable" so
            # the agent's existing circuit-breaker fallback engages cleanly.
            raise MCPUnavailableError(f"E2B call_tool({name}) failed: {exc}") from exc

    # ── File ops ───────────────────────────────────────────────────────────

    async def _write_file(self, sb: Any, args: dict[str, Any]) -> str:
        path = str(args.get("path", ""))
        content = str(args.get("content", ""))
        if not path:
            raise MCPUnavailableError("write_file: path is required")
        await sb.files.write(path, content)
        return f"{{\"written\": true, \"path\": \"{path}\"}}"

    async def _read_file(self, sb: Any, args: dict[str, Any]) -> str:
        path = str(args.get("path", ""))
        if not path:
            raise MCPUnavailableError("read_file: path is required")
        try:
            content = await sb.files.read(path)
        except Exception as exc:
            raise MCPUnavailableError(f"read_file({path}) failed: {exc}") from exc
        # The SDK may return bytes or str depending on the version; normalise.
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        return content

    # ── Command exec ───────────────────────────────────────────────────────

    async def _run_command(self, sb: Any, args: dict[str, Any]) -> str:
        cmd = str(args.get("cmd", ""))
        if not cmd:
            raise MCPUnavailableError("run_command: cmd is required")
        timeout = int(args.get("timeout", 120))
        try:
            result = await sb.commands.run(cmd, timeout=timeout)
        except Exception as exc:
            raise MCPUnavailableError(f"run_command failed: {exc}") from exc
        # Normalise the result shape to match mcp_server.workspace.run_command
        # so the agent's existing parsers (which look for stdout/stderr/exit_code)
        # work without modification.
        stdout = getattr(result, "stdout", "") or ""
        stderr = getattr(result, "stderr", "") or ""
        exit_code = getattr(result, "exit_code", getattr(result, "returncode", 0))
        import json as _json
        return _json.dumps({
            "stdout": stdout if isinstance(stdout, str) else stdout.decode(errors="replace"),
            "stderr": stderr if isinstance(stderr, str) else stderr.decode(errors="replace"),
            "exit_code": exit_code,
        })

    # ── Git ops ────────────────────────────────────────────────────────────

    async def _clone_repo(self, sb: Any, args: dict[str, Any]) -> str:
        repo_url = str(args.get("repo_url", ""))
        branch = str(args.get("branch", "main"))
        if not repo_url:
            raise MCPUnavailableError("clone_repo: repo_url is required")
        token = (
            os.environ.get("GITHUB_TOKEN")
            or os.environ.get("GH_TOKEN")
            or args.get("github_token")
            or ""
        )
        authed_url, clean_url = _inject_token(repo_url, token)
        # Clone shallow into /home/user/repo (E2B's default cwd is /home/user).
        # Use --depth=20 to match mcp_server.workspace.Workspace.clone.
        clone_cmd = (
            f"git clone --depth=20 --branch {branch} "
            f"{authed_url} repo"
        )
        try:
            result = await sb.commands.run(clone_cmd, timeout=120)
        except Exception as exc:
            raise MCPUnavailableError(f"git clone failed: {exc}") from exc
        stderr = getattr(result, "stderr", "") or ""
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        if getattr(result, "exit_code", getattr(result, "returncode", 0)) != 0:
            raise MCPUnavailableError(
                f"git clone failed: {_scrub_token(stderr, token).strip()}"
            )
        # Scrub token from .git/config — restore the clean origin URL.
        if token and authed_url != clean_url:
            try:
                await sb.commands.run(
                    f"git -C repo remote set-url origin {clean_url}", timeout=10
                )
            except Exception:  # pragma: no cover - best-effort
                log.debug("git remote set-url in E2B failed (best-effort)")
        import json as _json
        return _json.dumps({"cloned": True, "branch": branch})

    async def _git_commit(self, sb: Any, args: dict[str, Any]) -> str:
        message = str(args.get("message", "agent commit"))
        # Stage all by default (mirrors mcp_server.workspace.Workspace.commit
        # when ``paths`` is None).
        paths = args.get("paths")
        if paths is None:
            try:
                await sb.commands.run("git -C repo add -A", timeout=30)
            except Exception as exc:
                raise MCPUnavailableError(f"git add -A failed: {exc}") from exc
        else:
            for p in paths:
                try:
                    await sb.commands.run(f"git -C repo add {p}", timeout=30)
                except Exception as exc:
                    raise MCPUnavailableError(f"git add {p} failed: {exc}") from exc
        # Use a heredoc-safe commit message via -m with simple quoting.
        safe_msg = message.replace("'", "'\\''")
        try:
            result = await sb.commands.run(
                f"git -C repo commit -m '{safe_msg}'", timeout=30
            )
        except Exception as exc:
            raise MCPUnavailableError(f"git commit failed: {exc}") from exc
        if getattr(result, "exit_code", getattr(result, "returncode", 0)) != 0:
            stderr = getattr(result, "stderr", "") or ""
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            raise MCPUnavailableError(f"git commit failed: {stderr.strip()}")
        import json as _json
        return _json.dumps({"committed": True, "message": message})

    async def _git_push(self, sb: Any, args: dict[str, Any]) -> str:
        branch = args.get("branch")
        token = (
            os.environ.get("GITHUB_TOKEN")
            or os.environ.get("GH_TOKEN")
            or args.get("github_token")
            or ""
        )
        # Read the current origin URL, rewrite with the token for the push,
        # then restore the clean URL (mirror mcp_server.workspace.Workspace.push).
        try:
            remote_result = await sb.commands.run(
                "git -C repo remote get-url origin", timeout=10
            )
        except Exception as exc:
            raise MCPUnavailableError(f"git remote get-url failed: {exc}") from exc
        remote_url = (getattr(remote_result, "stdout", "") or "").strip()
        if isinstance(remote_url, bytes):
            remote_url = remote_url.decode(errors="replace")
        authed_url = remote_url
        if token and remote_url.startswith("https://github.com/"):
            authed_url = remote_url.replace(
                "https://github.com/", f"https://{token}@github.com/"
            )
        if authed_url != remote_url:
            try:
                await sb.commands.run(
                    f"git -C repo remote set-url origin {authed_url}", timeout=10
                )
            except Exception:  # pragma: no cover - best-effort
                pass
        try:
            if branch:
                cmd = f"git -C repo push --set-upstream origin {branch}"
            else:
                cmd = "git -C repo push"
            result = await sb.commands.run(cmd, timeout=60)
        except Exception as exc:
            raise MCPUnavailableError(f"git push failed: {exc}") from exc
        finally:
            if authed_url != remote_url and remote_url:
                try:
                    await sb.commands.run(
                        f"git -C repo remote set-url origin {remote_url}", timeout=10
                    )
                except Exception:  # pragma: no cover - best-effort
                    pass
        rc = getattr(result, "exit_code", getattr(result, "returncode", 0))
        stderr = getattr(result, "stderr", "") or ""
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        if rc != 0:
            raise MCPUnavailableError(
                f"git push failed: {_scrub_token(stderr, token).strip()}"
            )
        import json as _json
        return _json.dumps({"pushed": True})

    async def _git_diff(self, sb: Any, args: dict[str, Any]) -> str:
        try:
            result = await sb.commands.run("git -C repo diff HEAD", timeout=30)
        except Exception as exc:
            raise MCPUnavailableError(f"git diff failed: {exc}") from exc
        stdout = getattr(result, "stdout", "") or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        return stdout


async def maybe_attach_e2b(runner: Any, spec_or_ctx: Any = None) -> E2BSandboxSession | None:
    """Open an E2B session and attach it as ``runner._mcp``.

    Single wiring line for both the chat code-edit path and the task-execution
    path. Caller closes the returned session in a ``finally`` block (the agent
    loop never closes the MCP client itself — it's a session-scoped resource).

    Args:
        runner: an :class:`agent.loop.AgentRunner` (or any object exposing
            ``_mcp``). When E2B is unavailable or the SDK is missing, this is
            a no-op and ``runner._mcp`` is left untouched.
        spec_or_ctx: optional :class:`runtimes.base.TaskSpec` or context dict;
            currently unused (kept for forward-compat — future per-task sandbox
            sizing or template selection would read from here).

    Returns:
        The opened :class:`E2BSandboxSession` (caller closes it), or ``None``
        when E2B is disabled / unavailable / unconfigured. ``None`` is the
        graceful-degradation signal — the caller proceeds with today's local
        / MCP path.
    """
    if not e2b_enabled():
        return None
    if not is_e2b_sdk_importable():
        log.debug("E2B enabled but e2b-code-interpreter SDK not installed; skipping attach")
        return None
    config = resolve_e2b_config()
    if config is None:
        return None
    session = E2BSandboxSession(config=config)
    try:
        await session.open()
    except MCPUnavailableError as exc:
        log.warning("E2B sandbox open failed; falling back to local tools: %s", exc)
        return None
    # Attach. If the runner already has an MCP client (e.g. an MCP sidecar was
    # configured), prefer E2B for sandboxed execution by replacing it for the
    # duration of this run; the caller's finally restores the prior value via
    # the close() contract.
    prior = runner._mcp
    runner._mcp = session
    # Stash the prior client on the session so the caller can restore it
    # (optional — most callers just leave _mcp=None after close).
    session._prior_mcp = prior  # type: ignore[attr-defined]
    log.info("E2B sandbox attached to runner (template=%s, timeout=%ds)",
             config.template, config.timeout_sec)
    return session

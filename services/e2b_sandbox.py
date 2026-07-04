"""services/e2b_sandbox.py — E2B Firecracker micro-VM sandbox session.

Implements the same ``async def call_tool(name, arguments) -> str`` contract as
:class:`agent.mcp_client.MCPClient`, so an :class:`E2BSandboxSession` is a
drop-in replacement for ``runner._mcp``. Attaching it makes every
``write_file`` / ``read_file`` / ``run_command`` / ``apply_diff`` /
``search_code`` / ``list_files`` / ``clone_repo`` / ``git_commit`` /
``git_push`` execute inside a fresh E2B micro-VM (boot ≈150 ms, no local
Docker, clean per-session isolation) without touching ``agent/tools.py``.

**Data-flow model (post-fix)**: the sandbox has ONE working directory —
``/home/user/repo`` — shared by file ops, git ops, and command exec. This
ensures writes, reads, git diff, and pytest all agree on one location:

  * ``write_file`` / ``read_file`` / ``apply_diff`` resolve relative paths
    against ``SANDBOX_WORKDIR`` (``/home/user/repo``).
  * ``clone_repo`` clones INTO ``SANDBOX_WORKDIR``.
  * ``run_command`` cds into ``SANDBOX_WORKDIR`` before executing.
  * ``git_commit`` / ``git_push`` / ``git_diff`` run with ``-C repo``.
  * ``pytest`` runs from ``SANDBOX_WORKDIR``.

For the **agency/chat flow** (no company repo), the caller seeds the sandbox
from the host worktree via :func:`seed_from_worktree` before the run, then
extracts changed files back via :func:`extract_changes_to_worktree` after the
run. This makes the "writes go to sandbox, diffs escape to host" model real.

For the **company-repo flow**, :class:`runtimes.adapters.e2b.E2BAdapter`
clones the real repo into ``SANDBOX_WORKDIR`` and lands results via in-sandbox
``git_commit`` + ``git_push``.

When the SDK is missing, the sandbox is unreachable, or the quota is exhausted,
every call raises :class:`agent.mcp_client.MCPUnavailableError` — and
``AgentRunner._dispatch_tool`` catches that and falls back to local
``WorkspaceTools``. So unavailability automatically degrades to today's
behaviour via the existing circuit-breaker pattern.

The token-scrub logic mirrors :mod:`mcp_server.workspace` (clone / push
rewrite the origin URL with the GitHub token, then restore the clean URL so
the token is never persisted in ``.git/config``).
"""
from __future__ import annotations

import base64
import io
import json as _json
import logging
import os
import tarfile
from typing import Any

from agent.mcp_client import MCPUnavailableError
from services.e2b_config import E2BConfig, e2b_enabled, is_e2b_sdk_importable, resolve_e2b_config

log = logging.getLogger("qwen-proxy")

# ── The single sandbox working directory ─────────────────────────────────
# All file ops, git ops, and command exec share this directory so writes,
# reads, git diff, and pytest all agree on one location.
# E2B's default cwd is /home/user; we clone/seed into /home/user/repo and
# cd into it for every command.
SANDBOX_WORKDIR = "/home/user/repo"


def _scrub_token(text: str, token: str | None) -> str:
    """Best-effort scrub of ``token`` from ``text``."""
    if not token:
        return text
    return text.replace(token, "***")


def _inject_token(repo_url: str, token: str | None) -> tuple[str, str | None]:
    """Return ``(authed_url, clean_url)`` for a GitHub repo URL."""
    if not token:
        return repo_url, repo_url
    if not repo_url.startswith("https://github.com/"):
        return repo_url, repo_url
    authed = repo_url.replace("https://github.com/", f"https://{token}@github.com/")
    return authed, repo_url


def _resolve_sandbox_path(path: str) -> str:
    """Resolve a relative path against ``SANDBOX_WORKDIR``.

    Absolute paths are returned as-is (the E2B SDK expects absolute or
    relative-to-cwd paths). Relative paths are joined to ``SANDBOX_WORKDIR``
    so writes and reads land in the same directory the clone/seed populated.
    """
    if not path:
        return SANDBOX_WORKDIR
    if path.startswith("/"):
        return path
    return os.path.join(SANDBOX_WORKDIR, path)


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
        # Track whether the working dir has been seeded (clone or seed_from_worktree).
        # Used by extract_changes_to_worktree to decide whether extraction is safe.
        self._seeded = False

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
            from e2b_code_interpreter import AsyncSandbox
        except ImportError as exc:
            raise MCPUnavailableError(
                f"e2b-code-interpreter import failed: {exc}"
            ) from exc

        try:
            self._sandbox = await AsyncSandbox.create(
                api_key=self._config.api_key,
                timeout=self._config.timeout_sec,
                **({"template": self._config.template} if self._config.template else {}),
                **({"metadata": self._config.metadata} if self._config.metadata else {}),
            )
        except Exception as exc:
            raise MCPUnavailableError(f"E2B sandbox create failed: {exc}") from exc
        # Ensure the working directory exists.
        try:
            await self._sandbox.commands.run(
                f"mkdir -p {SANDBOX_WORKDIR}", timeout=10
            )
        except Exception:  # pragma: no cover - best-effort
            pass
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

        Implements: ``write_file``, ``read_file``, ``run_command``,
        ``apply_diff``, ``search_code``, ``list_files``, ``file_index``,
        ``clone_repo``, ``git_commit``, ``git_push``, ``git_diff``.

        All file/read/edit ops resolve relative paths against
        ``SANDBOX_WORKDIR`` so writes, reads, git, and pytest agree.
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
            if name == "apply_diff":
                return await self._apply_diff(sb, arguments)
            if name == "search_code":
                return await self._search_code(sb, arguments)
            if name == "list_files":
                return await self._list_files(sb, arguments)
            if name == "file_index":
                return await self._file_index(sb, arguments)
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
            raise MCPUnavailableError(f"E2B call_tool({name}) failed: {exc}") from exc

    # ── File ops (all resolve against SANDBOX_WORKDIR) ─────────────────────

    async def _write_file(self, sb: Any, args: dict[str, Any]) -> str:
        path = str(args.get("path", ""))
        content = str(args.get("content", ""))
        if not path:
            raise MCPUnavailableError("write_file: path is required")
        full_path = _resolve_sandbox_path(path)
        # Ensure parent dir exists.
        parent = os.path.dirname(full_path)
        if parent:
            await sb.commands.run(f"mkdir -p '{parent}'", timeout=10)
        await sb.files.write(full_path, content)
        return _json.dumps({"written": True, "path": path})

    async def _read_file(self, sb: Any, args: dict[str, Any]) -> str:
        path = str(args.get("path", ""))
        if not path:
            raise MCPUnavailableError("read_file: path is required")
        full_path = _resolve_sandbox_path(path)
        try:
            content = await sb.files.read(full_path)
        except Exception as exc:
            raise MCPUnavailableError(f"read_file({path}) failed: {exc}") from exc
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        return content

    # ── apply_diff: write new content to a file, return diff string ────────

    async def _apply_diff(self, sb: Any, args: dict[str, Any]) -> str:
        """Apply new content to a file inside the sandbox, return a diff.

        Mirrors ``agent/tools.py::WorkspaceTools.apply_diff``: reads the old
        content, writes the new content, and returns a unified diff string.
        All paths resolve against ``SANDBOX_WORKDIR``.
        """
        path = str(args.get("path", ""))
        new_content = str(args.get("new_content", args.get("content", "")))
        if not path:
            raise MCPUnavailableError("apply_diff: path is required")
        full_path = _resolve_sandbox_path(path)
        # Read old content (empty string if file doesn't exist).
        old_content = ""
        try:
            old_bytes = await sb.files.read(full_path)
            if isinstance(old_bytes, bytes):
                old_content = old_bytes.decode("utf-8", errors="replace")
            else:
                old_content = old_bytes
        except Exception:
            pass  # File doesn't exist yet — old_content stays ""
        # Write new content.
        parent = os.path.dirname(full_path)
        if parent:
            await sb.commands.run(f"mkdir -p '{parent}'", timeout=10)
        await sb.files.write(full_path, new_content)
        # Build unified diff.
        import difflib
        diff = "\n".join(
            difflib.unified_diff(
                old_content.splitlines(),
                new_content.splitlines(),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm="",
            )
        )
        return _json.dumps({"path": path, "diff": diff})

    # ── search_code / list_files / file_index ──────────────────────────────

    async def _search_code(self, sb: Any, args: dict[str, Any]) -> str:
        query = str(args.get("query", ""))
        limit = int(args.get("limit", 20))
        if not query:
            return _json.dumps([])
        # Use grep inside the sandbox working dir.
        cmd = (
            f"cd {SANDBOX_WORKDIR} && grep -rn --include='*.py' --include='*.js' "
            f"--include='*.ts' --include='*.jsx' --include='*.tsx' --include='*.md' "
            f"--include='*.yml' --include='*.yaml' --include='*.json' --include='*.txt' "
            f"-l '{query.replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}' . "
            f"2>/dev/null | head -{limit}"
        )
        try:
            result = await sb.commands.run(cmd, timeout=30)
        except Exception as exc:
            raise MCPUnavailableError(f"search_code failed: {exc}") from exc
        stdout = getattr(result, "stdout", "") or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        files = [line.strip() for line in stdout.strip().splitlines() if line.strip()]
        return _json.dumps(files)

    async def _list_files(self, sb: Any, args: dict[str, Any]) -> str:
        sub = str(args.get("path", "."))
        limit = int(args.get("limit", 200))
        base = _resolve_sandbox_path(sub)
        cmd = f"cd {base} && find . -type f -not -path './.git/*' | head -{limit}"
        try:
            result = await sb.commands.run(cmd, timeout=30)
        except Exception as exc:
            raise MCPUnavailableError(f"list_files failed: {exc}") from exc
        stdout = getattr(result, "stdout", "") or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        files = [line.strip().lstrip("./") for line in stdout.strip().splitlines() if line.strip()]
        return _json.dumps(files)

    async def _file_index(self, sb: Any, args: dict[str, Any]) -> str:
        sub = str(args.get("path", "."))
        max_entries = int(args.get("max_entries", 100))
        base = _resolve_sandbox_path(sub)
        cmd = (
            f"cd {base} && find . -type f -not -path './.git/*' "
            f"-printf '%p %s\\n' | head -{max_entries}"
        )
        try:
            result = await sb.commands.run(cmd, timeout=30)
        except Exception as exc:
            raise MCPUnavailableError(f"file_index failed: {exc}") from exc
        stdout = getattr(result, "stdout", "") or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        entries = []
        for line in stdout.strip().splitlines():
            parts = line.rsplit(" ", 1)
            if len(parts) == 2:
                entries.append({"path": parts[0].lstrip("./"), "size": int(parts[1]) if parts[1].isdigit() else 0})
            else:
                entries.append({"path": line.lstrip("./"), "size": 0})
        return _json.dumps(entries)

    # ── Command exec (cd into SANDBOX_WORKDIR) ─────────────────────────────

    async def _run_command(self, sb: Any, args: dict[str, Any]) -> str:
        cmd = str(args.get("cmd", ""))
        if not cmd:
            raise MCPUnavailableError("run_command: cmd is required")
        timeout = int(args.get("timeout", 120))
        # Cd into SANDBOX_WORKDIR so commands run in the same directory as
        # writes/reads/git/pytest.
        full_cmd = f"cd {SANDBOX_WORKDIR} && {cmd}"
        try:
            result = await sb.commands.run(full_cmd, timeout=timeout)
        except Exception as exc:
            raise MCPUnavailableError(f"run_command failed: {exc}") from exc
        stdout = getattr(result, "stdout", "") or ""
        stderr = getattr(result, "stderr", "") or ""
        exit_code = getattr(result, "exit_code", getattr(result, "returncode", 0))
        return _json.dumps({
            "stdout": stdout if isinstance(stdout, str) else stdout.decode(errors="replace"),
            "stderr": stderr if isinstance(stderr, str) else stderr.decode(errors="replace"),
            "exit_code": exit_code,
        })

    # ── Git ops (all use -C repo so they're independent of cwd) ───────────

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
        # Clone into SANDBOX_WORKDIR (remove any stale content first).
        clone_cmd = (
            f"rm -rf {SANDBOX_WORKDIR} && mkdir -p {SANDBOX_WORKDIR} && "
            f"git clone --depth=20 --branch {branch} {authed_url} {SANDBOX_WORKDIR}"
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
        # Scrub token from .git/config.
        if token and authed_url != clean_url:
            try:
                await sb.commands.run(
                    f"git -C {SANDBOX_WORKDIR} remote set-url origin {clean_url}", timeout=10
                )
            except Exception:  # pragma: no cover - best-effort
                log.debug("git remote set-url in E2B failed (best-effort)")
        self._seeded = True
        return _json.dumps({"cloned": True, "branch": branch})

    async def _git_commit(self, sb: Any, args: dict[str, Any]) -> str:
        message = str(args.get("message", "agent commit"))
        paths = args.get("paths")
        if paths is None:
            try:
                await sb.commands.run(f"git -C {SANDBOX_WORKDIR} add -A", timeout=30)
            except Exception as exc:
                raise MCPUnavailableError(f"git add -A failed: {exc}") from exc
        else:
            for p in paths:
                try:
                    await sb.commands.run(f"git -C {SANDBOX_WORKDIR} add {p}", timeout=30)
                except Exception as exc:
                    raise MCPUnavailableError(f"git add {p} failed: {exc}") from exc
        safe_msg = message.replace("'", "'\\''")
        try:
            result = await sb.commands.run(
                f"git -C {SANDBOX_WORKDIR} commit -m '{safe_msg}'", timeout=30
            )
        except Exception as exc:
            raise MCPUnavailableError(f"git commit failed: {exc}") from exc
        if getattr(result, "exit_code", getattr(result, "returncode", 0)) != 0:
            stderr = getattr(result, "stderr", "") or ""
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            raise MCPUnavailableError(f"git commit failed: {stderr.strip()}")
        return _json.dumps({"committed": True, "message": message})

    async def _git_push(self, sb: Any, args: dict[str, Any]) -> str:
        branch = args.get("branch")
        token = (
            os.environ.get("GITHUB_TOKEN")
            or os.environ.get("GH_TOKEN")
            or args.get("github_token")
            or ""
        )
        try:
            remote_result = await sb.commands.run(
                f"git -C {SANDBOX_WORKDIR} remote get-url origin", timeout=10
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
                    f"git -C {SANDBOX_WORKDIR} remote set-url origin {authed_url}", timeout=10
                )
            except Exception:  # pragma: no cover - best-effort
                pass
        try:
            if branch:
                cmd = f"git -C {SANDBOX_WORKDIR} push --set-upstream origin {branch}"
            else:
                cmd = f"git -C {SANDBOX_WORKDIR} push"
            result = await sb.commands.run(cmd, timeout=60)
        except Exception as exc:
            raise MCPUnavailableError(f"git push failed: {exc}") from exc
        finally:
            if authed_url != remote_url and remote_url:
                try:
                    await sb.commands.run(
                        f"git -C {SANDBOX_WORKDIR} remote set-url origin {remote_url}", timeout=10
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
        return _json.dumps({"pushed": True})

    async def _git_diff(self, sb: Any, args: dict[str, Any]) -> str:
        try:
            result = await sb.commands.run(
                f"git -C {SANDBOX_WORKDIR} diff HEAD", timeout=30
            )
        except Exception as exc:
            raise MCPUnavailableError(f"git diff failed: {exc}") from exc
        stdout = getattr(result, "stdout", "") or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        return stdout

    # ── Seed / extract (agency/chat flow) ─────────────────────────────────

    async def seed_from_worktree(self, worktree_path: str) -> bool:
        """Seed the sandbox from a host worktree by packing tracked files.

        Creates a tar of the git-tracked files in ``worktree_path``, writes
        it to the sandbox, and extracts it into ``SANDBOX_WORKDIR``. After
        this call, the agent can read, edit, and run commands against the
        same files it would have had access to in the host worktree.

        Returns ``True`` on success, ``False`` on failure (best-effort —
        the caller proceeds with an empty sandbox and the agent falls back
        to its own knowledge).
        """
        if not self.is_open:
            return False
        import subprocess
        try:
            # Get the list of tracked files.
            ls_result = subprocess.run(  # nosec B603, B607 — constant git argv, list form (no shell)
                ["git", "ls-files"],
                cwd=worktree_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if ls_result.returncode != 0:
                log.warning("E2B seed: git ls-files failed in %s: %s",
                            worktree_path, ls_result.stderr.strip())
                return False
            files = [f for f in ls_result.stdout.strip().split("\n") if f]
            if not files:
                return False

            # Create a tar in memory of the tracked files.
            tar_buf = io.BytesIO()
            with tarfile.open(fileobj=tar_buf, mode="w:gz") as tar:
                for f in files:
                    full_path = os.path.join(worktree_path, f)
                    if os.path.isfile(full_path):
                        try:
                            tar.add(full_path, arcname=f)
                        except (OSError, PermissionError):
                            pass  # Skip unreadable files
            tar_bytes = tar_buf.getvalue()
            if not tar_bytes:
                return False

            # Write the tar to the sandbox.
            # The E2B SDK's files.write accepts bytes.
            await self._sandbox.files.write("/tmp/seed.tar.gz", tar_bytes)  # nosec B108 — sandbox-internal path

            # Extract in the sandbox.
            extract_cmd = (
                f"rm -rf {SANDBOX_WORKDIR} && mkdir -p {SANDBOX_WORKDIR} && "
                f"tar xzf /tmp/seed.tar.gz -C {SANDBOX_WORKDIR} && "
                f"rm -f /tmp/seed.tar.gz"
            )
            result = await self._sandbox.commands.run(extract_cmd, timeout=120)
            rc = getattr(result, "exit_code", getattr(result, "returncode", 0))
            if rc != 0:
                stderr = getattr(result, "stderr", "") or ""
                if isinstance(stderr, bytes):
                    stderr = stderr.decode(errors="replace")
                log.warning("E2B seed: tar extract failed: %s", stderr.strip())
                return False

            # If the worktree is a git repo, init a git repo in the sandbox
            # too so git diff / git commit work for change extraction.
            try:
                await self._sandbox.commands.run(
                    f"cd {SANDBOX_WORKDIR} && git init && git add -A && "
                    f"git -c user.email='agent@e2b' -c user.name='E2B Agent' "
                    f"commit -m 'seed' --allow-empty",
                    timeout=30,
                )
            except Exception:  # pragma: no cover - best-effort
                pass

            self._seeded = True
            log.info("E2B sandbox seeded from %s (%d files)", worktree_path, len(files))
            return True
        except Exception as exc:
            log.warning("E2B seed_from_worktree failed: %s", exc)
            return False

    async def extract_changes_to_worktree(self, worktree_path: str) -> list[str]:
        """Extract changed files from the sandbox back to the host worktree.

        After the agent run, this reads the list of files changed in the
        sandbox (via ``git diff --name-only HEAD``) and writes each one back
        to the host worktree. This makes the "writes go to sandbox, diffs
        escape to host" model real — the existing changed_files collection
        and auto-commit in internal_agent.py work unchanged.

        Returns the list of changed file paths (relative to the worktree).
        """
        if not self.is_open:
            return []
        try:
            # Get the list of changed files.
            if self._seeded:
                # Sandbox was seeded → git diff works.
                result = await self._sandbox.commands.run(
                    f"git -C {SANDBOX_WORKDIR} diff --name-only HEAD", timeout=30
                )
                stdout = getattr(result, "stdout", "") or ""
                if isinstance(stdout, bytes):
                    stdout = stdout.decode(errors="replace")
                changed = [l.strip() for l in stdout.strip().splitlines() if l.strip()]
            else:
                # No git baseline → find all files (everything is "changed").
                result = await self._sandbox.commands.run(
                    f"cd {SANDBOX_WORKDIR} && find . -type f -not -path './.git/*' "
                    f"-printf '%p\\n'",
                    timeout=30,
                )
                stdout = getattr(result, "stdout", "") or ""
                if isinstance(stdout, bytes):
                    stdout = stdout.decode(errors="replace")
                changed = [l.strip().lstrip("./") for l in stdout.strip().splitlines() if l.strip()]

            # Read each changed file from the sandbox and write it to the host.
            for f in changed:
                try:
                    full_sandbox_path = os.path.join(SANDBOX_WORKDIR, f)
                    content = await self._sandbox.files.read(full_sandbox_path)
                    if isinstance(content, bytes):
                        content = content.decode("utf-8", errors="replace")
                    host_path = os.path.join(worktree_path, f)
                    os.makedirs(os.path.dirname(host_path), exist_ok=True)
                    with open(host_path, "w", encoding="utf-8") as fh:
                        fh.write(content)
                except Exception as exc:
                    log.debug("E2B extract: skip %s (%s)", f, exc)

            log.info("E2B extract: %d changed files written back to %s",
                     len(changed), worktree_path)
            return changed
        except Exception as exc:
            log.warning("E2B extract_changes_to_worktree failed: %s", exc)
            return []


async def maybe_attach_e2b(runner: Any, spec_or_ctx: Any = None) -> E2BSandboxSession | None:
    """Open an E2B session and attach it as ``runner._mcp``.

    Single wiring line for both the chat code-edit path and the task-execution
    path. Caller closes the returned session in a ``finally`` block.

    Args:
        runner: an :class:`agent.loop.AgentRunner` (or any object exposing
            ``_mcp``). When E2B is unavailable or the SDK is missing, this is
            a no-op and ``runner._mcp`` is left untouched.
        spec_or_ctx: optional :class:`runtimes.base.TaskSpec` or context dict;
            currently unused (kept for forward-compat).

    Returns:
        The opened :class:`E2BSandboxSession` (caller closes it), or ``None``
        when E2B is disabled / unavailable / unconfigured.
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
    prior = runner._mcp
    runner._mcp = session
    session._prior_mcp = prior  # type: ignore[attr-defined]
    log.info("E2B sandbox attached to runner (template=%s, timeout=%ds)",
             config.template, config.timeout_sec)
    return session

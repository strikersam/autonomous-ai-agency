"""runtimes/adapters/prime_agent.py — Prime Agent CLI adapter.

Prime Agent (https://github.com/PrimeIntellect-ai/prime-agent) is an
open-source coding and research agent built for long-running autonomous work.
It wraps ``@earendil-works/pi-coding-agent`` (the ``pi`` CLI), so this adapter
drives either binary: ``prime-agent`` when installed, ``pi`` as a fallback.

Integration mode: EXTERNAL_PROCESS
Tier: TIER_2 (promote only once benchmarked against internal_agent)

Execution model
---------------
The CLI is driven headlessly with ``-p --mode json``, which emits a stream of
newline-delimited JSON events on stdout.  Two behaviours of that CLI drive the
design here and are easy to get wrong:

1. **stdin must be closed.**  With an open stdin the process waits for
   interactive input and never exits, even under ``-p``.  We always pass
   ``stdin=DEVNULL``.
2. **The exit code is not a success signal.**  A run in which every single LLM
   call failed still exits 0.  Success is determined solely from the event
   stream — see :func:`parse_event_stream`.

All LLM traffic is routed back through this platform's own OpenAI-compatible
proxy via the extension in ``runtimes/extensions/prime_agent/agency-provider.ts``
so that provider failover, the brain watchdog, and cost accounting continue to
apply (CLAUDE.md §3: no provider implementation may bypass ProviderManager).

Configuration:
  PRIME_AGENT_BIN              — Binary name/path (default: prime-agent, then pi)
  PRIME_AGENT_MODEL            — Model id passed to --model
  PRIME_AGENT_PROVIDER         — Provider name passed to --provider (default: agency)
  PRIME_AGENT_EXTENSION        — Path to the agency provider extension (.ts)
  PRIME_AGENT_WORKSPACE        — Default working directory (default: .)
  PRIME_AGENT_TIMEOUT_SEC      — Default task timeout (default: 900)
  PRIME_AGENT_MAX_TURNS        — --autonomous-max-turns, when supported
  PRIME_AGENT_TRUST_WORKSPACE  — 'true' to load workspace-local extensions/skills
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Iterable

from runtimes.base import (
    IntegrationMode,
    RuntimeAdapter,
    RuntimeCapability,
    RuntimeDependency,
    RuntimeExecutionError,
    RuntimeHealth,
    RuntimeTier,
    RuntimeUnavailableError,
    RuntimeValidationIssue,
    TaskResult,
    TaskSpec,
)

log = logging.getLogger("runtime.prime_agent")

# Binaries tried in order when PRIME_AGENT_BIN is not set.
_DEFAULT_BINS: tuple[str, ...] = ("prime-agent", "pi")

# Environment handed to the child process. An allowlist, not os.environ: the CLI
# ships a model-controlled `bash` tool, so anything exported here is readable by
# whatever the model decides to run. Inheriting the worker environment would hand
# it GH_PAT, MONGO_URL, JWT_SECRET and every provider key in one go.
_ENV_ALLOWLIST: frozenset[str] = frozenset({
    "PATH", "HOME", "SHELL", "USER", "LOGNAME", "TMPDIR",
    "LANG", "LC_ALL", "TERM", "TZ",
    "NODE_OPTIONS", "NODE_PATH", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME",
    # Consumed by the agency provider extension, which needs them to reach our proxy.
    "AGENCY_PROXY_URL", "PROXY_API_KEY",
    "PRIME_AGENT_MODELS", "PRIME_AGENT_CONTEXT_WINDOW", "PRIME_AGENT_MAX_TOKENS",
    "PI_OFFLINE",
})

# Flags that quarantine workspace-supplied instructions. `--no-approve` alone is
# not enough: it withholds trust from workspace-local *approved* resources but
# still lets AGENTS.md / CLAUDE.md context files, prompt templates, themes and
# skills load out of the repository under test.
_UNTRUSTED_WORKSPACE_FLAGS: tuple[str, ...] = (
    "--no-approve",
    "--no-context-files",
    "--no-prompt-templates",
    "--no-themes",
    "--no-skills",
)

# stopReason values on the final assistant message that mean the run failed.
_ERROR_STOP_REASONS: frozenset[str] = frozenset({"error", "aborted"})


@dataclass
class ParsedRun:
    """Structured view of one ``--mode json`` event stream."""

    success: bool = False
    output: str = ""
    error: str | None = None
    session_id: str | None = None
    model: str | None = None
    provider: str | None = None
    stop_reason: str | None = None
    tokens_used: int | None = None
    cost_usd: float | None = None
    turns: int = 0
    retries: int = 0
    settled: bool = False
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


async def _kill_and_reap(proc: "asyncio.subprocess.Process | None") -> None:
    """Terminate a subprocess and wait for it, ignoring races.

    ``asyncio.wait_for`` cancels the pipe read but never signals the child, so
    every abandoned probe or timed-out run would otherwise leave an orphan.
    """
    if proc is None or proc.returncode is not None:
        return
    try:
        proc.kill()
        await proc.wait()
    except (ProcessLookupError, OSError) as exc:
        log.debug("prime_agent: reaping subprocess failed: %s", exc)


def _child_env() -> dict[str, str]:
    """Build the allowlisted environment for the CLI subprocess."""
    return {key: value for key, value in os.environ.items() if key in _ENV_ALLOWLIST}


def _iter_events(lines: Iterable[str]) -> Iterable[dict[str, Any]]:
    """Yield parsed JSON objects, skipping blank and non-JSON lines.

    Non-JSON lines occur when a subprocess writes diagnostics to stdout; they
    are noise, not a reason to fail the whole run.
    """
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(event, dict):
            yield event


def _assistant_messages(agent_end: dict[str, Any]) -> list[dict[str, Any]]:
    """Return assistant messages carried by an ``agent_end`` event."""
    messages = agent_end.get("messages")
    if not isinstance(messages, list):
        return []
    return [m for m in messages if isinstance(m, dict) and m.get("role") == "assistant"]


def _message_text(message: dict[str, Any]) -> str:
    """Concatenate the text blocks of one assistant message."""
    blocks = message.get("content")
    if not isinstance(blocks, list):
        return ""
    parts = [
        block.get("text", "")
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return "".join(parts).strip()


def _accumulate_usage(messages: list[dict[str, Any]]) -> tuple[int | None, float | None]:
    """Sum token and cost usage across assistant messages."""
    tokens = 0
    cost = 0.0
    seen = False
    for message in messages:
        usage = message.get("usage")
        if not isinstance(usage, dict):
            continue
        seen = True
        total = usage.get("totalTokens")
        if isinstance(total, (int, float)):
            tokens += int(total)
        cost_block = usage.get("cost")
        if isinstance(cost_block, dict) and isinstance(cost_block.get("total"), (int, float)):
            cost += float(cost_block["total"])
    return (tokens, cost) if seen else (None, None)


def parse_event_stream(lines: Iterable[str]) -> ParsedRun:
    """Reduce a ``--mode json`` NDJSON stream to a :class:`ParsedRun`.

    Kept a module-level pure function so it can be tested against captured
    fixtures without the binary, the network, or an event loop.

    Success rules, all derived from observed CLI behaviour:
      * The stream may contain **several** ``agent_end`` events — one per
        auto-retry attempt.  Only the last one describes the outcome.
      * ``auto_retry_end`` with ``success: false`` means every attempt failed.
      * A final assistant ``stopReason`` of ``error``/``aborted`` is a failure,
        and ``errorMessage`` carries the reason.
      * No ``agent_end`` at all means the process was killed mid-run.
    """
    run = ParsedRun()
    last_agent_end: dict[str, Any] | None = None
    retry_failure: str | None = None

    for event in _iter_events(lines):
        event_type = event.get("type")
        if event_type == "session":
            run.session_id = event.get("id")
        elif event_type == "turn_start":
            run.turns += 1
        elif event_type == "agent_end":
            last_agent_end = event
        elif event_type == "auto_retry_start":
            run.retries += 1
        elif event_type == "auto_retry_end":
            if event.get("success") is False:
                retry_failure = str(event.get("finalError") or "auto-retry exhausted")
        elif event_type == "agent_settled":
            run.settled = True
        elif event_type == "tool_execution_end":
            run.tool_calls.append(
                {
                    "name": event.get("toolName") or event.get("name"),
                    "ok": event.get("isError") is not True,
                    "detail": str(event.get("result") or "")[:500],
                }
            )

    if last_agent_end is None:
        run.error = "prime-agent produced no agent_end event (process killed or crashed)"
        run.output = run.error
        return run

    assistants = _assistant_messages(last_agent_end)
    run.tokens_used, run.cost_usd = _accumulate_usage(assistants)
    if not assistants:
        # agent_end with no assistant message: the run produced nothing. Falling
        # through would report success with empty output.
        run.error = "prime-agent ended without an assistant message"
        run.output = run.error
        run.success = False
        return run

    final = assistants[-1]
    run.model = final.get("model")
    run.provider = final.get("provider")
    run.stop_reason = final.get("stopReason")
    run.output = "\n".join(t for t in (_message_text(m) for m in assistants) if t)
    if final.get("errorMessage"):
        run.error = str(final["errorMessage"])

    if retry_failure:
        run.error = retry_failure
        run.success = False
    elif run.stop_reason in _ERROR_STOP_REASONS:
        run.success = False
        run.error = run.error or f"run ended with stopReason={run.stop_reason!r}"
    else:
        run.success = True

    if not run.output and not run.success and run.error:
        run.output = run.error
    return run


class PrimeAgentAdapter(RuntimeAdapter):
    """Adapter for the Prime Agent / pi coding CLI."""

    RUNTIME_ID = "prime_agent"
    DISPLAY_NAME = "Prime Agent"
    DESCRIPTION = (
        "Prime Intellect's open-source coding and research agent — persistent "
        "IPython tool environment, subagent delegation, and long-running "
        "autonomous work with turn/token budgets."
    )
    TIER = RuntimeTier.TIER_2
    INTEGRATION_MODE = IntegrationMode.EXTERNAL_PROCESS
    DOCS_URL = "https://github.com/PrimeIntellect-ai/prime-agent"
    CAPABILITIES = frozenset({
        RuntimeCapability.CODE_GENERATION,
        RuntimeCapability.CODE_REVIEW,
        RuntimeCapability.REPO_EDITING,
        RuntimeCapability.GIT_OPERATIONS,
        RuntimeCapability.FILE_READ_WRITE,
        RuntimeCapability.TOOL_USE,
        RuntimeCapability.SHELL_EXEC,
        RuntimeCapability.MULTI_FILE_EDIT,
        RuntimeCapability.STREAM_OUTPUT,
        RuntimeCapability.AUTONOMOUS_LOOP,
        RuntimeCapability.AGENT_DELEGATION,
    })

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self._bin = cfg.get("bin") or os.environ.get("PRIME_AGENT_BIN", "")
        self._model = cfg.get("model") or os.environ.get("PRIME_AGENT_MODEL", "")
        self._provider = cfg.get("provider") or os.environ.get("PRIME_AGENT_PROVIDER", "agency")
        self._extension = cfg.get("extension") or os.environ.get("PRIME_AGENT_EXTENSION", "")
        self._workspace = cfg.get("workspace") or os.environ.get("PRIME_AGENT_WORKSPACE", ".")
        self._timeout = int(cfg.get("timeout_sec") or os.environ.get("PRIME_AGENT_TIMEOUT_SEC", "900"))
        self._max_turns = os.environ.get("PRIME_AGENT_MAX_TURNS", "")
        self._trust_workspace = os.environ.get("PRIME_AGENT_TRUST_WORKSPACE", "").lower() in {"1", "true", "yes"}
        self._flag_cache: frozenset[str] | None = None

    # ── Binary + flag discovery ───────────────────────────────────────────────

    def resolve_bin(self) -> str | None:
        """Return the path of the first available CLI binary, or None."""
        candidates = (self._bin,) if self._bin else _DEFAULT_BINS
        for candidate in candidates:
            path = shutil.which(candidate)
            if path:
                return path
        return None

    async def _supported_flags(self, bin_path: str) -> frozenset[str]:
        """Parse ``--help`` once to learn which flags this build accepts.

        ``prime-agent`` adds autonomy flags that plain ``pi`` does not have;
        passing an unknown flag would fail the run, so we ask first.
        """
        if self._flag_cache is not None:
            return self._flag_cache
        flags: set[str] = set()
        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_exec(
                bin_path, "--help",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15.0)
            for token in stdout.decode(errors="replace").split():
                token = token.strip(",")
                if token.startswith("--"):
                    flags.add(token)
        except Exception as exc:
            log.debug("prime_agent: --help probe failed: %s", exc)
            # wait_for cancels the read but leaves the child running; reap it or
            # every failed probe leaks a process.
            await _kill_and_reap(proc)
        self._flag_cache = frozenset(flags)
        return self._flag_cache

    def required_dependencies(self) -> list[RuntimeDependency]:
        # Report the binary resolve_bin() would actually pick. The base class
        # preflight re-resolves this name with shutil.which, so hardcoding
        # "prime-agent" would fail a host that has only the documented `pi`
        # fallback installed — health_check() would pass and readiness_check()
        # would then block the run with missing_binary.
        resolved = self.resolve_bin()
        binary_name = os.path.basename(resolved) if resolved else (self._bin or _DEFAULT_BINS[0])
        deps = [
            RuntimeDependency(
                name=binary_name,
                config_var="PRIME_AGENT_BIN",
                install_hint=(
                    "Install Prime Agent: "
                    "curl -fsSL https://app.primeintellect.ai/prime-agent/install.sh | sh "
                    "(or `npm install -g @earendil-works/pi-coding-agent` for the `pi` CLI)."
                ),
            ),
        ]
        if self._provider == "agency" and not self._extension:
            deps.append(
                RuntimeDependency(
                    name="PRIME_AGENT_EXTENSION",
                    kind="env",
                    install_hint=(
                        "Point PRIME_AGENT_EXTENSION at "
                        "runtimes/extensions/prime_agent/agency-provider.ts so LLM calls "
                        "route through this platform's proxy."
                    ),
                )
            )
        return deps

    async def validate_task_spec(self, spec: TaskSpec) -> list[RuntimeValidationIssue]:
        """Fail preflight when the provider extension is configured but missing.

        Without the extension the CLI silently falls back to whatever provider
        keys sit in the environment, bypassing our router — a silent constitution
        violation is worse than a failed preflight.
        """
        issues = await super().validate_task_spec(spec)
        if self._provider == "agency" and not self._extension:
            issues.append(
                RuntimeValidationIssue(
                    code="missing_provider_extension",
                    field="PRIME_AGENT_EXTENSION",
                    message=(
                        "Provider 'agency' requires the proxy extension, but "
                        "PRIME_AGENT_EXTENSION is unset."
                    ),
                    fix_hint=(
                        "Set PRIME_AGENT_EXTENSION to "
                        "runtimes/extensions/prime_agent/agency-provider.ts, or choose a "
                        "different PRIME_AGENT_PROVIDER."
                    ),
                    details={"provider": self._provider},
                )
            )
        if self._extension and not os.path.isfile(self._extension):
            issues.append(
                RuntimeValidationIssue(
                    code="missing_provider_extension",
                    field="PRIME_AGENT_EXTENSION",
                    message=f"Provider extension '{self._extension}' does not exist.",
                    fix_hint=(
                        "Point PRIME_AGENT_EXTENSION at a readable .ts file, or unset it to "
                        "run against the CLI's own provider keys."
                    ),
                    details={"extension_path": self._extension},
                )
            )
        return issues

    # ── Health ────────────────────────────────────────────────────────────────

    async def health_check(self) -> RuntimeHealth:
        bin_path = self.resolve_bin()
        if not bin_path:
            wanted = self._bin or " / ".join(_DEFAULT_BINS)
            return RuntimeHealth(
                runtime_id=self.RUNTIME_ID,
                available=False,
                error=(
                    f"'{wanted}' not found in PATH. Install with "
                    "curl -fsSL https://app.primeintellect.ai/prime-agent/install.sh | sh"
                ),
            )
        t0 = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                bin_path, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15.0)
        except asyncio.TimeoutError:
            return RuntimeHealth(runtime_id=self.RUNTIME_ID, available=False,
                                 error="--version timed out after 15s")
        except Exception as exc:
            return RuntimeHealth(runtime_id=self.RUNTIME_ID, available=False, error=str(exc))

        version = stdout.decode(errors="replace").strip().splitlines()
        return RuntimeHealth(
            runtime_id=self.RUNTIME_ID,
            available=True,
            version=version[0] if version else "unknown",
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
            details={
                "bin": bin_path,
                "provider": self._provider,
                "extension": self._extension or None,
            },
        )

    # ── Execution ─────────────────────────────────────────────────────────────

    def unsupported_isolation_flags(self, supported: frozenset[str]) -> list[str]:
        """Isolation flags this build lacks, when the workspace is untrusted.

        A build that cannot quarantine workspace instructions must not silently
        run them: the caller refuses instead of degrading to a weaker posture.
        """
        if self._trust_workspace or not supported:
            return []
        return [flag for flag in _UNTRUSTED_WORKSPACE_FLAGS if flag not in supported]

    def build_command(
        self, bin_path: str, spec: TaskSpec, supported: frozenset[str]
    ) -> list[str]:
        """Assemble argv for one headless run.

        Note there is no ``--cwd``: plain ``pi`` does not accept it, so the
        working directory is set on the subprocess instead, which both binaries
        honour.
        """
        cmd = [bin_path, "-p", "--mode", "json", "--no-session"]
        if not self._trust_workspace:
            # Quarantine everything the workspace could use to steer the model.
            # Only flags this build actually accepts are passed; see
            # unsupported_isolation_flags() for the refusal path when a build is
            # too old to isolate properly.
            cmd += [flag for flag in _UNTRUSTED_WORKSPACE_FLAGS if flag in supported]
        if self._extension:
            cmd += ["--extension", self._extension]
        if self._provider:
            cmd += ["--provider", self._provider]
        model = spec.model_preference or self._model
        if model:
            cmd += ["--model", model]
        if "--autonomous" in supported:
            cmd.append("--autonomous")
            max_turns = str(spec.context.get("max_turns") or self._max_turns or "")
            if max_turns and "--autonomous-max-turns" in supported:
                cmd += ["--autonomous-max-turns", max_turns]
            if spec.max_tokens and "--autonomous-max-tokens" in supported:
                cmd += ["--autonomous-max-tokens", str(spec.max_tokens)]
        cmd.append(spec.instruction)
        return cmd

    async def execute(self, spec: TaskSpec) -> TaskResult:
        bin_path = self.resolve_bin()
        if not bin_path:
            raise RuntimeUnavailableError(
                self.RUNTIME_ID, f"'{self._bin or 'prime-agent'}' not found in PATH"
            )

        if self._provider == "agency" and not self._extension:
            # Guarded here too, not only in preflight: compare_runtimes.py and any
            # other direct caller bypasses readiness_check, and running 'agency'
            # without the extension silently falls back to ambient provider keys —
            # exactly the router bypass this adapter exists to prevent.
            raise RuntimeUnavailableError(
                self.RUNTIME_ID,
                "provider 'agency' requires PRIME_AGENT_EXTENSION (the proxy provider extension)",
            )

        workspace = spec.workspace_path or self._workspace
        supported = await self._supported_flags(bin_path)
        missing_isolation = self.unsupported_isolation_flags(supported)
        if missing_isolation:
            raise RuntimeUnavailableError(
                self.RUNTIME_ID,
                "installed CLI cannot isolate an untrusted workspace (missing "
                f"{', '.join(missing_isolation)}); upgrade it or set "
                "PRIME_AGENT_TRUST_WORKSPACE=true for workspaces you control",
            )
        cmd = self.build_command(bin_path, spec, supported)
        timeout = float(spec.timeout_sec or self._timeout)

        t0 = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,  # never inherit a TTY: the CLI would hang
                cwd=workspace,
                env=_child_env(),
            )
        except Exception as exc:
            raise RuntimeExecutionError(self.RUNTIME_ID, f"Subprocess error: {exc}", spec.task_id) from exc

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            proc.kill()
            await proc.wait()
            raise RuntimeExecutionError(
                self.RUNTIME_ID, f"Prime Agent task timed out after {timeout:.0f}s", spec.task_id
            ) from exc

        elapsed_ms = (time.monotonic() - t0) * 1000
        err_text = stderr.decode(errors="replace").strip()
        run = parse_event_stream(stdout.decode(errors="replace").splitlines())

        if not run.success:
            log.warning(
                "prime_agent task %s failed: %s (exit=%s)",
                spec.task_id, run.error, proc.returncode,
            )

        return TaskResult(
            runtime_id=self.RUNTIME_ID,
            task_id=spec.task_id,
            success=run.success,
            output=run.output or err_text,
            tool_calls=run.tool_calls,
            model_used=run.model or spec.model_preference or self._model or None,
            provider_used=run.provider or self._provider,
            tokens_used=run.tokens_used,
            cost_usd=run.cost_usd,
            execution_time_ms=elapsed_ms,
            metadata={
                # Recorded but deliberately NOT used as the success signal: the CLI
                # exits 0 even when every LLM call failed.
                "exit_code": proc.returncode,
                "session_id": run.session_id,
                "stop_reason": run.stop_reason,
                "turns": run.turns,
                "retries": run.retries,
                "settled": run.settled,
                "error": run.error,
                "stderr": err_text[:500],
            },
        )

    async def stream_execute(self, spec: TaskSpec) -> AsyncIterator[str]:
        """Stream assistant text as the CLI emits it."""
        bin_path = self.resolve_bin()
        if not bin_path:
            raise RuntimeUnavailableError(self.RUNTIME_ID, "prime-agent not found in PATH")

        if self._provider == "agency" and not self._extension:
            raise RuntimeUnavailableError(
                self.RUNTIME_ID,
                "provider 'agency' requires PRIME_AGENT_EXTENSION (the proxy provider extension)",
            )

        supported = await self._supported_flags(bin_path)
        missing_isolation = self.unsupported_isolation_flags(supported)
        if missing_isolation:
            raise RuntimeUnavailableError(
                self.RUNTIME_ID,
                "installed CLI cannot isolate an untrusted workspace (missing "
                f"{', '.join(missing_isolation)})",
            )
        cmd = self.build_command(bin_path, spec, supported)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            stdin=asyncio.subprocess.DEVNULL,
            cwd=spec.workspace_path or self._workspace,
            env=_child_env(),
        )
        assert proc.stdout is not None
        # The same deadline execute() enforces. Without it a stalled agent — or an
        # agent-spawned child holding the pipe open — streams nothing forever.
        deadline = time.monotonic() + float(spec.timeout_sec or self._timeout)
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeExecutionError(
                        self.RUNTIME_ID,
                        f"Prime Agent stream timed out after {spec.timeout_sec or self._timeout}s",
                        spec.task_id,
                    )
                try:
                    raw = await asyncio.wait_for(proc.stdout.readline(), timeout=remaining)
                except asyncio.TimeoutError as exc:
                    raise RuntimeExecutionError(
                        self.RUNTIME_ID,
                        f"Prime Agent stream timed out after {spec.timeout_sec or self._timeout}s",
                        spec.task_id,
                    ) from exc
                if not raw:
                    break
                for event in _iter_events([raw.decode(errors="replace")]):
                    if event.get("type") != "message_update":
                        continue
                    delta = (event.get("assistantMessageEvent") or {}).get("delta")
                    if delta:
                        yield str(delta)
        finally:
            await _kill_and_reap(proc)

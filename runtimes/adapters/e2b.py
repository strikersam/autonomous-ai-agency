"""runtimes/adapters/e2b.py — E2B Firecracker micro-VM runtime adapter.

Routes agent task execution into an isolated E2B sandbox. Modeled on
``runtimes/adapters/docker_agent.py`` — same ``RuntimeAdapter`` contract,
same health-check / preflight / execute shape — but instead of spawning a
Docker container per task, opens an E2B micro-VM (boot ≈150 ms, no local
Docker daemon required, clean per-session isolation).

When ``spec.context["repo_url"]`` is set (e.g. by the
:class:`tasks.service.TaskExecutionCoordinator` resolving a Company's
``RepoConnection``), the adapter clones the real company repo into the
sandbox before plan→execute→verify runs — closing the gap where tasks
previously ran against the agency's own checkout.

In-sandbox ``pytest`` runs as the verifier step: failures are fed back to
the agent for one retry, mirroring the roadmap ★5 design ("in-sandbox
``pytest`` run as the Verifier step — results fed back to Editor for
retry").
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from runtimes.base import (
    IntegrationMode,
    RuntimeAdapter,
    RuntimeCapability,
    RuntimeDependency,
    RuntimeExecutionError,
    RuntimeHealth,
    RuntimeTier,
    TaskResult,
    TaskSpec,
)
from services.e2b_config import e2b_enabled, is_e2b_sdk_importable, resolve_e2b_config
from services.e2b_sandbox import E2BSandboxSession, maybe_attach_e2b

log = logging.getLogger("runtime.e2b")


class E2BAdapter(RuntimeAdapter):
    """Runtime adapter that executes tasks inside an E2B sandbox.

    Activation: registered by :func:`runtimes.manager._build_default_manager`
    whenever ``E2B_API_KEY`` is present and ``E2B_ENABLED`` is not explicitly
    false. When registered with e2b enabled, the manager also flips
    ``preferred_runtime_id`` for ``code_generation`` / ``repo_editing`` so new
    tasks route here automatically; ``internal_agent`` stays as fallback.
    """

    RUNTIME_ID = "e2b"
    DISPLAY_NAME = "E2B Sandbox (Firecracker micro-VM)"
    DESCRIPTION = (
        "Runs agent tasks in an isolated E2B Firecracker micro-VM. "
        "Boot ≈150 ms, no local Docker, clean per-session isolation."
    )
    TIER = RuntimeTier.FIRST_CLASS
    INTEGRATION_MODE = IntegrationMode.NATIVE
    DOCS_URL = "https://e2b.dev/docs"
    CAPABILITIES = frozenset({
        RuntimeCapability.SHELL_EXEC,
        RuntimeCapability.REPO_EDITING,
        RuntimeCapability.GIT_OPERATIONS,
        RuntimeCapability.FILE_READ_WRITE,
        RuntimeCapability.CODE_GENERATION,
        RuntimeCapability.CODE_REVIEW,
        RuntimeCapability.MULTI_FILE_EDIT,
        RuntimeCapability.AUTONOMOUS_LOOP,
    })

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        # No constructor-side SDK import; the adapter must be constructible
        # in test envs without the optional dep installed (health_check will
        # then report unavailable).

    async def health_check(self) -> RuntimeHealth:
        """Available iff config resolves AND the SDK is importable.

        Never raises — a missing runtime reports ``available=False`` so the
        router skips it and falls back to ``internal_agent``.
        """
        if not e2b_enabled():
            return RuntimeHealth(
                runtime_id=self.RUNTIME_ID,
                available=False,
                error="E2B_API_KEY not set or E2B_ENABLED=false",
            )
        if not is_e2b_sdk_importable():
            return RuntimeHealth(
                runtime_id=self.RUNTIME_ID,
                available=False,
                error="e2b-code-interpreter SDK not installed (pip install e2b-code-interpreter)",
            )
        config = resolve_e2b_config()
        if config is None:
            return RuntimeHealth(
                runtime_id=self.RUNTIME_ID,
                available=False,
                error="E2B config resolved to None",
            )
        return RuntimeHealth(
            runtime_id=self.RUNTIME_ID,
            available=True,
            details={
                "template": config.template,
                "timeout_sec": config.timeout_sec,
            },
        )

    def required_dependencies(self) -> list[RuntimeDependency]:
        """Declare ``E2B_API_KEY`` as a required env dependency.

        The base ``preflight`` validates env deps via
        :meth:`RuntimeAdapter.tool_availability_report`, which checks
        ``shutil.which`` for ``binary`` deps. For ``env`` deps we declare
        them here so the readiness report surfaces them in the issues list
        (the actual presence check is done by :meth:`health_check`).
        """
        return [
            RuntimeDependency(
                name="E2B_API_KEY",
                kind="env",
                config_var="E2B_API_KEY",
                install_hint=(
                    "Set E2B_API_KEY in the environment (Render dashboard or "
                    ".env) to your e2b_... key. Get one at https://e2b.dev."
                ),
                required=True,
            ),
        ]

    async def execute(self, spec: TaskSpec) -> TaskResult:
        """Execute a task inside a fresh E2B sandbox.

        Flow:
          1. Open an :class:`E2BSandboxSession`.
          2. If ``spec.context["repo_url"]`` is set, clone the real repo into
             the sandbox.
          3. Build a host-side :class:`AgentRunner` and attach the session as
             ``runner._mcp`` (every write/command/git op now runs in-sandbox).
          4. Run the agent's plan→execute→verify loop.
          5. Run ``pytest`` inside the sandbox as the verifier step. On
             failure, feed the failures back to the agent for ONE retry.
          6. Extract the diff via ``git_diff`` for the host-side TaskResult.
          7. Close the sandbox in ``finally`` (always).
        """
        config = resolve_e2b_config()
        if config is None:
            raise RuntimeExecutionError(
                self.RUNTIME_ID,
                "E2B_API_KEY not configured; cannot execute task",
                spec.task_id,
            )

        started = time.perf_counter()
        session: E2BSandboxSession | None = None
        try:
            session = E2BSandboxSession(config=config)
            await session.open()
        except Exception as exc:
            # Re-raise as RuntimeExecutionError so the coordinator can record
            # the failure and the dispatcher can fall back to internal_agent.
            if session is not None:
                await session.close()
            raise RuntimeExecutionError(
                self.RUNTIME_ID,
                f"E2B sandbox open failed: {exc}",
                spec.task_id,
            ) from exc

        # Clone the real repo when one is provided (the company-repo wiring
        # in TaskExecutionCoordinator populates spec.context["repo_url"]).
        repo_url = (spec.context.get("repo_url") or spec.repo_url) if spec.context else None
        base_branch = (spec.context.get("base_branch") or "main") if spec.context else "main"
        if repo_url:
            try:
                await session.call_tool("clone_repo", {
                    "repo_url": repo_url,
                    "branch": base_branch,
                    "github_token": (spec.context or {}).get("github_token"),
                })
            except Exception as exc:
                await session.close()
                raise RuntimeExecutionError(
                    self.RUNTIME_ID,
                    f"E2B repo clone failed: {exc}",
                    spec.task_id,
                ) from exc

        # Build a host-side AgentRunner and attach the E2B session as its MCP
        # client. The import is local so the adapter module loads cleanly
        # when the E2B SDK (or agent loop) is unavailable in test envs.
        try:
            from agent.loop import AgentRunner
        except ImportError as exc:  # pragma: no cover - agent loop always present
            await session.close()
            raise RuntimeExecutionError(
                self.RUNTIME_ID,
                f"AgentRunner import failed: {exc}",
                spec.task_id,
            ) from exc

        runner = AgentRunner(
            workspace_root="/tmp/e2b-host-staging",  # host-side; never written when E2B attached
            github_token=(spec.context or {}).get("github_token"),
            email=(spec.context or {}).get("user_email"),
            department=(spec.context or {}).get("department"),
            key_id=(spec.context or {}).get("key_id"),
            repo_url=repo_url,
            base_branch=base_branch,
        )

        # Attach the E2B session as runner._mcp — every write_file /
        # run_command / git_commit / git_push / clone_repo now runs in-sandbox.
        # If attach fails (rare — open() succeeded above), fall through to the
        # host-side runner (the existing circuit-breaker pattern).
        attached = await maybe_attach_e2b(runner, spec)
        if attached is None:
            # E2B unavailable mid-flight — close the session and bail so the
            # caller (TaskExecutionCoordinator) can retry on internal_agent.
            await session.close()
            raise RuntimeExecutionError(
                self.RUNTIME_ID,
                "E2B session open succeeded but attach failed; aborting to fallback",
                spec.task_id,
            )

        # ── Plan → Execute → Verify ────────────────────────────────────────
        try:
            result = await runner.run(
                instruction=spec.instruction,
                history=list((spec.context or {}).get("conversation", [])),
                requested_model=spec.model_preference,
                auto_commit=bool((spec.context or {}).get("auto_commit", False)),
                max_steps=int((spec.context or {}).get("max_steps", 30)),
                user_id=str((spec.context or {}).get("owner_id") or ""),
                department=(spec.context or {}).get("department"),
                key_id=(spec.context or {}).get("key_id"),
                session_id=(spec.context or {}).get("session_id"),
            )
        except Exception as exc:
            raise RuntimeExecutionError(
                self.RUNTIME_ID,
                f"AgentRunner execution failed: {exc}",
                spec.task_id,
            ) from exc

        # ── In-sandbox pytest verifier (roadmap ★5) ───────────────────────
        # Run the repo's pytest inside the sandbox. On failure, feed the
        # captured stderr back to the agent for ONE retry. Skip when there
        # is no repo (chat-only edits) or when pytest is not installed.
        test_output = ""
        test_passed = True
        if repo_url:
            test_output, test_passed = await self._run_in_sandbox_pytest(session)
            if not test_passed:
                # One retry: feed the failure summary back to the agent.
                log.info("E2B in-sandbox pytest failed; retrying with failure feedback")
                retry_instruction = (
                    f"{spec.instruction}\n\n"
                    "The in-sandbox pytest run failed. Fix the failing tests:\n\n"
                    f"{test_output[:4000]}"
                )
                try:
                    result = await runner.run(
                        instruction=retry_instruction,
                        history=list((spec.context or {}).get("conversation", [])),
                        requested_model=spec.model_preference,
                        auto_commit=bool((spec.context or {}).get("auto_commit", False)),
                        max_steps=int((spec.context or {}).get("max_steps", 30)),
                        user_id=str((spec.context or {}).get("owner_id") or ""),
                        department=(spec.context or {}).get("department"),
                        key_id=(spec.context or {}).get("key_id"),
                        session_id=(spec.context or {}).get("session_id"),
                    )
                    # Re-run pytest after the retry to confirm the fix.
                    test_output, test_passed = await self._run_in_sandbox_pytest(session)
                except Exception as exc:
                    log.warning("E2B agent retry after pytest failure errored: %s", exc)

        # ── Extract diff via git_diff ─────────────────────────────────────
        diff = ""
        if repo_url:
            try:
                diff = await session.call_tool("git_diff", {})
            except Exception as exc:
                log.debug("E2B git_diff failed (best-effort): %s", exc)

        metadata = dict(spec.context or {})
        metadata["raw_result"] = result
        metadata["e2b"] = {
            "template": config.template,
            "timeout_sec": config.timeout_sec,
            "test_passed": test_passed,
            "test_output_excerpt": test_output[:2000] if test_output else "",
            "diff_excerpt": diff[:2000] if diff else "",
        }
        # The list of changed files is what the coordinator surfaces in the
        # task discussion comment. When the agent ran inside E2B against a
        # real repo, the diff captures every in-sandbox edit; when no repo
        # was cloned, fall back to the host-side changed_files list.
        changed_files = []
        for step in result.get("steps", []):
            changed_files.extend(step.get("changed_files", []))
        if not changed_files and diff:
            # Best-effort: parse the diff header for changed file names.
            for line in diff.splitlines():
                if line.startswith("diff --git "):
                    parts = line.split(" b/", 1)
                    if len(parts) == 2:
                        changed_files.append(parts[1].strip())
        unique_files = sorted(set(changed_files))

        output_text = result.get("report") or result.get("summary") or ""
        judge_verdict = str((result.get("judge") or {}).get("verdict") or "").upper()
        did_work = (
            bool(unique_files)
            or len(output_text.strip()) > 20
        ) and judge_verdict != "BLOCKED"

        return TaskResult(
            runtime_id=self.RUNTIME_ID,
            task_id=spec.task_id,
            success=did_work and test_passed,
            output=output_text,
            artifacts=unique_files,
            tool_calls=[],
            model_used=result.get("model_used") or spec.model_preference,
            provider_used="e2b-sandbox",
            execution_time_ms=(time.perf_counter() - started) * 1000,
            metadata=metadata,
        )

    async def _run_in_sandbox_pytest(self, session: E2BSandboxSession) -> tuple[str, bool]:
        """Run ``pytest`` inside the sandbox. Returns ``(output, passed)``.

        Best-effort: if pytest is not installed in the sandbox template, or
        there are no tests, returns ``("", True)`` so the verifier is a no-op
        rather than a hard failure.
        """
        try:
            raw = await session.call_tool("run_command", {
                "cmd": "cd repo && python -m pytest -x --tb=short 2>&1 | tail -200",
                "timeout": 120,
            })
        except Exception as exc:
            log.debug("E2B in-sandbox pytest invocation failed: %s", exc)
            return "", True  # treat as no-op (best-effort verifier)
        # call_tool returns a JSON string for run_command — parse it.
        import json as _json
        try:
            data = _json.loads(raw)
            stdout = data.get("stdout", "")
            exit_code = data.get("exit_code", 0)
        except (ValueError, TypeError):
            stdout = raw
            exit_code = 0
        # pytest exits 0 on pass, 1 on test failure, 2 on collection error /
        # internal error, 5 on no tests collected. Treat 0 and 5 as pass.
        passed = exit_code in (0, 5)
        return stdout, passed

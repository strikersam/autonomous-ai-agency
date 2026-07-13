"""Internal runtime adapter that executes tasks via the built-in AgentRunner.

Routes through free cloud LLMs in priority order:
  1. Nvidia NIM        (NVIDIA_API_KEY)
  2. DeepSeek API      (DEEPSEEK_API_KEY)
  3. Groq              (GROQ_API_KEY)
  4. Qwen/DashScope    (DASHSCOPE_API_KEY / QWEN_API_KEY)
  5. OpenRouter        (OPENROUTER_API_KEY)
  6. Together AI free  (TOGETHER_API_KEY)
  7. Local Ollama      (last resort — no key required)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from agent.loop import AgentRunner
from packages.ai.router import ProviderConfig, _normalize_nvidia_base_url
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

# Nvidia NIM endpoint — OpenAI-compatible, free tier.
# NOTE: do NOT include /v1 in the base URL; the downstream OpenAI-compatible
# URL builders (_openai_url, AgentRunner._chat_text) append it themselves.
_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com"


def _resolve_nvidia_default_model() -> str:
    """Resolve the NVIDIA default model via the catalog (UNIT 7).

    Was hardcoded to ``meta/llama-3.3-70b-instruct`` — now consults the
    catalog so a UI Apply or a ``config/models.yaml`` edit is reflected
    without a redeploy. Falls back to the legacy hardcoded value on
    import error so this module never breaks the agent runtime.
    """
    try:
        from packages.ai.brain_config import (
            PROVIDER_CANDIDATES,
            SAFE_DEFAULT_MODEL,
        )
        cands = PROVIDER_CANDIDATES.get("nvidia") or []
        # First candidate is the catalog preset for nvidia's executor role.
        if cands:
            return cands[0]
        return SAFE_DEFAULT_MODEL
    except Exception:
        return "meta/llama-3.3-70b-instruct"


_NVIDIA_DEFAULT_MODEL = _resolve_nvidia_default_model()


def _nvidia_provider_chain() -> list[ProviderConfig]:
    """Build Nvidia NIM provider config from env.  Empty list when key is absent."""
    key = (
        os.environ.get("NVIDIA_API_KEY")
        or os.environ.get("NVidiaApiKey")
        or ""
    ).strip()
    if not key:
        return []
    base = _normalize_nvidia_base_url(os.environ.get("NVIDIA_BASE_URL") or _NVIDIA_BASE_URL)
    return [
        ProviderConfig(
            provider_id="nvidia-nim",
            type="openai-compatible",
            base_url=base,
            api_key=key,
            default_model=os.environ.get("NVIDIA_DEFAULT_MODEL") or _NVIDIA_DEFAULT_MODEL,
            priority=0,
        )
    ]


def _best_cloud_primary_base(local_ollama_base: str) -> str:
    """Return the highest-priority available cloud LLM base URL.

    Tries free cloud providers in priority order. Falls back to local Ollama
    only when no cloud key is configured, keeping local out of the fallback
    chain when a cloud alternative exists.
    """
    nvidia_key = (os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey") or "").strip()
    if nvidia_key:
        return _normalize_nvidia_base_url(os.environ.get("NVIDIA_BASE_URL") or _NVIDIA_BASE_URL)

    zen_key = os.environ.get("OPENCODE_ZEN_API_KEY")
    if zen_key:
        return (os.environ.get("OPENCODE_ZEN_BASE_URL") or "https://gateway.opencode.ai/v1").rstrip("/")

    if os.environ.get("DEEPSEEK_API_KEY"):
        return (os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")

    if os.environ.get("GROQ_API_KEY"):
        return "https://api.groq.com/openai/v1"

    if os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY"):
        return (
            os.environ.get("DASHSCOPE_BASE_URL")
            or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        ).rstrip("/")

    if os.environ.get("OPENROUTER_API_KEY"):
        return (os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").rstrip("/")

    if os.environ.get("TOGETHER_API_KEY"):
        return (os.environ.get("TOGETHER_BASE_URL") or "https://api.together.xyz/v1").rstrip("/")

    if os.environ.get("MISTRAL_API_KEY"):
        return "https://api.mistral.ai/v1"

    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        return "https://generativelanguage.googleapis.com/v1beta/openai"

    _cf_token = os.environ.get("CLOUDFLARE_API_TOKEN")
    _cf_account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if _cf_token and _cf_account:
        return f"https://api.cloudflare.com/client/v4/accounts/{_cf_account}/ai/v1"

    if os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_TOKEN"):
        return (os.environ.get("HF_BASE_URL") or "https://api-inference.huggingface.co/v1").rstrip("/")

    if os.environ.get("ZHIPU_API_KEY"):
        return "https://open.bigmodel.cn/api/paas/v4"

    if os.environ.get("MINIMAX_API_KEY"):
        return "https://api.minimax.chat/v1"

    return local_ollama_base


class InternalAgentAdapter(RuntimeAdapter):
    """Built-in agent loop — Nvidia NIM primary, Ollama fallback."""

    RUNTIME_ID = "internal_agent"
    DISPLAY_NAME = "Internal Agent (Nvidia NIM)"
    DESCRIPTION = "Built-in agent loop — routes through Nvidia NIM free models with Ollama as fallback."
    TIER = RuntimeTier.FIRST_CLASS
    INTEGRATION_MODE = IntegrationMode.NATIVE
    DOCS_URL = ""
    CAPABILITIES = frozenset(
        {
            RuntimeCapability.CODE_GENERATION,
            RuntimeCapability.CODE_REVIEW,
            RuntimeCapability.REPO_EDITING,
            RuntimeCapability.FILE_READ_WRITE,
            RuntimeCapability.TOOL_USE,
            RuntimeCapability.SHELL_EXEC,
            RuntimeCapability.AUTONOMOUS_LOOP,
        }
    )

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        # Ollama base URL is UI-configurable (DB-persisted via the Brain card)
        # so a local/tunnelled Ollama can be the brain with no env edit. An
        # explicit config value still wins; otherwise the DB/env/default resolver.
        _resolved_ollama_base: str | None = None
        try:
            from packages.ai.brain_config import resolve_ollama_base_url
            _resolved_ollama_base = resolve_ollama_base_url()
        except Exception:  # pragma: no cover - defensive
            _resolved_ollama_base = None
        self._ollama_base = (
            (config or {}).get("ollama_base")
            or _resolved_ollama_base
            or os.environ.get("OLLAMA_BASE")
            or os.environ.get("OLLAMA_BASE_URL")
            or "http://localhost:11434"
        )
        self._workspace_root = (
            (config or {}).get("workspace_root")
            or str(Path(__file__).resolve().parents[2])
        )
        self._task_harness_required = str(
            (config or {}).get("task_harness_required", os.environ.get("TASK_HARNESS_REQUIRED", "false"))
        ).lower() == "true"

    def required_dependencies(self) -> list[RuntimeDependency]:
        """
        Return runtime dependencies required by this adapter.
        
        Returns:
            list[RuntimeDependency]: An empty list when a task harness is not required; otherwise a list containing a single `RuntimeDependency` for the `task-harness` with `config_var="TASK_HARNESS_BIN"` and an install hint.
        """
        if not self._task_harness_required:
            return []
        return [
            RuntimeDependency(
                name="task-harness",
                config_var="TASK_HARNESS_BIN",
                install_hint="Install a compatible harness and point TASK_HARNESS_BIN at it.",
            )
        ]

    async def health_check(self) -> RuntimeHealth:
        """
        Determine availability of the internal agent runtime.

        Checks cloud providers in the same priority order as ``_best_cloud_primary_base()``:
        Nvidia NIM → OpenCode Zen → DeepSeek → Groq → DashScope → OpenRouter →
        Together → Mistral → Google Gemini → Cloudflare → HuggingFace → ZhiPu →
        MiniMax.  If ANY cloud provider key is configured, the runtime is reported
        available without a network probe (assumes the provider is reachable).

        Falls back to a local Ollama HTTP probe only when no cloud key is present.
        The Ollama probe is lightweight (GET on the configured base URL, 2 s timeout)
        and only marks the runtime unavailable when it definitively fails.

        Returns:
            RuntimeHealth: ``available=True`` when any cloud key or a reachable
            Ollama endpoint is found; ``available=False`` with a diagnostic error
            otherwise.
        """
        # Check ALL cloud providers that _best_cloud_primary_base() knows about.
        # If any key is set, assume the provider is reachable (same best-effort
        # assumption already made for Nvidia).  This matches the actual execution
        # path where AgentRunner routes through whichever cloud provider is
        # configured — so the health check must not report "unavailable" when a
        # working cloud provider (e.g. DeepSeek) exists but isn't Nvidia.
        cloud_keys: list[tuple[str, str]] = [
            ("nvidia-nim", "NVIDIA_API_KEY"),
            ("nvidia-nim", "NVidiaApiKey"),
            ("opencode-zen", "OPENCODE_ZEN_API_KEY"),
            ("deepseek", "DEEPSEEK_API_KEY"),
            ("groq", "GROQ_API_KEY"),
            ("dashscope", "DASHSCOPE_API_KEY"),
            ("dashscope", "QWEN_API_KEY"),
            ("openrouter", "OPENROUTER_API_KEY"),
            ("together", "TOGETHER_API_KEY"),
            ("mistral", "MISTRAL_API_KEY"),
            ("google-gemini", "GOOGLE_API_KEY"),
            ("google-gemini", "GEMINI_API_KEY"),
            # Cloudflare requires BOTH token AND account ID — single-key check
            # would falsely report healthy when only one is set.
            ("cloudflare", ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID")),
            ("huggingface", "HF_TOKEN"),
            ("huggingface", "HUGGINGFACE_API_TOKEN"),
            ("zhipu", "ZHIPU_API_KEY"),
            ("minimax", "MINIMAX_API_KEY"),
        ]
        for provider_label, env_spec in cloud_keys:
            if isinstance(env_spec, tuple):
                # Multi-key requirement (e.g. Cloudflare needs token + account)
                if all(os.environ.get(k, "").strip() for k in env_spec):
                    return RuntimeHealth(
                        runtime_id=self.RUNTIME_ID,
                        available=True,
                        details={
                            "workspace_root": self._workspace_root,
                            "provider": provider_label,
                            "source": f"env:{','.join(env_spec)}",
                        },
                    )
            elif os.environ.get(env_spec, "").strip():
                return RuntimeHealth(
                    runtime_id=self.RUNTIME_ID,
                    available=True,
                    details={
                        "workspace_root": self._workspace_root,
                        "provider": provider_label,
                        "source": f"env:{env_spec}",
                    },
                )

        # No cloud key found — probe local Ollama as the last resort.
        import httpx
        base = (os.environ.get("OLLAMA_BASE") or os.environ.get("OLLAMA_BASE_URL") or self._ollama_base).rstrip("/")
        probe_url = f"{base}/v1/health" if base.endswith(":11434") else base
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(probe_url)
            if resp.status_code >= 200 and resp.status_code < 400:
                return RuntimeHealth(
                    runtime_id=self.RUNTIME_ID,
                    available=True,
                    details={"workspace_root": self._workspace_root, "provider": "ollama", "probe_url": probe_url},
                )
            return RuntimeHealth(
                runtime_id=self.RUNTIME_ID,
                available=False,
                error=f"Ollama probe returned HTTP {resp.status_code} at {probe_url}",
                details={"workspace_root": self._workspace_root, "provider": "ollama"},
            )
        except Exception:
            pass
        return RuntimeHealth(
            runtime_id=self.RUNTIME_ID,
            available=False,
            error=(
                "No cloud provider API key configured and local Ollama not reachable. "
                "Set any of NVIDIA_API_KEY, DEEPSEEK_API_KEY, GROQ_API_KEY, "
                "TOGETHER_API_KEY, HF_TOKEN, etc. to enable the internal agent runtime."
            ),
            details={"workspace_root": self._workspace_root, "provider": "none"},
        )

    async def execute(self, spec: TaskSpec) -> TaskResult:
        """
        Execute a TaskSpec using the internal AgentRunner and convert the agent's outcome into a TaskResult.
        
        Parameters:
            spec (TaskSpec): Specification of the task to run, including instruction, model preference, workspace path, and contextual keys used to configure the runner (e.g., conversation, auto_commit, max_steps, owner_id, department, key_id, session_id).
        
        Returns:
            TaskResult: Aggregated result of the execution containing:
                - success: true when files were modified or applied steps exist, or when the agent produced a substantive textual report/summary (more than ~20 characters), unless the judge verdict is "BLOCKED".
                - output: the agent's report or summary.
                - artifacts: sorted list of unique file paths the agent changed.
                - model_used: model requested or chosen (falls back to a default).
                - provider_used: "nvidia-nim" when an NVIDIA provider chain was active, otherwise "ollama".
                - execution_time_ms and metadata (includes the raw agent result, changed_files, agent_comment, and task status/review info when applicable).
        
        Raises:
            RuntimeExecutionError: If the AgentRunner fails during execution.
        """
        nvidia_chain = _nvidia_provider_chain()

        # Resolve LLM provider through the per-surface policy (honours allow_paid
        # gating, explicit surface assignment, and failover exclusion). Falls
        # back to the legacy _best_cloud_primary_base chain when the policy
        # module is unavailable.
        provider_headers: dict[str, str] = {}
        primary_base = _best_cloud_primary_base(self._ollama_base)
        try:
            from services.workflow_orchestrator import resolve_provider_for
            ia_base, ia_headers, ia_model = await resolve_provider_for("internal_agent")
            if ia_base:
                primary_base = ia_base
            if ia_headers:
                provider_headers = dict(ia_headers)
                provider_headers.pop("Content-Type", None)
        except Exception:
            provider_headers = {}

        # --- Worktree isolation -------------------------------------------
        # Each task executes in its own git worktree (or a temp dir copy if
        # the workspace is not a git repo).  This prevents concurrent tasks
        # from clobbering each other's in-flight edits.
        base_workspace = spec.workspace_path or self._workspace_root
        worktree_path, _worktree_tmp = self._create_worktree(
            base_workspace, spec.task_id or "adhoc"
        )
        # ------------------------------------------------------------------

        if not provider_headers:
            nvidia_key = (os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey") or "").strip()
            normalized_primary = primary_base.rstrip("/")
            nvidia_normalized = _normalize_nvidia_base_url(os.environ.get("NVIDIA_BASE_URL") or _NVIDIA_BASE_URL).rstrip("/")
            if nvidia_key and normalized_primary == nvidia_normalized:
                provider_headers = {"Authorization": f"Bearer {nvidia_key}"}
            elif os.environ.get("DEEPSEEK_API_KEY") and "deepseek" in normalized_primary:
                provider_headers = {"Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}"}
            elif os.environ.get("GROQ_API_KEY") and "groq" in normalized_primary:
                provider_headers = {"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"}
            elif os.environ.get("OPENROUTER_API_KEY") and "openrouter" in normalized_primary:
                provider_headers = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"}
            elif os.environ.get("TOGETHER_API_KEY") and "together" in normalized_primary:
                provider_headers = {"Authorization": f"Bearer {os.environ['TOGETHER_API_KEY']}"}
            elif os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY"):
                dash_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY") or ""
                if dash_key and "dashscope" in normalized_primary:
                    provider_headers = {"Authorization": f"Bearer {dash_key}"}

        runner = AgentRunner(
            ollama_base=primary_base,
            workspace_root=worktree_path,
            provider_headers=provider_headers or None,
            github_token=spec.context.get("github_token"),
            email=spec.context.get("user_email"),
            department=spec.context.get("department"),
            key_id=spec.context.get("key_id"),
            repo_url=spec.context.get("repo_url"),
            base_branch=spec.context.get("base_branch", "main"),
        )

        started = time.perf_counter()

        # ── E2B sandbox attach (roadmap ★5) ────────────────────────────────
        # When E2B is enabled (E2B_ENABLED=true, E2B_API_KEY set, SDK
        # importable), open a Firecracker micro-VM and attach it as
        # runner._mcp so every write_file / read_file / run_command /
        # apply_diff / git_commit / git_push / clone_repo executes inside
        # the sandbox instead of against the host worktree.
        #
        # Data-flow (post-fix):
        #   1. Seed the sandbox from the host worktree (tar tracked files
        #      into the sandbox's /home/user/repo).
        #   2. Run the agent — all reads/writes/commands hit the sandbox.
        #   3. Extract changed files back to the host worktree so the
        #      existing changed_files collection + auto-commit work.
        #
        # Falls back gracefully to today's local path when E2B is
        # unavailable — maybe_attach_e2b returns None and the runner
        # keeps its original (None) _mcp, routing through local WorkspaceTools.
        _e2b_session = None
        try:
            from services.e2b_sandbox import maybe_attach_e2b
            _e2b_session = await maybe_attach_e2b(runner, spec)
        except Exception as _e2b_exc:  # pragma: no cover - defensive
            self._log.debug("E2B attach failed; using local tools: %s", _e2b_exc)
            _e2b_session = None

        # Seed the sandbox from the host worktree so the agent can read
        # the files it's meant to edit. Only seed when there's no repo_url
        # in the context (the company-repo flow clones its own repo).
        if _e2b_session is not None and not spec.context.get("repo_url"):
            try:
                seeded = await _e2b_session.seed_from_worktree(worktree_path)
                if not seeded:
                    self._log.debug(
                        "E2B seed_from_worktree returned False; agent will run "
                        "against an empty sandbox (reads may fail)"
                    )
            except Exception as exc:  # pragma: no cover - best-effort
                self._log.debug("E2B seed failed (best-effort): %s", exc)

        try:
            # Resolve model: prefer spec → Nvidia default → leave None (auto)
            model = spec.model_preference
            if not model and nvidia_chain:
                model = nvidia_chain[0].default_model

            # auto_commit can be requested via task context; defaults off so the
            # agent writes files but lets the user review before committing.
            auto_commit = bool(spec.context.get("auto_commit", False))

            # NOTE: the orchestrator bypass is intentionally NOT set here. This
            # adapter is also reachable via the direct `/runtimes/{id}/execute` API
            # (runtimes/api.py), and that path must stay gated so direct callers
            # cannot skip workflow approval. The bypass is instead set by the
            # *sanctioned* background caller (TaskExecutionCoordinator.execute) and
            # by the CEO Agency cycle, both of which are autonomous, gate-aware
            # execution paths.
            result = await runner.run(
                instruction=spec.instruction,
                history=list(spec.context.get("conversation", [])),
                requested_model=model,
                auto_commit=auto_commit,
                max_steps=int(spec.context.get("max_steps", 30)),
                user_id=str(spec.context.get("owner_id") or ""),
                department=spec.context.get("department"),
                key_id=spec.context.get("key_id"),
                session_id=spec.context.get("session_id"),
            )
        except Exception as exc:
            self._remove_worktree(base_workspace, worktree_path, _worktree_tmp)
            # Close the E2B sandbox if it was opened (best-effort).
            if _e2b_session is not None:
                try:
                    await _e2b_session.close()
                except Exception:  # pragma: no cover - best-effort
                    pass
            raise RuntimeExecutionError(self.RUNTIME_ID, str(exc), spec.task_id) from exc

        # Close the E2B sandbox now that the agent run is complete (best-effort).
        # Before closing, extract changed files from the sandbox back to the
        # host worktree so the existing changed_files collection + auto-commit
        # see the sandbox's edits. This is the "writes go to sandbox, diffs
        # escape to host" model made real.
        if _e2b_session is not None:
            try:
                extracted = await _e2b_session.extract_changes_to_worktree(worktree_path)
                if extracted:
                    self._log.info(
                        "E2B: extracted %d changed files from sandbox to %s",
                        len(extracted), worktree_path,
                    )
            except Exception as exc:  # pragma: no cover - best-effort
                self._log.debug("E2B extract failed (best-effort): %s", exc)
            try:
                await _e2b_session.close()
            except Exception:  # pragma: no cover - best-effort
                pass

        # Collect every file that was actually written to disk across all steps.
        changed_files: list[str] = []
        for step in result.get("steps", []):
            changed_files.extend(step.get("changed_files", []))
        unique_files = sorted(set(changed_files))

        metadata = dict(spec.context)
        metadata["raw_result"] = result
        metadata["changed_files"] = unique_files
        if spec.context.get("task", {}).get("requires_approval"):
            metadata["task_status"] = "in_review"
            metadata["review_reason"] = "Awaiting human approval"

        # Prefer the rich markdown report for the task discussion comment.
        # Falls back to the one-liner summary when report is unavailable.
        agent_comment = result.get("report") or result.get("summary") or ""
        if agent_comment:
            metadata["agent_comment"] = agent_comment

        # Determine actual success: the agent must have either changed files or
        # produced a non-empty text output.  An empty plan (0 steps executed) or
        # all-failed steps with no output is treated as a failure so the task is
        # not silently moved to DONE without any real work.
        steps = result.get("steps") or []
        applied_steps = [s for s in steps if s.get("status") == "applied"]
        failed_steps = [s for s in steps if s.get("status") == "failed"]
        output_text = result.get("report") or result.get("summary") or ""
        judge_verdict = str((result.get("judge") or {}).get("verdict") or "").upper()

        # Step-success-ratio gate: a task with planned steps needs a MAJORITY
        # applied to count as done. This prevents the "1 applied + 21 failed →
        # DONE" bug where a single applied step overrides 21 failures. The
        # free-text-report path (len(output_text) > 20) only applies when
        # there were NO steps at all (pure analysis/report tasks), not as an
        # override when steps existed and mostly failed.
        total_steps = len(steps)
        step_success_ratio = (len(applied_steps) / total_steps) if total_steps else None
        steps_ok = step_success_ratio is None or step_success_ratio >= 0.5

        did_work = (
            steps_ok
            and (bool(unique_files or applied_steps) or (not steps and len(output_text.strip()) > 20))
            and judge_verdict != "BLOCKED"
        )

        # Clean up the isolated worktree once the agent is done.
        self._remove_worktree(base_workspace, worktree_path, _worktree_tmp)

        # If the task failed the step-success-ratio gate, prepend a clear
        # failure summary to the output so the task's error_message (set by
        # _apply_result when success=False) explains what went wrong.
        if not did_work and total_steps > 0 and step_success_ratio is not None and step_success_ratio < 0.5:
            failure_summary = (
                f"Task marked as FAILED: {len(applied_steps)}/{total_steps} steps "
                f"applied ({step_success_ratio:.0%} < 50% threshold). "
                f"{len(failed_steps)} step(s) failed. "
                f"Agent report: {output_text[:500]}"
            )
            output_text = failure_summary

        provider_label = "nvidia-nim" if nvidia_chain else "ollama"
        return TaskResult(
            runtime_id=self.RUNTIME_ID,
            task_id=spec.task_id,
            success=did_work,
            output=output_text,
            artifacts=unique_files,
            tool_calls=[],
            model_used=model or _NVIDIA_DEFAULT_MODEL,
            provider_used=provider_label,
            execution_time_ms=(time.perf_counter() - started) * 1000,
            metadata=metadata,
        )

    # ── Worktree helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _create_worktree(
        workspace: str,
        task_id: str,
    ) -> "tuple[str, tempfile.TemporaryDirectory | None]":
        """Create an isolated execution context for a single task.

        Tries ``git worktree add`` first so the agent gets a full index and
        history without duplicating the object store.  Falls back to a plain
        ``tempfile.TemporaryDirectory`` copy when the workspace is not a git
        repo or worktree creation fails.

        Returns:
            (worktree_path, tmp_dir_or_None)
            tmp_dir is non-None only when we fell back to a plain copy.
        """
        import logging as _logging
        _log = _logging.getLogger("qwen-proxy")

        task_slug = str(task_id).replace("/", "-")[:40]
        wt_path = os.path.join(tempfile.gettempdir(), f"llm-task-wt-{task_slug}")

        # Prune any stale worktree from a previous crash before adding a new one.
        if os.path.exists(wt_path):
            try:
                subprocess.run(  # nosec B603, B607 — constant git argv, list form, no shell
                    ["git", "worktree", "prune"],
                    cwd=workspace,
                    capture_output=True,
                    timeout=10,
                )
                shutil.rmtree(wt_path, ignore_errors=True)
            except Exception:
                pass

        try:
            result = subprocess.run(  # nosec B603, B607 — constant git argv, list form, no shell
                ["git", "worktree", "add", "--detach", wt_path, "HEAD"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                _log.debug("Worktree created at %s for task %s", wt_path, task_id)
                return wt_path, None
            _log.debug(
                "git worktree add failed (%s): %s — using temp copy",
                result.returncode,
                result.stderr.strip(),
            )
        except Exception as exc:
            _log.debug("git worktree unavailable (%s) — using temp copy", exc)

        # Fallback: copy the workspace into a temporary directory.
        tmp = tempfile.TemporaryDirectory(prefix=f"llm-task-copy-{task_slug}-")
        try:
            shutil.copytree(
                workspace,
                tmp.name,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(
                    ".git", "__pycache__", "*.pyc", "node_modules"
                ),
            )
        except Exception as exc:
            _log.warning(
                "Workspace copy failed: %s — using original workspace", exc
            )
            tmp.cleanup()
            return workspace, None
        _log.debug("Workspace copied to %s for task %s", tmp.name, task_id)
        return tmp.name, tmp

    @staticmethod
    def _remove_worktree(
        workspace: str,
        worktree_path: str,
        tmp: "tempfile.TemporaryDirectory | None",
    ) -> None:
        """Clean up the worktree or temp copy created by ``_create_worktree``."""
        import logging as _logging
        _log = _logging.getLogger("qwen-proxy")

        if worktree_path == workspace:
            return  # used the original workspace — nothing to clean up

        if tmp is not None:
            try:
                tmp.cleanup()
            except Exception as exc:
                _log.debug("Temp worktree cleanup failed: %s", exc)
            return

        # Git worktree — remove via git first, then rmtree as a safety net.
        try:
            subprocess.run(  # nosec B603, B607 — constant git argv, list form, no shell
                ["git", "worktree", "remove", "--force", worktree_path],
                cwd=workspace,
                capture_output=True,
                timeout=10,
            )
        except Exception as exc:
            _log.debug("git worktree remove failed: %s", exc)
        shutil.rmtree(worktree_path, ignore_errors=True)

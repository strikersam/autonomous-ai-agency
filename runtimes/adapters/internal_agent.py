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
from provider_router import ProviderConfig, _normalize_nvidia_base_url
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
_NVIDIA_DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"


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


def _ordered_provider_configs(local_ollama_base: str) -> list[tuple[str, str | None, str]]:
    """Return (base_url, api_key_or_None, default_model) for every configured provider.

    Ordered by priority — highest first.  Local Ollama is always appended as the
    last resort so there is always at least one entry.  Callers iterate this list
    and pass ``Authorization: Bearer <api_key>`` only when api_key is not None.
    """
    configs: list[tuple[str, str | None, str]] = []

    nvidia_key = (os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey") or "").strip()
    if nvidia_key:
        base = _normalize_nvidia_base_url(os.environ.get("NVIDIA_BASE_URL") or _NVIDIA_BASE_URL)
        model = os.environ.get("NVIDIA_DEFAULT_MODEL") or _NVIDIA_DEFAULT_MODEL
        configs.append((base, nvidia_key, model))

    zen_key = (os.environ.get("OPENCODE_ZEN_API_KEY") or "").strip()
    if zen_key:
        base = (os.environ.get("OPENCODE_ZEN_BASE_URL") or "https://gateway.opencode.ai/v1").rstrip("/")
        configs.append((base, zen_key, "qwen3-coder-30b"))

    deepseek_key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if deepseek_key:
        base = (os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")
        configs.append((base, deepseek_key, "deepseek-chat"))

    groq_key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if groq_key:
        configs.append(("https://api.groq.com/openai/v1", groq_key, "llama-3.3-70b-versatile"))

    dashscope_key = (os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY") or "").strip()
    if dashscope_key:
        base = (os.environ.get("DASHSCOPE_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
        configs.append((base, dashscope_key, "qwen-max"))

    openrouter_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if openrouter_key:
        base = (os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").rstrip("/")
        configs.append((base, openrouter_key, "mistralai/mixtral-8x7b-instruct"))

    together_key = (os.environ.get("TOGETHER_API_KEY") or "").strip()
    if together_key:
        base = (os.environ.get("TOGETHER_BASE_URL") or "https://api.together.xyz/v1").rstrip("/")
        configs.append((base, together_key, "mistralai/Mixtral-8x7B-Instruct-v0.1"))

    mistral_key = (os.environ.get("MISTRAL_API_KEY") or "").strip()
    if mistral_key:
        configs.append(("https://api.mistral.ai/v1", mistral_key, "mistral-small-latest"))

    google_key = (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
    if google_key:
        configs.append(("https://generativelanguage.googleapis.com/v1beta/openai", google_key, "gemini-1.5-flash"))

    cf_token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    cf_account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    if cf_token and cf_account:
        base = f"https://api.cloudflare.com/client/v4/accounts/{cf_account}/ai/v1"
        configs.append((base, cf_token, "@cf/meta/llama-3.1-8b-instruct"))

    hf_key = (os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_TOKEN") or "").strip()
    if hf_key:
        base = (os.environ.get("HF_BASE_URL") or "https://api-inference.huggingface.co/v1").rstrip("/")
        configs.append((base, hf_key, "HuggingFaceH4/zephyr-7b-beta"))

    zhipu_key = (os.environ.get("ZHIPU_API_KEY") or "").strip()
    if zhipu_key:
        configs.append(("https://open.bigmodel.cn/api/paas/v4", zhipu_key, "glm-4-flash"))

    minimax_key = (os.environ.get("MINIMAX_API_KEY") or "").strip()
    if minimax_key:
        configs.append(("https://api.minimax.chat/v1", minimax_key, "abab6.5s-chat"))

    # Local Ollama is always the last resort — no API key required.
    configs.append((local_ollama_base.rstrip("/"), None, "qwen3-coder:30b"))

    return configs


def _best_cloud_primary_base(local_ollama_base: str) -> str:
    """Return the highest-priority available cloud LLM base URL.

    Kept for backwards-compat.  New code should call ``_ordered_provider_configs()``.
    """
    configs = _ordered_provider_configs(local_ollama_base)
    return configs[0][0] if configs else local_ollama_base


def _is_auth_error(exc: BaseException) -> bool:
    """Return True when the exception signals an authentication failure (HTTP 401)."""
    msg = str(exc)
    return "401" in msg or "Unauthorized" in msg or "authentication" in msg.lower()


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
        self._ollama_base = (
            (config or {}).get("ollama_base")
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
            RuntimeExecutionError: If all configured providers fail.
        """
        import logging as _logging
        _log = _logging.getLogger("qwen-proxy")

        # --- Worktree isolation -------------------------------------------
        # Each task executes in its own git worktree (or a temp dir copy if
        # the workspace is not a git repo).  This prevents concurrent tasks
        # from clobbering each other's in-flight edits.
        base_workspace = spec.workspace_path or self._workspace_root
        worktree_path, _worktree_tmp = self._create_worktree(
            base_workspace, spec.task_id or "adhoc"
        )
        # ------------------------------------------------------------------

        started = time.perf_counter()
        auto_commit = bool(spec.context.get("auto_commit", False))
        max_steps = int(spec.context.get("max_steps", 30))

        # Build an ordered list of providers to try.  Each entry is
        # (base_url, api_key_or_None, default_model).  We pass the API key as
        # an Authorization header so the runner actually authenticates.
        providers = _ordered_provider_configs(self._ollama_base)

        last_exc: Exception | None = None
        used_provider_label = "ollama"
        result: dict | None = None

        for base_url, api_key, default_model in providers:
            model = spec.model_preference or default_model
            auth_headers: dict[str, str] = (
                {"Authorization": f"Bearer {api_key}"} if api_key else {}
            )

            runner = AgentRunner(
                ollama_base=base_url,
                workspace_root=worktree_path,
                provider_headers=auth_headers,
                github_token=spec.context.get("github_token"),
                email=spec.context.get("user_email"),
                department=spec.context.get("department"),
                key_id=spec.context.get("key_id"),
                repo_url=spec.context.get("repo_url"),
                base_branch=spec.context.get("base_branch", "main"),
            )

            try:
                # NOTE: the orchestrator bypass is intentionally NOT set here.
                # See original comment — direct callers via /runtimes/{id}/execute
                # must stay gated; only sanctioned coordinators set the bypass.
                result = await runner.run(
                    instruction=spec.instruction,
                    history=list(spec.context.get("conversation", [])),
                    requested_model=model,
                    auto_commit=auto_commit,
                    max_steps=max_steps,
                    user_id=str(spec.context.get("owner_id") or ""),
                    department=spec.context.get("department"),
                    key_id=spec.context.get("key_id"),
                    session_id=spec.context.get("session_id"),
                )
                # Success — record which provider we used.
                used_provider_label = "nvidia-nim" if "nvidia" in base_url else (
                    "ollama" if api_key is None else base_url.split("//")[-1].split("/")[0]
                )
                break
            except Exception as exc:
                last_exc = exc
                if _is_auth_error(exc):
                    # 401 from this provider — skip immediately to the next one.
                    _log.warning(
                        "Provider %s returned auth error (401) — skipping to next provider. "
                        "Check that the API key is valid: %s",
                        base_url,
                        exc,
                    )
                    continue
                # Non-auth error (model unavailable, timeout, etc.) — also try
                # the next provider so a single flaky cloud endpoint doesn't
                # block the whole task.
                _log.warning(
                    "Provider %s failed (%s) — trying next provider",
                    base_url,
                    exc,
                )
                continue

        if result is None:
            self._remove_worktree(base_workspace, worktree_path, _worktree_tmp)
            tried = [p[0] for p in providers]
            raise RuntimeExecutionError(
                self.RUNTIME_ID,
                f"All {len(tried)} provider(s) failed. Last error: {last_exc}. "
                f"Tried: {tried}",
                spec.task_id,
            ) from last_exc

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
        output_text = result.get("report") or result.get("summary") or ""
        judge_verdict = str((result.get("judge") or {}).get("verdict") or "").upper()
        # Actual work is considered done if files were modified, steps were applied,
        # or if the agent produced a meaningful informational report/answer.
        did_work = (bool(unique_files or applied_steps) or len(output_text.strip()) > 20) and judge_verdict != "BLOCKED"

        # Clean up the isolated worktree once the agent is done.
        self._remove_worktree(base_workspace, worktree_path, _worktree_tmp)

        provider_label = used_provider_label
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
                subprocess.run(
                    ["git", "worktree", "prune"],
                    cwd=workspace,
                    capture_output=True,
                    timeout=10,
                )
                shutil.rmtree(wt_path, ignore_errors=True)
            except Exception:
                pass

        try:
            result = subprocess.run(
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
            subprocess.run(
                ["git", "worktree", "remove", "--force", worktree_path],
                cwd=workspace,
                capture_output=True,
                timeout=10,
            )
        except Exception as exc:
            _log.debug("git worktree remove failed: %s", exc)
        shutil.rmtree(worktree_path, ignore_errors=True)

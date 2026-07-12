"""loop.py — AgentRunner: plan → execute → verify loop with locked tool signatures."""
from __future__ import annotations

import ast
import inspect
import json
import logging
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import time
import asyncio
import httpx

from agent.context_manager import ContextManager
from agent.context_pruner import ContextPruner
from agent.models import AgentPlan, ToolCall, VerificationResult
from agent.token_budget import BudgetExceededError, TokenBudget
from agent.prompts import (
    build_compaction_prompt,
    build_execution_prompt,
    build_planning_prompt,
    build_tool_prompt,
    build_verification_prompt,
)
from agent.harness_enrichment import get_enrichment
from agent.react_loop import ReactScratchpad
from agent.state import AgentSessionStore
from agent.stuck_detector import StuckDetector
from agent.tools import WorkspaceTools
from agent.user_memory import UserMemoryStore
from router import get_router

# Durable agent checkpointing — soft import so the runner works even without the module
try:
    from agent.checkpoint import checkpoint_agent_state
except ImportError:
    checkpoint_agent_state = None  # type: ignore[assignment]
    log.debug("agent/checkpoint.py not available — checkpointing disabled")

log = logging.getLogger("qwen-agent")

# ── Contract: locked method signatures (J) ────────────────────────────────────
# These are the ONLY public methods and their exact parameter names.  Any caller
# passing unknown kwargs receives a TypeError at runtime — matching extra="forbid"
# behavior in Pydantic models.  This kills signature-drift bugs silently.
_LOCKED_RUN_PARAMS = frozenset({
    "instruction", "history", "requested_model", "auto_commit", "max_steps",
    "user_id", "department", "key_id", "memory_store", "session_id", "metadata",
})
_LOCKED_PLAN_PARAMS = frozenset({
    "instruction", "history", "requested_model", "max_steps",
    "user_id", "memory_store", "session_id", "metadata",
})
_LOCKED_SPAWN_PARAMS = frozenset({
    "instruction", "max_steps", "role",
})
_LOCKED_CONFIGURE_SUBAGENTS_PARAMS = frozenset({"configs",})


def _enforce_signature(fn: Any, locked_params: frozenset[str], fn_name: str) -> None:
    """Raise TypeError if fn's signature drifts from the locked contract (Pydantic extra='forbid').

    Two-way validation:
      1. Every named parameter on fn must appear in locked_params (no extras).
      2. Every locked_param must appear on fn (no missing required params).
    **kwargs is allowed to pass through — runtime _check_extra_kwargs handles
    the dynamic case. *args has no name to check.
    """
    sig = inspect.signature(fn)
    named_params: set[str] = set()
    for name, param in sig.parameters.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            continue
        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            continue
        if name == 'self':
            continue
        named_params.add(name)
        if name not in locked_params:
            raise TypeError(
                f"{fn_name}() has unexpected parameter {name!r}. "
                f"Accepted: {sorted(locked_params)}"
            )
    missing = locked_params - named_params
    if missing:
        raise TypeError(
            f"{fn_name}() is missing required locked parameter(s): {sorted(missing)}. "
            f"Expected: {sorted(locked_params)}"
        )


def _check_extra_kwargs(kwargs: dict[str, Any], locked: frozenset[str], label: str) -> None:
    """Raise TypeError on unknown kwarg (runtime extra='forbid' for non-Pydantic classes)."""
    unknown = [k for k in kwargs if k not in locked]
    if unknown:
        raise TypeError(
            f"{label}() got unexpected keyword argument(s): {unknown}. "
            f"Accepted: {sorted(locked)}"
        )
_VALID_STEP_TYPES: frozenset[str] = frozenset({"edit", "create", "github", "analyze"})

# Live-verified default brain models (2026-06-20 probe). The planner/verifier
# path uses the reasoning-tuned 120B-a12b MoE; the executor path uses the dense
# 49B (JSON-clean tool-calling). The dense 49B is also the explicit-opt-in
# fallback — set AGENT_*_MODEL=meta/llama-3.3-70b-instruct anywhere
# the operator prefers the dense model. The legacy Ollama-local names
# (``deepseek-r1:32b`` / ``qwen3-coder:30b``) are retained as last-resort
# fallbacks for installs without NVIDIA_API_KEY — they remained usable when
# this constant was introduced but the cloud-first defaults now win.
#
# ── DB-driven brain config (PR #824 follow-up) ──────────────────────────────
# These constants are kept as the *final* fallback so nothing regresses, but
# the **call-time** resolver ``_resolve_role_model`` (defined below) now sits
# in front of them with precedence:
#
#     requested_model  →  BrainConfig (DB)  →  env var  →  safe default
#
# A DB change applied via the admin UI therefore takes effect on the next
# agent run without a redeploy. The resolver lives in
# ``services.brain_config_store`` so it can be reused by the workflow
# orchestrator and the brain_policy module without circular imports.
DEFAULT_PLANNER_MODEL = (
    os.environ.get("AGENT_PLANNER_MODEL")
    or os.environ.get("NVIDIA_DEFAULT_MODEL")
    or "meta/llama-3.3-70b-instruct"
)
DEFAULT_EXECUTOR_MODEL = (
    os.environ.get("AGENT_EXECUTOR_MODEL")
    or "meta/llama-3.3-70b-instruct"
)
DEFAULT_VERIFIER_MODEL = (
    os.environ.get("AGENT_VERIFIER_MODEL")
    or os.environ.get("NVIDIA_DEFAULT_MODEL")
    or "meta/llama-3.3-70b-instruct"
)
# Default judge model — historically fell through to ``DEFAULT_VERIFIER_MODEL``.
# Promoted to a named constant so the call-time resolver can route it through
# the DB field ``judge_model`` (part of the BrainConfig card on the UI).
DEFAULT_JUDGE_MODEL = (
    os.environ.get("AGENT_JUDGE_MODEL")
    or DEFAULT_VERIFIER_MODEL
)
# Ollama-local last-resort fallback when no NVIDIA key is configured.
_DEFAULT_PLANNER_MODEL_OLLAMA = "deepseek-r1:32b"
_DEFAULT_EXECUTOR_MODEL_OLLAMA = "qwen3-coder:30b"
_DEFAULT_VERIFIER_MODEL_OLLAMA = "deepseek-r1:32b"


def _resolve_role_model(role: str, requested: str | None = None) -> str:
    """Call-time resolver for an agent role model id.

    Delegates to ``services.brain_config_store.resolve_role_model_sync`` so
    the DB-driven ``BrainConfig`` (set from the admin UI) takes effect
    without a redeploy. Falls back to the module-level
    ``DEFAULT_<ROLE>_MODEL`` constants if the store module is unavailable
    (e.g. during early boot or in stripped-down test environments).

    Never raises — returns the safe default on any error so the agent loop
    can keep running.
    """
    try:
        from packages.ai.brain_config import resolve_role_model_sync
        return resolve_role_model_sync(role, requested)
    except Exception:  # noqa: BLE001 — defensive; never block the loop
        if requested and requested.strip():
            return requested.strip()
        const_map = {
            "planner": DEFAULT_PLANNER_MODEL,
            "executor": DEFAULT_EXECUTOR_MODEL,
            "verifier": DEFAULT_VERIFIER_MODEL,
            "judge": DEFAULT_JUDGE_MODEL,
        }
        return const_map.get(role, DEFAULT_VERIFIER_MODEL)

# Nemotron Reward Model toggle (B1).  When NVIDIA_API_KEY is set, the reward
# model scores step outputs as a cheaper/faster alternative to the LLM verifier.
# Set NEMOTRON_REWARD_ENABLED=false to disable and always use the LLM verifier.
_REWARD_ENABLED = os.environ.get("NEMOTRON_REWARD_ENABLED", "auto").strip().lower() not in ("false", "0", "no", "off")

# C4/C5 integration toggle for chat history and context window management
_AGENT_CHAT_HISTORY_ENABLED = os.environ.get("AGENT_CHAT_HISTORY_ENABLED", "false").strip().lower() in ("true", "1", "yes")
_AGENT_CONTEXT_WINDOW_ENABLED = os.environ.get("AGENT_CONTEXT_WINDOW_ENABLED", "true").strip().lower() in ("true", "1", "yes")

# Adaptive Loop Halting: exit the plan→execute→verify cycle early when the
# verifier returns confidence >= this threshold on a step.  Reduces average
# LLM calls per simple step from ~3 to ~1.5.  Set to 1.0 to disable.
_CONFIDENCE_THRESHOLD = float(os.environ.get("AGENT_CONFIDENCE_THRESHOLD", "0.9"))

# Reasoning token budget (★3 roadmap item).  Controls thinking/reasoning depth
# for models that support it (DeepSeek-R1, Qwen3-Coder, Nemotron NIM, vLLM).
# low=512, medium=2048, high=8192, max=unbounded (default: high).
_REASONING_BUDGET_MAP: dict[str, int] = {
    "low": 512,
    "medium": 2048,
    "high": 8192,
    "max": -1,
}
_REASONING_BUDGET_DEFAULT = os.environ.get("AGENT_REASONING_BUDGET", "high").strip().lower()




class AgentPhaseError(Exception):
    """Raised when a named agent phase (planning, verification, etc.) fails."""

class AgentRunner:
    """GATE: Golden Path steps #7-12 — the primary agent execution loop.

    This is the backbone for:
      #7  Repo bootstrap (workspace tools)
      #8  Direct chat control center (invoked from /agent/chat, /agent/sessions/*/run)
      #9  Workflow engine backbone (used by WorkflowEngine for slice execution)
      #11 CEO loop (BackgroundAgent._process dispatches through this)
      #12 HITL approvals (workflow engine enforces approval gate before dispatch)
      #14 Evidence capture (event log + KPI tracking)

    HARDENED (PR #468): KPI tracking calls added at key decision points.
    """
    def __init__(
        self,
        *,
        ollama_base: str,
        workspace_root: str | Path | None = None,
        provider_headers: dict[str, str] | None = None,
        provider_temperature: float | None = None,
        session_store: AgentSessionStore | None = None,
        github_token: str | None = None,
        email: str | None = None,
        department: str | None = None,
        key_id: str | None = None,
        num_ctx: int | None = None,
        keep_alive: str | None = None,
        repo_url: str | None = None,
        base_branch: str = "main",
    ) -> None:
        # NOTE: "ollama_base" is kept for backwards compatibility; this runner only needs an
        # OpenAI-compatible base URL with /v1/chat/completions.
        self.ollama_base = ollama_base.rstrip("/")
        self.provider_headers = dict(provider_headers or {})
        self.provider_temperature = provider_temperature
        self.num_ctx = num_ctx
        self.keep_alive = keep_alive
        self.tools = WorkspaceTools(workspace_root)
        from agent.github_tools import GitHubTools
        # agent_initiated=True activates the autonomy gate for everything this agent
        # does on GitHub: no commits/pushes to protected branches and no PR merges —
        # the agent proposes via PR and a human merges.
        self.github = GitHubTools(github_token, agent_initiated=True)
        self.ctx = ContextManager()
        # 3-phase context-pruner middleware: runs before every LLM call to enforce
        # token budgets and wrap older context as historical memory.
        self.pruner = ContextPruner()
        # OpenHands-style stuck detection: breaks a step's tool loop when the
        # last observations repeat or alternate without progress.
        self.stuck = StuckDetector()
        # Specialized sub-agent configurations (★2 roadmap item).
        # Keyed by role name ("file_picker", "planner", "editor", "reviewer").
        # When set, _spawn_subagent uses the configured per-role model.
        self.sub_agents: dict[str, Any] = {}
        # Optional session store for event-log writes (append-only durable log).
        # When provided the harness logs key events so the session is
        # recoverable and queryable outside the LLM context window.
        self._session_store = session_store
        # PR #1014: per-session token budget tracking. Set by run() before
        # each agent run; None when not in a session (e.g. direct _chat_text
        # calls from tests). Initialised here so __getattr__ never fails.
        self._current_session_id: str | None = None
        # Nemotron reward scorer (B1): quick quality check before LLM verifier.
        # Lazily initialised on first use so it doesn't break in envs without httpx.
        self._reward_scorer: Any = None
        # Capability registry (A3): dynamic tool dispatch replacing hardcoded
        # if/elif chains with registry-based lookup.
        self._tool_registry: Any = None
        # Steering injector (B2): quality-biased generation via SteerLM tokens.
        self._steering: Any = None
        # MCP client — injected after construction when an MCP sidecar is
        # available.  None means fall back to local WorkspaceTools for all ops.
        self._mcp = None
        # Repository context for auto-push + PR (Direct Chat / managed agents)
        self.repo_url = repo_url
        self.base_branch = base_branch
        # Legacy auth storage (prefer passing to run())
        self.email = email
        self.department = department
        self.key_id = key_id
        # Per-session token spend caps (★3 roadmap item).
        # Populated via set_token_budget(); checked after every LLM call.
        self._token_budget: TokenBudget = TokenBudget()

    def configure_sub_agents(self, configs: list[dict[str, Any]]) -> None:
        """Set per-role sub-agent configurations for specialized routing (★2).

        When sub-agent configs are registered, ``_spawn_subagent`` and the
        tool-call loop use the configured per-role model instead of the default
        executor/verifier — enabling the File Picker → Planner → Editor →
        Reviewer pattern where each role is routed to the cheapest capable model.
        """
        self.sub_agents = {c.role: c for c in configs}
        log.debug("configured %d specialized sub-agent(s): %s", len(configs), list(self.sub_agents.keys()))

    def set_token_budget(self, session_id: str, cap: int) -> None:
        """Set a per-session token spend cap (★3 rollout token budget).

        When *cap* > 0 the runner raises :class:`~agent.token_budget.BudgetExceededError`
        the moment cumulative token spend for *session_id* exceeds *cap*, aborting the
        run cleanly instead of burning unbounded API credits.  Set *cap* = 0 (default)
        for unlimited spend.

        Aligned with Codex's "configurable rollout token budgets" feature (July 2026).
        Call before ``run()``::

            runner.set_token_budget(session_id, cap=50_000)
            result = await runner.run(session_id=session_id, ...)
        """
        self._token_budget.set_cap(session_id, cap=cap)
        log.debug("Token budget set: session=%s cap=%d", session_id, cap)

    def _record_tokens(self, session_id: str | None, prompt_tokens: int, completion_tokens: int) -> None:
        """Record token spend for *session_id* and enforce the budget cap.

        Logs a warning when 80 % of the budget is exhausted.
        Raises :class:`~agent.token_budget.BudgetExceededError` when 100 % is hit.
        Called after every LLM API call in :meth:`_chat_text`.
        """
        if not session_id:
            return
        usage = self._token_budget.record(
            session_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        if usage.cap > 0 and usage.remaining >= 0:
            pct_used = usage.total_tokens / usage.cap * 100
            if pct_used >= 80:
                log.warning(
                    "Token budget at %.0f%%: session=%s used=%d remaining=%d cap=%d",
                    pct_used, session_id, usage.total_tokens, usage.remaining, usage.cap,
                )
        self._token_budget.check(session_id)  # raises BudgetExceededError if over cap

    async def plan(
        self,
        *,
        instruction: str,
        history: list[dict[str, str]],
        requested_model: str | None,
        max_steps: int = 30,
        user_id: str | None = None,
        memory_store: UserMemoryStore | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentPlan:
        """Public wrapper around _generate_plan for callers that want plan-only.

        Returns the AgentPlan so the caller can inspect it (e.g. check
        requires_risky_review) before deciding whether to proceed with run().
        The ``metadata`` argument is accepted for forward-compatibility but
        currently unused.
        """
        return await self._generate_plan(
            instruction=instruction,
            history=history,
            requested_model=requested_model,
            max_steps=max_steps,
            user_id=user_id,
            memory_store=memory_store,
        )

    async def run(
        self,
        *,
        instruction: str,
        history: list[dict[str, str]],
        requested_model: str | None,
        auto_commit: bool,
        max_steps: int,
        user_id: str | None = None,
        department: str | None = None,
        key_id: str | None = None,
        memory_store: UserMemoryStore | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # ``metadata`` is accepted for forward-compatibility (callers like
        # direct_chat.py may pass it) but is not consumed by the core loop.

        # ── DEPRECATION: AgentRunner.run() bypasses WorkflowOrchestrator ──
        # All execution should route through WorkflowOrchestrator.execute().
        # Set AGENCY_WORKFLOW_MODE=orchestrator to enforce the golden path.
        from services.workflow_orchestrator import emit_deprecation, is_legacy_mode
        if not is_legacy_mode():
            raise RuntimeError(
                "AgentRunner.run() is blocked in orchestrator mode. "
                "Use WorkflowOrchestrator.execute() instead. "
                "Set AGENCY_WORKFLOW_MODE=legacy to bypass (deprecated)."
            )
        emit_deprecation("AgentRunner.run()")

        # Store current session_id for use by helper methods that need to
        # write into the durable session event log (e.g., tool_call/tool_result).
        self._current_session_id = session_id
        # Initialised before the try block so the finally handler can safely
        # reference them even when an exception occurs before assignment.
        plan: Any = None
        step_results: list[dict[str, Any]] = []
        commits: list[str] = []
        # Keep the current session marker for the duration of the run so
        # helper methods like _run_tool can write durable events to the
        # correct session. Ensure it is cleared on exit.
        try:
            # Context compaction: if history is long, summarise the old portion
            # before planning so the planner doesn't spend tokens on verbatim
            # repetition.  (Anthropic managed-agents: preserve architectural
            # decisions, discard redundant tool outputs.)
            effective_history = history
            if self.ctx.needs_compaction(history):
                effective_history = await self._compact_history(
                    history, requested_model, session_id
                )

            self._log_event(session_id, "user_message", {"instruction": instruction})

            # C4: Persist the user instruction and history to chat history
            if _AGENT_CHAT_HISTORY_ENABLED and session_id:
                try:
                    from services.chat_history import get_chat_history
                    store = get_chat_history()
                    store.append(session_id, {"role": "user", "content": instruction[:2000]})
                except Exception:  # nosec B110 -- KPI tracking is best-effort
                    pass

            plan = await self._generate_plan(
                instruction, effective_history, requested_model, max_steps, user_id, memory_store
            )
            self._log_event(session_id, "step_start", {"goal": plan.goal, "steps": len(plan.steps)})

            # ── Durable checkpoint: snapshot agent state after planning ──
            if session_id and checkpoint_agent_state is not None:
                try:
                    checkpoint_agent_state(
                        session_id=session_id,
                        step_index=0,
                        goal=plan.goal,
                        plan_steps=[s.model_dump() for s in plan.steps],
                        completed_steps=[],
                        tool_call_history=[],
                        scratchpad_raw=str(plan.goal),
                    )
                except Exception:  # nosec B110 -- KPI tracking is best-effort
                    log.debug("Checkpoint after plan failed (non-fatal)", exc_info=True)

            # A5: Publish plan creation event on the inter-agent message bus
            try:
                from services.agent_bus import get_agent_bus
                await get_agent_bus().publish("agent.planned", {"goal": plan.goal, "steps": len(plan.steps)})
            except Exception:  # nosec B110 -- KPI tracking is best-effort
                pass



            # Warn about risky steps before executing
            for step in plan.steps[:max_steps]:
                if step.risky:
                    log.warning(
                        "RISKY MODULE: step %d touches security-sensitive files: %s",
                        step.id, step.files,
                    )

            # Check for parallel execution opportunity; if it returns a result
            # dict, short-circuit the sequential loop and use that result directly.
            parallel_result = await self._maybe_run_parallel(
                plan=plan,
                requested_model=requested_model,
                auto_commit=auto_commit,
                session_id=session_id,
            )
            if parallel_result is not None:
                self._log_event(session_id, "assistant_message", {"summary": parallel_result.get("summary", "")})
                return parallel_result

            for step in plan.steps[:max_steps]:
                step_data = step.model_dump()
                self._log_event(session_id, "step_start", {"step_id": step_data["id"], "description": step_data["description"]})
                result = await self._execute_step(plan.goal, step_data, requested_model, user_id, memory_store)
                # Sub-agent condensed summary: trim step results before storing so
                # the orchestrator's context stays lean.  (1-2k token budget.)
                condensed = ContextManager.condense_step_result(result)
                self._log_event(session_id, "step_complete", condensed)
                step_results.append(result)

                # ── Durable checkpoint: snapshot after each step ──
                if session_id and checkpoint_agent_state is not None:
                    try:
                        error_raw = result.get("issues")
                        error_str = "; ".join(error_raw) if isinstance(error_raw, list) else str(error_raw) if error_raw else None
                        checkpoint_agent_state(
                            session_id=session_id,
                            step_index=step.id,
                            goal=plan.goal,
                            plan_steps=[s.model_dump() for s in plan.steps],
                            completed_steps=[s["id"] for s in step_results if isinstance(s, dict) and s.get("status") == "applied"],
                            tool_call_history=result.get("observations", []),
                            scratchpad_raw=str(condensed.get("description", "")),
                            error_info=error_str,
                        )
                    except Exception:  # nosec B110 -- KPI tracking is best-effort
                        log.debug("Checkpoint after step failed (non-fatal)", exc_info=True)

                if auto_commit and result["status"] == "applied" and result["changed_files"]:
                    commit = self._commit_step(step_data["description"], result["changed_files"])
                    if commit:
                        commits.append(commit)

                # Adaptive Loop Halting: early-exit when verifier confidence >= threshold
                # on all files touched this step. Simple single-file edits often finish
                # in one pass; no need to burn through remaining planned steps.
                if _CONFIDENCE_THRESHOLD < 1.0 and result.get("status") == "applied":
                    scores = step_data.get("_confidence_scores") or []
                    if scores and all(s >= _CONFIDENCE_THRESHOLD for s in scores):
                        remaining = plan.steps[max_steps:] if len(plan.steps) > max_steps else []
                        skipped = [s.id for s in plan.steps if s.id > step.id]
                        log.info(
                            "Adaptive halting: all verifier confidence scores >= %.2f on step %d "
                            "(%s). Skipping %d remaining step(s) %s.",
                            _CONFIDENCE_THRESHOLD, step.id, scores, len(skipped), skipped or "(none)",
                        )
                        self._log_event(
                            session_id, "step_complete",
                            {"adaptive_halt": True, "confidence_scores": scores, "skipped_steps": skipped},
                        )
                        break

            # A5: Publish run complete event on the inter-agent message bus
            try:
                from services.agent_bus import get_agent_bus
                await get_agent_bus().publish("agent.completed", {
                    "goal": plan.goal,
                    "applied": sum(1 for s in step_results if s.get("status") == "applied"),
                    "total_steps": len(step_results),
                })
            except Exception:  # nosec B110 -- KPI tracking is best-effort
                pass

            # Judge the overall run result
            judge: dict[str, Any] = {}
            if step_results:
                # Call-time resolution: requested → BrainConfig (DB) → env → safe default.
                judge_model = _resolve_role_model("judge", requested_model)
                judge_messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are a code-review judge. Respond with ONLY a JSON object with keys: "
                            "verdict (APPROVED, APPROVED_WITH_CONDITIONS, or REJECTED), "
                            "security (PASS, WARN, or FAIL), correctness (PASS, WARN, or FAIL), "
                            "notes (string)."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Goal: {plan.goal}\n"
                            f"Steps completed: {len(step_results)}\n"
                            f"All applied: {all(s.get('status') == 'applied' for s in step_results)}\n"
                            f"Risky review required: {plan.requires_risky_review}"
                        ),
                    },
                ]
                for _ in range(3):
                    try:
                        raw = await self._chat_json(judge_model, judge_messages)
                        if "verdict" not in raw:
                            continue
                        judge = raw
                        break
                    except Exception:  # nosec B110 -- KPI tracking is best-effort
                        continue
                # If all judge attempts failed, mark the run as BLOCKED so callers
                # can surface a clear failure rather than returning an empty verdict.
                if not judge:
                    judge = {
                        "verdict": "BLOCKED",
                        "security": "FAIL",
                        "correctness": "FAIL",
                        "notes": "Judge produced no valid output after 3 attempts.",
                        "failure_phase": "judge",
                    }

            # Push and open a PR when auto_commit produced local commits and we have
            # a GitHub repo URL to target. Gated behind AGENT_AUTO_PR_ENABLED (default
            # off) so this new agent-initiated GitHub write path is opt-in and has a
            # rollout kill switch.
            pr_url: str | None = None
            if (
                auto_commit
                and commits
                and self.repo_url
                and os.environ.get("AGENT_AUTO_PR_ENABLED", "").strip().lower()
                in {"true", "1", "yes"}
            ):
                pr_url = await self._auto_push_and_pr(
                    commits, self._current_session_id, plan.goal
                )

            summary = self._build_summary(plan.goal, step_results, commits, pr_url)
            self._log_event(session_id, "assistant_message", {"summary": summary})

            # C4: Persist the agent response summary to chat history
            if _AGENT_CHAT_HISTORY_ENABLED and session_id and summary:
                try:
                    from services.chat_history import get_chat_history
                    store = get_chat_history()
                    store.append(session_id, {"role": "assistant", "content": summary[:2000]})
                except Exception:  # nosec B110 -- KPI tracking is best-effort
                    pass

            # Update auth context if passed in run()
            if user_id:
                self.email = user_id
            if department:
                self.department = department
            if key_id:
                self.key_id = key_id

            # ── Learning loop: persist the cause of every failed step so the
            # next run's planner sees it (agent/lessons.py). Retry without
            # this is not learning — the same mistake recurs forever.
            try:
                from agent.lessons import record_step_failures
                record_step_failures(plan.goal, step_results)
            except Exception:
                pass

            return {
                "goal": plan.goal,
                "plan": plan.model_dump(),
                "steps": step_results,
                "commits": commits,
                "summary": summary,
                "judge": judge,
                "pr_url": pr_url,
            }
        finally:
            # ── Durable checkpoint: snapshot on error for crash-recovery ──
            if self._current_session_id and checkpoint_agent_state is not None:
                try:
                    exc_type, exc_value, _ = sys.exc_info()
                    if exc_type is not None:
                        plan_steps_list = [s.model_dump() for s in plan.steps] if plan is not None and hasattr(plan, "steps") and plan.steps else []
                        step_index = plan_steps_list[-1]["id"] if plan_steps_list else 0
                        goal_str = plan.goal if plan is not None and hasattr(plan, "goal") else instruction
                        completed = [s["id"] for s in step_results if isinstance(s, dict) and s.get("status") == "applied"]
                        checkpoint_agent_state(
                            session_id=self._current_session_id,
                            step_index=step_index,
                            goal=goal_str,
                            plan_steps=plan_steps_list,
                            completed_steps=completed,
                            tool_call_history=[],
                            error_info=str(exc_value) if exc_value else "AgentRunner exception",
                        )
                except Exception:  # nosec B110 -- KPI tracking is best-effort
                    log.debug("Error checkpoint failed (non-fatal)", exc_info=True)
            # Clear the ephemeral session marker to avoid accidental cross-session writes
            self._current_session_id = None

    def _normalize_plan_response(self, raw: dict[str, Any], instruction: str) -> dict[str, Any]:
        """Normalise a raw planner JSON response into a consistent plan dict.

        Handles:
        - ``slices`` key renamed to ``steps`` (some model outputs use CRISPY schema)
        - Missing or empty ``goal`` derived from ``instruction`` (truncated to 200 chars)
        - Step ``type`` defaulted/corrected to ``analyze`` when absent or unrecognised
        """
        # Rename slices -> steps
        if "slices" in raw and "steps" not in raw:
            raw = dict(raw)
            raw["steps"] = raw.pop("slices")

        # Derive goal from instruction if absent
        if not raw.get("goal"):
            raw = dict(raw)
            raw["goal"] = instruction[:200]
        elif len(raw["goal"]) > 200:
            raw = dict(raw)
            raw["goal"] = raw["goal"][:200]

        # Normalise step types
        steps = raw.get("steps") or []
        normalised_steps = []
        for step in steps:
            step = dict(step)
            if step.get("type") not in _VALID_STEP_TYPES:
                # Default to "edit" when files are listed, "analyze" otherwise
                step["type"] = "edit" if step.get("files") else "analyze"
            normalised_steps.append(step)
        raw = dict(raw)
        raw["steps"] = normalised_steps
        return raw

    async def _generate_plan(
        self,
        instruction: str,
        history: list[dict[str, str]],
        requested_model: str | None,
        max_steps: int,
        user_id: str | None = None,
        memory_store: UserMemoryStore | None = None,
    ) -> AgentPlan:
        user_memories = memory_store.recall_all(user_id) if memory_store and user_id else {}
        messages = build_planning_prompt(instruction, history, user_memories=user_memories)
        # ── Harness enrichment: inject available tools + skills into planner ───
        self._inject_enrichment(messages)
        # ── Learning loop: surface lessons from recent failed runs so the
        # planner avoids known failure modes (agent/lessons.py).
        try:
            from agent.lessons import recent_lessons_block
            _lessons = recent_lessons_block()
            if _lessons and messages and messages[0].get("role") == "system":
                messages[0]["content"] = f"{messages[0]['content']}\n\n{_lessons}"
        except Exception:
            pass
        # ── Microagents: OpenHands-style keyword-triggered repo knowledge
        # (.openhands/microagents/*.md) injected when the instruction matches
        # a trigger (agent/microagents.py).
        try:
            from agent.microagents import microagents_block
            _knowledge = microagents_block(instruction, root=self.tools.root)
            if _knowledge and messages and messages[0].get("role") == "system":
                messages[0]["content"] = f"{messages[0]['content']}\n\n{_knowledge}"
        except Exception:
            pass
        planner_decision = get_router().route(
            requested_model=requested_model,
            messages=messages,
            override_model=requested_model if requested_model else None,
            endpoint_type="agent_plan",
        )
        planner_model = planner_decision.resolved_model if not requested_model else requested_model
        if not planner_model:
            # Call-time resolution: requested → BrainConfig (DB) → env → safe default.
            planner_model = _resolve_role_model("planner", requested_model)
        log.debug(
            "agent plan: model=%s [%s/%s]",
            planner_model, planner_decision.mode, planner_decision.selection_source,
        )
        try:
            raw = await self._chat_json(planner_model, messages)
            raw = self._normalize_plan_response(raw, instruction)
            plan = AgentPlan.model_validate(raw)
        except Exception as exc:
            raise AgentPhaseError(f"planning: {exc}") from exc
        plan.steps = plan.steps[:max_steps]
        return plan

    async def _execute_step(
        self,
        goal: str,
        step: dict[str, Any],
        requested_model: str | None,
        user_id: str | None = None,
        memory_store: UserMemoryStore | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        observations: list[dict[str, Any]] = []
        context_items: list[dict[str, Any]] = []
        changed_files: list[str] = []
        retries = 0
        target_files = list(step.get("files") or [])

        if not target_files and step.get("type") == "create":
            target_files = [f"generated/step_{step['id']}.txt"]
        elif not target_files and step.get("type") == "github":
            target_files = ["github_operation"]

        executor_decision = get_router().route(
            requested_model=requested_model,
            override_model=requested_model if requested_model else None,
            endpoint_type="agent_execute",
        )
        executor_model = executor_decision.resolved_model if not requested_model else requested_model
        if not executor_model:
            # Call-time resolution: requested → BrainConfig (DB) → env → safe default.
            executor_model = _resolve_role_model("executor", requested_model)
        # Consult sub-agent configs for per-phase model selection (★2)
        editor_cfg = self.sub_agents.get("editor")
        if editor_cfg and editor_cfg.model:
            executor_model = editor_cfg.model

        verifier_decision = get_router().route(
            requested_model=requested_model,
            endpoint_type="agent_verify",
        )
        verifier_model = verifier_decision.resolved_model if not requested_model else requested_model
        if not verifier_model:
            # Call-time resolution: requested → BrainConfig (DB) → env → safe default.
            verifier_model = _resolve_role_model("verifier", requested_model)
        # Consult sub-agent configs for verifier role (★2)
        reviewer_cfg = self.sub_agents.get("reviewer")
        if reviewer_cfg and reviewer_cfg.model:
            verifier_model = reviewer_cfg.model

        log.debug(
            "agent execute: executor=%s verifier=%s",
            executor_model, verifier_model,
        )

        # ReAct scratchpad: accumulates reasoning trace across tool calls (A2)
        scratchpad = ReactScratchpad()

        # Retry loop for tool-call failures (tool dispatch, parse errors, etc.)
        # Note: the outer `for remaining in range(15, 0, -1)` loop controls
        # max tool-call iterations; this inner retry handles transient errors
        # that should be retried before giving up on the step.
        tool_retry_count = 0
        max_tool_retries = 3
        for remaining in range(15, 0, -1):
            # Stuck detection (OpenHands pattern): when the recent observations
            # repeat or alternate without progress, stop the tool loop instead
            # of spending the remaining LLM-call budget on the same mistake.
            stuck_reason = self.stuck.check(observations)
            if stuck_reason:
                log.warning(
                    "stuck detector tripped on step %s: %s", step.get("id"), stuck_reason,
                )
                observations.append(
                    {"tool": "stuck_detector", "result": f"tool loop aborted: {stuck_reason}"}
                )
                self._log_event(session_id, "stuck_detected", {"reason": stuck_reason})
                break
            try:
                # Observation masking: pass truncated older observations to
                # keep the tool-selection prompt lean.  Recent observations are
                # passed verbatim; older ones are summarised.
                masked_obs = self.ctx.mask_observations(observations)
                tool_messages = build_tool_prompt(goal=goal, step=step, observations=masked_obs, remaining_calls=remaining)
                # ── Harness enrichment: inject tool + skill catalog into tool prompt ───
                self._inject_enrichment(tool_messages)
                # Inject ReAct scratchpad trace into the system message so the
                # model can see its own reasoning across tool calls (A2)
                scratchpad_ctx = scratchpad.to_prompt_context()
                if scratchpad_ctx and tool_messages:
                    sys_content = str(tool_messages[0].get("content", ""))
                    tool_messages[0]["content"] = f"{sys_content}\n\n{scratchpad_ctx}"
                tool_call = await self._chat_json(executor_model, tool_messages)
                call = ToolCall.model_validate(tool_call)
            except Exception as exc:
                tool_retry_count += 1
                error_msg = f"tool selection failed: {exc}"
                observations.append({"tool": "error", "result": error_msg})
                log.warning(
                    "_execute_step tool selection error on attempt %d/%d (remaining=%d): %s",
                    tool_retry_count, max_tool_retries + 1, remaining, exc,
                )
                if tool_retry_count > max_tool_retries - 1:
                    # Exhausted retries — fail the step gracefully rather than
                    # consuming the remaining iteration budget with repeated errors
                    return {
                        "step_id": step["id"],
                        "description": step["description"],
                        "status": "failed",
                        "failure_phase": "tool_selection",
                        "issues": [f"Tool selection failed after {max_tool_retries} attempts: {exc}"],
                        "changed_files": changed_files,
                        "observations": observations,
                        "models": {"executor": executor_model, "verifier": verifier_model},
                    }
                # Brief pause before retry to let transient errors settle
                await asyncio.sleep(0.5)
                continue
            if call.tool == "finish":
                observations.append({"tool": "finish", "result": call.args.get("reason", "done inspecting")})
                scratchpad.record_thought(call.args.get("reason", "step complete"))
                break
            if call.tool == "execute_skill":
                skill_result = self._execute_skill_tool(call.args)
                observations.append({"tool": "execute_skill", "result": skill_result})
                context_items.append({"tool": "execute_skill", "result": skill_result})
                scratchpad.record_action("execute_skill", call.args)
                scratchpad.record_observation(skill_result)
                continue
            if call.tool == "recommend_skills":
                rec_result = self._recommend_skills_tool(call.args)
                observations.append({"tool": "recommend_skills", "result": rec_result})
                context_items.append({"tool": "recommend_skills", "result": rec_result})
                scratchpad.record_action("recommend_skills", call.args)
                scratchpad.record_observation(rec_result)
                continue
            if call.tool == "spawn_subagent":
                sub_result = await self._spawn_subagent(**call.args)
                observations.append({"tool": "spawn_subagent", "result": sub_result.get("summary", str(sub_result))})
                context_items.append({"tool": "spawn_subagent", "result": sub_result})
                scratchpad.record_action("spawn_subagent", call.args)
                scratchpad.record_observation(sub_result.get("summary", "subagent completed"))
                continue
            scratchpad.record_action(call.tool, call.args)
            self._log_event(session_id, "tool_call", {"tool": call.tool, "args": call.args})
            result = await self._run_tool(call.tool, call.args, user_id=user_id, memory_store=memory_store)
            scratchpad.record_observation(result)
            self._log_event(session_id, "tool_result", {"tool": call.tool, "result": str(result)[:500]})
            observations.append({"tool": call.tool, "args": call.args, "result": result})
            context_items.append({"tool": call.tool, "result": result})

        if not target_files and step.get("type") not in ("github", "analyze"):
            # Route search_code through _mcp (E2B sandbox) when attached so
            # the agent sees the sandbox's files, not the host worktree's.
            from agent.mcp_client import MCPUnavailableError as _MCPUnavail
            search_hits: list = []
            if self._mcp is not None:
                try:
                    raw = await self._mcp.call_tool(
                        "search_code",
                        {"query": step["description"], "limit": 3},
                    )
                    import json as _json
                    search_hits = _json.loads(raw) if isinstance(raw, str) else raw
                    # search_hits from E2B is a list of path strings; adapt
                    # to the dict shape the host tools return.
                    target_files = [h if isinstance(h, str) else h.get("path", "") for h in search_hits if h]
                except _MCPUnavail:
                    search_hits = self.tools.search_code(step["description"], limit=3)
                    target_files = [hit["path"] for hit in search_hits if isinstance(hit.get("path"), str)]
            else:
                search_hits = self.tools.search_code(step["description"], limit=3)
                target_files = [hit["path"] for hit in search_hits if isinstance(hit.get("path"), str)]

        if not target_files and step.get("type") not in ("github", "analyze"):
            return {
                "step_id": step["id"],
                "description": step["description"],
                "status": "skipped",
                "reason": "No target files identified",
                "changed_files": [],
                "observations": observations,
                "models": {"executor": executor_model, "verifier": verifier_model},
            }

        if step.get("type") in ("github", "analyze"):
            return {
                "step_id": step["id"],
                "description": step["description"],
                "status": "applied",
                "changed_files": [],
                "observations": observations,
                "models": {"executor": executor_model, "verifier": verifier_model},
            }

        for target_file in target_files:
            original_content = self._safe_read(target_file)
            retries = 0
            feedback_issues: list[str] = []
            file_applied = False
            while retries <= 4:
                response = await self._chat_text(
                    executor_model,
                    build_execution_prompt(
                        goal=goal,
                        step=step,
                        target_file=target_file,
                        context_items=context_items,
                        feedback_issues=feedback_issues,
                    ),
                )
                parsed = self._parse_execution_response(response, target_file)
                if not parsed:
                    repaired = await self._chat_text(
                        executor_model,
                        [
                            {
                                "role": "system",
                                "content": (
                                    "Convert the input into the required format only.\n"
                                    "Return ONLY:\n"
                                    "FILE: <path>\n"
                                    "ACTION: <create|replace|append>\n"
                                    "```text\n"
                                    "<FULL FILE CONTENT>\n"
                                    "```"
                                ),
                            },
                            {"role": "user", "content": response},
                        ],
                    )
                    parsed = self._parse_execution_response(repaired, target_file)
                if not parsed:
                    retries += 1
                    feedback_issues = ["You violated format. Fix only format."]
                    if retries > 2:
                        return {
                            "step_id": step["id"],
                            "description": step["description"],
                            "status": "failed",
                            "issues": feedback_issues,
                            "changed_files": changed_files,
                            "observations": observations,
                            "models": {"executor": executor_model, "verifier": verifier_model},
                        }
                    continue

                out_path, new_content = parsed
                new_content = self._clean_generated_file_content(new_content)
                syntax_issues = self._local_syntax_check(out_path, new_content)
                syntax_issues.extend(self._local_safety_check(out_path, new_content))

                # ── B1: Nemotron Reward Model fast-path scoring ────────────
                # Before calling the expensive LLM verifier, try the reward
                # model for a quick quality score.  If the score is high enough
                # (>= _REWARD_PASS_THRESHOLD), skip the LLM verifier entirely.
                # Falls back to LLM verifier when reward model is unavailable.
                reward_score: float | None = None
                if _REWARD_ENABLED and not syntax_issues:
                    scorer = self._get_reward_scorer()
                    if scorer and scorer.is_available:
                        try:
                            reward_result = await scorer.score(
                                prompt=f"{goal}\nStep: {step.get('description', '')}\nFile: {out_path}",
                                response=new_content[:8000],
                            )
                            reward_score = reward_result.score
                            self._log_event(
                                session_id, "step_complete",
                                {"reward_score": reward_score, "reward_model_used": reward_result.model_used},
                            )
                        except Exception as exc:
                            log.debug("Reward scoring failed (falling back to LLM verifier): %s", exc)

                # If reward score is high enough, skip the LLM verifier
                if reward_score is not None and reward_score >= float(os.environ.get("NEMOTRON_REWARD_PASS_THRESHOLD", "0.7")):
                    log.info(
                        "Reward model score %.2f >= threshold — skipping LLM verifier for %s",
                        reward_score, out_path,
                    )
                    verdict = VerificationResult(status="pass", issues=[], confidence=reward_score)
                else:
                    try:
                        verification = await self._chat_json(
                            verifier_model,
                            build_verification_prompt(
                                goal=goal,
                                step=step,
                                target_file=out_path,
                                original_content=original_content,
                                new_content=new_content,
                                syntax_issues=syntax_issues,
                            ),
                        )
                        verdict = VerificationResult.model_validate(verification)
                    except Exception as verif_exc:
                        retries += 1
                        feedback_issues = syntax_issues + [f"verifier_output_invalid: {verif_exc}"]
                        # StopIteration (exhausted mock iterator) or persistent format failure → fail immediately
                        is_exhausted = isinstance(verif_exc, (StopIteration, RuntimeError)) and "StopIteration" in str(verif_exc)
                        if retries > 2 or is_exhausted:
                            return {
                                "step_id": step["id"],
                                "description": step["description"],
                                "status": "failed",
                                "failure_phase": "verification",
                                "issues": feedback_issues,
                                "changed_files": changed_files,
                                "observations": observations,
                                "models": {"executor": executor_model, "verifier": verifier_model},
                            }
                        continue
                if verdict.status == "pass" and not syntax_issues:
                    # Route apply_diff through _mcp (E2B sandbox) when attached,
                    # falling back to host WorkspaceTools on MCPUnavailableError.
                    # This is the PRIMARY edit path — routing it through the
                    # sandbox is what makes "all code edits go to the sandbox"
                    # actually true (roadmap ★5 data-flow fix).
                    from agent.mcp_client import MCPUnavailableError as _MCPUnavail
                    if self._mcp is not None:
                        try:
                            diff_result = await self._mcp.call_tool(
                                "apply_diff",
                                {"path": out_path, "new_content": new_content},
                            )
                        except _MCPUnavail:
                            diff_result = self.tools.apply_diff(out_path, new_content)
                    else:
                        diff_result = self.tools.apply_diff(out_path, new_content)
                    changed_files.append(out_path)
                    context_items.append({"tool": "apply_diff", "result": diff_result})
                    file_applied = True
                    # Adaptive Loop Halting: track confidence for early exit
                    if "_confidence_scores" not in step:
                        step["_confidence_scores"] = []
                    step["_confidence_scores"].append(verdict.confidence)
                    break

                # GATE: Golden Path #14 — evidence capture (KPI: safety block)
                # Record a safety block event whenever syntax/safety issues prevented
                # the diff from being applied. Reachable on every retry where the
                # safety gate fired.
                if syntax_issues:
                    try:
                        from agent.kpi import get_tracker
                        get_tracker().record_safety_block()
                    except Exception:  # nosec B110 -- KPI tracking is best-effort
                        pass

                retries += 1
                feedback_issues = syntax_issues + verdict.issues
                if retries > 2:
                    return {
                        "step_id": step["id"],
                        "description": step["description"],
                        "status": "failed",
                        "issues": feedback_issues,
                        "changed_files": changed_files,
                        "observations": observations,
                        "models": {"executor": executor_model, "verifier": verifier_model},
                    }
            if not file_applied:
                return {
                    "step_id": step["id"],
                    "description": step["description"],
                    "status": "failed",
                    "issues": ["Executor did not produce an applicable file update."],
                    "changed_files": changed_files,
                    "observations": observations,
                    "models": {"executor": executor_model, "verifier": verifier_model},
                }

        step_review_issues = self._review_step_result(step=step, changed_files=changed_files)
        if step_review_issues:
            return {
                "step_id": step["id"],
                "description": step["description"],
                "status": "failed",
                "issues": step_review_issues,
                "changed_files": changed_files,
                "observations": observations,
                "models": {"executor": executor_model, "verifier": verifier_model},
            }

        return {
            "step_id": step["id"],
            "description": step["description"],
            "status": "applied",
            "changed_files": changed_files,
            "observations": observations,
            "models": {"executor": executor_model, "verifier": verifier_model},
        }

    async def _run_tool(
        self,
        tool: str,
        args: dict[str, Any],
        user_id: str | None = None,
        memory_store: UserMemoryStore | None = None,
    ) -> Any:
        # Emit a durable event for the tool call so the harness/UI can show live tool usage
        try:
            self._log_event(getattr(self, "_current_session_id", None), "tool_call", {"tool": tool, "args": args})
        except Exception:  # nosec B110 -- KPI tracking is best-effort
            # Non-fatal: logging should not break tool execution
            pass
        try:
            result = await self._dispatch_tool(tool, args, user_id=user_id, memory_store=memory_store)
            try:
                self._log_event(getattr(self, "_current_session_id", None), "tool_result", {"tool": tool, "result": result})
            except Exception:  # nosec B110 -- KPI tracking is best-effort
                pass
            return result
        except Exception as exc:
            # The harness catches tool failures as tool-call errors and feeds
            # them back to the model — it never surfaces raw exceptions.
            # (Anthropic managed-agents: decoupled sandbox; if the container
            # dies the harness returns the failure as a tool result.)
            log.warning("tool %r failed: %s", tool, exc)
            err = f"[tool error: {exc}]"
            try:
                self._log_event(getattr(self, "_current_session_id", None), "tool_result", {"tool": tool, "result": err})
            except Exception:  # nosec B110 -- KPI tracking is best-effort
                pass
            return err

    async def _dispatch_tool(
        self,
        tool: str,
        args: dict[str, Any],
        user_id: str | None = None,
        memory_store: UserMemoryStore | None = None,
    ) -> Any:
        # ── A3: Capability Registry dynamic dispatch ─────────────────────────
        # Try the tool registry first for dynamically registered tools.
        # Falls back to the hardcoded if/elif chain for legacy tools.
        tr = self._get_tool_registry()
        if tr is not None:
            tool_def = tr.get(tool)
            if tool_def is not None:
                try:
                    result = tool_def.handler(**args)
                    if asyncio.iscoroutine(result):
                        result = await result
                    return result
                except Exception as exc:
                    log.debug("Capability registry tool %r failed: %s", tool, exc)
                    return f"[tool error via registry: {exc}]"

        # Legacy hardcoded dispatch (fallback)
        # ── E2B sandbox routing (roadmap ★5) ───────────────────────────────
        # When runner._mcp is attached (E2B sandbox), route ALL fs/edit ops
        # through it first. On MCPUnavailableError, fall back to local
        # WorkspaceTools — mirroring the existing write_file/run_command
        # pattern. This ensures reads, edits, and commands all hit the same
        # sandbox working directory instead of the host worktree.
        from agent.mcp_client import MCPUnavailableError as _MCPUnavail

        if tool == "read_file":
            if self._mcp is not None:
                try:
                    return await self._mcp.call_tool("read_file", args)
                except _MCPUnavail:
                    pass
            return self.tools.read_file(str(args.get("path", "")))
        if tool == "head_file":
            # head_file is read_file + truncate; route through _mcp when attached.
            if self._mcp is not None:
                try:
                    content = await self._mcp.call_tool("read_file", args)
                    lines = int(args.get("lines", 50))
                    return "\n".join(content.splitlines()[:lines])
                except _MCPUnavail:
                    pass
            return self.tools.head_file(str(args.get("path", "")), int(args.get("lines", 50)))
        if tool == "file_index":
            if self._mcp is not None:
                try:
                    return await self._mcp.call_tool("file_index", args)
                except _MCPUnavail:
                    pass
            return self.tools.file_index(str(args.get("path", ".")), int(args.get("max_entries", 100)))
        if tool == "list_files":
            if self._mcp is not None:
                try:
                    return await self._mcp.call_tool("list_files", args)
                except _MCPUnavail:
                    pass
            return self.tools.list_files(str(args.get("path", ".")), int(args.get("limit", 200)))
        if tool == "search_code":
            if self._mcp is not None:
                try:
                    return await self._mcp.call_tool("search_code", args)
                except _MCPUnavail:
                    pass
            return self.tools.search_code(str(args.get("query", "")), int(args.get("limit", 20)))
        if tool == "recall_memory":
            if not memory_store or not user_id:
                return "(memory not available)"
            return self.tools.recall_memory(str(args.get("key", "")), user_id=user_id, memory_store=memory_store)
        if tool == "save_memory":
            if not memory_store or not user_id:
                return "(memory not available)"
            return self.tools.save_memory(str(args.get("key", "")), str(args.get("value", "")), user_id=user_id, memory_store=memory_store)
        # ├─ Skill execution (harness enrichment)
        if tool == "execute_skill":
            return self._execute_skill_tool(args)
        if tool == "recommend_skills":
            return self._recommend_skills_tool(args)

        # ═══════════════════════════════════════════════════════════════════
        # GitHub Tools
        if tool == "github_read_repo_file":
            return await self.github.read_repo_file(
                repo_name=str(args.get("repo_name", "")),
                path=str(args.get("path", "")),
                branch=str(args.get("branch", "main"))
            )
        if tool == "github_create_branch":
            return await self.github.create_branch(
                repo_name=str(args.get("repo_name", "")),
                branch_name=str(args.get("branch_name", "")),
                base_branch=str(args.get("base_branch", "main"))
            )
        if tool == "github_commit_changes":
            return await self.github.commit_changes(
                repo_name=str(args.get("repo_name", "")),
                branch_name=str(args.get("branch_name", "")),
                message=str(args.get("message", "agent commit")),
                path=str(args.get("path", "")),
                content=str(args.get("content", ""))
            )
        if tool == "github_open_pull_request":
            return await self.github.open_pull_request(
                repo_name=str(args.get("repo_name", "")),
                title=str(args.get("title", "Pull Request from AI Agent")),
                head=str(args.get("head", "")),
                base=str(args.get("base", "main")),
                body=str(args.get("body", ""))
            )
        if tool == "github_list_repos":
            return await self.github.list_repos()
        if tool == "github_list_branches":
            return await self.github.list_branches(
                repo_name=str(args.get("repo_name", ""))
            )

        # ------------------------------------------------------------------
        # MCP-delegated and MCP-with-local-fallback tools
        # ------------------------------------------------------------------
        from agent.mcp_client import MCPUnavailableError

        # write_file — try MCP first; fall back to local WorkspaceTools if unavailable
        if tool == "write_file":
            if self._mcp is not None:
                try:
                    return await self._mcp.call_tool("write_file", args)
                except MCPUnavailableError:
                    pass
            return self.tools.write_file(str(args.get("path", "")), str(args.get("content", "")))

        # run_command — try MCP first; fall back to local _run_command if unavailable
        if tool == "run_command":
            if self._mcp is not None:
                try:
                    return await self._mcp.call_tool("run_command", args)
                except MCPUnavailableError:
                    pass
            run_fn = getattr(self, "_run_command", None)
            if run_fn is not None:
                return await run_fn(str(args.get("cmd", "")), timeout=int(args.get("timeout", 120)))
            return "[tool error: run_command not available locally]"

        # MCP-only tools: clone_repo, git_commit — require MCP to be configured
        _MCP_ONLY = {"clone_repo", "git_commit", "git_push"}
        if tool in _MCP_ONLY:
            if self._mcp is None:
                return f"[tool error: MCP not configured — cannot execute {tool}]"
            try:
                return await self._mcp.call_tool(tool, args)
            except MCPUnavailableError as exc:
                return f"[tool error: MCP unavailable for {tool}: {exc}]"

        # Time awareness — agents can query the current UTC time without
        # relying on hallucinated or stale dates embedded in context.
        if tool == "get_current_time":
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            return {
                "utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "unix_timestamp": int(now.timestamp()),
                "date": now.strftime("%Y-%m-%d"),
                "day_of_week": now.strftime("%A"),
            }

        raise ValueError(f"Unsupported tool: {tool}")

    # ------------------------------------------------------------------
    # Event log helpers  (stateless harness / durable session log)
    # ------------------------------------------------------------------

    def _log_event(self, session_id: str | None, event_type: str, payload: dict[str, Any]) -> None:
        """Append an event to the durable session log if a store is wired in."""
        if session_id and self._session_store:
            try:
                self._session_store.append_event(session_id, event_type, payload)
            except Exception as exc:
                log.debug("event log write failed (non-fatal): %s", exc)

    # ------------------------------------------------------------------
    # Context compaction
    # ------------------------------------------------------------------

    async def _compact_history(
        self,
        history: list[dict[str, Any]],
        requested_model: str | None,
        session_id: str | None,
    ) -> list[dict[str, Any]]:
        """Summarise a long history and compact it.

        Asks the planner model to write a concise summary, then replaces the
        old messages with that summary + the most recent context.
        """
        try:
            summary_text = await self._chat_text(
                requested_model or DEFAULT_PLANNER_MODEL,
                build_compaction_prompt(history),
            )
            self._log_event(
                session_id, "compaction",
                {"original_length": len(history), "summary_length": len(summary_text)},
            )
            return self.ctx.compact_history(history, compaction_summary=summary_text)
        except Exception as exc:
            log.warning("context compaction failed (continuing uncompacted): %s", exc)
            return history

    async def _chat_text(self, model: str, messages: list[dict[str, str]]) -> str:
        """Send chat messages and return the assistant's text output.

        If an Anthropic/Bedrock Opus model is configured and the request targets
        an Opus/Claude model, prefer calling Anthropic (Opus) directly. Fall
        back to the Ollama-compatible endpoint otherwise.
        """
        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": False}

        # Context pruning: enforce token budgets before sending to the LLM
        messages = self.pruner.prune(messages)
        payload["messages"] = messages

        # C5: Auto-truncate messages to fit within the model's context window
        if _AGENT_CONTEXT_WINDOW_ENABLED and isinstance(messages, list) and len(messages) > 4:
            try:
                from services.context_window import get_context_window_manager
                mgr = get_context_window_manager()
                if mgr.needs_truncation(messages, model=model):
                    result = mgr.truncate(messages, model=model)
                    payload["messages"] = result.messages
                    log.debug("Agent context window truncated: %d → %d messages (model=%s)",
                             result.original_count, result.truncated_count, model)
            except Exception:  # nosec B110 -- KPI tracking is best-effort
                pass

        # SteerLM steering injection (B2): inject quality-biasing instruction
        # Only inject for execution-phase calls; planning/verification use
        # their own prompt structures that shouldn't be steered.
        steering = self._get_steering()
        if steering is not None and steering.enabled:
            try:
                from router.steering import steering_for_task
                # Use code_generation steering by default for execution calls.
                # Callers can override by setting _steering_labels on the runner.
                labels = getattr(self, "_steering_labels", None) or steering_for_task("code_generation")
                payload["messages"] = steering.inject(
                    messages=payload["messages"],
                    labels=labels,
                )
            except Exception:  # nosec B110 -- KPI tracking is best-effort
                pass

        if self.provider_temperature is not None:
            payload["temperature"] = self.provider_temperature

        normalized_base = self.ollama_base.rstrip("/")
        explicit_provider_configured = bool(self.provider_headers)
        provider_header_names = {key.lower() for key in self.provider_headers}

        # Ollama-specific fields — ONLY add when targeting a local Ollama
        # endpoint. NVIDIA NIM and other OpenAI-compatible endpoints reject
        # unknown fields with HTTP 400 Bad Request.
        _is_ollama_target = "localhost:11434" in normalized_base or "ollama" in normalized_base.lower()
        if _is_ollama_target:
            if self.num_ctx:
                payload["options"] = {"num_ctx": self.num_ctx}
            if self.keep_alive:
                payload["keep_alive"] = self.keep_alive
        else:
            # NVIDIA NIM / OpenAI-compatible: add max_tokens (required by NIM)
            if "max_tokens" not in payload:
                payload["max_tokens"] = 4096
        provider_is_anthropic = (
            "x-api-key" in provider_header_names
            or (urlparse(normalized_base).hostname or "").lower().endswith("anthropic.com")
        )

        # Effective endpoint for the OpenAI-compatible fallback. Defaults to the
        # configured Ollama/provider, but the free-brain guard below may override
        # it to the free NVIDIA brain.
        _call_base = self.ollama_base
        _call_headers = dict(self.provider_headers)

        # ── Free-brain policy guard (issue #656) ──────────────────────────────
        # The agent runtime must NEVER call paid Anthropic/Bedrock unless the
        # operator explicitly opted in via ALLOW_PAID_BRAIN=true. When the
        # requested model is Anthropic-shaped (e.g. a stale
        # AGENT_*_MODEL=us.anthropic.claude-opus-*), transparently route to the
        # free NVIDIA brain instead. If no free brain is configured, refuse
        # loudly rather than returning a confusing 400/401 from api.anthropic.com.
        # Defense-in-depth: brain_policy is a top-level module. If it is ever
        # missing from the runtime (e.g. a packaging/Docker gap), a bare import
        # here would raise ModuleNotFoundError and brick ALL planning — exactly
        # the "No module named brain_policy → blocked after 10 failed dispatch
        # attempts" outage. Fall back to an inline free-only policy that mirrors
        # brain_policy so the agent stays on the free NVIDIA brain and never
        # silently escalates to paid Anthropic.
        try:
            from packages.ai.brain import (
                allow_paid_brain as _allow_paid_brain_fn,
                is_anthropic_model as _is_anthropic_model,
                resolve_free_nvidia_brain as _resolve_free_nvidia_brain,
            )
        except Exception as _bp_exc:  # noqa: BLE001 — never let a missing policy module brick planning
            log.warning(
                "brain_policy import failed (%s); using inline free-brain fallback "
                "(paid Anthropic stays disabled).", _bp_exc,
            )

            def _allow_paid_brain_fn() -> bool:
                return os.environ.get("ALLOW_PAID_BRAIN", "").strip().lower() in {"1", "true", "yes", "on"}

            def _is_anthropic_model(_m: str | None) -> bool:
                _s = (_m or "").strip().lower()
                return bool(_s) and (
                    _s.startswith(("claude", "us.anthropic", "anthropic"))
                    or "anthropic." in _s
                    or "opus" in _s
                )

            def _resolve_free_nvidia_brain():
                _key = (os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey") or "").strip()
                if not _key:
                    return None
                _base = (os.environ.get("NVIDIA_BASE_URL") or "").strip().rstrip("/") or "https://integrate.api.nvidia.com"
                if not _base.endswith("/v1"):
                    _base = f"{_base}/v1"
                _model = (os.environ.get("NVIDIA_DEFAULT_MODEL") or "").strip() or "meta/llama-3.3-70b-instruct"
                return _base, {"Authorization": f"Bearer {_key}"}, _model
        _paid_allowed = _allow_paid_brain_fn()
        if (not _paid_allowed) and (_is_anthropic_model(model) or provider_is_anthropic):
            _nv = _resolve_free_nvidia_brain()
            if _nv is None:
                raise RuntimeError(
                    "Free-brain policy is active (ALLOW_PAID_BRAIN unset) but no "
                    "free brain is configured. Set NVIDIA_API_KEY (free, "
                    "https://build.nvidia.com) to run the agent on a free model. "
                    f"Refusing to call paid Anthropic for model {model!r}."
                )
            _nv_base, _nv_headers, _nv_model = _nv
            log.info(
                "Free-brain policy: routing Anthropic-shaped agent model %r → "
                "free NVIDIA brain %r",
                model, _nv_model,
            )
            model = _nv_model
            payload["model"] = _nv_model
            _call_base = _nv_base
            _call_headers = dict(_nv_headers)
            normalized_base = _nv_base.rstrip("/")
            explicit_provider_configured = True
            provider_is_anthropic = False

        # Prefer Anthropic Opus when available for Claude/Opus-like models
        # (only when the operator has explicitly opted into a paid brain).
        try:
            opus_model = None
            try:
                from router.model_router import _opus_model
                opus_model = _opus_model()
            except Exception:  # nosec B110 -- KPI tracking is best-effort
                opus_model = None
            anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
            target_is_opus = "opus" in model.lower() or model.lower().startswith("claude")
            if _paid_allowed and (not explicit_provider_configured) and anthropic_key and (target_is_opus or (opus_model and model == opus_model)):
                try:
                    import anthropic as _anthropic
                    client = _anthropic.AsyncAnthropic(api_key=anthropic_key)
                    # Split off system message (Anthropic expects a separate system arg)
                    system_content = None
                    anth_messages: list[dict[str, str]] = []
                    for m in messages:
                        if m.get("role") == "system":
                            system_content = m.get("content")
                        else:
                            anth_messages.append({"role": m.get("role"), "content": m.get("content")})
                    use_model = opus_model if opus_model else model
                    resp = await client.messages.create(
                        model=use_model,
                        max_tokens=4096,
                        system=system_content or "",
                        messages=anth_messages,
                    )
                    # Collect text blocks
                    out_parts: list[str] = []
                    for block in resp.content:
                        if getattr(block, "type", None) == "text":
                            out_parts.append(block.text)
                    out_text = "\n".join(out_parts)

                    # Try to emit Langfuse observation asynchronously
                    if self.email:
                        try:
                            from langfuse_obs import emit_chat_observation
                            usage = {}
                            await asyncio.to_thread(
                                emit_chat_observation,
                                email=self.email,
                                department=self.department or "agent",
                                key_id=self.key_id,
                                model=use_model,
                                messages=messages,
                                output_text=out_text,
                                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                                completion_tokens=int(usage.get("completion_tokens") or 0),
                                latency_ms=0,
                                task_name="agent-task",
                            )
                        except Exception:  # nosec B110 -- KPI tracking is best-effort
                            pass

                    return out_text
                except Exception as exc:
                    log.debug("Anthropic Opus call failed (falling back to Ollama): %s", exc)

            # Bedrock fallback: used when only AWS credentials are set (no ANTHROPIC_API_KEY)
            if _paid_allowed and (not explicit_provider_configured) and (not anthropic_key) and target_is_opus:
                aws_access = os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("BEDROCK_ACCESS_KEY")
                aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY") or os.environ.get("BEDROCK_SECRET_KEY")
                aws_region = (
                    os.environ.get("AWS_REGION")
                    or os.environ.get("AWS_DEFAULT_REGION")
                    or os.environ.get("BEDROCK_REGION")
                    or "us-east-1"
                )
                bedrock_model = os.environ.get("BEDROCK_MODEL_ID") or "us.anthropic.claude-opus-4-6-v1"
                if aws_access and aws_secret:
                    try:
                        import anthropic as _anthropic
                        bedrock_client = _anthropic.AsyncAnthropicBedrock(
                            aws_access_key=aws_access,
                            aws_secret_key=aws_secret,
                            aws_region=aws_region,
                        )
                        system_content = None
                        anth_messages: list[dict[str, str]] = []
                        for m in messages:
                            if m.get("role") == "system":
                                system_content = m.get("content")
                            else:
                                anth_messages.append({"role": m.get("role"), "content": m.get("content")})
                        resp = await bedrock_client.messages.create(
                            model=bedrock_model,
                            max_tokens=4096,
                            system=system_content or "",
                            messages=anth_messages,
                        )
                        out_parts: list[str] = []
                        for block in resp.content:
                            if getattr(block, "type", None) == "text":
                                out_parts.append(block.text)
                        out_text = "\n".join(out_parts)
                        if self.email:
                            try:
                                from langfuse_obs import emit_chat_observation
                                await asyncio.to_thread(
                                    emit_chat_observation,
                                    email=self.email,
                                    department=self.department or "agent",
                                    key_id=self.key_id,
                                    model=bedrock_model,
                                    messages=messages,
                                    output_text=out_text,
                                    prompt_tokens=0,
                                    completion_tokens=0,
                                    latency_ms=0,
                                    task_name="agent-task",
                                )
                            except Exception:  # nosec B110 -- KPI tracking is best-effort
                                pass
                        return out_text
                    except Exception as exc:
                        log.debug("Bedrock Opus call failed (falling back to Ollama): %s", exc)
        except Exception:  # nosec B110 -- KPI tracking is best-effort
            # Any unexpected error should not break the normal Ollama path
            pass

        if provider_is_anthropic and _paid_allowed:
            headers = {"Content-Type": "application/json", **self.provider_headers}
            system_parts: list[str] = []
            anthropic_messages: list[dict[str, str]] = []
            for message in payload.get("messages") or []:
                if not isinstance(message, dict):
                    continue
                role = str(message.get("role") or "user")
                content = str(message.get("content") or "")
                if role == "system":
                    system_parts.append(content)
                elif role in {"user", "assistant"}:
                    anthropic_messages.append({"role": role, "content": content})
            anthropic_payload = {
                "model": model,
                "messages": anthropic_messages or [{"role": "user", "content": ""}],
                "system": "\n\n".join(system_parts) if system_parts else None,
                "max_tokens": 4096,
                "temperature": payload.get("temperature", 0.3),
            }
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
                resp = await client.post(
                    f"{normalized_base}/v1/messages",
                    json=anthropic_payload,
                    headers=headers,
                )
            duration_ms = int((time.perf_counter() - start) * 1000)
            resp.raise_for_status()
            data = resp.json()
            out_text = "\n".join(
                block.get("text", "")
                for block in data.get("content", [])
                if isinstance(block, dict) and block.get("type") == "text"
            ).strip()

            anth_usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
            pt_anth = int(anth_usage.get("input_tokens") or 0)
            ct_anth = int(anth_usage.get("output_tokens") or 0)
            if self.email:
                try:
                    from langfuse_obs import emit_chat_observation
                    await asyncio.to_thread(
                        emit_chat_observation,
                        email=self.email,
                        department=self.department or "agent",
                        key_id=self.key_id,
                        model=model,
                        messages=messages,
                        output_text=out_text,
                        prompt_tokens=pt_anth,
                        completion_tokens=ct_anth,
                        latency_ms=duration_ms,
                        task_name="agent-task",
                    )
                except Exception:  # nosec B110 -- KPI tracking is best-effort
                    pass
            # ★3: enforce per-session token budget cap
            self._record_tokens(self._current_session_id, pt_anth, ct_anth)
            return out_text

        # ── Universal multi-provider failover ──────────────────────────────
        # The brain_failover manager treats EVERY configured provider as a
        # candidate brain. On 429/410/5xx, it marks the provider unhealthy
        # and we retry on the next healthy provider. This is the permanent
        # solution to the recurring NVIDIA 429/410 rate-limit problem.
        from services.brain_failover import get_failover_manager
        from packages.ai.router import _openai_url

        fm = get_failover_manager()
        tried: set[str] = set()
        last_resp: httpx.Response | None = None
        last_error: str = ""

        for _attempt in range(fm.max_attempts()):
            provider = fm.next_provider(exclude=tried, requested_model=model)
            if provider is None:
                log.error("brain_failover: no healthy providers left (tried=%s)", tried)
                break

            tried.add(provider.id)
            # Resolve the model for this provider (alias mapping)
            provider_model = fm.resolve_model(provider, model)

            # Build the URL + headers for this provider
            chat_url = _openai_url(provider.base_url, "/chat/completions")
            headers = {"Content-Type": "application/json"}
            if provider.api_key:
                headers["Authorization"] = f"Bearer {provider.api_key}"

            # Try multiple models on this provider before giving up — when a
            # model returns 410 Gone (dead), try the next model. This handles
            # the case where NVIDIA_DEFAULT_MODEL points at a dead model.
            models_to_try = [provider_model] + [
                m for m in provider.models if m != provider_model
            ]
            for try_model in models_to_try[:3]:
                payload["model"] = try_model
                log.debug("brain_failover: attempt %d -> %s (model=%s)",
                           _attempt + 1, provider.id, try_model)

                call_start = time.perf_counter()
                try:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                        resp = await client.post(chat_url, json=payload, headers=headers)
                except Exception as exc:
                    last_error = f"{provider.id} network error: {exc}"
                    log.warning("brain_failover: %s network error: %s", provider.id, exc)
                    fm.record_failure(provider.id, "network_error")
                    break

                last_resp = resp
                call_ms = int((time.perf_counter() - call_start) * 1000)

                if resp.status_code < 400:
                    fm.record_success(provider.id, latency_ms=call_ms)
                    data = resp.json()
                    out_text = data["choices"][0]["message"]["content"]
                    if self.email:
                        usage = data.get("usage", {})
                        pt = int(usage.get("prompt_tokens") or 0)
                        ct = int(usage.get("completion_tokens") or 0)
                        try:
                            from langfuse_obs import emit_chat_observation
                            await asyncio.to_thread(
                                emit_chat_observation,
                                email=self.email,
                                department=self.department or "agent",
                                key_id=self.key_id,
                                model=try_model,
                                messages=messages,
                                output_text=out_text,
                                prompt_tokens=pt,
                                completion_tokens=ct,
                                latency_ms=call_ms,
                                task_name="agent-task",
                            )
                        except Exception as exc:
                            log.debug("Agent Langfuse emit failed: %s", exc)
                    # ★3: enforce per-session token budget cap (raises BudgetExceededError if hit)
                    self._record_tokens(self._current_session_id, pt, ct)
                    return out_text

                if resp.status_code == 410:
                    log.warning("brain_failover: %s model %s 410 Gone - trying next model",
                               provider.id, try_model)
                    continue

                if resp.status_code in (429, 419):
                    last_error = f"{provider.id} {resp.status_code} rate-limited"
                    fm.record_failure(provider.id, "rate_limited", resp.status_code)
                    break

                if resp.status_code >= 500:
                    last_error = f"{provider.id} {resp.status_code} server error"
                    fm.record_failure(provider.id, "server_error", resp.status_code)
                    break

                last_error = f"{provider.id} {resp.status_code}: {resp.text[:200]}"
                log.warning("brain_failover: %s model %s returned %d - trying next model",
                           provider.id, try_model, resp.status_code)
                continue
            else:
                fm.record_failure(provider.id, "all_models_failed")
                continue

        # All providers exhausted — raise with the last error
        if last_resp is not None:
            last_resp.raise_for_status()
        raise RuntimeError(f"All brain providers exhausted. Last error: {last_error}")

    async def _chat_json(self, model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        raw = await self._chat_text(model, messages)
        for _ in range(3):
            try:
                parsed = self._extract_json(raw)
                if not isinstance(parsed, dict):
                    raise ValueError("Model did not return a JSON object")
                return parsed
            except Exception:  # nosec B110 -- KPI tracking is best-effort
                raw = await self._chat_text(
                    model,
                    [
                        {"role": "system", "content": "Return only a valid JSON object. No prose. No code fences."},
                        {"role": "user", "content": raw},
                    ],
                )
        parsed = self._extract_json(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Model did not return a JSON object")
        return parsed

    def _extract_json(self, raw: str) -> Any:
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.S)
            if not match:
                raise
            return json.loads(match.group(0))

    def _parse_execution_response(self, raw: str, fallback_path: str) -> tuple[str, str] | None:
        match = re.search(
            r"FILE:\s*(?P<path>[^\r\n]+)\s*ACTION:\s*(?P<action>create|replace|append)\s*```[^\n]*\n(?P<content>.*?)\n```",
            raw.strip(),
            re.S,
        )
        if not match:
            return None
        path = match.group("path").strip() or fallback_path
        action = match.group("action").strip()
        content = match.group("content")
        if action == "append":
            existing = self._safe_read(path)
            content = (existing + ("\n" if existing else "") + content).rstrip("\n") + "\n"
        return path, content

    _LANG_PREFIXES = (
        "python\n", "javascript\n", "typescript\n", "html\n", "css\n",
        "json\n", "yaml\n", "yml\n", "sh\n", "bash\n", "zsh\n", "text\n",
        "rust\n", "go\n", "java\n", "cpp\n", "c\n", "csharp\n", "cs\n",
        "markdown\n", "md\n", "sql\n", "xml\n", "toml\n", "ini\n",
        "dockerfile\n", "makefile\n", "ruby\n", "php\n", "swift\n",
        "kotlin\n", "scala\n", "r\n",
    )

    def _clean_generated_file_content(self, content: str) -> str:
        cleaned = content.replace("\r\n", "\n")
        # Remove language identifier if it leaked into the content block
        for prefix in self._LANG_PREFIXES:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):]
                break
        cleaned = cleaned.strip("\n")
        if cleaned and not cleaned.endswith("\n"):
            cleaned += "\n"
        return cleaned

    def _local_syntax_check(self, path: str, content: str) -> list[str]:
        issues: list[str] = []
        if path.endswith(".py"):
            try:
                ast.parse(content)
            except SyntaxError as exc:
                issues.append(f"Python syntax error: {exc.msg} at line {exc.lineno}")
        return issues

    def _local_safety_check(self, path: str, content: str) -> list[str]:
        issues: list[str] = []
        if not path.endswith(".py"):
            return issues

        lowered = content.lower()
        if "jwt" in lowered or "oauth2" in lowered or "authentication" in lowered:
            if re.search(r"SECRET_KEY\s*=\s*[\"'][^\"']+[\"']", content):
                issues.append("Auth/JWT code hardcodes SECRET_KEY instead of reading configuration from the environment.")
            if "fake_users_db" in lowered:
                issues.append("Auth/JWT code introduces fake in-memory users, which is not a safe default for real authentication work.")
        return issues

    def _review_step_result(self, *, step: dict[str, Any], changed_files: list[str]) -> list[str]:
        issues: list[str] = []
        desc = str(step.get("description", "")).lower()
        changed_set = {path.replace("\\", "/").lower() for path in changed_files}

        if "across this module" in desc and len(changed_files) < 2:
            issues.append("Module-wide change touched too few files to be complete.")

        if "shared logger utility" in desc:
            has_logger_utility = any(
                path.endswith(("logger.py", "logging_utils.py", "logger_util.py"))
                for path in changed_set
            )
            if not has_logger_utility:
                issues.append("Shared logger utility was requested but no logger utility file was created or updated.")
            if len(changed_files) < 2:
                issues.append("Logging task changed too few files to count as a module-wide update.")

        if "jwt" in desc or "authentication" in desc:
            if not any(path.endswith(("requirements.txt", "pyproject.toml", "poetry.lock")) for path in changed_set):
                issues.append("Auth task did not update dependency metadata for JWT/auth packages.")

            hardcoded_secret = False
            for path in changed_files:
                content = self._safe_read(path)
                if re.search(r"SECRET_KEY\s*=\s*[\"'][^\"']+[\"']", content):
                    hardcoded_secret = True
                    break
            if hardcoded_secret:
                issues.append("Auth task still contains a hardcoded SECRET_KEY.")

        return issues

    # ── Reward scorer accessor (B1) ─────────────────────────────────────────

    def _get_reward_scorer(self) -> Any:
        if self._reward_scorer is None:
            try:
                from services.reward_scorer import get_reward_scorer
                self._reward_scorer = get_reward_scorer()
            except Exception as exc:
                log.debug("Could not load reward scorer: %s", exc)
                self._reward_scorer = False  # sentinel: tried and failed
        return self._reward_scorer if self._reward_scorer is not False else None

    # ── Capability registry accessor (A3) ───────────────────────────────────

    def _get_tool_registry(self) -> Any:
        if self._tool_registry is None:
            try:
                from agent.capability_registry import get_tool_registry
                self._tool_registry = get_tool_registry()
            except Exception as exc:
                log.debug("Could not load tool registry: %s", exc)
                self._tool_registry = False
        return self._tool_registry if self._tool_registry is not False else None

    def _get_steering(self) -> Any:
        """Lazy accessor for the SteerLM steering injector (B2)."""
        if self._steering is None:
            try:
                from router.steering import get_steering_injector
                self._steering = get_steering_injector()
            except Exception as exc:
                log.debug("Could not load steering injector: %s", exc)
                self._steering = False
        return self._steering if self._steering is not False else None

    def _safe_read(self, path: str) -> str:
        """Read a file safely, returning '' on error.

        When an E2B sandbox is attached (``self._mcp``), reads should go to
        the sandbox — but this method is sync and the sandbox is async. The
        caller (verifier/judge) runs inside an async step, so we use
        ``asyncio.get_event_loop().run_until_complete`` is NOT safe here
        (we're already in a running loop). Instead, the primary edit path
        (apply_diff at line ~1006) routes through the sandbox directly, and
        after the run ``extract_changes_to_worktree`` copies sandbox changes
        back to the host worktree. So this host-side read sees the extracted
        changes — which is correct for the verifier's post-extraction checks.

        During the run (before extraction), the verifier may see stale host
        content. This is acceptable because the verifier's job is to check
        syntax/safety of the *new* content (which it receives via the
        ``new_content`` argument, not by re-reading the file).
        """
        try:
            return self.tools.read_file(path, max_chars=200000)
        except Exception:  # nosec B110 -- best-effort read
            return ""

    def _commit_step(self, description: str, changed_files: list[str]) -> str | None:
        try:
            subprocess.run(["git", "add", *changed_files], cwd=self.tools.root, check=True, capture_output=True, text=True)  # nosec B603,B607 - constant git argv, list form (no shell)
            subprocess.run(  # nosec B603,B607 - constant git argv, list form (no shell)
                ["git", "commit", "-m", f"agent: {description}"],
                cwd=self.tools.root,
                check=True,
                capture_output=True,
                text=True,
            )
            proc = subprocess.run(  # nosec B603,B607 - constant git argv, list form (no shell)
                ["git", "rev-parse", "HEAD"],
                cwd=self.tools.root,
                check=True,
                capture_output=True,
                text=True,
            )
            return proc.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
            log.warning("Auto-commit failed: %s", exc)
            return None

    # ── Harness enrichment helpers ───────────────────────────────────────────

    @staticmethod
    def _inject_enrichment(messages: list[dict[str, str]]) -> None:
        """Inject available tools + skills catalog into the system message.

        Best-effort — never raises, never blocks the agent loop.
        """
        try:
            enrichment = get_enrichment()
            full = enrichment.build_full_enrichment()
            if full:
                sys_content = str(messages[0].get("content", ""))
                messages[0]["content"] = f"{sys_content}\n\n{full}"
        except Exception:
            pass  # enrichment is best-effort — never break agent loop

    # ── Skill execution helpers (harness enrichment) ─────────────────────────

    @staticmethod
    def _execute_skill_tool(args: dict[str, Any]) -> str:
        """Execute a named skill via SkillBindings.

        Called from the tool-call loop when the model selects 'execute_skill'.
        """
        skill_id = str(args.get("skill_id") or args.get("skill") or "")
        if not skill_id:
            return "[error: execute_skill requires a skill_id]"
        try:
            from services.skill_bindings import get_skill_bindings
            sb = get_skill_bindings()
            result = sb.execute_skill(skill_id, args.get("params") or {})
            if result.get("success"):
                res = result.get("result", "done")
                return str(res)[:2000]
            return f"[skill error: {result.get('error', 'unknown')}]"
        except Exception as exc:
            return f"[skill error: {exc}]"

    @staticmethod
    def _recommend_skills_tool(args: dict[str, Any]) -> str:
        """Recommend skills relevant to the current task.

        Called from the tool-call loop when the model selects 'recommend_skills'.
        """
        query = str(args.get("query") or args.get("task") or "")
        try:
            from services.skill_bindings import get_skill_bindings
            sb = get_skill_bindings()
            skills = sb.search(query) if query else sb.list_all()
            # Return top 10 enabled skills with one-line descriptions
            enabled = [s for s in skills if getattr(s, "is_enabled", True)][:10]
            if not enabled:
                # Try the SkillRegistry for a broader search
                try:
                    from agent.skill_registry import get_skill_registry_safe
                    sr = get_skill_registry_safe()
                    if sr:
                        registry_skills = sr.search(query) if query else sr.list()
                        top = registry_skills[:10]
                        lines = [f"- {s.skill_id}: {s.description[:120]}" for s in top]
                        return "RECOMMENDED SKILLS (from registry):\n" + "\n".join(lines) if lines else "(no relevant skills found)"
                except Exception:
                    pass
                return "(no enabled skills match your query)"
            lines = [
                f"- {s.skill_id}: {s.description[:120]}"
                for s in enabled
            ]
            return "RECOMMENDED SKILLS:\n" + "\n".join(lines) if lines else "(no skills found)"
        except Exception as exc:
            return f"[skill search error: {exc}]"

    async def _maybe_run_parallel(
        self,
        *,
        plan: Any,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Check if plan steps can run in parallel; returns result dict or None to fall through."""
        return None

    @staticmethod
    def _steps_are_independent(steps: list) -> bool:
        """Return True when no file is touched by more than one step."""
        seen: set[str] = set()
        for step in steps:
            files = step.files if hasattr(step, "files") else step.get("files", [])
            for f in files:
                if f in seen:
                    return False
                seen.add(f)
        return True

    async def _spawn_subagent(
        self,
        *,
        instruction: str = None,  # type: ignore[assignment]
        max_steps: int = 3,
        role: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Spawn a child AgentRunner for a delegated sub-task.

        When sub-agent configs are registered (★2), the child runner inherits
        the per-role model and tool allowlist.  The ``role`` kwarg selects the
        config (e.g. ``"file_picker"``, ``"editor"``); when empty or unmatched
        the child uses the parent's default model.

        The executor model may emit ``command``, ``task``, or ``text`` as the
        instruction field name instead of ``instruction`` — all three are
        accepted as aliases.
        """
        if not instruction:
            instruction = kwargs.pop("command", None) or kwargs.pop("task", None) or kwargs.pop("text", None) or ""
        if not instruction or not instruction.strip():
            return {"error": "spawn_subagent requires a non-empty instruction"}
        sub = AgentRunner(
            ollama_base=self.ollama_base,
            workspace_root=self.tools.root,
            provider_headers=self.provider_headers or None,
            provider_temperature=self.provider_temperature,
            session_store=self._session_store,
        )
        # Apply per-role sub-agent config if available
        cfg = self.sub_agents.get(role) if role else None
        if cfg:
            sub.configure_sub_agents([cfg])
            override_model = cfg.model or None
            log.debug("spawn_subagent role=%s model=%s", role, override_model or "(inherit)")
        else:
            override_model = None
        return await sub.run(
            instruction=instruction,
            history=[],
            requested_model=override_model,
            auto_commit=False,
            max_steps=int(max_steps) if not cfg else min(int(max_steps), cfg.max_steps),
        )

    async def _auto_push_and_pr(self, commits: list[str], session_id: str | None, goal: str = "") -> str | None:
        """Push commits and open a PR on GitHub. Returns the PR URL or None.

        Only activates when repo_url points to a GitHub repository and the
        runner has a valid GitHub token.  Protected branches (main/master) are
        never pushed to directly — we create a feature branch, push that, and
        open a PR for the user to review.
        """
        if not self.repo_url or not self.github.token:
            return None

        import re as _re
        from agent.github_tools import LocalWorkspace

        # Accept dotted repo names (e.g. service.api), an optional .git suffix, and
        # extra path/query segments after owner/repo.
        match = _re.search(
            r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/#?]+?)(?:\.git)?(?:[/?#]|$)",
            self.repo_url,
        )
        if not match:
            log.debug("repo_url %r does not match github.com pattern — skipping auto-PR", self.repo_url)
            return None

        owner, repo = match.group("owner"), match.group("repo")

        try:
            ws = LocalWorkspace(owner, repo, self.github.token)
            # Force the workspace path to the runner's actual working directory
            # (which may be a worktree or temp copy, not WORKSPACE_BASE_DIR).
            ws.path = Path(self.tools.root)

            if not ws.exists():
                log.debug("Workspace %s is not a git repo — skipping auto-PR", self.tools.root)
                return None

            current_branch = await ws.current_branch()
            base_branch = self.base_branch

            # Never push directly to a protected branch OR to the PR base branch —
            # opening a PR with head == base is rejected by GitHub. Isolate the agent's
            # changes on a fresh feature branch in those cases.
            if current_branch == base_branch or current_branch in ("main", "master"):
                push_branch = f"agent/task-{uuid.uuid4().hex[:8]}"
                await ws.create_branch(push_branch, current_branch)
                self._log_event(session_id, "step_start", {"description": f"Created branch {push_branch}"})
            else:
                push_branch = current_branch

            # Push with token-scrubbing (LocalWorkspace.push handles try/finally).
            await ws.push(branch=push_branch, agent_initiated=True)
            self._log_event(session_id, "step_start", {"description": f"Pushed branch {push_branch}"})

            # Derive a meaningful PR title from the task goal or first commit.
            pr_title = goal or (commits[0] if commits else "Agent auto-commit")
            # Strip commit hash if goal wasn't available and we fell through.
            if not goal and len(pr_title) == 40 and pr_title.isalnum():
                pr_title = f"Agent changes ({pr_title[:7]})"
            # Cap title length for GitHub (256 char limit, leave slack).
            pr_title = pr_title[:200]

            pr_body = "🤖 Automated PR created by AI Agent.\n\n### Commits\n" + "\n".join(
                f"- `{c[:7]}`" for c in commits
            )

            pr_result = await self.github.open_pull_request(
                owner=owner,
                repo=repo,
                title=pr_title,
                head=push_branch,
                base=base_branch,
                body=pr_body,
                agent_initiated=True,
            )
            pr_url = pr_result.get("html_url") or ""
            self._log_event(session_id, "assistant_message", {
                "summary": f"Opened PR: {pr_url}",
                "pr_url": pr_url,
            })
            log.info("Auto-PR opened: %s", pr_url)
            return pr_url

        except Exception as exc:
            log.warning("Auto-push/PR failed (non-fatal): %s", exc)
            return None

    def _build_summary(self, goal: str, step_results: list[dict[str, Any]], commits: list[str], pr_url: str | None = None) -> str:
        applied = sum(1 for step in step_results if step.get("status") == "applied")
        failed = [step for step in step_results if step.get("status") == "failed"]
        parts = [f"Goal: {goal}", f"Applied steps: {applied}/{len(step_results)}"]
        if failed:
            parts.append(f"Failed steps: {len(failed)}")
        if commits:
            parts.append(f"Commits: {len(commits)}")
        if pr_url:
            parts.append(f"PR: {pr_url}")
        return " | ".join(parts)


# ── FreeBuff: self-hosted Codebuff-style agent on free NVIDIA NIM models ───────

# Curated set of free NVIDIA NIM model IDs FreeBuff is allowed to route to.
# Overridable via FREEBUFF_MODELS (comma-separated) for new-model rollouts.
# Live-verified 2026-06-20: only these four models return HTTP 200 against
# https://integrate.api.nvidia.com/v1/chat/completions. The previously-listed
# qwen/qwen2.5-coder-32b-instruct (410 Gone), meta/llama-3.1-8b-instruct
# (undocumented on free tier at the time of probe), and deepseek-ai/deepseek-r1
# (404) are removed — they would silently 4xx every FreeBuff run.
_DEFAULT_FREE_NVIDIA_MODELS: tuple[str, ...] = (
    "meta/llama-3.3-70b-instruct",
    "meta/llama-3.1-70b-instruct",
)

# NVIDIA NIM is OpenAI-compatible and lives behind /v1; the runner's _chat_text
# uses _openai_url() so this base must NOT double the /v1 segment.
NVIDIA_NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"


def free_nvidia_models() -> list[str]:
    """Return the curated list of free NVIDIA NIM models FreeBuff may use."""
    raw = os.environ.get("FREEBUFF_MODELS", "").strip()
    if raw:
        models = [m.strip() for m in raw.split(",") if m.strip()]
        if models:
            return models
    return list(_DEFAULT_FREE_NVIDIA_MODELS)


def _nvidia_api_key() -> str | None:
    return os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey")


class FreeBuffAgent(AgentRunner):
    """Codebuff-style coding agent pinned to free NVIDIA NIM models.

    FreeBuff is a self-hosted take on Codebuff's "Free Buff": a cloud coding
    agent that runs on free models. It reuses the full ``AgentRunner`` plan →
    execute → verify loop but constrains model selection to the curated free
    NVIDIA NIM set (see :meth:`available_models`) so it never routes to a paid
    endpoint. It is designed to be driven from a phone via the Telegram bot:
    pick a model, review the plan, then accept (commit + draft PR) or reject.

    When ``NVIDIA_API_KEY`` is configured the runner is pinned to the NVIDIA NIM
    base URL with the key in the Authorization header. With no key set it falls
    back to a local OpenAI-compatible base so construction never fails (tests /
    local-only deployments).
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        ollama_base: str | None = None,
        provider_headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        api_key = _nvidia_api_key()
        base = ollama_base
        headers = dict(provider_headers or {})
        if api_key:
            base = base or NVIDIA_NIM_BASE_URL
            headers.setdefault("Authorization", f"Bearer {api_key}")
        base = base or os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434/v1"
        super().__init__(ollama_base=base, provider_headers=headers or None, **kwargs)
        # Selected free model for this session (coerced to a valid free model).
        self.model = self.resolve_model(model)

    @classmethod
    def available_models(cls) -> list[str]:
        """List the free NVIDIA NIM models a user may pick (e.g. via Telegram)."""
        return free_nvidia_models()

    @classmethod
    def is_free_model(cls, model: str | None) -> bool:
        """True when *model* is in the curated free NVIDIA NIM set."""
        return bool(model) and model in free_nvidia_models()

    def resolve_model(self, requested: str | None) -> str:
        """Coerce *requested* to a free NVIDIA model.

        Returns *requested* when it is already a free model; otherwise falls
        back to the currently-selected model (if any) or the first free model.
        Never returns a paid/non-free model — that is the whole point of FreeBuff.
        """
        models = free_nvidia_models()
        if requested and requested in models:
            return requested
        if requested:
            log.warning(
                "FreeBuff: %r is not a free NVIDIA model — using %s instead",
                requested, (getattr(self, "model", None) or models[0]),
            )
        return getattr(self, "model", None) or models[0]

    async def plan(  # type: ignore[override]
        self,
        *,
        instruction: str,
        history: list[dict[str, str]] | None = None,
        requested_model: str | None = None,
        max_steps: int = 30,
        user_id: str | None = None,
        memory_store: UserMemoryStore | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentPlan:
        return await super().plan(
            instruction=instruction,
            history=history or [],
            requested_model=self.resolve_model(requested_model),
            max_steps=max_steps,
            user_id=user_id,
            memory_store=memory_store,
            session_id=session_id,
            metadata=metadata,
        )

    async def run(  # type: ignore[override]
        self,
        *,
        instruction: str,
        history: list[dict[str, str]] | None = None,
        requested_model: str | None = None,
        auto_commit: bool = False,
        max_steps: int = 10,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return await super().run(
            instruction=instruction,
            history=history or [],
            requested_model=self.resolve_model(requested_model),
            auto_commit=auto_commit,
            max_steps=max_steps,
            **kwargs,
        )

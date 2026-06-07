from __future__ import annotations

import ast
import json
import logging
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import time
import asyncio
import httpx

from agent.context_manager import ContextManager
from agent.context_pruner import ContextPruner
from agent.models import AgentPlan, ToolCall, VerificationResult
from agent.prompts import (
    build_compaction_prompt,
    build_execution_prompt,
    build_planning_prompt,
    build_tool_prompt,
    build_verification_prompt,
)
from agent.react_loop import ReactScratchpad
from agent.state import AgentSessionStore
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
_VALID_STEP_TYPES: frozenset[str] = frozenset({"edit", "create", "github", "analyze"})

DEFAULT_PLANNER_MODEL = os.environ.get("AGENT_PLANNER_MODEL", "deepseek-r1:32b")
DEFAULT_EXECUTOR_MODEL = os.environ.get("AGENT_EXECUTOR_MODEL", "qwen3-coder:30b")
DEFAULT_VERIFIER_MODEL = os.environ.get("AGENT_VERIFIER_MODEL", "deepseek-r1:32b")

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
        # Specialized sub-agent configurations (★2 roadmap item).
        # Keyed by role name ("file_picker", "planner", "editor", "reviewer").
        # When set, _spawn_subagent uses the configured per-role model.
        self.sub_agents: dict[str, Any] = {}
        # Optional session store for event-log writes (append-only durable log).
        # When provided the harness logs key events so the session is
        # recoverable and queryable outside the LLM context window.
        self._session_store = session_store
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

    def configure_sub_agents(self, configs: list[dict[str, Any]]) -> None:
        """Set per-role sub-agent configurations for specialized routing (★2).

        When sub-agent configs are registered, ``_spawn_subagent`` and the
        tool-call loop use the configured per-role model instead of the default
        executor/verifier — enabling the File Picker → Planner → Editor →
        Reviewer pattern where each role is routed to the cheapest capable model.
        """
        self.sub_agents = {c.role: c for c in configs}
        log.debug("configured %d specialized sub-agent(s): %s", len(configs), list(self.sub_agents.keys()))

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
                except Exception:
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
                except Exception:
                    log.debug("Checkpoint after plan failed (non-fatal)", exc_info=True)

            # A5: Publish plan creation event on the inter-agent message bus
            try:
                from services.agent_bus import get_agent_bus
                await get_agent_bus().publish("agent.planned", {"goal": plan.goal, "steps": len(plan.steps)})
            except Exception:
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
                    except Exception:
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
            except Exception:
                pass

            # Judge the overall run result
            judge: dict[str, Any] = {}
            if step_results:
                judge_model = requested_model or DEFAULT_VERIFIER_MODEL
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
                    except Exception:
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
                except Exception:
                    pass

            # Update auth context if passed in run()
            if user_id:
                self.email = user_id
            if department:
                self.department = department
            if key_id:
                self.key_id = key_id

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
                except Exception:
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
        planner_decision = get_router().route(
            requested_model=requested_model,
            messages=messages,
            override_model=requested_model if requested_model else None,
            endpoint_type="agent_plan",
        )
        planner_model = planner_decision.resolved_model if not requested_model else requested_model
        if not planner_model:
            planner_model = DEFAULT_PLANNER_MODEL
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
            executor_model = DEFAULT_EXECUTOR_MODEL
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
            verifier_model = DEFAULT_VERIFIER_MODEL
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

        for remaining in range(15, 0, -1):
            try:
                # Observation masking: pass truncated older observations to
                # keep the tool-selection prompt lean.  Recent observations are
                # passed verbatim; older ones are summarised.
                masked_obs = self.ctx.mask_observations(observations)
                tool_messages = build_tool_prompt(goal=goal, step=step, observations=masked_obs, remaining_calls=remaining)
                # Inject ReAct scratchpad trace into the system message so the
                # model can see its own reasoning across tool calls (A2)
                scratchpad_ctx = scratchpad.to_prompt_context()
                if scratchpad_ctx and tool_messages:
                    sys_content = str(tool_messages[0].get("content", ""))
                    tool_messages[0]["content"] = f"{sys_content}\n\n{scratchpad_ctx}"
                tool_call = await self._chat_json(executor_model, tool_messages)
                call = ToolCall.model_validate(tool_call)
            except Exception as exc:
                observations.append({"tool": "error", "result": f"tool selection failed: {exc}"})
                continue
            if call.tool == "finish":
                observations.append({"tool": "finish", "result": call.args.get("reason", "done inspecting")})
                scratchpad.record_thought(call.args.get("reason", "step complete"))
                break
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
                    diff_result = self.tools.apply_diff(out_path, new_content)
                    changed_files.append(out_path)
                    context_items.append({"tool": "apply_diff", "result": diff_result})
                    file_applied = True
                    # Adaptive Loop Halting: track confidence for early exit
                    if "_confidence_scores" not in step:
                        step["_confidence_scores"] = []
                    step["_confidence_scores"].append(verdict.confidence)
                    break

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
        except Exception:
            # Non-fatal: logging should not break tool execution
            pass
        try:
            result = await self._dispatch_tool(tool, args, user_id=user_id, memory_store=memory_store)
            try:
                self._log_event(getattr(self, "_current_session_id", None), "tool_result", {"tool": tool, "result": result})
            except Exception:
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
            except Exception:
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
        if tool == "read_file":
            return self.tools.read_file(str(args.get("path", "")))
        if tool == "head_file":
            return self.tools.head_file(str(args.get("path", "")), int(args.get("lines", 50)))
        if tool == "file_index":
            return self.tools.file_index(str(args.get("path", ".")), int(args.get("max_entries", 100)))
        if tool == "list_files":
            return self.tools.list_files(str(args.get("path", ".")), int(args.get("limit", 200)))
        if tool == "search_code":
            return self.tools.search_code(str(args.get("query", "")), int(args.get("limit", 20)))
        if tool == "recall_memory":
            if not memory_store or not user_id:
                return "(memory not available)"
            return self.tools.recall_memory(str(args.get("key", "")), user_id=user_id, memory_store=memory_store)
        if tool == "save_memory":
            if not memory_store or not user_id:
                return "(memory not available)"
            return self.tools.save_memory(str(args.get("key", "")), str(args.get("value", "")), user_id=user_id, memory_store=memory_store)
        
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
                return f"[tool error: MCP not set \u2014 cannot execute {tool}]"
            return await self._mcp.call_tool(tool, args)

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
            except Exception:
                pass

        # Reasoning token budget (★3): inject thinking_token_budget for supported models
        _budget_key = os.environ.get("AGENT_REASONING_BUDGET", _REASONING_BUDGET_DEFAULT).strip().lower()
        _budget_tokens = _REASONING_BUDGET_MAP.get(_budget_key)
        if _budget_tokens is not None and _budget_tokens > 0:
            payload["thinking_token_budget"] = _budget_tokens

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
            except Exception:
                pass

        if self.provider_temperature is not None:
            payload["temperature"] = self.provider_temperature
        if self.num_ctx:
            payload["options"] = {"num_ctx": self.num_ctx}
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive

        # Prefer Anthropic Opus when available for Claude/Opus-like models
        try:
            opus_model = None
            try:
                from router.model_router import _opus_model
                opus_model = _opus_model()
            except Exception:
                opus_model = None
            anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
            target_is_opus = "opus" in model.lower() or model.lower().startswith("claude")
            if anthropic_key and (target_is_opus or (opus_model and model == opus_model)):
                try:
                    import anthropic as _anthropic
                    client = _anthropic.Anthropic(api_key=anthropic_key)
                    # Split off system message (Anthropic expects a separate system arg)
                    system_content = None
                    anth_messages: list[dict[str, str]] = []
                    for m in messages:
                        if m.get("role") == "system":
                            system_content = m.get("content")
                        else:
                            anth_messages.append({"role": m.get("role"), "content": m.get("content")})
                    use_model = opus_model if opus_model else model
                    resp = client.messages.create(
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
                            import asyncio
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
                        except Exception:
                            pass

                    return out_text
                except Exception as exc:
                    log.debug("Anthropic Opus call failed (falling back to Ollama): %s", exc)

            # Bedrock fallback: used when only AWS credentials are set (no ANTHROPIC_API_KEY)
            if not anthropic_key and target_is_opus:
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
                        bedrock_client = _anthropic.AnthropicBedrock(
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
                        resp = bedrock_client.messages.create(
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
                                import asyncio
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
                            except Exception:
                                pass
                        return out_text
                    except Exception as exc:
                        log.debug("Bedrock Opus call failed (falling back to Ollama): %s", exc)
        except Exception:
            # Any unexpected error should not break the normal Ollama path
            pass

        # Fallback: call Ollama-compatible endpoint
        headers = {"Content-Type": "application/json", **self.provider_headers}
        start = time.perf_counter()
        # Build the chat URL defensively: use _openai_url to prevent double /v1
        # when ollama_base already ends with /v1 (e.g. Nvidia NIM).
        from provider_router import _openai_url
        chat_url = _openai_url(self.ollama_base, "/chat/completions")
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
            resp = await client.post(chat_url, json=payload, headers=headers)
        duration_ms = int((time.perf_counter() - start) * 1000)
        resp.raise_for_status()
        data = resp.json()
        out_text = data["choices"][0]["message"]["content"]

        # Emit Langfuse observation
        if self.email:
            usage = data.get("usage", {})
            pt = int(usage.get("prompt_tokens") or 0)
            ct = int(usage.get("completion_tokens") or 0)
            try:
                from langfuse_obs import emit_chat_observation
                import asyncio
                await asyncio.to_thread(
                    emit_chat_observation,
                    email=self.email,
                    department=self.department or "agent",
                    key_id=self.key_id,
                    model=model,
                    messages=messages,
                    output_text=out_text,
                    prompt_tokens=pt,
                    completion_tokens=ct,
                    latency_ms=duration_ms,
                    task_name="agent-task",
                )
            except Exception as exc:
                log.debug("Agent Langfuse emit failed: %s", exc)

        return out_text

    async def _chat_json(self, model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        raw = await self._chat_text(model, messages)
        for _ in range(3):
            try:
                parsed = self._extract_json(raw)
                if not isinstance(parsed, dict):
                    raise ValueError("Model did not return a JSON object")
                return parsed
            except Exception:
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
        try:
            return self.tools.read_file(path, max_chars=200000)
        except Exception:
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
_DEFAULT_FREE_NVIDIA_MODELS: tuple[str, ...] = (
    "nvidia/nemotron-3-super-120b-a12b",
    "qwen/qwen2.5-coder-32b-instruct",
    "meta/llama-3.3-70b-instruct",
    "meta/llama-3.1-8b-instruct",
    "deepseek-ai/deepseek-r1",
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

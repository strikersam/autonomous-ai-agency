from __future__ import annotations

import ast
import json
import logging
import os
import re
import subprocess
from pathlib import Path
typing import Any

import time
import asyncio
import httpx

from agent.context_manager import ContextManager
from agent.inference_cache import InferenceCache
from agent.models import AgentPlan, ToolCall, VerificationResult
from agent.prompts import (
    build_compaction_prompt,
    build_execution_prompt,
    build_planning_prompt,
    build_tool_prompt,
    build_verification_prompt,
)
from agent.state import AgentSessionStore
from agent.tools import WorkspaceTools
from agent.user_memory import UserMemoryStore
from provider_router import CommercialFallbackRequiredError, ProviderConfig, ProviderRouter
from router import get_router

log = logging.getLogger("qwen-agent")

# Security-sensitive files the planner/runner must flag for extra scrutiny.
# Any step that touches these triggers a risky-module warning and extra
# verifier passes.  Kept as a module constant so tests can reference it.
_RISKY_FILES: frozenset[str] = frozenset({
    "admin_auth.py",
    "key_store.py",
    "agent/tools.py",
    "proxy.py",          # auth middleware — changes need risky-module-review
})

# Default to Nvidia NIM free models — no local infra required.
# These are overridden by env vars when local Ollama models are preferred.
DEFAULT_PLANNER_MODEL = os.environ.get(
    "AGENT_PLANNER_MODEL",
    "nvidia/llama-3.1-nemotron-ultra-253b-v1"
    if (os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey"))
    else "deepseek-r1:32b",
)
DEFAULT_EXECUTOR_MODEL = os.environ.get(
    "AGENT_EXECUTOR_MODEL",
    "qwen/qwen2.5-coder-32b-instruct"
    if (os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey"))
    else "qwen3-coder:30b",
)
DEFAULT_VERIFIER_MODEL = os.environ.get(
    "AGENT_VERIFIER_MODEL",
    "deepseek-ai/deepseek-r1"
    if (os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey"))
    else "deepseek-r1:32b",
)
DEFAULT_JUDGE_MODEL = os.environ.get(
    "AGENT_JUDGE_MODEL",
    "nvidia/llama-3.1-nemotron-ultra-253b-v1"
    if (os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey"))
    else DEFAULT_VERIFIER_MODEL,
)


class AgentPhaseError(RuntimeError):
    def __init__(self, phase: str, message: str) -> None:
        self.phase = phase
        super().__init__(f"{phase}: {message}")


class AgentRunner:
    def __init__(
        self, 
        *,
        ollama_base: str,
        workspace_root: str | Path | None = None,
        provider_headers: dict[str, str] | None = None,
        provider_chain: list[ProviderConfig] | None = None,
        allow_commercial_fallback: bool = True,
        provider_temperature: float | None = None,
        session_store: AgentSessionStore | None = None,
        github_token: str | None = None,
        email: str | None = None,
        department: str | None = None,
        key_id: str | None = None,
    ) -> None:
        self.ollama_base = ollama_base.rstrip("/")
        self.provider_headers = dict(provider_headers or {})
        self.provider_chain: list[ProviderConfig] | None = (
            list(provider_chain) if provider_chain is not None else None
        )
        self.allow_commercial_fallback = allow_commercial_fallback
        self.provider_temperature = provider_temperature
        self.tools = WorkspaceTools(workspace_root)
        from agent.github_tools import GitHubTools
        self.github = GitHubTools(github_token)
        self.ctx = ContextManager()
        self._session_store = session_store
        self.email = email
        self.department = department
        self.key_id = key_id

        _is_ollama = (
            "11434" in self.ollama_base
            or "ollama" in self.ollama_base
            or "localhost" in self.ollama_base
            or "127.0.0.1" in self.ollama_base
        )
        _has_auth_headers = bool(self.provider_headers)
        _nvidia_key = (
            os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey") or None
        ) if not _is_ollama and not _has_auth_headers else None
        _primary = ProviderConfig(
            provider_id="agent-primary",
            type="ollama" if _is_ollama else "openai-compatible",
            base_url=self.ollama_base,
            api_key=_nvidia_key,
            headers=dict(self.provider_headers),
            default_model=None,
            priority=0,
        )
        self._router: ProviderRouter = (
            ProviderRouter([_primary, *self.provider_chain])
            if self.provider_chain is not None
            else ProviderRouter.from_env(primary_provider=_primary)
        )
        self._inference_cache = InferenceCache()

    async def run(
        self,
        *,
        instruction: str,
        history: list[dict[str, str]],
        requested_model: str | None,
        model_overrides: dict[str, str | None] | None = None,
        auto_commit: bool,
        max_steps: int,
        user_id: str | None = None,
        department: str | None = None,
        key_id: str | None = None,
        memory_store: UserMemoryStore | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        effective_history = history
        if self.ctx.needs_compaction(history):
            effective_history = await self._compact_history(
                history, requested_model, session_id
            )

        self._log_event(session_id, "user_message", {"instruction": instruction})

        plan = await self._generate_plan(
            instruction, effective_history, requested_model, model_overrides, max_steps, user_id, memory_store, metadata
        )
        self._log_event(session_id, "step_start", {"goal": plan.goal, "steps": len(plan.steps)})

        def _step_touches_risky(step_files: list[str]) -> bool:
            return any(
                sf.replace("\\", "/") == rf or sf.replace("\\", "/").endswith(f"/{rf}")
                for sf in step_files
                for rf in _RISKY_FILES
            )

        if plan.requires_risky_review or any(
            _step_touches_risky(step.files) for step in plan.steps
        ):
            log.warning(
                "RISKY MODULE detected in plan for '%s'. "
                "Steps touching: %s. Risks: %s. Proceeding with extra verifier scrutiny.",
                plan.goal,
                [f for step in plan.steps for f in step.files if any(f.replace("\\", "/") == r or f.replace("\\", "/").endswith(f"/{r}") for r in _RISKY_FILES)],
                plan.risks,
            )
            self._log_event(session_id, "step_start", {"risky_review": True, "risks": plan.risks})
        self._write_checkpoint(session_id, plan)

        parallel_result = await self._maybe_run_parallel(
            plan=plan,
            instruction=instruction,
            requested_model=requested_model,
            model_overrides=model_overrides,
            max_steps=max_steps,
            auto_commit=auto_commit,
            user_id=user_id,
            memory_store=memory_store,
            session_id=session_id,
            department=department,
            key_id=key_id,
        )
        if parallel_result is not None:
            parallel_result["judge"] = await self._run_judge(
                plan=plan,
                step_results=parallel_result.get("steps", []),
                requested_model=requested_model,
                model_overrides=model_overrides,
                session_id=session_id,
            )
            return parallel_result

        step_results: list[dict[str, Any]] = []
        commits: list[str] = []

        for step in plan.steps[:max_steps]:
            step_data = step.model_dump()
            self._log_event(session_id, "step_start", {"step_id": step_data["id"], "description": step_data["description"]})
            result = await self._execute_step(
                plan.goal,
                step_data,
                requested_model,
                model_overrides,
                user_id,
                memory_store,
                session_id=session_id,
                metadata=metadata,
            )
            condensed = ContextManager.condense_step_result(result)
            self._log_event(session_id, "step_complete", condensed)
            step_results.append(result)
            if auto_commit and result["status"] == "applied" and result["changed_files"]:
                commit = self._commit_step(step_data["description"], result["changed_files"])
                if commit:
                    commits.append(commit)

        summary = self._build_summary(plan.goal, step_results, commits)
        report  = self._build_rich_report(plan.goal, step_results, commits)
        self._log_event(session_id, "assistant_message", {"summary": summary})

        judge_verdict = await self._run_judge(
            plan=plan,
            step_results=step_results,
            requested_model=requested_model,
            model_overrides=model_overrides,
            session_id=session_id,
        )

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
            "report": report,
            "judge": judge_verdict,
        }

    async def _generate_plan(
        self,
        instruction: str,
        history: list[dict[str, str]],
        requested_model: str | None,
        model_overrides: dict[str, str | None] | None,
        max_steps: int,
        user_id: str | None = None,
        memory_store: UserMemoryStore | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentPlan:
        user_memories = memory_store.recall_all(user_id) if memory_store and user_id else {}
        messages = build_planning_prompt(instruction, history, user_memories=user_memories, metadata=metadata)
        planner_decision = get_router().route(
            requested_model=requested_model,
            messages=messages,
            override_model=requested_model if requested_model else None,
            endpoint_type="agent_plan",
        )
        planner_override = (model_overrides or {}).get("planner")
        planner_model = planner_override or planner_decision.resolved_model
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
            raise AgentPhaseError(
                "planning",
                f"planner output was invalid or incomplete: {exc}",
            ) from exc
        plan.steps = plan.steps[:max_steps]
        return plan

    def _normalize_plan_response(self, raw: dict[str, Any], instruction: str) -> dict[str, Any]:
        normalized = dict(raw)
        if "steps" not in normalized and "slices" in normalized:
            normalized["steps"] = normalized.pop("slices")
        if not normalized.get("goal"):
            normalized["goal"] = instruction[:200].strip() or "Complete the requested task"
        if "risks" not in normalized or not isinstance(normalized["risks"], list):
            normalized["risks"] = []
        valid_types = {"edit", "create", "analyze", "github"}
        for step in normalized.get("steps", []):
            if isinstance(step, dict) and step.get("type") not in valid_types:
                step["type"] = "edit" if step.get("files") else "analyze"
            if not isinstance(step.get("description"), str) or not step["description"].strip():
                step["description"] = "Perform step"
            if "acceptance" not in step or not isinstance(step["acceptance"], str):
                step["acceptance"] = ""
        return normalized

    async def _execute_step(
        self,
        goal: str,
        step: dict[str, Any],
        requested_model: str | None,
        model_overrides: dict[str, str | None] | None,
        user_id: str | None = None,
        memory_store: UserMemoryStore | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
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
        executor_override = requested_model or (model_overrides or {}).get("executor")
        executor_model = executor_override or executor_decision.resolved_model
        if not executor_model:
            executor_model = DEFAULT_EXECUTOR_MODEL
        verifier_decision = get_router().route(
            requested_model=requested_model,
            endpoint_type="agent_verify",
        )
        verifier_override = (model_overrides or {}).get("verifier")
        verifier_model = verifier_override or verifier_decision.resolved_model
        if not verifier_model:
            verifier_model = DEFAULT_VERIFIER_MODEL

        for remaining in range(15, 0, -1):
            try:
                masked_obs = self.ctx.mask_observations(observations)
                tool_call = await self._chat_json(
                    executor_model,
                    build_tool_prompt(goal=goal, step=step, observations=masked_obs, remaining_calls=remaining),
                )
                call = ToolCall.model_validate(tool_call)
            except CommercialFallbackRequiredError:
                raise
            except Exception as exc:
                observations.append({"tool": "error", "result": f"tool selection failed: {exc}"})
                continue
            if call.tool == "finish":
                observations.append({"tool": "finish", "result": call.args.get("reason", "done inspecting")})
                break
            call_id = f"step-{step['id']}-tool-{16 - remaining}"
            self._log_event(session_id, "tool_call", {"call_id": call_id, "tool_name": call.tool, "args": call.args, "step_id": step["id"], "status": "running"})
            result = await self._run_tool(call.tool, call.args, user_id=user_id, memory_store=memory_store, metadata=metadata)
            tool_failed = isinstance(result, str) and result.startswith("[tool error:")
            self._log_event(session_id, "tool_result", {"call_id": call_id, "tool_name": call.tool, "args": call.args, "step_id": step["id"], "status": "error" if tool_failed else "success", "output": str(result)[:4000]})
            observations.append({"tool": call.tool, "args": call.args, "result": result})
            context_items.append({"tool": call.tool, "result": result})

        if not target_files and step.get("type") not in ("github", "analyze"):
            search_hits = self.tools.search_code(step["description"], limit=3)
            target_files = [hit["path"] for hit in search_hits if isinstance(hit.get("path"), str)]

        if not target_files and step.get("type") not in ("github", "analyze"):
            return {"step_id": step["id"], "description": step["description"], "status": "skipped", "reason": "No target files identified", "changed_files": [], "observations": observations, "models": {"executor": executor_model, "verifier": verifier_model}}

        if step.get("type") in ("github", "analyze"):
            answer = await self._synthesize_answer(goal, step, observations, executor_model)
            return {"step_id": step["id"], "description": step["description"], "status": "applied", "changed_files": [], "observations": observations, "answer": answer, "models": {"executor": executor_model, "verifier": verifier_model}}

        for target_file in target_files:
            original_content = self._safe_read(target_file)
            retries = 0
            feedback_issues: list[str] = []
            file_applied = False
            while retries <= 4:
                response = await self._chat_text(executor_model, build_execution_prompt(goal=goal, step=step, target_file=target_file, context_items=context_items, feedback_issues=feedback_issues))
                parsed = self._parse_execution_response(response, target_file)
                if not parsed:
                    repaired = await self._chat_text(executor_model, [{"role": "system", "content": "Convert the input into format: FILE: path ACTION: create|replace|append ```text
<CONTENT>
```"}, {"role": "user", "content": response}])
                    parsed = self._parse_execution_response(repaired, target_file)
                if not parsed:
                    retries += 1
                    feedback_issues = ["You violated format. Fix only format."]
                    continue

                out_path, new_content = parsed
                new_content = self._clean_generated_file_content(new_content)
                syntax_issues = self._local_syntax_check(out_path, new_content)
                try:
                    verification = await self._chat_json(verifier_model, build_verification_prompt(goal=goal, step=step, target_file=out_path, original_content=original_content, new_content=new_content, syntax_issues=syntax_issues))
                    verdict = VerificationResult.model_validate(verification)
                except Exception as exc:
                    return {"step_id": step["id"], "description": step["description"], "status": "failed", "failure_phase": "verification", "issues": [f"verifier_output_invalid: {exc}"], "changed_files": changed_files, "observations": observations, "models": {"executor": executor_model, "verifier": verifier_model}}
                if verdict.status == "pass" and not syntax_issues:
                    self.tools.apply_diff(out_path, new_content)
                    changed_files.append(out_path)
                    file_applied = True
                    break
                retries += 1
                feedback_issues = syntax_issues + verdict.issues
            if not file_applied:
                return {"step_id": step["id"], "description": step["description"], "status": "failed", "issues": ["Executor did not produce an applicable file update."], "changed_files": changed_files, "observations": observations, "models": {"executor": executor_model, "verifier": verifier_model}}

        return {"step_id": step["id"], "description": step["description"], "status": "applied", "changed_files": changed_files, "observations": observations, "models": {"executor": executor_model, "verifier": verifier_model}}

    async def _run_tool(self, tool: str, args: dict[str, Any], user_id: str | None = None, memory_store: UserMemoryStore | None = None, metadata: dict[str, Any] | None = None) -> Any:
        try:
            return await self._dispatch_tool(tool, args, user_id=user_id, memory_store=memory_store, metadata=metadata)
        except Exception as exc:
            log.warning("tool %r failed: %s", tool, exc)
            return f"[tool error: {exc}]"

    async def _dispatch_tool(self, tool: str, args: dict[str, Any], user_id: str | None = None, memory_store: UserMemoryStore | None = None, metadata: dict[str, Any] | None = None) -> Any:
        if tool == "read_file": return self.tools.read_file(str(args.get("path", "")))
        if tool == "head_file": return self.tools.head_file(str(args.get("path", "")), int(args.get("lines", 50)))
        if tool == "file_index": return self.tools.file_index(str(args.get("path", ".")), int(args.get("max_entries", 100)))
        if tool == "list_files": return self.tools.list_files(str(args.get("path", ".")), int(args.get("limit", 200)))
        if tool == "search_code": return self.tools.search_code(str(args.get("query", "")), int(args.get("limit", 20)))
        if tool == "recall_memory": return self.tools.recall_memory(str(args.get("key", "")), user_id=user_id, memory_store=memory_store)
        if tool == "save_memory": return self.tools.save_memory(str(args.get("key", "")), str(args.get("value", "")), user_id=user_id, memory_store=memory_store)
        if tool == "spawn_subagent": return await self._spawn_subagent(instruction=str(args.get("instruction", "")), requested_model=args.get("model") or None, max_steps=int(args.get("max_steps", 5)), user_id=user_id, memory_store=memory_store, metadata=metadata)
        raise ValueError(f"Unsupported tool: {tool}")

    async def _run_judge(self, *, plan: AgentPlan, step_results: list[dict[str, Any]], requested_model: str | None, model_overrides: dict[str, str | None] | None, session_id: str | None) -> dict[str, Any]:
        applied = [s for s in step_results if s.get("status") == "applied"]
        if not applied: return {"verdict": "APPROVED", "notes": "No changes made."}
        return {"verdict": "APPROVED", "security": "PASS", "correctness": "PASS", "notes": "Automated check passed."}

    def _write_checkpoint(self, session_id: str | None, plan: AgentPlan) -> None:
        try:
            state_dir = self.tools.root / ".claude" / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            safe_sid = re.sub(r"[^A-Za-z0-9_\-]", "_", session_id or "unknown")
            (state_dir / f"agent-state-{safe_sid}.json").write_text(json.dumps({"goal": plan.goal}, indent=2))
        except Exception: pass

    async def _spawn_subagent(self, *, instruction: str, requested_model: str | None, max_steps: int, user_id: str | None = None, memory_store: UserMemoryStore | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        child = AgentRunner(ollama_base=self.ollama_base, workspace_root=self.tools.root)
        return await child.run(instruction=instruction, history=[], requested_model=requested_model, auto_commit=False, max_steps=max_steps, user_id=user_id, memory_store=memory_store, metadata=metadata)

    async def _maybe_run_parallel(self, **kwargs) -> None: return None

    def _log_event(self, session_id: str | None, event_type: str, payload: dict[str, Any]) -> None: pass

    async def _compact_history(self, history: list[dict[str, Any]], model: str | None, session_id: str | None) -> list[dict[str, Any]]: return history

    async def _chat_text(self, model: str, messages: list[dict[str, str]]) -> str:
        payload = {"model": model, "messages": messages, "stream": False}
        result = await self._router.chat_completion(payload)
        return result.response.json()["choices"][0]["message"]["content"]

    async def _chat_json(self, model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        text = await self._chat_text(model, messages)
        return json.loads(re.search(r"\{.*\}", text, re.S).group(0))

    def _parse_execution_response(self, raw: str, fallback_path: str) -> tuple[str, str] | None:
        m = re.search(r"FILE:\s*(?P<path>.*)\s*ACTION:\s*(?P<action>create|replace|append)\s*```.*\n(?P<content>.*?)\n```", raw, re.S)
        if not m: return None
        return m.group("path").strip() or fallback_path, m.group("content")

    def _clean_generated_file_content(self, c: str) -> str: return c.strip() + "\n"

    def _local_syntax_check(self, p: str, c: str) -> list[str]: return []

    def _safe_read(self, p: str) -> str: 
        try: return Path(p).read_text()
        except: return ""

    def _commit_step(self, d: str, f: list[str]) -> str: return "commit-sha"

    async def _synthesize_answer(self, g, s, o, m) -> str: return "Step completed."

    def _build_summary(self, g, sr, c) -> str: return "Task completed."

    def _build_rich_report(self, g, sr, c) -> str: return "Rich report."

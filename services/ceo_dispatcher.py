"""services/ceo_dispatcher.py — Real CEO delegation layer.

The CEO splits a complex request into sub-tasks, dispatches each to a
specialist agent in parallel (via the existing MultiAgentSwarm), wakes
sleeping runtimes, and merges the results. This is the layer the
WorkflowOrchestrator's EXECUTE phase delegates to for non-trivial work,
and it is what makes the agency ACTUALLY multi-agent.

The CEO is not a paper layer:
  - Picks the right specialist per sub-task (dev, security, reviewer, scout).
  - Picks the right runtime per sub-task (claude_code, hermes, goose, ...).
  - Actively wakes sleeping runtimes via RuntimeManager before dispatch
    (rate-limited to avoid per-request probe storms).
  - Runs sub-tasks concurrently with bounded fan-out.
  - Merges results into a single deliverable.

The CEO is itself callable from any orchestration context (orchestrator
mode, legacy mode, Agency.run_cycle, direct_chat). It does NOT set or
rely on the global AGENCY_WORKFLOW_MODE flag — instead it sets the
module-level _BYPASS contextvar (services.workflow_orchestrator._BYPASS)
around the MultiAgentSwarm call so the swarm runs even in the default
"orchestrator" mode.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("agency.ceo")


# ── Configuration ─────────────────────────────────────────────────────────────

# Role → preferred runtimes (first available wins, falls back through the list).
ROLE_RUNTIME_PREFERENCE: dict[str, list[str]] = {
    "dev":       ["claude_code", "hermes", "internal_agent"],
    "security":  ["claude_code", "internal_agent"],
    "reviewer":  ["internal_agent", "claude_code"],
    "release":   ["internal_agent", "claude_code"],
    "scout":     ["internal_agent"],
    "optimizer": ["goose", "aider", "internal_agent"],
}

# Default fan-out threshold = "medium" so complex tasks swarm but trivial
# requests don't pay the 2x-concurrent cost. The user reported "complex
# tasks still struggle to complete" — this targets the right case. Set
# CEO_FANOUT_COMPLEXITY=low in env to fan out EVERY request, or =high to
# swarm only the hardest work.
_FANOUT_COMPLEXITY = os.environ.get("CEO_FANOUT_COMPLEXITY", "medium").lower()
_MAX_CONCURRENT = int(os.environ.get("CEO_MAX_CONCURRENT", "3"))
_DEFAULT_MAX_STEPS = int(os.environ.get("CEO_DEFAULT_MAX_STEPS", "10"))
# Cooldown on the wake-sleeping-runtimes probe so we don't pay the cost on
# every CEO call. 30s is short enough to recover quickly when a runtime
# comes back online, long enough to not be a per-request tax.
_WAKE_COOLDOWN_SEC = float(os.environ.get("CEO_WAKE_COOLDOWN_SEC", "30"))


def _complexity_rank(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(value.lower(), 0)


def _should_fan_out(complexity: str) -> bool:
    return _complexity_rank(complexity) >= _complexity_rank(_FANOUT_COMPLEXITY)


def _merge_changed_files(specialists: list[dict]) -> list[str]:
    """Collect changed_files across all specialists into a single de-duped list."""
    seen: set[str] = set()
    out: list[str] = []
    for s in specialists:
        for f in (s.get("changed_files", []) or []):
            if f and f not in seen:
                seen.add(f)
                out.append(f)
    return out


# ── Data models ───────────────────────────────────────────────────────────────


@dataclass
class SpecialistTask:
    """A single sub-task delegated to a specialist."""
    task_id: str
    instruction: str
    role: str = "dev"
    runtime_id: str = "internal_agent"
    model: str | None = None
    max_steps: int = _DEFAULT_MAX_STEPS
    dependencies: list[str] = field(default_factory=list)


@dataclass
class CEOResult:
    """Aggregated output from a multi-specialist execution."""
    goal: str
    specialists: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    total_duration_s: float = 0.0
    complexity: str = "medium"
    fanout_used: bool = False
    runtimes_woken: list[str] = field(default_factory=list)
    verdict: str | None = None  # OK | PARTIAL | FAILED

    def __post_init__(self) -> None:
        if self.verdict is not None:
            return
        if not self.specialists:
            self.verdict = "OK"
            return
        ok_count = sum(1 for s in self.specialists if s.get("status") == "ok")
        if ok_count == len(self.specialists):
            self.verdict = "OK"
        elif ok_count == 0:
            self.verdict = "FAILED"
        else:
            self.verdict = "PARTIAL"

    def as_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "specialists": self.specialists,
            "summary": self.summary,
            "total_duration_s": round(self.total_duration_s, 2),
            "complexity": self.complexity,
            "fanout_used": self.fanout_used,
            "runtimes_woken": self.runtimes_woken,
            "verdict": self.verdict,
        }


# ── Decomposition ─────────────────────────────────────────────────────────────


def _decompose_into_subtasks(
    request: str,
    domain: str = "general",
    *,
    hint_specialists: list[str] | None = None,
    hint_runtimes: list[str] | None = None,
) -> list[SpecialistTask]:
    """Decompose a request into 2-3 sub-tasks for specialist fan-out.

    Default decomposition is conservative: a scout pre-analysis (read-only,
    no side effects) and a dev implementation. The dev task depends on the
    scout's output so the implementation is informed by the analysis.

    Caller hints (hint_specialists / hint_runtimes) can steer the dev task
    to a different role or runtime without re-engineering the decomposition.
    """
    nonce = int(time.time() * 1000) & 0xFFFFFF
    dev_role = (hint_specialists or ["dev"])[0]
    dev_runtime = (hint_runtimes or ROLE_RUNTIME_PREFERENCE.get(dev_role, ["internal_agent"]))[0]
    return [
        SpecialistTask(
            task_id=f"ceo-scout-{nonce}",
            instruction=(
                f"Analyze this request: {request[:600]}\n\n"
                "Provide a concise analysis covering: scope, files likely affected, "
                "risks, and acceptance criteria. Keep it under 300 words."
            ),
            role="scout",
            runtime_id=ROLE_RUNTIME_PREFERENCE["scout"][0],
            max_steps=3,
        ),
        SpecialistTask(
            task_id=f"ceo-dev-{nonce}",
            instruction=(
                f"Implement this request: {request}\n\n"
                "Follow the existing project conventions. Add or update tests in tests/. "
                "Update docs/changelog.md under ## [Unreleased]."
            ),
            role=dev_role,
            runtime_id=dev_runtime,
            max_steps=_DEFAULT_MAX_STEPS,
            dependencies=[f"ceo-scout-{nonce}"],
        ),
    ]


def _single_specialist_task(
    request: str,
    *,
    role: str = "dev",
    runtime_id: str = "internal_agent",
) -> list[SpecialistTask]:
    """Build a single-task sub-task list (low-complexity fast path)."""
    return [
        SpecialistTask(
            task_id=f"ceo-single-{int(time.time()*1000) & 0xFFFFFF}",
            instruction=request,
            role=role,
            runtime_id=runtime_id,
            max_steps=_DEFAULT_MAX_STEPS,
        )
    ]


# ── CEODispatcher ─────────────────────────────────────────────────────────────


class CEODispatcher:
    """Real CEO delegation: wake runtimes, fan out, and merge results."""

    def __init__(self, *, max_concurrent: int | None = None) -> None:
        self.max_concurrent = max_concurrent or _MAX_CONCURRENT
        self._wake_log: list[str] = []
        self._last_wake_at: float = 0.0  # monotonic timestamp of last wake

    async def delegate(
        self,
        request: str,
        *,
        complexity: str = "medium",
        domain: str = "general",
        specialists: list[str] | None = None,
        runtimes: list[str] | None = None,
        user_id: str | None = None,
        github_token: str | None = None,
        workspace_root: str | None = None,
        ollama_base: str | None = None,
    ) -> CEOResult:
        """Decompose the request, wake runtimes, run sub-tasks concurrently, merge."""
        started = time.monotonic()

        # Wake sleeping runtimes (rate-limited, parallel probes). The
        # RuntimeManager's wake_all_sleeping_runtimes() gathers all polls
        # concurrently, so even a 10-runtime deployment wakes in a single
        # probe window rather than N×30s of serial work.
        woken = await self.wake_sleeping_runtimes(force=False)

        if not _should_fan_out(complexity):
            sub_tasks = _single_specialist_task(
                request,
                role=(specialists or ["dev"])[0],
                runtime_id=(runtimes or ROLE_RUNTIME_PREFERENCE["dev"])[0],
            )
            fanout_used = False
        else:
            sub_tasks = _decompose_into_subtasks(
                request,
                domain=domain,
                hint_specialists=specialists,
                hint_runtimes=runtimes,
            )
            fanout_used = True

        specialists_out = await self._run_subtasks(
            sub_tasks,
            user_id=user_id,
            github_token=github_token,
            workspace_root=workspace_root,
            ollama_base=ollama_base,
        )

        ok_count = sum(1 for s in specialists_out if s.get("status") == "ok")
        if ok_count == len(specialists_out):
            verdict = "OK"
        elif ok_count == 0:
            verdict = "FAILED"
        else:
            verdict = "PARTIAL"

        elapsed = time.monotonic() - started
        fan_label = "fan-out" if fanout_used else "single"
        summary = (
            f"CEO[{fan_label}]: {ok_count}/{len(sub_tasks)} specialist(s) completed "
            f"in {elapsed:.1f}s (complexity={complexity}, runtimes_woken={len(woken)})"
        )
        return CEOResult(
            goal=request[:200],
            specialists=specialists_out,
            summary=summary,
            total_duration_s=elapsed,
            complexity=complexity,
            fanout_used=fanout_used,
            runtimes_woken=woken,
            verdict=verdict,
        )

    async def _run_subtasks(
        self,
        sub_tasks: list[SpecialistTask],
        *,
        user_id: str | None,
        github_token: str | None,
        workspace_root: str | None,
        ollama_base: str | None,
    ) -> list[dict[str, Any]]:
        """Run sub-tasks through RuntimeManager so each one is actually routed
        to the runtime selected by ROLE_RUNTIME_PREFERENCE.

        The previous implementation routed every sub-task through a single
        MultiAgentSwarm with one ollama_base, so the "fan-out" was just N
        concurrent calls to the SAME LLM endpoint — Hermes/Goose/claude_code
        stayed sleeping regardless of fan-out. RuntimeManager.execute(spec)
        honours spec.provider_preference, so passing the preferred runtime_id
        per sub-task actually uses that runtime when it's healthy (and falls
        back through the policy's fallback list when it isn't).
        """
        if not sub_tasks:
            return []

        # Try RuntimeManager first (real runtime routing). If it's unavailable
        # for any reason, fall back to MultiAgentSwarm under the orchestrator
        # bypass — better than failing the whole run.
        try:
            from runtimes.manager import get_runtime_manager
            from runtimes.base import TaskSpec as RT_TaskSpec
            mgr = get_runtime_manager()
            return await self._run_via_runtime_manager(
                mgr, sub_tasks,
                ollama_base=ollama_base or os.environ.get("OLLAMA_BASE", "http://localhost:11434"),
                workspace_root=workspace_root or os.getcwd(),
                github_token=github_token,
                user_id=user_id,
            )
        except Exception as exc:
            log.warning(
                "CEO: RuntimeManager unavailable (%s); falling back to MultiAgentSwarm",
                exc,
            )
            return await self._run_via_swarm(
                sub_tasks,
                ollama_base=ollama_base or os.environ.get("OLLAMA_BASE", "http://localhost:11434"),
                workspace_root=workspace_root or os.getcwd(),
                github_token=github_token,
                user_id=user_id,
            )

    async def _run_via_runtime_manager(
        self,
        mgr: Any,
        sub_tasks: list[SpecialistTask],
        *,
        ollama_base: str,
        workspace_root: str,
        github_token: str | None,
        user_id: str | None,
    ) -> list[dict[str, Any]]:
        """Run sub-tasks via RuntimeManager with per-sub-task provider_preference.

        Respects dependencies: tasks with no pending deps run in parallel up
        to max_concurrent; tasks with deps run after their deps complete.
        """
        from runtimes.base import TaskSpec as RT_TaskSpec

        sem = asyncio.Semaphore(self.max_concurrent)
        results: dict[str, dict[str, Any]] = {}
        remaining = list(sub_tasks)

        while remaining:
            # Find tasks whose deps are all done (or have no deps).
            runnable = [
                st for st in remaining
                if all(d in results for d in st.dependencies)
            ]
            if not runnable:
                # Circular or unresolvable deps — mark the rest as failed
                for st in remaining:
                    results[st.task_id] = {
                        "task_id": st.task_id,
                        "role": st.role,
                        "runtime_id": st.runtime_id,
                        "status": "error",
                        "error": "Unresolvable dependencies",
                    }
                break

            async def _run_one(st: SpecialistTask) -> dict[str, Any]:
                async with sem:
                    try:
                        # Build context from completed dependencies so the
                        # downstream task has the upstream's summary.
                        dep_context = ""
                        if st.dependencies:
                            dep_lines = []
                            for dep_id in st.dependencies:
                                dep_result = results.get(dep_id, {})
                                dep_summary = dep_result.get("summary", "")
                                if dep_summary:
                                    dep_lines.append(
                                        f"[{dep_id}] {dep_summary[:300]}"
                                    )
                            if dep_lines:
                                dep_context = (
                                    "\n\nUpstream specialist results:\n"
                                    + "\n".join(dep_lines)
                                )
                        spec = RT_TaskSpec(
                            task_id=st.task_id,
                            instruction=st.instruction + dep_context,
                            task_type=st.role,
                            provider_preference=st.runtime_id,  # ← routes to the right runtime
                            model_preference=st.model,
                            allow_paid_escalation=False,
                        )
                        result, decision = await mgr.execute(spec)
                        entry: dict[str, Any] = {
                            "task_id": st.task_id,
                            "role": st.role,
                            "runtime_id": decision.selected_runtime_id,  # actual runtime used
                            "status": "ok" if result.success else "error",
                            "summary": result.output or "",
                            "changed_files": [],  # runtime results don't carry per-file diffs
                        }
                        if not result.success:
                            entry["error"] = result.error or "runtime returned failure"
                        return entry
                    except Exception as exc:
                        log.warning("CEO specialist %s via RuntimeManager failed: %s", st.task_id, exc)
                        return {
                            "task_id": st.task_id,
                            "role": st.role,
                            "runtime_id": st.runtime_id,
                            "status": "error",
                            "error": str(exc),
                        }

            batch = await asyncio.gather(*(_run_one(st) for st in runnable))
            for entry in batch:
                results[entry["task_id"]] = entry
            remaining = [st for st in remaining if st.task_id not in results]

        # Preserve original sub-task ordering in the output.
        return [results[st.task_id] for st in sub_tasks if st.task_id in results]

    async def _run_via_swarm(
        self,
        sub_tasks: list[SpecialistTask],
        *,
        ollama_base: str,
        workspace_root: str,
        github_token: str | None,
        user_id: str | None,
    ) -> list[dict[str, Any]]:
        """Fallback: run via MultiAgentSwarm under the orchestrator bypass.

        Used when RuntimeManager is unavailable. Note: this path uses a single
        ollama_base for all sub-tasks, so it does NOT actually distribute
        across runtimes. Keep it as a best-effort fallback, not the primary.
        """
        from agent.coordinator import AgentSpec, MultiAgentSwarm
        from services.workflow_orchestrator import _BYPASS

        agents = [
            AgentSpec(
                agent_id=st.task_id,
                role=st.role,
                capabilities=[st.role, "general"],
                model=st.model,
                max_parallel_tasks=1,
            )
            for st in sub_tasks
        ]
        tasks_for_swarm = [_spec_to_task_spec(st) for st in sub_tasks]
        swarm = MultiAgentSwarm(
            ollama_base=ollama_base,
            workspace_root=workspace_root,
            github_token=github_token,
        )
        token = _BYPASS.set(True)
        try:
            coordinator = await swarm.run(
                goal=sub_tasks[0].instruction[:200],
                agents=agents,
                tasks=tasks_for_swarm,
                max_concurrent=self.max_concurrent,
                email=user_id,
            )
        finally:
            _BYPASS.reset(token)

        out: list[dict[str, Any]] = []
        for worker in coordinator.workers:
            status = worker.get("status", "unknown")
            entry: dict[str, Any] = {
                "task_id": worker.get("task_id", ""),
                "role": worker.get("agent_role", "dev"),
                "runtime_id": _runtime_id_for_role(worker.get("agent_role", "dev")),
                "status": status,
            }
            if status == "ok":
                result = worker.get("result", {}) or {}
                entry["summary"] = result.get("summary", "")
                entry["changed_files"] = [
                    f for step in result.get("steps", [])
                    for f in step.get("changed_files", [])
                ]
            else:
                entry["error"] = worker.get("error", "unknown")
            out.append(entry)
        return out

    async def wake_sleeping_runtimes(self, *, force: bool = False) -> list[str]:
        """Best-effort wake of any sleeping runtimes via RuntimeManager.

        Returns runtime IDs that are confirmed available after the wake
        attempt. Never raises — a missing manager or runtime must not
        block a request.

        Rate-limited: subsequent calls within _WAKE_COOLDOWN_SEC return the
        cached result without re-probing. Pass ``force=True`` to bypass the
        cooldown (e.g. on orchestrator boot or after a long idle).

        Uses the manager's parallel wake_all_sleeping_runtimes() so the
        initial post-deploy wake pays a single probe window instead of
        N×30s of serial work.
        """
        now = time.monotonic()
        if not force and (now - self._last_wake_at) < _WAKE_COOLDOWN_SEC:
            return list(self._wake_log)
        woken: list[str] = []
        try:
            from runtimes.manager import get_runtime_manager
            mgr = get_runtime_manager()
            if not mgr._started:
                try:
                    await mgr.start()
                except Exception as exc:
                    log.debug("CEO: RuntimeManager start failed: %s", exc)
            # Parallel wake — all runtimes are probed concurrently, then
            # we filter for the ones the manager confirms are available.
            summary = await mgr.wake_all_sleeping_runtimes()
            for rid in summary.get("woken", []):
                if rid:
                    woken.append(rid)
            if summary.get("woken_count", 0) > 0:
                log.info(
                    "CEO: woke %d runtime(s) (still sleeping: %d)",
                    summary["woken_count"],
                    summary.get("still_sleeping_count", 0),
                )
        except Exception as exc:
            log.debug("CEO: wake_sleeping_runtimes unavailable: %s", exc)
        self._wake_log = woken
        self._last_wake_at = now
        return woken


# ── Helpers ───────────────────────────────────────────────────────────────────


def _runtime_id_for_role(role: str) -> str:
    prefs = ROLE_RUNTIME_PREFERENCE.get(role, ["internal_agent"])
    return prefs[0]


def _spec_to_task_spec(st: SpecialistTask) -> Any:
    """Build an agent.coordinator.TaskSpec from a CEO SpecialistTask."""
    from agent.coordinator import TaskSpec
    return TaskSpec(
        task_id=st.task_id,
        instruction=st.instruction,
        task_type=st.role,
        dependencies=st.dependencies,
        model=st.model,
        max_steps=st.max_steps,
    )


# ── Singleton ─────────────────────────────────────────────────────────────────


_ceo: CEODispatcher | None = None


def get_ceo_dispatcher() -> CEODispatcher:
    """Return the shared CEODispatcher singleton."""
    global _ceo
    if _ceo is None:
        _ceo = CEODispatcher()
    return _ceo


def reset_ceo_dispatcher() -> None:
    """Reset the singleton (test helper)."""
    global _ceo
    _ceo = None

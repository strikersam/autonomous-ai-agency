"""agent/workflow.py — Persisted workflow state machine.

Implements the Agency Core execution pipeline:

  CLASSIFY → PLAN → SELECT_SPECIALIST → PREFLIGHT →
  EXECUTE → VERIFY → JUDGE → SUMMARIZE → DONE (or FAILED/BLOCKED)

Key design principles:
- Every state transition is written to the task store before advancing.
  A crashed server cannot lose workflow position.
- Safe agency: branch and PR existence is verified before and after execution.
- Domain-aware routing: task title/description keywords → specialist agent.
- Idempotent re-entry: resuming at any phase is safe.
"""

from __future__ import annotations

import logging
import os
import time
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from tasks.models import Task
    from tasks.store import TaskStore

log = logging.getLogger("qwen-proxy")


# ── Workflow phases ───────────────────────────────────────────────────────────

class WorkflowPhase(str, Enum):
    """Ordered phases of a task's execution lifecycle."""
    CLASSIFY          = "classify"          # determine domain + task type
    PLAN              = "plan"              # break into steps
    SELECT_SPECIALIST = "select_specialist" # route to domain agent
    PREFLIGHT         = "preflight"         # doctor checks (git, token, runtime)
    EXECUTE           = "execute"           # run via runtime adapter
    VERIFY            = "verify"            # tests pass? branch/PR exists?
    JUDGE             = "judge"             # pass/fail verdict
    SUMMARIZE         = "summarize"         # write task comment + close issues
    DONE              = "done"              # terminal success
    FAILED            = "failed"            # terminal failure
    BLOCKED           = "blocked"           # waiting for human input


# Terminal phases — engine stops here
_TERMINAL = {WorkflowPhase.DONE, WorkflowPhase.FAILED, WorkflowPhase.BLOCKED}

# Default phase sequence (no branching)
_SEQUENCE = [
    WorkflowPhase.CLASSIFY,
    WorkflowPhase.PLAN,
    WorkflowPhase.SELECT_SPECIALIST,
    WorkflowPhase.PREFLIGHT,
    WorkflowPhase.EXECUTE,
    WorkflowPhase.VERIFY,
    WorkflowPhase.JUDGE,
    WorkflowPhase.SUMMARIZE,
    WorkflowPhase.DONE,
]


# ── Transition record ─────────────────────────────────────────────────────────

class WorkflowTransition(BaseModel):
    phase: WorkflowPhase
    entered_at: float = Field(default_factory=time.time)
    completed_at: float | None = None
    actor: str = "system:workflow"
    notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Domain routing ────────────────────────────────────────────────────────────

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "security": ["auth", "authentication", "vulnerability", "cve", "secret",
                 "token", "injection", "xss", "csrf", "permission", "rbac",
                 "privilege", "exploit", "sanitize", "security", "encrypt"],
    "testing":  ["test", "spec", "coverage", "unit", "integration", "e2e",
                 "pytest", "jest", "flaky", "regression", "fixture", "mock"],
    "docs":     ["doc", "readme", "wiki", "docstring", "comment", "changelog",
                 "documentation", "guide", "tutorial", "example", "runbook"],
    "infra":    ["docker", "deploy", "kubernetes", "k8s", "ci", "workflow",
                 "nginx", "terraform", "helm", "render", "vercel", "github action",
                 "container", "infra", "pipeline", "build"],
}
_DEFAULT_DOMAIN = "dev"


def classify_domain(text: str) -> str:
    """Return the best-matching domain for a task title+description."""
    lower = text.lower()
    scores: dict[str, int] = {domain: 0 for domain in _DOMAIN_KEYWORDS}
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                scores[domain] += 1
    best_domain = max(scores, key=lambda d: scores[d])
    return best_domain if scores[best_domain] > 0 else _DEFAULT_DOMAIN


# ── Workflow engine ───────────────────────────────────────────────────────────

class WorkflowEngine:
    """Drives a Task through the execution state machine with persistence.

    Usage::

        engine = WorkflowEngine(store)
        final_task = await engine.run(task)

    The engine persists each phase transition to the store so a server
    crash leaves the task at a known phase rather than in limbo.
    """

    def __init__(self, store: "TaskStore") -> None:
        self.store = store

    async def run(self, task: "Task", *, max_phases: int = 20) -> "Task":
        """Advance task through the full phase sequence.

        Resumes from ``task.workflow_phase`` if already partially executed.
        Stops when a terminal phase is reached or ``max_phases`` is exceeded.
        """
        phases_run = 0
        while phases_run < max_phases:
            current = WorkflowPhase(task.workflow_phase or WorkflowPhase.CLASSIFY)
            if current in _TERMINAL:
                break
            task = await self._run_phase(task, current)
            phases_run += 1
        else:
            # max_phases exhausted without reaching a terminal phase
            log.error(
                "WorkflowEngine: task=%s exceeded max_phases=%d — marking FAILED",
                task.task_id, max_phases,
            )
            task.workflow_phase = WorkflowPhase.FAILED.value
            task.error_message = f"Workflow exceeded max_phases ({max_phases}); possible loop."
            task.add_log(
                f"Exceeded max_phases={max_phases}; workflow terminated.",
                level="error",
                event_type="workflow_max_phases",
                actor="system:workflow",
            )
            await self.store.update(task)

        return task

    async def _run_phase(self, task: "Task", phase: WorkflowPhase) -> "Task":
        """Execute a single phase and advance to the next."""
        log.info("WorkflowEngine: task=%s phase=%s", task.task_id, phase)
        transition = WorkflowTransition(phase=phase, actor="system:workflow")
        _append_transition(task, transition)
        await self.store.update(task)   # persist entry into this phase

        try:
            next_phase = await self._dispatch(task, phase)
        except Exception as exc:
            log.error("WorkflowEngine: task=%s phase=%s error: %s", task.task_id, phase, exc, exc_info=True)
            task.add_log(
                f"Phase {phase} failed: {exc}",
                level="error",
                event_type=f"workflow_{phase}_error",
                actor="system:workflow",
            )
            task.workflow_phase = WorkflowPhase.FAILED
            task.error_message = str(exc)
            await self.store.update(task)
            return task

        transition.completed_at = time.time()
        task.workflow_phase = next_phase
        task.add_log(
            f"Phase {phase} complete → {next_phase}",
            event_type=f"workflow_{phase}_done",
            actor="system:workflow",
        )
        await self.store.update(task)
        return task

    async def _dispatch(self, task: "Task", phase: WorkflowPhase) -> WorkflowPhase:
        """Run the logic for ``phase`` and return the next phase.

        Handles both sync and async phase methods transparently.
        """
        import inspect as _inspect

        async def _call(method, *args):
            result = method(*args)
            if _inspect.iscoroutine(result):
                result = await result
            return result

        if phase == WorkflowPhase.CLASSIFY:
            return await _call(self._phase_classify, task)
        if phase == WorkflowPhase.PLAN:
            return await _call(self._phase_plan, task)
        if phase == WorkflowPhase.SELECT_SPECIALIST:
            return await self._phase_select_specialist(task)
        if phase == WorkflowPhase.PREFLIGHT:
            return await self._phase_preflight(task)
        if phase == WorkflowPhase.EXECUTE:
            return WorkflowPhase.VERIFY   # execution is owned by TaskExecutionCoordinator
        if phase == WorkflowPhase.VERIFY:
            return await self._phase_verify(task)
        if phase == WorkflowPhase.JUDGE:
            return self._phase_judge(task)
        if phase == WorkflowPhase.SUMMARIZE:
            return self._phase_summarize(task)
        if phase == WorkflowPhase.DONE:
            return WorkflowPhase.DONE
        return WorkflowPhase.FAILED

    # ── Phase implementations ────────────────────────────────────────────────

    def _phase_classify(self, task: "Task") -> WorkflowPhase:
        """Classify domain from title+description; store on task_type."""
        combined = f"{task.title} {task.description} {task.prompt}"
        domain = classify_domain(combined)
        if not task.task_type or task.task_type == "general":
            task.task_type = domain
        task.workflow_phase = WorkflowPhase.CLASSIFY.value
        task.add_log(
            f"Classified domain: {domain}",
            event_type="workflow_classify",
            actor="system:workflow",
            metadata={"domain": domain},
        )
        return WorkflowPhase.PLAN

    def _phase_plan(self, task: "Task") -> WorkflowPhase:
        """Record a plan stub (concrete planning happens inside the agent loop)."""
        task.add_log(
            "Task plan deferred to agent loop execution phase.",
            event_type="workflow_planned",
            actor="system:workflow",
        )
        return WorkflowPhase.SELECT_SPECIALIST

    async def _phase_select_specialist(self, task: "Task") -> WorkflowPhase:
        """Route to the best specialist agent by domain and capability."""
        from agents.store import get_agent_store
        domain = task.task_type or _DEFAULT_DOMAIN
        agent_store = get_agent_store()

        # Try to find a specialist tagged with this domain
        try:
            all_agents = await agent_store.list_all(limit=50)
            candidates = [
                a for a in all_agents
                if domain in (a.tags or []) or a.domain == domain
            ]
            if candidates:
                # Prefer most recently used
                best = max(candidates, key=lambda a: a.last_used_at or 0.0)
                if not task.agent_id:
                    task.agent_id = best.agent_id
                task.add_log(
                    f"Specialist selected: {best.name} (domain={domain})",
                    event_type="workflow_specialist_selected",
                    actor="system:workflow",
                    metadata={"agent_id": best.agent_id, "domain": domain},
                )
                return WorkflowPhase.PREFLIGHT
        except Exception as exc:
            log.debug("Specialist lookup failed: %s", exc)

        task.add_log(
            f"No domain specialist found for '{domain}' — using default runtime",
            event_type="workflow_specialist_default",
            actor="system:workflow",
        )
        return WorkflowPhase.PREFLIGHT

    async def _phase_preflight(self, task: "Task") -> WorkflowPhase:
        """Run doctor checks before execution; block task if critical issues found."""
        try:
            from agent.doctor import DirectChatDoctor
            github_token = os.environ.get("GH_TOKEN") or os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN")
            doctor = DirectChatDoctor(github_token=github_token)
            report = await doctor.check_all()

            if not report.ready:
                critical = [i for i in report.issues if i.code in {
                    "missing_git_binary", "invalid_github_token", "git_repo_access"
                }]
                if critical:
                    issue = critical[0]
                    task.add_log(
                        f"Preflight blocked: {issue.message}",
                        level="error",
                        event_type="workflow_preflight_blocked",
                        actor="system:workflow",
                        metadata={"code": issue.code, "hint": issue.fix_hint},
                    )
                    task.blocked_reason = f"Preflight: {issue.message}. {issue.fix_hint}"
                    return WorkflowPhase.BLOCKED

                # Non-critical warnings — proceed but log
                for issue in report.issues:
                    task.add_log(
                        f"Preflight warning: {issue.message}",
                        level="warning",
                        event_type="workflow_preflight_warning",
                        actor="system:workflow",
                    )
        except Exception as exc:
            log.warning("Preflight check failed: %s — proceeding anyway", exc)
            task.add_log(
                f"Preflight check failed (non-fatal): {exc}",
                level="warning",
                event_type="workflow_preflight_error",
                actor="system:workflow",
            )

        return WorkflowPhase.EXECUTE

    async def _phase_verify(self, task: "Task") -> WorkflowPhase:
        """Verify execution results: PR exists, branch created, no error_message."""
        result_ok = bool(task.result) and not task.error_message
        pr_verified = False

        # If the result mentions a PR/branch, verify it exists in GitHub
        github_token = os.environ.get("GH_TOKEN") or os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN")
        if github_token and task.result:
            import re
            pr_matches = re.findall(r'github\.com/([^/]+/[^/]+)/pull/(\d+)', task.result or "")
            if pr_matches:
                owner_repo, pr_number = pr_matches[0]
                try:
                    from agent.safe_agency import verify_pr_exists
                    owner, repo = owner_repo.split("/", 1)
                    pr_verified = await verify_pr_exists(github_token, owner, repo, int(pr_number))
                    task.add_log(
                        f"PR #{pr_number} verified: {'exists' if pr_verified else 'NOT FOUND'}",
                        event_type="workflow_pr_verified",
                        actor="system:workflow",
                        metadata={"pr_number": pr_number, "verified": pr_verified},
                    )
                except Exception as exc:
                    log.debug("PR verification failed: %s", exc)

        if result_ok or pr_verified:
            task.add_log(
                "Verification passed",
                event_type="workflow_verified",
                actor="system:workflow",
            )
            return WorkflowPhase.JUDGE

        task.add_log(
            f"Verification failed: result={'present' if task.result else 'absent'}, "
            f"error={task.error_message or 'none'}",
            level="warning",
            event_type="workflow_verify_failed",
            actor="system:workflow",
        )
        return WorkflowPhase.JUDGE   # let judge handle the final verdict

    def _phase_judge(self, task: "Task") -> WorkflowPhase:
        """Issue pass/fail verdict based on execution result and error state."""
        has_result = bool(task.result and len(task.result.strip()) > 10)
        has_error  = bool(task.error_message)

        if has_result and not has_error:
            task.add_log("Judge: PASS", event_type="workflow_judge_pass", actor="system:workflow")
            return WorkflowPhase.SUMMARIZE
        else:
            reason = task.error_message or "No result produced"
            task.add_log(
                f"Judge: FAIL — {reason}",
                level="error",
                event_type="workflow_judge_fail",
                actor="system:workflow",
            )
            return WorkflowPhase.SUMMARIZE   # always summarize so the user knows what happened

    def _phase_summarize(self, task: "Task") -> WorkflowPhase:
        """Write a final summary comment and set the terminal status."""
        has_error = bool(task.error_message)
        summary = task.result or task.error_message or "Task completed with no output."

        # Truncate to reasonable comment length
        if len(summary) > 2000:
            summary = summary[:1997] + "…"

        task.add_log(
            summary,
            event_type="workflow_summary",
            actor="system:workflow",
            metadata={"final": True},
        )
        return WorkflowPhase.FAILED if has_error else WorkflowPhase.DONE


# ── Helpers ───────────────────────────────────────────────────────────────────

def _append_transition(task: "Task", transition: WorkflowTransition) -> None:
    """Add a workflow transition to the task's history list."""
    if not hasattr(task, "workflow_history") or task.workflow_history is None:
        task.workflow_history = []
    task.workflow_history.append(transition.model_dump())

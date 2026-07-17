"""Domain services for task workflow and runtime-backed execution."""

from __future__ import annotations

import logging
import os
import time
import asyncio
from typing import Any

from agents.store import AgentDefinition, AgentStore, get_agent_store
from runtimes.base import RuntimeUnavailableError, TaskResult, TaskSpec
from runtimes.manager import RuntimeManager, get_runtime_manager
from tasks.models import Task, TaskComment, TaskStatus
from tasks.store import TaskStore, get_task_store
from agent.workflow import WorkflowEngine, WorkflowPhase, classify_domain
from services.shared_state import claim as _shared_claim, release as _shared_release

log = logging.getLogger("qwen-proxy")

# Self-repo task types that should ship real code (commit + PR) rather than
# stay report-only. Portfolio-materialized initiatives and GitHub-issue
# ceo_direct tasks are meant to result in shipped fixes/features. The
# default "general" task type is ALSO included so CEO-agency tasks (which
# are created as "general") produce commits/PRs instead of just reports.
_SELF_REPO_SHIP_CODE_TASK_TYPES = {"portfolio_initiative", "issue", "quick_note", "general"}


def _get_workflow_engine() -> WorkflowEngine:
    """Return a lazily-created WorkflowEngine singleton."""
    if not hasattr(_get_workflow_engine, "_instance"):
        _get_workflow_engine._instance = WorkflowEngine(get_task_store())
    return _get_workflow_engine._instance


ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.TODO: {TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.FAILED},
    TaskStatus.IN_PROGRESS: {TaskStatus.IN_REVIEW, TaskStatus.BLOCKED, TaskStatus.DONE, TaskStatus.FAILED},
    TaskStatus.IN_REVIEW: {TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.DONE},
    TaskStatus.BLOCKED: {TaskStatus.IN_PROGRESS, TaskStatus.FAILED},
    TaskStatus.FAILED: {TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED},
    TaskStatus.DONE: {TaskStatus.IN_PROGRESS},
    # A task awaiting human input can be re-opened, re-queued, or terminated.
    # Without this key, any transition from NEEDS_CLARIFICATION raised
    # "Cannot transition…" → a 400 on the Retry button.
    TaskStatus.NEEDS_CLARIFICATION: {
        TaskStatus.TODO,
        TaskStatus.IN_PROGRESS,
        TaskStatus.BLOCKED,
        TaskStatus.FAILED,
        TaskStatus.DONE,
    },
}


class TaskWorkflowService:
    """Owns lifecycle transitions, comment semantics, and approval rules."""

    def __init__(self, *, store: TaskStore | None = None) -> None:
        self.store = store or get_task_store()

    async def create_task(self, task: Task, *, actor: str) -> Task:
        self._validate_status_payload(task.status, blocked_reason=task.blocked_reason, review_reason=task.review_reason)
        auto_assigned_agent: AgentDefinition | None = None
        if not task.agent_id and task.status in {TaskStatus.TODO, TaskStatus.IN_PROGRESS}:
            auto_assigned_agent = await self._select_agent(task)
            if auto_assigned_agent is not None:
                task.agent_id = auto_assigned_agent.agent_id
        # Always queue for execution when the task is runnable — even when no
        # specific agent is assigned.  The coordinator will use the internal_agent
        # runtime (which routes through Nvidia NIM) as the universal fallback.
        if self.should_queue_for_execution(task.status):
            task.pending_agent_run = True
        task.add_log(
            f"Task created by {actor}",
            event_type="task_created",
            actor=actor,
            task_status=task.status,
            metadata={"source": task.source},
        )
        if auto_assigned_agent is not None:
            task.add_log(
                f"Auto-assigned to {auto_assigned_agent.name}",
                event_type="agent_auto_assigned",
                actor="system:auto-assignment",
                task_status=task.status,
                metadata={
                    "agent_id": auto_assigned_agent.agent_id,
                    "runtime_id": auto_assigned_agent.runtime_id,
                    "task_type": task.task_type,
                },
            )
        await self.store.create(task)
        return task

    @staticmethod
    def should_queue_for_execution(status: TaskStatus) -> bool:
        return status in {TaskStatus.TODO, TaskStatus.IN_PROGRESS}

    async def save(self, task: Task) -> Task:
        await self.store.update(task)
        return task

    def transition(
        self,
        task: Task,
        status: TaskStatus,
        *,
        actor: str,
        blocked_reason: str | None = None,
        review_reason: str | None = None,
        message: str | None = None,
        pending_agent_run: bool | None = None,
    ) -> Task:
        if status != task.status:
            allowed = ALLOWED_TRANSITIONS.get(task.status, set())
            if status not in allowed:
                raise ValueError(f"Cannot transition task from {task.status.value} to {status.value}")

        self._validate_status_payload(status, blocked_reason=blocked_reason, review_reason=review_reason)

        task.status = status
        task.blocked_reason = blocked_reason if status is TaskStatus.BLOCKED else None
        task.review_reason = review_reason if status is TaskStatus.IN_REVIEW else None

        if status in {TaskStatus.TODO, TaskStatus.IN_PROGRESS}:
            # Both states are "runnable" — the dispatcher's list_pending() requires
            # status in {todo, in_progress} AND pending_agent_run is True. Previously
            # TODO was not handled here, so a FAILED→TODO retry left pending_agent_run
            # False and the dispatcher never picked the task back up.
            if status is TaskStatus.IN_PROGRESS and task.started_at is None:
                task.started_at = time.time()
            task.pending_agent_run = True if pending_agent_run is None else pending_agent_run
        elif status in {TaskStatus.IN_REVIEW, TaskStatus.BLOCKED, TaskStatus.DONE, TaskStatus.FAILED}:
            task.pending_agent_run = bool(pending_agent_run) if pending_agent_run is not None else False

        if status is TaskStatus.DONE and task.completed_at is None:
            task.completed_at = time.time()
        if status in {TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.IN_REVIEW, TaskStatus.FAILED}:
            if status is not TaskStatus.DONE:
                task.completed_at = None

        task.add_log(
            message or f"Task moved to {status.value} by {actor}",
            event_type="status_changed",
            actor=actor,
            task_status=status,
            metadata={
                "blocked_reason": blocked_reason,
                "review_reason": review_reason,
            },
        )
        return task

    def assign_agent(self, task: Task, agent_id: str | None, *, actor: str) -> Task:
        previous = task.agent_id
        task.agent_id = agent_id
        if agent_id and self.should_queue_for_execution(task.status):
            task.pending_agent_run = True
        task.add_log(
            f"Agent assignment updated by {actor}",
            event_type="agent_assigned",
            actor=actor,
            task_status=task.status,
            metadata={"previous_agent_id": previous, "agent_id": agent_id},
        )
        return task

    def add_comment(
        self,
        task: Task,
        *,
        author: str,
        body: str,
        reply_to: str | None = None,
    ) -> TaskComment:
        if reply_to and not any(comment.comment_id == reply_to for comment in task.comments):
            raise ValueError(f"Unknown parent comment: {reply_to}")

        comment = TaskComment(author=author, body=body, reply_to=reply_to)
        task.comments.append(comment)
        task.add_log(
            f"Comment added by {author}",
            event_type="comment_added",
            actor=author,
            task_status=task.status,
            metadata={"comment_id": comment.comment_id, "reply_to": reply_to},
        )

        is_agent = author.startswith("agent:")
        if not is_agent and task.status is TaskStatus.IN_REVIEW:
            self.transition(
                task,
                TaskStatus.IN_PROGRESS,
                actor=author,
                message=f"Task re-entered execution after comment by {author}",
                pending_agent_run=True,
            )

        return comment

    def record_approval(
        self,
        task: Task,
        *,
        checkpoint_id: str,
        approved: bool,
        actor: str,
        reason: str | None = None,
    ) -> Task:
        checkpoint = next(
            (item for item in task.approval_checkpoints if item.checkpoint_id == checkpoint_id),
            None,
        )
        if checkpoint is None:
            raise ValueError(f"Unknown checkpoint: {checkpoint_id}")

        checkpoint.approved = approved
        checkpoint.approved_by = actor
        checkpoint.approved_at = time.time()
        checkpoint.reason = reason

        if approved:
            pending_required = [
                item for item in task.approval_checkpoints
                if item.required and item.approved is not True
            ]
            if not pending_required:
                self.transition(
                    task,
                    TaskStatus.DONE,
                    actor=actor,
                    message=f"All approvals completed by {actor}",
                )
        else:
            self.transition(
                task,
                TaskStatus.IN_PROGRESS,
                actor=actor,
                message=f"Checkpoint rejected by {actor}; task returned to execution",
                pending_agent_run=True,
            )

        task.add_log(
            f"Checkpoint {'approved' if approved else 'rejected'} by {actor}",
            event_type="approval_decision",
            actor=actor,
            task_status=task.status,
            metadata={"checkpoint_id": checkpoint_id, "approved": approved, "reason": reason},
        )
        return task

    def approve_execution(
        self, task: Task, *, actor: str, approved: bool = True, reason: str | None = None
    ) -> Task:
        """Record the human decision on a task's **pre-execution** approval gate.

        A ``requires_approval`` task is parked by the dispatcher before it runs
        (charter Gate Matrix). Approve → set ``execution_approved`` and re-queue
        for execution; reject → BLOCKED with a reason (re-openable). This is the
        gate that stops risky/outward-facing work from running unattended; it is
        distinct from ``record_approval`` (which signs off COMPLETED work).
        """
        if approved:
            task.execution_approved = True
            self.transition(
                task,
                TaskStatus.IN_PROGRESS,
                actor=actor,
                message=f"Execution approved by {actor}",
                pending_agent_run=True,
            )
        else:
            self.transition(
                task,
                TaskStatus.BLOCKED,
                actor=actor,
                blocked_reason=f"Execution rejected by {actor}: {reason or 'no reason given'}",
                message=f"Execution rejected by {actor}",
            )
        task.add_log(
            f"Pre-execution gate {'approved' if approved else 'rejected'} by {actor}",
            event_type="approval_decision",
            actor=actor,
            task_status=task.status,
            metadata={"gate": "pre_execution", "approved": approved, "reason": reason},
        )
        return task

    def retry(self, task: Task, *, actor: str) -> Task:
        """Re-run a task. Permissive across every non-active state so the dashboard
        Retry button (which is always visible) never returns a 400: terminal,
        blocked, in-review and clarification-pending tasks are re-opened, while
        already-runnable tasks (todo/in_progress) are simply re-armed.
        """
        if task.status in {TaskStatus.TODO, TaskStatus.IN_PROGRESS}:
            # Already runnable — re-arm the agent run without an illegal self-transition.
            task.pending_agent_run = True
            task.add_log(
                f"Task re-armed for retry by {actor}",
                event_type="status_changed",
                actor=actor,
                task_status=task.status,
            )
        else:
            # FAILED → TODO (back of the queue); everything else → IN_PROGRESS (resume).
            target = TaskStatus.TODO if task.status is TaskStatus.FAILED else TaskStatus.IN_PROGRESS
            self.transition(
                task,
                target,
                actor=actor,
                message=f"Task reset for retry by {actor}",
                pending_agent_run=True,
            )
        task.auto_retry_count = 0  # human retry resets the auto-retry counter
        task.add_log(
            "Runtime-unavailable counter reset by human retry",
            event_type="runtime_retry_reset",
            actor=actor,
            task_status=task.status,
        )
        task.error_message = None
        return task

    def follow_up(
        self,
        task: Task,
        *,
        actor: str,
        message: str,
        model_preference: str | None = None,
    ) -> Task:
        """Add a follow-up instruction to a task and re-queue it for execution.

        Unlike :meth:`retry` (which simply re-runs the same task), ``follow_up``
        lets a human (or the CEO) give *new* guidance. The message is appended as a
        comment so it carries into the agent's conversation/instruction context
        (see ``_build_spec``'s ``conversation`` key), then the task is re-opened and
        re-queued. Works from any non-active state (done/failed/blocked/in_review)
        and from in_progress (which just re-arms the pending run).
        """
        if not message or not message.strip():
            raise ValueError("Follow-up message must not be empty")

        # Append the new instruction as a comment first — this becomes part of the
        # conversation history handed to the runtime on the next run.
        self.add_comment(task, author=actor, body=message)

        if model_preference:
            task.model_preference = model_preference

        # add_comment already re-queues IN_REVIEW tasks for non-agent authors; for
        # other states, re-open and queue explicitly.
        if not task.pending_agent_run:
            if task.status is TaskStatus.IN_PROGRESS:
                task.pending_agent_run = True
            else:
                self.transition(
                    task,
                    TaskStatus.IN_PROGRESS,
                    actor=actor,
                    message=f"Follow-up requested by {actor}",
                    pending_agent_run=True,
                )
        task.add_log(
            "Runtime-unavailable counter reset by follow-up",
            event_type="runtime_retry_reset",
            actor=actor,
            task_status=task.status,
        )
        task.error_message = None
        return task

    def escalate(self, task: Task, *, actor: str, reason: str | None = None) -> Task:
        task.escalation_count += 1
        task.escalation_reason = reason or task.escalation_reason
        self.transition(
            task,
            TaskStatus.BLOCKED,
            actor=actor,
            blocked_reason=reason or "Escalated for human intervention",
            message=f"Task escalated by {actor}",
        )
        return task

    def _validate_status_payload(
        self,
        status: TaskStatus,
        *,
        blocked_reason: str | None,
        review_reason: str | None,
    ) -> None:
        if status is TaskStatus.BLOCKED and not blocked_reason:
            raise ValueError("blocked_reason is required when moving a task to blocked")
        if status is TaskStatus.IN_REVIEW and not review_reason:
            raise ValueError("review_reason is required when moving a task to in_review")

    async def _select_agent(self, task: Task) -> AgentDefinition | None:
        agent_store = get_agent_store()
        runtime_manager = get_runtime_manager()
        candidates = await agent_store.list_for_user(task.owner_id, include_public=True)

        # ── Company specialist routing ──────────────────────────────────
        # If a task carries a "company:{id}" tag, prefer agents that belong
        # to that company (registered by CompanyAgencyService.activate_company).
        # This is the bridge that makes provisioned specialists actually
        # receive dispatched work instead of being orphaned database records.
        task_company_id: str | None = None
        for tag in (task.tags or []):
            if tag.startswith("company:") and len(tag) > 8:
                task_company_id = tag[8:]
                break
        if task_company_id and candidates:
            company_candidates = [
                a for a in candidates
                if a.owner_id == task_company_id
                or any(t == f"company:{task_company_id}" for t in (a.tags or []))
            ]
            if company_candidates:
                candidates = company_candidates

        # Also match on specialist-family tags if the task carries one.
        task_specialist_family: str | None = None
        for tag in (task.tags or []):
            if tag.startswith("specialist-family:") and len(tag) > 18:
                task_specialist_family = tag[18:]
                break
        if task_specialist_family and candidates:
            family_candidates = [
                a for a in candidates
                if a.role == task_specialist_family
                or any(t == f"specialist-family:{task_specialist_family}" for t in (a.tags or []))
            ]
            if family_candidates:
                candidates = family_candidates

        if not candidates:
            return None
        open_counts = await self.store.count_by_agent(
            owner_id=task.owner_id,
            statuses={
                TaskStatus.TODO,
                TaskStatus.IN_PROGRESS,
                TaskStatus.IN_REVIEW,
                TaskStatus.BLOCKED,
            },
        )
        active_counts = await self.store.count_by_agent(
            owner_id=task.owner_id,
            statuses={TaskStatus.IN_PROGRESS},
        )

        def _score(agent: AgentDefinition) -> tuple[int, int, float]:
            score = 0
            task_types = {task_type.strip().lower() for task_type in (agent.task_types or []) if task_type}
            task_type = (task.task_type or "general").strip().lower()

            if task_type and task_type in task_types:
                score += 100
            elif "general" in task_types:
                score += 45
            elif not task_types:
                score += 20

            if task.runtime_id and agent.runtime_id == task.runtime_id:
                score += 30
            elif not task.runtime_id and agent.runtime_id:
                runtime = runtime_manager.get_runtime(agent.runtime_id)
                if runtime and runtime.get("health", {}).get("available") is True:
                    score += 15

            if task.model_preference and agent.model == task.model_preference:
                score += 10

            if agent.is_public:
                score += 5

            if any(tag.startswith("crispy:") for tag in agent.tags):
                score += 3

            score -= open_counts.get(agent.agent_id, 0) * 12
            score -= active_counts.get(agent.agent_id, 0) * 25

            return (score, -agent.use_count, -agent.created_at)

        ranked = sorted(candidates, key=_score, reverse=True)
        best = ranked[0]
        best_score = _score(best)[0]
        if best_score <= 0:
            return None
        return best


# PR #937: lowered from 10 to 5. With the self_heal module unblocking tasks
# every minute, 10 retries meant a task could burn 10 dispatch cycles before
# getting blocked — each cycle hitting a dead endpoint. 5 is enough to ride
# out a transient blip, and the self_heal pass will unblock it after the
# brain failovers anyway.
_DISPATCH_RETRY_LIMIT = 5  # max re-queues before a task is blocked
_BRAIN_DEFER_LIMIT = 12     # max brain-unavailable deferrals before blocking — a
                            # missing brain is an operator-fixable config issue, so
                            # we keep the task queued a little longer than a runtime
                            # outage before parking it as BLOCKED.


async def _brain_is_configured() -> bool:
    """Best-effort, fail-open check that *some* usable LLM brain is configured.

    Returns ``True`` unless we can positively determine that NO brain is reachable
    (no ``AGENT_LLM_BASE_URL`` override, no explicit ``OLLAMA_BASE``, no free NVIDIA
    key, paid brain not allowed, and no configured provider record with a usable
    endpoint). Used as a pre-dispatch gate so a misconfigured deploy *defers* tasks
    (keeps them queued) instead of spinning up a worktree per task and hammering a
    dead endpoint. Never raises — any probe error fails open (assume configured) so
    this can never wedge the happy path or a non-standard provider setup.
    """
    try:
        if os.environ.get("AGENT_LLM_BASE_URL", "").strip():
            return True
        if os.environ.get("OLLAMA_BASE", "").strip():
            # Operator explicitly pointed at a local/remote Ollama — trust intent.
            return True
        try:
            import packages.ai.brain as brain_policy
            if brain_policy.resolve_free_nvidia_brain() is not None:
                return True
            if brain_policy.allow_paid_brain():
                return True
        except Exception:
            return True  # fail-open
        # Any configured provider record with a usable endpoint (incl. ollama)?
        try:
            from backend.server import _list_configured_provider_records
            for rec in await _list_configured_provider_records():
                rtype = str(rec.get("type") or "").lower()
                base = str(rec.get("base_url") or "").strip()
                key = str(rec.get("api_key") or "").strip()
                if base and (rtype == "ollama" or key):
                    return True
        except Exception:
            return True  # fail-open — never block dispatch on a registry probe error
        return False
    except Exception:  # pragma: no cover - defensive belt-and-braces
        return True


def _is_brain_connection_error(exc: BaseException) -> bool:
    """True if *exc* looks like an LLM-brain/endpoint connectivity failure.

    Such errors are transient/operator-fixable (the brain is unreachable), not a
    task defect, so they should re-queue like ``RuntimeUnavailableError`` rather
    than mark the task permanently FAILED. Matches httpx connection/timeout types
    and common connection-refused message fragments (the error usually arrives
    wrapped in several layers, so we also sniff the stringified message)."""
    try:
        import httpx
        if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout,
                            httpx.ReadTimeout, httpx.PoolTimeout)):
            return True
    except Exception:  # pragma: no cover - httpx always present in this app
        pass
    s = str(exc).lower()
    return any(k in s for k in (
        "connection refused", "connecterror", "failed to connect",
        "all connection attempts failed", "name or service not known",
        "max retries", "no brain", "connection error",
    ))


class TaskExecutionCoordinator:
    """Executes tasks through the runtime layer using agent definitions."""

    # Shared lock key prefix used by _claim_task / _release_task.
    _CLAIM_PREFIX = "task:active:"

    def __init__(
        self,
        *,
        store: TaskStore | None = None,
        workflow: TaskWorkflowService | None = None,
        agent_store: AgentStore | None = None,
        runtime_manager: RuntimeManager | None = None,
        workspace_root: str = ".",
        execution_timeout_s: float | None = None,
        company_graph_store: Any = None,
    ) -> None:
        self.store = store or get_task_store()
        self.workflow = workflow or TaskWorkflowService(store=self.store)
        self.agent_store = agent_store or get_agent_store()
        self.runtime_manager = runtime_manager or get_runtime_manager()
        self.workspace_root = workspace_root
        # Company graph store is optional — only used when task.company_id is
        # set AND E2B is enabled (roadmap ★5 sandbox integration). Lazy-loaded
        # on first use so a deploy without MongoDB / the company-graph feature
        # is unaffected.
        self._company_graph_store = company_graph_store
        # Default raised 150s → 300s: a full agent run on the FREE cloud brain
        # makes several sequential LLM calls (plan → execute → verify → judge),
        # which routinely exceeds 150s and then fails + auto-retries — the
        # "Execution timed out after 150s" / "blocked after N dispatch attempts"
        # churn that made the board feel dead-slow. Giving runs room to *complete*
        # once beats failing and retrying many times. Tune via env.
        # PR #923: bumped default from 300s to 600s to match the chat agent-run
        # budget. A 300s timeout was too tight for NVIDIA NIM under load + Ollama
        # cold model loading. Combined with the new transient-timeout handling
        # (re-queue instead of hard-fail), 600s gives tasks room to complete
        # while still bounding a truly dead endpoint. Tune via env.
        self.execution_timeout_s = execution_timeout_s or float(
            os.environ.get("TASK_EXECUTION_TIMEOUT_SEC", "600")
        )
        # In-memory set of task_ids currently being executed by this coordinator
        # instance.  Used by TaskDispatcher._reconcile() to determine which tasks
        # are active so stranded-task recovery skips them.
        self._active_task_ids: set[str] = set()

    async def execute(self, task_id: str) -> Task:
        _exec_start = time.time()
        claimed = await self._claim_task(task_id)
        if not claimed:
            # Either we already hold the lock or another process does — either way
            # skip this duplicate dispatch attempt.
            log.info("Task %s is already executing; skipping duplicate run request", task_id)
            existing = await self.store.get(task_id)
            if existing is None:
                raise ValueError(f"Task not found: {task_id}")
            return existing

        # Track this task as active on this coordinator instance so the reconciler
        # knows to exclude it from stranded-task recovery.
        self._active_task_ids.add(task_id)

        task = await self.store.get(task_id)
        if task is None:
            await self._release_task(task_id)
            raise ValueError(f"Task not found: {task_id}")
        if not task.pending_agent_run:
            await self._release_task(task_id)
            return task

        # ── Pre-execution approval gate (Autonomy Charter Gate Matrix) ──
        # A risky/outward-facing task (requires_approval) must NEVER run before a
        # human approves. Park it here — BEFORE resolving the agent or invoking any
        # runtime — so autonomous dispatch cannot execute it. Clearing
        # pending_agent_run stops the dispatcher re-picking it; a best-effort
        # Telegram heads-up is pushed. Approval arrives via
        # TaskWorkflowService.approve_execution() (POST /api/tasks/{id}/approve-execution),
        # which sets execution_approved and re-queues the task.
        if task.requires_approval and not task.execution_approved:
            task.pending_agent_run = False
            task.review_reason = "⏸ Awaiting human approval before execution (requires_approval)."
            task.add_log(
                "Execution gated — awaiting human approval before the agent runs.",
                event_type="approval_gate",
                actor="system:dispatcher",
                task_status=task.status,
                metadata={"gate": "pre_execution"},
            )
            await self.store.update(task)
            self._notify_execution_gate(task)
            self._active_task_ids.discard(task_id)
            await self._release_task(task_id)
            return task

        # ── Brain-availability preflight (graceful degradation) ──
        # If NO LLM brain is configured anywhere, don't spin up a worktree and
        # hammer a dead endpoint (which would burn a full _DISPATCH_RETRY_LIMIT of
        # runtime retries per task). DEFER instead: keep the task queued
        # (pending_agent_run stays True, status stays TODO) so the dispatcher
        # auto-re-picks it the moment a brain is configured/reachable — no human
        # action, no FAILED tasks, no worktree churn. After _BRAIN_DEFER_LIMIT
        # deferrals, park it as BLOCKED so a permanently-misconfigured deploy
        # doesn't loop forever. The check fails open, so a configured brain (the
        # normal case) passes straight through with zero behaviour change.
        if not await _brain_is_configured():
            defer_events = 0
            for e in task.execution_log:
                if e.event_type == "runtime_retry_reset":
                    defer_events = 0
                elif e.event_type == "brain_unavailable":
                    defer_events += 1
            if defer_events >= _BRAIN_DEFER_LIMIT:
                task.pending_agent_run = False
                task.error_message = "No LLM brain configured (set NVIDIA_API_KEY)."
                self.workflow.transition(
                    task,
                    TaskStatus.BLOCKED,
                    actor="system:dispatcher",
                    blocked_reason=(
                        f"No LLM brain reachable after {defer_events} deferrals — "
                        "set NVIDIA_API_KEY (free) or configure a provider."
                    ),
                    message="Task blocked — no LLM brain reachable.",
                )
                log.error(
                    "Task %s blocked — no LLM brain configured after %d deferrals",
                    task.task_id, defer_events,
                )
            else:
                task.pending_agent_run = True  # stay on the dispatch queue
                task.review_reason = "⏸ Deferred — no LLM brain reachable (set NVIDIA_API_KEY)."
                task.add_log(
                    f"Execution deferred — no LLM brain configured "
                    f"(attempt {defer_events + 1}/{_BRAIN_DEFER_LIMIT}); "
                    "will retry automatically once a brain is set.",
                    level="warning",
                    event_type="brain_unavailable",
                    actor="system:dispatcher",
                    task_status=task.status,
                )
                log.warning(
                    "Task %s deferred — no LLM brain configured (attempt %d/%d)",
                    task.task_id, defer_events + 1, _BRAIN_DEFER_LIMIT,
                )
            await self.store.update(task)
            self._active_task_ids.discard(task_id)
            await self._release_task(task_id)
            return task

        try:
            agent = await self._resolve_agent(task)

            self.workflow.transition(
                task,
                TaskStatus.IN_PROGRESS,
                actor=f"agent:{agent.agent_id}" if agent else "system:dispatcher",
                message=f"Execution started for task {task.task_id}",
                pending_agent_run=False,
            )
            task.add_log(
                "Resolved execution context",
                event_type="execution_context",
                actor=f"agent:{agent.agent_id}" if agent else "system:dispatcher",
                task_status=task.status,
                metadata={
                    "agent_id": agent.agent_id if agent else None,
                    "runtime_id": task.runtime_id or (agent.runtime_id if agent else None),
                    "model": task.model_preference or (agent.model if agent else None),
                },
            )
            await self.store.update(task)

            spec = self._build_spec(task, agent)

            # ── Workflow phase: CLASSIFY then EXECUTE ──
            domain = classify_domain(f"{task.title} {task.description}")
            task.workflow_phase = WorkflowPhase.CLASSIFY.value
            task.add_log(
                f"Workflow: classified domain='{domain}'",
                event_type="workflow_classify",
                actor="system:workflow",
                metadata={"domain": domain},
            )
            await self.store.update(task)
            task.workflow_phase = WorkflowPhase.EXECUTE.value
            task.add_log(
                "Workflow: executing",
                event_type="workflow_execute",
                actor="system:workflow",
            )
            await self.store.update(task)
            # Sanctioned autonomous execution path: the TaskExecutionCoordinator is
            # driven by the background TaskDispatcher and (via the scheduler) by the
            # CEO Agency. Tasks have their own approval workflow (requires_approval →
            # IN_REVIEW), so they do not need the WorkflowOrchestrator's per-request
            # ApprovalGate. Set the orchestrator bypass (async-safe ContextVar,
            # isolated to this asyncio task) so the runtime's AgentRunner.run() is not
            # blocked under the default AGENCY_WORKFLOW_MODE=orchestrator. The direct
            # /runtimes/{id}/execute API stays gated because it does not set this.
            import services.workflow_orchestrator as _wo

            _bypass_token = _wo._BYPASS.set(True)
            try:
                result, decision = await asyncio.wait_for(
                    self.runtime_manager.execute(spec),
                    timeout=self.execution_timeout_s,
                )
            finally:
                _wo._BYPASS.reset(_bypass_token)

            task.last_runtime_id = decision.selected_runtime_id
            task.last_model_used = result.model_used or decision.model_used
            task.tokens_used = result.tokens_used
            task.cost_usd = result.cost_usd
            task.result = result.output
            task.error_message = None
            task.add_log(
                f"Runtime selected: {decision.selected_runtime_id}",
                event_type="runtime_selected",
                actor="system:dispatcher",
                task_status=task.status,
                runtime_id=decision.selected_runtime_id,
                model_used=result.model_used or decision.model_used,
                metadata={
                    "reason": decision.reason,
                    "fallback_runtime_id": decision.fallback_runtime_id,
                    "fallback_attempted": decision.fallback_attempted,
                },
            )

            await self._apply_result(task, agent, result)
            task.workflow_phase = WorkflowPhase.VERIFY.value
            task.add_log(
                "Workflow: verifying result",
                event_type="workflow_verify",
                actor="system:workflow",
            )
            # Langfuse trace: task executed successfully
            try:
                from langfuse_obs import emit_agency_observation
                emit_agency_observation(
                    operation="task_execute",
                    actor="system:coordinator",
                    task_id=task.task_id,
                    task_title=task.title,
                    task_type=task.task_type,
                    status="ok",
                    duration_ms=int((time.time() - _exec_start) * 1000) if _exec_start else 0,
                    model=result.model_used,
                    output_text=result.output[:2000] if result.output else None,
                    metadata={"runtime_id": decision.selected_runtime_id},
                )
            except Exception:
                pass
        except asyncio.TimeoutError:
            message = (
                f"Execution timed out after {self.execution_timeout_s:.0f}s"
            )
            log.error("Task %s %s", task.task_id, message)
            task.error_message = message
            # PR #923: treat execution timeout as TRANSIENT (re-queue) instead
            # of hard-failing the task. A timeout usually means the LLM endpoint
            # is overloaded or slow (e.g. NVIDIA NIM under load, or a cold
            # Ollama model loading for the first time) — NOT a task defect.
            # Hard-failing meant every timed-out task was permanently stuck
            # (pending_agent_run=False) and never picked up again, even after
            # the backend recovered. Re-queueing gives the task another chance
            # on the next dispatch cycle. The _requeue_or_block_unavailable
            # helper handles the retry-count cap + eventual BLOCKED transition.
            self._requeue_or_block_unavailable(task, asyncio.TimeoutError(), what=message)
            # Langfuse trace: task timed out
            try:
                from langfuse_obs import emit_agency_observation
                emit_agency_observation(
                    operation="task_execute",
                    actor="system:coordinator",
                    task_id=task.task_id,
                    task_title=task.title,
                    task_type=task.task_type,
                    status="timeout",
                    duration_ms=int((time.time() - _exec_start) * 1000),
                    error=message,
                )
            except Exception:
                pass
        except RuntimeUnavailableError as exc:
            # No healthy runtime was available at dispatch time.  Re-queue the
            # task instead of failing it so the next dispatcher cycle retries.
            self._requeue_or_block_unavailable(task, exc, what="No runtime available")
        except Exception as exc:
            # A brain/LLM-endpoint connectivity failure is transient/operator-fixable
            # (the configured brain is momentarily unreachable), NOT a task defect —
            # re-queue it like RuntimeUnavailableError instead of marking it
            # permanently FAILED. Everything else is a genuine failure.
            if _is_brain_connection_error(exc):
                self._requeue_or_block_unavailable(task, exc, what="Brain/LLM endpoint unreachable")
            else:
                log.error("Error executing task %s: %s", task.task_id, exc, exc_info=True)
                task.error_message = str(exc)
                self.workflow.transition(
                    task,
                    TaskStatus.FAILED,
                    actor="system:coordinator",
                    message=f"Execution failed: {exc}",
                )
                # Langfuse trace: task failed
                try:
                    from langfuse_obs import emit_agency_observation
                    emit_agency_observation(
                        operation="task_execute",
                        actor="system:coordinator",
                        task_id=task.task_id,
                        task_title=task.title,
                        task_type=task.task_type,
                        status="failed",
                        duration_ms=int((time.time() - _exec_start) * 1000),
                        error=str(exc)[:500],
                    )
                except Exception:
                    pass
        finally:
            await self.store.update(task)
            await self._release_task(task_id)
            self._active_task_ids.discard(task_id)
        return task

    def _requeue_or_block_unavailable(self, task: Task, exc: BaseException, *, what: str) -> None:
        """Re-queue a task that couldn't run because no runtime/brain was available.

        Counts ``runtime_unavailable`` events since the most recent
        ``runtime_retry_reset`` (so a human retry/follow-up resets the budget) and
        re-queues up to ``_DISPATCH_RETRY_LIMIT`` times before parking the task as
        BLOCKED. Shared by the ``RuntimeUnavailableError`` handler and the
        brain/connection-error path so both degrade identically instead of one
        re-queueing and the other hard-failing.
        """
        unavailable_events = 0
        for e in task.execution_log:
            if e.event_type == "runtime_retry_reset":
                unavailable_events = 0
            elif e.event_type == "runtime_unavailable":
                unavailable_events += 1
        if unavailable_events >= _DISPATCH_RETRY_LIMIT:
            log.error(
                "Task %s blocked after %d failed dispatch attempts (%s): %s",
                task.task_id, unavailable_events, what, exc,
            )
            task.error_message = str(exc)
            self.workflow.transition(
                task,
                TaskStatus.BLOCKED,
                actor="system:coordinator",
                blocked_reason=f"{what} after {unavailable_events} attempts: {exc}",
                message=f"Task blocked — {what.lower()} after {unavailable_events} retries",
            )
        else:
            log.warning(
                "Task %s re-queued — %s (attempt %d/%d): %s",
                task.task_id, what.lower(), unavailable_events + 1, _DISPATCH_RETRY_LIMIT, exc,
            )
            # Restore pending state so the dispatcher picks it up again.
            task.pending_agent_run = True
            if task.status == TaskStatus.IN_PROGRESS:
                task.status = TaskStatus.TODO
            task.add_log(
                f"{what} (attempt {unavailable_events + 1}/{_DISPATCH_RETRY_LIMIT}): {exc}",
                level="warning",
                event_type="runtime_unavailable",
                actor="system:coordinator",
                task_status=task.status,
            )

    @staticmethod
    async def _claim_task(task_id: str) -> bool:
        return await _shared_claim(f"task:active:{task_id}", ttl=3600)

    @staticmethod
    async def _release_task(task_id: str) -> None:
        await _shared_release(f"task:active:{task_id}")

    @staticmethod
    def _notify_execution_gate(task: Task) -> None:
        """Best-effort Telegram heads-up that a task is parked awaiting approval.

        Sends an inline keyboard with Approve/Reject buttons so the operator
        can act directly from Telegram.  Falls back silently on error.
        """
        try:
            from telegram_service import NotificationDispatcher, _escape_md_v1

            nd = NotificationDispatcher()
            if not nd.telegram_token or not nd.telegram_chat_ids:
                return

            title_safe = _escape_md_v1((task.title or "")[:120])
            msg = (
                "\u23f8 *Task awaiting approval before execution*\n"
                f"`{task.task_id}` \u2014 {title_safe}\n"
                "Tap a button below to approve or reject."
            )
            keyboard = [[
                {"text": "\u2705 Approve", "callback_data": f"task:approve:{task.task_id}"},
                {"text": "\u274c Reject", "callback_data": f"task:reject:{task.task_id}"},
            ]]
            nd._send_telegram_keyboard(msg, keyboard)
        except Exception:  # nosec B110 - notification is best-effort
            pass

    async def _resolve_agent(self, task: Task) -> AgentDefinition | None:
        if task.agent_id:
            agent = await self.agent_store.get(task.agent_id, owner_id=None)
            if agent:
                agent.record_use()
                await self.agent_store.update(agent)
                return agent

        if task.agent_id:
            log.warning("Assigned agent %s not found; falling back to task configuration", task.agent_id)
        auto_assigned = await self.workflow._select_agent(task)
        if auto_assigned is not None:
            previous = task.agent_id
            task.agent_id = auto_assigned.agent_id
            task.add_log(
                f"Auto-assigned to {auto_assigned.name}",
                event_type="agent_auto_assigned",
                actor="system:auto-assignment",
                task_status=task.status,
                metadata={
                    "previous_agent_id": previous,
                    "agent_id": auto_assigned.agent_id,
                    "runtime_id": auto_assigned.runtime_id,
                },
            )
            await self.store.update(task)
            auto_assigned.record_use()
            await self.agent_store.update(auto_assigned)
            return auto_assigned
        return None

    def _build_spec(self, task: Task, agent: AgentDefinition | None) -> TaskSpec:
        task_type = task.task_type or (agent.task_types[0] if agent and agent.task_types else "general")
        runtime_preference = task.runtime_id or (agent.runtime_id if agent else None) or "internal_agent"
        model_preference = task.model_preference or (agent.model if agent else None)
        # Always allow paid-free escalation to Nvidia NIM (it's free)
        allow_paid_escalation = True

        context = {
            "task": {
                "title": task.title,
                "description": task.description,
                "prompt": task.prompt,
                "tags": task.tags,
                "requires_approval": task.requires_approval,
            },
            "agent": {
                "agent_id": agent.agent_id if agent else None,
                "name": agent.name if agent else "Default Agent",
                "system_prompt": agent.system_prompt if agent else "",
                "cost_policy": agent.cost_policy if agent else "local_only",
                "task_types": agent.task_types if agent else [],
            },
            "comments": [comment.model_dump() for comment in task.comments[-20:]],
            "history": [entry.model_dump() for entry in task.execution_log[-20:]],
            # Structured conversation history for the runtime's AgentRunner
            # (it reads context["conversation"]). This is what carries follow-up
            # instructions and prior agent replies across re-runs — without it,
            # a re-queued task would lose the thread.
            "conversation": [
                {
                    "role": "assistant"
                    if comment.author.startswith(("agent:", "runtime:"))
                    else "user",
                    "content": comment.body,
                }
                for comment in task.comments[-20:]
            ],
        }

        # ── Onboarded company repo wiring (roadmap ★5 — E2B sandbox) ──────
        # When a task is bound to a company (task.company_id set) AND the
        # company has a RepoConnection, resolve repo_url / base_branch /
        # github_token and inject them into spec.context so the runtime
        # (E2BAdapter or InternalAgentAdapter) clones the REAL company repo
        # into the sandbox instead of running against the agency's own
        # checkout. E2B-enabled check happens here so the legacy path is
        # untouched when E2B is off — a deploy without E2B_API_KEY continues
        # to run against the agency checkout exactly as before.
        if getattr(task, "company_id", None):
            try:
                from services.e2b_config import e2b_enabled as _e2b_on
                if _e2b_on():
                    repo_info = self._resolve_company_repo(task.company_id)
                    if repo_info:
                        context["repo_url"] = repo_info["repo_url"]
                        context["base_branch"] = repo_info["base_branch"]
                        context["github_token"] = repo_info["github_token"]
                        context["company_id"] = task.company_id
            except Exception as exc:
                log.warning(
                    "Task %s company repo resolution failed (continuing with default workspace): %s",
                    task.task_id, exc,
                )
        elif task_type in _SELF_REPO_SHIP_CODE_TASK_TYPES:
            self._inject_self_repo_ship_context(task, context)

        return TaskSpec(
            task_id=task.task_id,
            instruction=self._compose_instruction(task, agent),
            task_type=task_type,
            workspace_path=self.workspace_root,
            model_preference=model_preference,
            provider_preference=runtime_preference,
            allow_paid_escalation=allow_paid_escalation,
            context=context,
        )

    def _inject_self_repo_ship_context(self, task: Task, context: dict[str, Any]) -> None:
        """Inject auto_commit + repo context for self-repo ship-code tasks.

        Without repo_url/base_branch/github_token/auto_commit injected here,
        the runtime has nothing to commit or push to: the agent applies its
        changes to an isolated worktree that is deleted unconditionally after
        the run (``InternalAgentAdapter._remove_worktree``), so the work was
        silently discarded — the task showed DONE with a text summary but no
        code ever reached git. ``auto_commit`` only makes git commits happen
        locally; it is the runtime's own ``AGENT_AUTO_PR_ENABLED`` check
        (``agent/loop.py::_auto_push_and_pr``, already true in
        ``render.yaml``) that pushes a feature branch and opens a PR.
        ``GitHubTools`` is constructed with ``agent_initiated=True``
        (``agent/loop.py``), so ``agent/autonomy_gate.py`` hard-blocks any
        write to master/main and any PR merge regardless of this flag: the
        worst case is a PR never opens, never that master gets touched.

        Flag-gated (default ON) — ``packages.config.settings`` is the
        rollback lever, matching the portfolio-materializer / model-catalog
        flag pattern already used in this codebase. Never raises — falls
        back to report-only execution on any resolution failure.
        """
        try:
            from packages.config import settings
            self_repo_enabled = settings.is_self_repo_auto_commit_enabled
        except Exception:
            self_repo_enabled = True  # fail-open, matches other flags in this file

        if not self_repo_enabled:
            log.debug(
                "Task %s: SELF_REPO_AUTO_COMMIT_ENABLED=false — running "
                "report-only (no commit/PR)", task.task_id,
            )
            return

        try:
            import agent.agency as _ag
            repo = _ag._gh_repo()
            token = _ag._gh_token()
            if repo and token:
                context["repo_url"] = f"https://github.com/{repo}"
                context["base_branch"] = "master"
                context["github_token"] = token
                context["auto_commit"] = True
            else:
                log.debug(
                    "Task %s: no GitHub repo/token configured — running "
                    "report-only (no commit/PR)", task.task_id,
                )
        except Exception as exc:
            log.debug(
                "Task %s self-repo context resolution failed (continuing "
                "report-only): %s", task.task_id, exc,
            )

    def _resolve_company_repo(self, company_id: str) -> dict[str, Any] | None:
        """Resolve a company's RepoConnection into runtime-ready repo info.

        Returns ``None`` when:
          * The company doesn't exist.
          * The company has no RepoConnection (URL-only company — code work
            pauses ``awaiting_repo_connection`` per the Autonomy Charter).
          * The CompanyGraphStore isn't reachable (lazy load failure).

        Returns a dict with ``repo_url``, ``base_branch``, ``github_token``
        when resolution succeeds. The token is read from env (``GITHUB_TOKEN``
        / ``GH_TOKEN``) — RepoConnection.token_ref is a *reference* into the
        secrets store, never the token itself, so we resolve it the same way
        ``mcp_server.workspace.Workspace.clone`` does.
        """
        try:
            store = self._company_graph_store
            if store is None:
                # Lazy-load the singleton on first use. Wrapped in try/except
                # so a deploy without Mongo (or with the company feature off)
                # degrades gracefully — the task runs against the agency
                # checkout as before.
                from services.company_graph_store import get_company_graph_store
                store = get_company_graph_store()
                self._company_graph_store = store

            company = None
            try:
                company = store.get_company(company_id)
            except TypeError:
                # Some store impls are async — try the async path.
                import asyncio as _asyncio
                try:
                    loop = _asyncio.get_event_loop()
                    if loop.is_running():
                        # We're inside an event loop already; can't call run
                        # until. Fall through to None — the runtime will run
                        # against the default workspace.
                        company = None
                    else:
                        company = _asyncio.run(store.get_company(company_id))
                except Exception:
                    company = None
            if company is None:
                return None

            repo_conn = getattr(company, "repo_connection", None)
            if repo_conn is None:
                return None

            owner = getattr(repo_conn, "owner", None)
            repo = getattr(repo_conn, "repo", None)
            if not owner or not repo:
                return None

            repo_url = f"https://github.com/{owner}/{repo}"
            base_branch = getattr(repo_conn, "default_branch", "main") or "main"
            github_token = (
                os.environ.get("GITHUB_TOKEN")
                or os.environ.get("GH_TOKEN")
                or ""
            )
            return {
                "repo_url": repo_url,
                "base_branch": base_branch,
                "github_token": github_token,
            }
        except Exception as exc:
            log.debug(
                "company repo resolution failed for %s: %s",
                company_id, exc,
            )
            return None

    async def _apply_result(self, task: Task, agent: AgentDefinition | None, result: TaskResult) -> None:
        metadata = result.metadata or {}
        actor = f"agent:{agent.agent_id}" if agent else f"runtime:{result.runtime_id}"
        task.add_log(
            "Execution completed" if result.success else "Execution failed",
            event_type="execution_finished" if result.success else "execution_failed",
            actor=actor,
            task_status=task.status,
            runtime_id=result.runtime_id,
            model_used=result.model_used,
            tokens=result.tokens_used,
            raw_trace=metadata.get("raw_trace"),
            metadata={
                "provider_used": result.provider_used,
                "artifacts": result.artifacts,
                "tool_calls": result.tool_calls,
                "execution_time_ms": result.execution_time_ms,
            },
        )

        if not result.success:
            task.error_message = result.output
            # Post the agent_comment as a task comment EVEN on the FAILED path
            # so the operator can see the per-step failure details (the
            # "report" field from agent/loop.py::_build_report). Without this,
            # a failed task shows only the terse error_message and the
            # detailed failure analysis is silently dropped.
            agent_comment = metadata.get("agent_comment")
            if agent_comment:
                self.workflow.add_comment(task, author=actor, body=agent_comment)
            self.workflow.transition(
                task,
                TaskStatus.FAILED,
                actor=actor,
                message=f"Execution failed on runtime {result.runtime_id}",
            )
            return

        agent_comment = metadata.get("agent_comment")
        if agent_comment:
            self.workflow.add_comment(task, author=actor, body=agent_comment)

        next_status = metadata.get("task_status")
        if task.requires_approval and next_status in (None, TaskStatus.DONE.value):
            next_status = TaskStatus.IN_REVIEW.value
            metadata.setdefault("review_reason", "Awaiting approval before completion")

        if next_status == TaskStatus.BLOCKED.value:
            self.workflow.transition(
                task,
                TaskStatus.BLOCKED,
                actor=actor,
                blocked_reason=metadata.get("blocked_reason") or "Agent reported a blocker",
                message=f"Execution blocked on runtime {result.runtime_id}",
            )
        elif next_status == TaskStatus.IN_REVIEW.value:
            self.workflow.transition(
                task,
                TaskStatus.IN_REVIEW,
                actor=actor,
                review_reason=metadata.get("review_reason") or "Awaiting review",
                message=f"Execution finished and moved to review on runtime {result.runtime_id}",
            )
        else:
            self.workflow.transition(
                task,
                TaskStatus.DONE,
                actor=actor,
                message=f"Execution finished successfully on runtime {result.runtime_id}",
            )

    def _compose_instruction(self, task: Task, agent: AgentDefinition | None) -> str:
        parts: list[str] = []
        # BUG-07 fix: the system prompt is already available to the runtime via
        # _build_spec()'s context.agent.system_prompt field. Prepending it here
        # bloated task comments and logs with the full agent system prompt, making
        # them unreadable. The instruction should carry only task-specific content.
        parts.append(f"Task title: {task.title}")
        if task.description:
            parts.append(f"Task description:\n{task.description.strip()}")
        if task.prompt:
            parts.append(f"Task prompt:\n{task.prompt.strip()}")
        if task.comments:
            comment_lines = [
                f"- {comment.author}: {comment.body}"
                for comment in task.comments[-10:]
            ]
            parts.append("Task discussion:\n" + "\n".join(comment_lines))
        if task.review_reason:
            parts.append(f"Review context:\n{task.review_reason}")
        if task.blocked_reason:
            parts.append(f"Blocked context:\n{task.blocked_reason}")
        return "\n\n".join(parts)

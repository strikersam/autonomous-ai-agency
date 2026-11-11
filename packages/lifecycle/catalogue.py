"""packages/lifecycle/catalogue.py — every status field, declared once.

Each entry names the module that owns the states, the states themselves, the
moves the code actually makes, and the resting states.  The declarations are
data: no domain module is imported, so this file stays cheap to load from a
CLI, a test or an agent sandbox.

Where a lifecycle has drifted (a state written but not declared, or two
declarations of the same field disagreeing), the entry's ``notes`` says so and
``FINDINGS`` records it.  Findings are reported, not silently fixed: changing
an observable status is a separate, reviewed change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from packages.lifecycle.machine import StateMachine
from packages.lifecycle.registry import register

__all__ = [
    "AGENT_JOB_LIFECYCLE",
    "APPROVAL_GATE_LIFECYCLE",
    "BOUNTY_LIFECYCLE",
    "CATALOGUE_FINDINGS",
    "CEO_ATTEMPT_LIFECYCLE",
    "CEO_GOAL_LIFECYCLE",
    "CEO_SUBTASK_LIFECYCLE",
    "CatalogueFinding",
    "DIRECT_CHAT_LIFECYCLE",
    "GOVERNANCE_APPROVAL_LIFECYCLE",
    "HEAL_LIFECYCLE",
    "ONBOARDING_LIFECYCLE",
    "ONBOARDING_PROGRESS_LIFECYCLE",
    "SCAN_LIFECYCLE",
    "SPEC_LIFECYCLE",
    "SPECIALIST_LIFECYCLE",
    "TASK_LIFECYCLE",
    "TASK_QUEUE_JOB_LIFECYCLE",
    "TASK_WORKFLOW_PHASE_LIFECYCLE",
    "WORKFLOW_PHASE_LIFECYCLE",
    "WORKFLOW_RUN_LIFECYCLE",
    "WORKFLOW_SLICE_LIFECYCLE",
    "WORKSPACE_LIFECYCLE",
]


def _declare(
    name: str,
    *,
    states: str,
    initial: str,
    transitions: Mapping[str, str],
    owner: str,
    description: str,
    terminal: str = "",
    notes: Sequence[str] = (),
    status_type: str | None = None,
) -> StateMachine:
    """Build and register one machine from comma-separated state lists.

    The compact syntax keeps the table readable: ``"todo: in_progress, blocked"``
    reads the way a person says the lifecycle out loud.  Every declared state
    must appear as a key, including resting ones (as ``"done:"``), so an
    omitted entry fails loudly at import instead of silently meaning "no moves".
    """
    state_set = frozenset(_split(states))
    parsed: dict[str, frozenset[str]] = {}
    for source, targets in transitions.items():
        if source not in state_set:
            raise ValueError(f"{name}: transition source {source!r} is not a declared state")
        parsed[source] = frozenset(_split(targets))
    missing = state_set - set(parsed)
    if missing:
        raise ValueError(f"{name}: no transition entry for {sorted(missing)}")
    return register(
        StateMachine(
            name=name,
            states=state_set,
            initial=initial,
            transitions=parsed,
            owner=owner,
            description=description,
            terminal=frozenset(_split(terminal)),
            notes=tuple(notes),
            status_type=status_type,
        )
    )


def _split(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in str(value or "").split(",") if part.strip())


# ── Task lifecycle ───────────────────────────────────────────────────────────

TASK_LIFECYCLE = _declare(
    "task",
    states=(
        "todo, in_progress, in_review, blocked, needs_clarification, done, failed, wont_do"
    ),
    initial="todo",
    transitions={
        "todo": "in_progress, blocked, failed, wont_do",
        "in_progress": "in_review, blocked, done, failed, wont_do",
        "in_review": "in_progress, blocked, done, failed, wont_do",
        "blocked": "in_progress, failed, wont_do",
        "needs_clarification": "todo, in_progress, blocked, failed, done, wont_do",
        "done": "in_progress",
        "failed": "todo, in_progress, blocked, wont_do",
        "wont_do": "todo, in_progress",
    },
    terminal="done, wont_do",
    status_type="tasks.models:TaskStatus",
    owner="tasks/service.py (Task.status)",
    description=(
        "A task's visible status, from creation through execution and review to a "
        "resting outcome. DONE and WONT_DO are resting states with an explicit "
        "re-open edge because Retry must always work."
    ),
    notes=(
        "WONT_DO means a person declined the work; it must not read as FAILED.",
        "ALLOWED_TRANSITIONS in tasks/service.py is derived from this declaration.",
        "needs_clarification has no incoming edge: tasks/api.py writes the field "
        "directly in clarify_task (see \"Clarifying a task bypasses its legal-transition table\").",
    ),
)

TASK_WORKFLOW_PHASE_LIFECYCLE = _declare(
    "task_workflow_phase",
    states=(
        "classify, plan, select_specialist, preflight, execute, verify, judge, "
        "summarize, done, failed, blocked"
    ),
    initial="classify",
    transitions={
        "classify": "plan, failed",
        "plan": "select_specialist, failed",
        "select_specialist": "preflight, failed",
        "preflight": "execute, blocked, failed",
        "execute": "verify, failed",
        "verify": "judge, failed",
        "judge": "summarize, failed",
        "summarize": "done, failed",
        "done": "",
        "failed": "",
        "blocked": "",
    },
    terminal="done, failed, blocked",
    status_type="agent.workflow:WorkflowPhase",
    owner="agent/workflow.py (Task.workflow_phase)",
    description=(
        "The persisted phase of a task's execution pipeline, written to the task "
        "store before each advance so a crash resumes at a known phase."
    ),
    notes=(
        "Any phase becomes FAILED on an exception; preflight alone can BLOCK.",
        "This is a second, independent notion of done/failed/blocked on the same "
        "task as Task.status (see \"One task carries two independent lifecycle phases\").",
    ),
)

# ── CRISPY workflow engine ───────────────────────────────────────────────────

WORKFLOW_RUN_LIFECYCLE = _declare(
    "workflow_run",
    states=(
        "pending, context, research, investigate, structure, plan, awaiting_approval, "
        "executing, reviewing, verifying, done, failed, cancelled"
    ),
    initial="pending",
    transitions={
        "pending": "context, failed, cancelled",
        "context": "research, failed, cancelled",
        "research": "investigate, failed, cancelled",
        "investigate": "structure, failed, cancelled",
        "structure": "plan, failed, cancelled",
        "plan": "awaiting_approval, failed, cancelled",
        "awaiting_approval": "executing, failed, cancelled",
        "executing": "reviewing, verifying, done, failed, cancelled",
        "reviewing": "verifying, executing, done, failed, cancelled",
        "verifying": "executing, done, failed, cancelled",
        "done": "executing",
        "failed": "executing",
        "cancelled": "",
    },
    terminal="done, failed, cancelled",
    status_type="workflow.models:WorkflowStatus",
    owner="workflow/models.py (WorkflowRun.status)",
    description=(
        "A CRISPY build run: pre-gate phases, the hard human approval gate, then "
        "slice execution and a final report."
    ),
    notes=(
        "The gate is mandatory: only approve() moves awaiting_approval to executing.",
        "The engine sets reviewing and verifying around each slice's review and "
        "verify stages, then returns to executing; the post-gate 'report' phase "
        "does not change the run status.",
        "done -> executing re-runs a slice with force; failed -> executing resumes a "
        "failed run.",
    ),
)

WORKFLOW_PHASE_LIFECYCLE = _declare(
    "workflow_phase",
    states="pending, running, done, failed, skipped",
    initial="pending",
    transitions={
        "pending": "running, skipped",
        "running": "done, failed",
        "done": "",
        "failed": "",
        "skipped": "",
    },
    terminal="done, failed, skipped",
    status_type="workflow.models:PhaseStatus",
    owner="workflow/models.py (Phase.status)",
    description="One named phase inside a workflow run.",
    notes=("'skipped' is declared but no writer in workflow/ sets it.",),
)

WORKFLOW_SLICE_LIFECYCLE = _declare(
    "workflow_slice",
    states="pending, running, applied, failed, skipped",
    initial="pending",
    transitions={
        "pending": "running, skipped",
        "running": "applied, failed",
        "applied": "running",
        "failed": "",
        "skipped": "",
    },
    terminal="applied, failed, skipped",
    status_type="workflow.models:SliceStatus",
    owner="workflow/models.py (Slice.status)",
    description=(
        "One independently deliverable slice: execute, review, verify, then applied "
        "or failed. A forced re-run moves an applied slice back to running."
    ),
    notes=("'skipped' is declared but no writer in workflow/ sets it.",),
)

APPROVAL_GATE_LIFECYCLE = _declare(
    "approval_gate",
    states="pending, approved, rejected",
    initial="pending",
    transitions={"pending": "approved, rejected", "approved": "", "rejected": ""},
    terminal="approved, rejected",
    owner="workflow/models.py (ApprovalGate.status)",
    description="The hard human gate between a plan and its execution.",
)

# ── CEO ledger ───────────────────────────────────────────────────────────────

CEO_GOAL_LIFECYCLE = _declare(
    "ceo_goal",
    states="open, closed, abandoned",
    initial="open",
    transitions={"open": "closed, abandoned", "closed": "", "abandoned": ""},
    terminal="closed, abandoned",
    owner="services/ceo_ledger.py (GoalRecord.state)",
    description=(
        "A goal the CEO has taken ownership of. Only the 24x7 supervisor abandons "
        "one; a failed drive leaves the goal open for it to re-drive."
    ),
    notes=(
        "ABANDONED is deliberately distinct from CLOSED so a failure is never "
        "presented as success.",
    ),
)

CEO_SUBTASK_LIFECYCLE = _declare(
    "ceo_subtask",
    states="pending, running, done, failed",
    initial="pending",
    transitions={
        "pending": "running",
        "running": "done, failed",
        "done": "",
        "failed": "running",
    },
    terminal="done",
    owner="services/ceo_ledger.py (SubtaskRecord.status)",
    description="One delegated piece of a CEO goal, with every attempt recorded.",
    notes=("A failed subtask is retried on a supervisor re-drive, hence failed -> running.",),
)

CEO_ATTEMPT_LIFECYCLE = _declare(
    "ceo_attempt",
    states="running, accepted, rejected, error",
    initial="running",
    transitions={
        "running": "accepted, rejected, error",
        "accepted": "",
        "rejected": "",
        "error": "",
    },
    terminal="accepted, rejected, error",
    owner="services/ceo_ledger.py (Attempt.status)",
    description="One delegation of one subtask to one model tier.",
)

# ── Workspaces ───────────────────────────────────────────────────────────────

WORKSPACE_LIFECYCLE = _declare(
    "workspace",
    states=(
        "creating, ready, active, paused, completed, failed, cancelling, cancelled, "
        "archived, cleaned"
    ),
    initial="creating",
    transitions={
        "creating": "ready, failed, cancelling",
        "ready": "active, completed, failed, cancelling",
        "active": "paused, completed, failed, cancelling",
        "paused": "active, completed, failed, cancelling",
        "completed": "archived, cleaned",
        "failed": "archived, cleaned",
        "cancelling": "cancelled, failed",
        "cancelled": "archived, cleaned",
        "archived": "cleaned",
        "cleaned": "",
    },
    terminal="completed, failed, cancelled, archived, cleaned",
    status_type="agent.workspace:WorkspaceStatus",
    owner="workspace/manifest.py (WorkspaceManifest.status)",
    description=(
        "An isolated agent workspace: created, activated, optionally paused, then "
        "completed/failed/cancelled, archived and eventually cleaned."
    ),
    notes=(
        "archive() and cleanup are guarded by CLEANABLE_STATES; pause/complete/fail/"
        "cancel accept any current status.",
        "agent/workspace.py imports RESUMABLE_STATES and ACTIVE_STATES from this "
        "module, so both managers answer resume and cleanup questions identically.",
    ),
)

# ── Self-healing ─────────────────────────────────────────────────────────────

HEAL_LIFECYCLE = _declare(
    "heal",
    states="detected, fixing, verifying, resolved, regressed, awaiting_human",
    initial="detected",
    transitions={
        "detected": "fixing, verifying, awaiting_human",
        "fixing": "verifying, awaiting_human",
        "verifying": "resolved, regressed, awaiting_human",
        "regressed": "fixing, awaiting_human",
        "resolved": "",
        "awaiting_human": "",
    },
    terminal="resolved, awaiting_human",
    status_type="agent.self_healing:HealState",
    owner="agent/self_healing.py (HealingEvent.state)",
    description=(
        "A CI failure or bug report driven from detection to a fix that survives a "
        "quiet verification window, or escalated to a person."
    ),
    notes=(
        "A recurrence during verification marks the heal REGRESSED and re-fixes it "
        "until HEAL_MAX_ATTEMPTS, then escalates.",
    ),
)

# ── Agent jobs and direct chat ───────────────────────────────────────────────

AGENT_JOB_LIFECYCLE = _declare(
    "agent_job",
    states="queued, running, succeeded, failed, cancelled",
    initial="queued",
    transitions={
        "queued": "running, cancelled",
        "running": "succeeded, failed, cancelled",
        "succeeded": "",
        "failed": "",
        "cancelled": "",
    },
    terminal="succeeded, failed, cancelled",
    owner="agent/job_manager.py (AgentJob.status)",
    description="A background agent job: accepted, run, then settled or cancelled.",
)

DIRECT_CHAT_LIFECYCLE = _declare(
    "direct_chat",
    states=(
        "assistant_reply, working, needs_input, needs_approval, completed, "
        "failed_with_fix_hint"
    ),
    initial="assistant_reply",
    transitions={
        "assistant_reply": "working",
        "working": "needs_input, needs_approval, completed, failed_with_fix_hint",
        "needs_input": "working, completed, failed_with_fix_hint",
        "needs_approval": "working, completed, failed_with_fix_hint",
        "completed": "",
        "failed_with_fix_hint": "working, completed",
    },
    terminal="completed",
    status_type="agent.schemas:DirectChatState",
    owner="agent/schemas.py (DirectChatState)",
    description=(
        "What the direct-chat surface shows the user while an agent job is running. "
        "It is a view over agent_job, not a second job record."
    ),
    notes=(
        "direct_chat.py maps job running -> working, succeeded -> completed, "
        "failed -> failed_with_fix_hint.",
    ),
)

# ── Specs, bounties, onboarding ──────────────────────────────────────────────

SPEC_LIFECYCLE = _declare(
    "spec",
    states="pending, approved, rejected, skipped",
    initial="pending",
    transitions={
        "pending": "approved, rejected, skipped",
        "approved": "",
        "rejected": "",
        "skipped": "",
    },
    terminal="approved, rejected, skipped",
    owner="services/spec_store.py (spec.status)",
    description=(
        "A reviewable plan spec. Runs are auto-approved unless "
        "AGENT_SPEC_APPROVAL_REQUIRED is on, in which case execution waits here."
    ),
    notes=(
        "set_spec_status validates the status name but not the move, so it can "
        "re-decide an already-decided spec.",
        "A fresh spec is created already approved unless "
        "AGENT_SPEC_APPROVAL_REQUIRED is on, so 'pending' is the initial state "
        "only in that mode.",
    ),
)

BOUNTY_LIFECYCLE = _declare(
    "bounty",
    states="failed, awaiting-review, declined, submitted, merged, paid, lost",
    initial="failed",
    transitions={
        "failed": "",
        "awaiting-review": "submitted, declined, lost",
        "declined": "",
        "submitted": "merged, lost",
        "merged": "paid, lost",
        "paid": "",
        "lost": "",
    },
    terminal="failed, declined, paid, lost",
    status_type="packages.bounty.models:BountyState",
    owner="packages/bounty/models.py (HuntRecord.state)",
    description=(
        "One bounty attempt: solved and parked for a person to approve, then "
        "submitted upstream and swept until merged and paid, or lost."
    ),
    notes=(
        "attempt() creates the record as FAILED and only a successful publish moves "
        "it to awaiting-review; every failure keeps the initial value.",
        "Nothing is submitted upstream until the operator approves the tracking issue.",
    ),
)

ONBOARDING_LIFECYCLE = _declare(
    "onboarding",
    states=(
        "not_started, scanning, detected, configured, in_progress, paused, failed, "
        "cancelled, complete, archived"
    ),
    initial="not_started",
    transitions={
        "not_started": "in_progress, cancelled",
        "in_progress": "scanning, detected, configured, paused, failed, cancelled, complete",
        "scanning": "detected, configured, paused, failed, cancelled",
        "detected": "configured, paused, failed, cancelled",
        "configured": "paused, failed, cancelled, complete",
        "paused": "in_progress, failed, cancelled",
        "failed": "in_progress, cancelled",
        "cancelled": "",
        "complete": "archived",
        "archived": "",
    },
    terminal="cancelled, complete, archived",
    owner="models/company_graph.py (Company.onboarding_status)",
    description=(
        "A company's onboarding: create, scan websites and repos, detect systems, "
        "provision specialists, activate the agency."
    ),
    notes=(
        "services/onboarding.py writes in_progress, scanning, detected, configured, "
        "paused, failed, cancelled and complete as the run advances, and the progress "
        "view reports scanning/detected/configured as in_progress at that phase.",
        "'archived' is legacy data from an earlier deploy, repaired by self_bootstrap.",
    ),
)

ONBOARDING_PROGRESS_LIFECYCLE = _declare(
    "onboarding_progress",
    states="not_started, in_progress, paused, completed, failed, cancelled",
    initial="not_started",
    transitions={
        "not_started": "in_progress, cancelled",
        "in_progress": "paused, completed, failed, cancelled",
        "paused": "in_progress, cancelled",
        "failed": "in_progress, cancelled",
        "completed": "",
        "cancelled": "",
    },
    terminal="completed, cancelled",
    owner="models/company_graph.py (OnboardingProgress.status)",
    description=(
        "The API-facing progress view for onboarding. Its vocabulary differs from "
        "Company.onboarding_status ('completed' vs 'complete'), deliberately, so the "
        "two must be read through their own types."
    ),
)

SCAN_LIFECYCLE = _declare(
    "scan",
    states="pending, success, partial, failed",
    initial="pending",
    transitions={"pending": "success, partial, failed", "success": "", "partial": "", "failed": ""},
    terminal="success, partial, failed",
    owner="models/company_graph.py (Website.scan_status, RepoScanResult.status)",
    description=(
        "A website or repository scan. 'partial' means enough was detected to be "
        "useful and the gaps are reported in errors."
    ),
)

# ── Governance and queues ───────────────────────────────────────────────────

GOVERNANCE_APPROVAL_LIFECYCLE = _declare(
    "governance_approval",
    states="pending, approved, denied, expired",
    initial="pending",
    transitions={
        "pending": "approved, denied, expired",
        "approved": "",
        "denied": "",
        "expired": "",
    },
    terminal="approved, denied, expired",
    status_type="packages.governance.approvals:ApprovalStatus",
    owner="packages/governance/approvals.py (ApprovalStatus)",
    description=(
        "A human decision on a high-risk agent action. Waiting is bounded: an "
        "unanswered request expires, and expiry denies."
    ),
)

TASK_QUEUE_JOB_LIFECYCLE = _declare(
    "task_queue_job",
    states="pending, running, done, failed, cancelled",
    initial="pending",
    transitions={
        "pending": "running, cancelled",
        "running": "done, failed, cancelled",
        "done": "",
        "failed": "",
        "cancelled": "",
    },
    terminal="done, failed, cancelled",
    owner="services/task_queue.py (PrioritizedTask.status)",
    description="A queued background task executed by the in-process worker pool.",
)

SPECIALIST_LIFECYCLE = _declare(
    "specialist",
    states="available, busy, error, disabled",
    initial="available",
    transitions={
        "available": "busy, error, disabled",
        "busy": "available, error, disabled",
        "error": "available, disabled",
        "disabled": "available",
    },
    terminal="disabled",
    owner="models/company_graph.py (Specialist.status)",
    description=(
        "Whether a provisioned specialist can take work. Readers filter on these "
        "four values; no single writer owns the transitions."
    ),
    notes=(
        "Provisioning writes 'available'; company/agency code filters available, "
        "busy and disabled. The moves marked here are the field's intent, not an "
        "enforced transition table.",
    ),
)


# ── Findings ────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CatalogueFinding:
    """A drift or ambiguity found while mapping the lifecycles.

    Findings are documentation, not defects fixed by this change: an observable
    status must not change without its own review.
    """

    title: str
    detail: str
    machines: tuple[str, ...] = ()


CATALOGUE_FINDINGS: tuple[CatalogueFinding, ...] = (
    CatalogueFinding(
        title="One task carries two independent lifecycle phases",
        detail=(
            "`Task.status` (todo/in_progress/.../done) and `Task.workflow_phase` "
            "(classify/plan/.../done/failed/blocked) both describe where a task is, "
            "both have a `done`, a `failed` and a `blocked`, and they are written by "
            "different components. A reader must consult both to answer \"what is "
            "this task doing?\", and they can disagree (status IN_REVIEW while the "
            "workflow phase is DONE). No change here; the mapping makes the dual "
            "state explicit."
        ),
        machines=("task", "task_workflow_phase"),
    ),
    CatalogueFinding(
        title="Clarifying a task bypasses its legal-transition table",
        detail=(
            "`tasks/api.py` sets `task.status = TaskStatus.NEEDS_CLARIFICATION` "
            "directly, and no state in `ALLOWED_TRANSITIONS` has "
            "needs_clarification as a target. The state is therefore reachable only "
            "through that endpoint, and the transition guard cannot check the move. "
            "Kept as-is for behaviour compatibility; recorded so the next change to "
            "the task lifecycle does not assume every state has an incoming edge."
        ),
        machines=("task",),
    ),
)

# Unattended approval: deny-and-continue vs. park-and-wait

**Status:** design note only — nothing here is implemented, and this note deliberately stops
before the first code change.
**Date:** 2026-11-12
**Backlog:** item 4 of #1892 (routine backlog 2026-W46).
**Sensitivity:** gate-adjacent. `agent/tools.py` and the approval path are rule-15 risky
modules, and bug 16 (P0 gate bypass, DEFERRED) lives on this same path, so a human has to
decide before any of this is built.

## Why this was raised

Claude Code 2.1.319 added `permissions.denyInsteadOfPrompting`: a call that would wait on a
prompt is denied instead, and the turn carries on (terminal, subagents, teammates). The
appeal here is the number in the 2026-11-07 changelog — 283 of 483 tasks blocked — where
some unknown share is work that stopped because a gate was waiting for a person nobody had
told.

## What the code does today

The gate is **task-level and pre-dispatch**, not tool-level and mid-turn. That distinction
is the whole design question, so it is worth stating precisely.

- `tasks/service.py` dispatch (`~line 857`) checks `task.requires_approval and not
  task.execution_approved` **before** an agent, runtime or worktree is resolved. When the
  condition holds it sets `pending_agent_run = False`, writes `review_reason = "⏸ Awaiting
  human approval before execution (requires_approval)."`, logs an `approval_gate` event,
  sends one Telegram heads-up, and returns.
- `approve_execution()` (`~line 346`) is the only way through: approve → `execution_approved
  = True`, transition to `IN_PROGRESS`, `pending_agent_run = True`; reject → `WONT_DO` (never
  `BLOCKED`/`FAILED`, deliberately, so the auto-retry reconciler and the blocked-backlog
  retirement cannot sweep a human's decision).
- `packages/scheduler/scheduler.py` and `schedules/api.py` only carry the flag through
  (`approval_gate` → `requires_approval`); they do not decide anything.
- Outward-facing autonomous work can be auto-promoted to `requires_approval` on first
  dispatch (`~line 843`) when `AGENCY_GATE_OUTWARD_FACING` is on, so the parked population
  includes work that was never flagged by a human in the first place.

So there is no step "waiting on a prompt" inside a running turn, as there is in Claude Code.
A gated task never starts. The observable failure is not a hung turn but a queue entry that
sits at TODO with a review reason until a person notices — which is consistent with a large
blocked population and with the fear that unattended runs "refuse work".

What is **not** established: what fraction of parked tasks are unattended runs versus tasks
a human simply has not got to, and whether any parked task is re-picked, re-parked and
re-notified in a loop. Both are measurable from `execution_log` (`approval_gate`,
`approval_decision` events) without touching the gate.

## What "deny-and-continue" could mean here

Three shapes, in ascending order of risk. None is recommended yet.

**A. Keep the gate, change the accounting.** Parking becomes a first-class terminal-ish
state with a machine-readable reason (`denied: requires_approval`, plus the derived "why"
from `_needs_approval` tags) instead of a `review_reason` that reads as an instruction to a
human. The task shows up as gated rather than silently pending, and the blocked-backlog
number becomes explainable. No policy change, no gate change, no new bypass surface. This is
the only option that cannot weaken the gate.

**B. Deny the gated *action* and continue the rest of the run.** The turn proceeds but the
gated step returns a denial the model can see, and the task completes with an explicit
`denied_actions` list instead of a partial success. This is the closest analogue to
`denyInsteadOfPrompting`. It requires a tool-level gate that does not exist today: the
current gate is evaluated once, for the whole task, before any tool call is possible.
Introducing a second, later gate is exactly where bug 16 (P0 gate bypass) lives, and a
denial that arrives mid-run can leave outward-facing side effects half-done.

**C. Auto-approve when no human is present.** Not a reading of the source proposal — it says
*deny* rather than *wait* — and the wrong one to take. It inverts the charter gate.

## Invariants any implementation must keep

1. A denial is never an approval. No code path may set `execution_approved = True` except
   `approve_execution()` called by a human actor.
2. A gated task must not perform its gated action and then report success. If a run denies
   a step, the task's outcome says so in a field a caller can branch on.
3. Rejection stays `WONT_DO`. Parking stays reversible. Denial must not become
   `BLOCKED`/`FAILED` and must not enter the auto-retry sweep.
4. Every transition writes an `approval_decision` event with the actor, so the audit trail
   distinguishes a human decision from a policy decision.
5. The pre-dispatch gate keeps running before runtime resolution — a mid-run gate is an
   addition, never a replacement.

## Open questions for a human

- Is the 283/483 blocked figure caused by this gate at all, or by runtime unavailability?
  Until that is measured, the motivating number is anecdote.
- Should an unattended task that is auto-promoted (never human-flagged) be denied by policy,
  or parked like the rest? The charter's intent and the operator's intent differ here.
- Does deny-and-continue apply to subagents and teammates, which share the loop but not the
  task? The current gate has no view of either.
- What is the acceptable failure mode for a half-completed outward-facing task: deny the
  step and continue, or abort the task? Option B assumes the former; the charter gate's whole
  design assumes the latter.

## Recommendation

Do not implement in the ship routine. If this is picked up, do **A** first — it is a
reporting change on the existing gate, gives the measurement that decides whether B is worth
its risk, and cannot weaken the gate. B needs its own design review with bug 16 on the table.

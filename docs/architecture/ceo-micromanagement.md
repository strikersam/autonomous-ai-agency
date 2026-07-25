# CEO Micro-Management

How the CEO splits work, assigns it, judges it, and drives it to closure —
and what stops the whole thing running away when nobody is watching.

Related: [`agent-orchestration.md`](agent-orchestration.md),
[`golden-path.md`](golden-path.md), [`runtime-model.md`](runtime-model.md).

---

## The problem this solves

The CEO used to delegate and then never look at the work again:

- It split every request the same way — one scout pass, one dev pass —
  regardless of what the request actually was.
- It recorded whatever came back as done. A subtask that returned
  *"all done, the route is now available"* having changed no files was
  indistinguishable from one that worked.
- It had no memory of a delegation once the coroutine ended. A redeploy, a
  Render cold start, or a sleeping runtime mid-fan-out lost the work with
  nothing tracking that it never finished.

The visible symptom was an agency that looked busy and quietly dropped tasks.

---

## The four pieces

| Module | Responsibility |
|--------|----------------|
| `services/ceo_micromanager.py` | Decides: how to split, who gets it, is the result acceptable, what happens if not |
| `services/ceo_dispatcher.py` | Executes: routes each subtask to a runtime, runs the escalation loop |
| `services/ceo_ledger.py` | Remembers: durable record of every goal, subtask, attempt and verdict |
| `services/ceo_supervisor.py` | Watches: 24x7 sweep that closes, re-drives, or abandons open goals |
| `backend/ceo_router.py` | Surfaces: `/api/ceo/*` for operators |

Nothing in `ceo_micromanager.py` executes work — it is pure decision logic, which
is what makes it cheap to test exhaustively.

---

## The tier ladder

Four rungs, cheapest and narrowest first:

| Tier | Steps | Files | Remit |
|------|-------|-------|-------|
| `intern` | 3 | 1 | Implement exactly what the brief says; report blockers rather than guessing |
| `junior` | 6 | 1 | Implement and fix your own errors; stop after three identical failures |
| `midlevel` | 10 | 3 | Choose your own approach within the stated scope |
| `senior` | 20 | 10 | Own the outcome; read as much as correctness requires |

A subtask enters at the rung `starting_tier()` picks — read-only recon starts at
`intern`, security work starts at `senior` regardless of complexity (a cheap
wrong answer there is expensive), everything else keys off the classifier's
complexity — and moves **one rung up** each time its result is rejected.

### Tier does not re-route the role

`resolve_runtime(role, tier, ROLE_RUNTIME_PREFERENCE)` picks the runtime from
the **role's** preference list; the tier only chooses *within* it. The two junior
tiers take the cheapest entry (`internal_agent` where the role permits), midlevel
and above take the role's first and most capable preference.

This matters: deriving the runtime from the tier alone would have silently moved
every dev subtask off `claude_code`, a routing change nobody asked for.
`ROLE_RUNTIME_PREFERENCE` remains the single source of truth for which runtimes
may serve which role.

---

## The subtask brief

Every delegated subtask carries the same seven sections:

```
# Context              the overall goal, this subtask's part in it, upstream results
# Scope                exactly what to accomplish
# Focus                only this work; report anything out of scope, don't act on it
# Outcome              the observable end state
# Completion           report what you actually did, including what failed
# Instruction Priority these instructions outrank general role instructions
# Mode Restriction     do not delegate onward, do not switch role
```

Plus a `# Previous Attempt Failed` section on a re-delegation, so the higher tier
diagnoses rather than repeating what already did not work.

The structure is the point. An agent that receives only *"implement X"* invents
its own scope, and inventing scope is what produces slop. Context isolation is
deliberate: the executing agent sees the goal and its upstream results, never the
CEO's whole conversation.

---

## The anti-slop gate

`assess_quality(plan, result)` runs on every subtask result before it can be
accepted. It is deliberately mechanical rather than an LLM judgement — it runs on
an unattended loop, so it has to be cheap, deterministic, and impossible to talk
out of.

**Hard rejects** (regardless of score):

- the runtime reported failure
- no summary at all
- the summary's **first sentence** is a refusal (*"I am unable to…"*)
- the subtask was expected to change files, the runtime **does** report changed
  files, and it changed none — the strongest slop signal available

**Penalties** (accumulate; accepted at ≥ 0.5):

- summary shorter than `CEO_MIN_OUTPUT_CHARS`
- source files changed but no test file touched
- the runtime cannot report changed files (small penalty; see below)

### Two deliberate narrowings

**Files are only checked when the runtime can answer.** `internal_agent` and
`e2b` report the files they touched; `hermes`, `claude_code` and `goose` return
prose. Applying *"you changed no files"* to a runtime that cannot say would
reject every successful subtask it ran. `_harvest_changed_files()` returns
`(files, reported)` and the gate branches on `reported`.

**Refusals are matched in the first sentence only.** A genuine refusal opens the
message. Scanning the whole summary would reject an honest report for describing
a bug it correctly declined to fix — *"…the legacy shim still logs 'unable to
complete' on timeout, which I left alone as out of scope"* is good work, not a
failure.

---

## Escalation, and why it terminates

```
attempt 1 (intern)  → rejected → escalate
attempt 2 (junior)  → rejected → escalate
attempt 3 (midlevel)→ rejected → budget spent → record hard failure
```

Two independent bounds, both checked inside `decide_escalation()` so no caller
can bypass one:

1. **The ladder.** A subtask at `senior` has nowhere to escalate to.
2. **The attempt budget.** `CEO_MAX_ATTEMPTS_PER_SUBTASK`, clamped to the ladder
   length when read from the environment — an env typo cannot uncap retries.

Worst case for one subtask is 3 executions. A rejected subtask that exhausts its
budget is recorded as `error`, never as done.

---

## The ledger

`services/ceo_ledger.py` follows the dual-backend contract of
`agent/schedule_store.py`: synchronous (written from async handlers *and* the
supervisor's background context), Mongo in production, SQLite in dev/CI,
in-memory when neither is reachable, and no method raises.

The plan is written **before** execution starts. That is what makes closure
trackable: a process that dies mid-fan-out leaves an open goal with pending
subtasks, not nothing at all.

Goal states:

| State | Meaning |
|-------|---------|
| `open` | Subtasks still running or pending — the supervisor owns it |
| `closed` | Every subtask accepted |
| `abandoned` | Budget or age limit spent; a human needs to look |

`closed` and `abandoned` are distinct on purpose. A failure must never read as
success on the dashboard, and the supervisor must not keep re-driving something
already given up on.

---

## The 24x7 supervisor

Wired into `services/background.py` alongside the other autonomy loops, gated by
`CEO_SUPERVISOR_ENABLED` (off under `TESTING`). Each sweep:

1. Force-wakes sleeping runtimes, so an idle Hermes or a spun-down free-tier
   service self-recovers rather than becoming a permanent outage.
2. Loads open goals, most-stalled first.
3. Classifies each one — **close** (all subtasks done) → **abandon** (age or
   intervention budget spent) → **re-drive** (no progress past the stall
   threshold) → **leave alone**. The order matters: closure is checked first so a
   goal that finished just before a stall window is never re-driven, and
   abandonment before re-drive so an exhausted goal cannot buy another attempt by
   also being stalled.

A re-drive calls `delegate(..., goal_id=<existing>)`, reusing the ledger entry
instead of opening a duplicate, and runs as a detached task so one slow goal does
not hold up the sweep. The goal id is claimed in `_driving` **synchronously**,
before the task starts — otherwise a re-drive slower than the sweep interval
would be started again on the next sweep, duplicating the work it was meant to
rescue.

### Four bounds

| Bound | Default | Stops |
|-------|---------|-------|
| `CEO_SUPERVISOR_INTERVAL_S` | 180 | Sweeping hotter than work completes |
| `CEO_SUPERVISOR_STALL_S` | 1800 | Re-driving healthy long-running work |
| `CEO_SUPERVISOR_MAX_INTERVENTIONS` | 3 | A broken goal consuming budget forever |
| `CEO_SUPERVISOR_MAX_GOAL_AGE_S` | 86400 | A goal lingering indefinitely |
| `CEO_SUPERVISOR_MAX_REDRIVES_PER_SWEEP` | 2 | A stampede after a long outage |

All are clamped on read. A failing sweep is logged and the loop continues — the
supervisor keeps everything else alive, so it must be the last thing to die.

**Tuning note:** `stall_s` must comfortably exceed how long a single senior
subtask can legitimately run. Set it too low and the supervisor re-drives healthy
work, doubling spend.

---

## Operator surface

| Route | Auth | Purpose |
|-------|------|---------|
| `GET /api/ceo/status` | user | Supervisor state, ledger aggregates, active config |
| `GET /api/ceo/goals` | user | Recent goals (`?state=open`), headline fields only |
| `GET /api/ceo/goals/{id}` | user | One goal with full subtask and attempt history |
| `POST /api/ceo/sweep` | **admin** | Run one sweep now |
| `POST /api/ceo/goals/{id}/redrive` | **admin** | Force a re-drive |

The two POST routes are admin-only because both start real agent work, which
spends provider tokens. The manual re-drive still honours the intervention cap —
it is not a way around the budget.

---

## Configuration reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `CEO_MAX_SUBTASKS` | `6` | Cap on subtasks per decomposition |
| `CEO_MAX_ATTEMPTS_PER_SUBTASK` | `3` | Attempts per subtask (clamped to ladder length) |
| `CEO_MIN_OUTPUT_CHARS` | `24` | Below this, a summary is penalised as insubstantial |
| `CEO_REQUIRE_TESTS_FOR_CODE` | `true` | Penalise code changes with no test touched |
| `CEO_LLM_DECOMPOSITION` | `true` | Brain-driven split; off under `TESTING` |
| `CEO_DECOMPOSITION_TIMEOUT_S` | `45` | Before falling back to the deterministic split |
| `CEO_ESCALATION_ENABLED` | `true` | Master switch for re-delegation |
| `CEO_SUPERVISOR_ENABLED` | `true` | 24x7 sweep; off under `TESTING` |

Every micro-manager environment read lives in `MicroManagerConfig.from_env()` and
every supervisor read in `SupervisorConfig.from_env()` — a single configuration
boundary per module, per the repository constitution.

---

## Tests

| File | Covers |
|------|--------|
| `tests/test_ceo_micromanager.py` | Ladder, brief structure, decomposition (LLM + fallback + malformed), quality gate, escalation bounds |
| `tests/test_ceo_supervision.py` | Ledger durability and degradation, changed-file harvesting, the escalation loop end to end, all four supervisor classifications |
| `tests/test_ceo_router.py` | Route auth (including the admin gate on both POSTs) and response shapes |
| `tests/test_ceo_dispatcher.py` | Pre-existing fan-out and runtime-routing contract (unchanged) |

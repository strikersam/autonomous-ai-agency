# Enterprise reliability and durable multi agent execution: implementation plan

**Status:** decided, implementation in progress on this branch. Decisions D1 to D5 were
made by Claude under the operator's explicit delegation on 2026-11-14 ("you make all the
decisions ... full autonomous mode"); they are recorded in section 4.
**Date:** 2026-11-14
**Audited at:** `8075306` on `master`.
**Source brief:** "Autonomous AI Agency: Enterprise Reliability and Durable Multi Agent
Execution Upgrade" (operator brief, 18 sections, 10 priorities, 24 failure scenarios).
**Sensitivity:** touches `agent/loop.py`, the approval path and storage schemas. The rule 40
gates and who cleared each are listed in section 4.1.

## 1. What the audit found

Every row below was read from the repo at the commit above. "Not verified" means the
audit did not prove it either way and the first phase must settle it.

### 1.1 The headline finding

The brief says "do not create a second orchestration framework". The repo already has
four, plus two swarm coordinators:

| Module | Lines | Role it claims |
|---|---|---|
| `services/workflow_orchestrator.py` | 1984 | "THE single entry point for ALL agent driven work". Has `WorkflowRun`, `run_id`, phase timeouts, heartbeat, checkpoint, FIFO queue |
| `workflow/engine.py` | 1063 | CRISPY workflow runs with slices, artifacts, approve, resume, cancel, events (`workflow/api.py`) |
| `agent/workflow.py` | 408 | Task phase engine: classify, plan, select specialist, preflight, verify, judge, summarize |
| `agents/workflow_engine.py` | 185 | DAG engine with its own `WorkflowTaskStatus` |
| `agent/coordinator.py` | 330 | `AgentCoordinator` and `MultiAgentSwarm` with a semaphore |
| `agents/swarm.py` | 267 | Second swarm |

Adding parent and child runs, fan out and recovery to all of them would multiply the
problem. **Decision D1 (section 4) picks the one that receives the new work.** The plan
assumes `services/workflow_orchestrator.py`, because it already declares itself canonical
and already owns `run_id`, heartbeat, checkpoint and queue.

### 1.2 Gap matrix

| Capability | Existing implementation | Verified limitations | Proposed change | Tests required |
|---|---|---|---|---|
| Stable run identity | `WorkflowRun.run_id` in `services/workflow_orchestrator.py`; `run_id` in `workflow/models.py`; `Task` carries `company_id` and parent linkage | No single run record shared by the task path and the orchestrator path. The run lease is keyed by `task_id`, not by run | One `RunRecord` (typed, persisted) owned by the canonical orchestrator; task path writes one per dispatch | Create, read, parent and child linkage, backward read of records with no run |
| Run API (new `/api/runs` tree per D1: the only run surface spanning both engines) | `/api/workflow/orchestrator/runs`, `/runs/{run_id}`, `/approve/{run_id}` in `backend/server.py`; `/workflow/{run_id}` with approve, reject, resume, cancel, artifacts, events in `workflow/api.py` | Two run APIs over two engines. No client idempotency key on run creation (only `source_id` dedup on task create in `tasks/store.py`) | New `/api/runs` routes over `packages/runs/`: create, get, events, artifacts, cancel, retry, capabilities, with `Idempotency-Key`. Existing routes keep working unchanged | One test per route; a duplicate key returns the same run; cross company access refused |
| Run lifecycle states | `packages/lifecycle/` declares 21 lifecycles and guards transitions | `workflow_run` belongs to the CRISPY engine; the orchestrator's `WorkflowRun.status` is a free string with no lifecycle | New `RunState` enum in `packages/runs/models.py`, declared as a new `run` lifecycle bound to it; `workflow_run` untouched | `scripts/lifecycles.py check`, legal and illegal move tests |
| Worker ownership and lease | `tasks/run_lease.py`; `TaskStore.acquire_run_lease` / `release_run_lease` | **Process local on every production backend:** `TaskStore._lease_collection()` (`tasks/store.py:152`) returns `None` for any `packages.storage.*` db, and production passes `MongoStore` (`backend/server.py:2909`), so the web process, the worker and `/api/autonomy/tick` can each run the same task. The test uses a fake db type, so it never caught this. TTL is a fixed 3600 s and no renewal function exists. A run longer than one hour can be claimed by a second worker. A crashed holder blocks the task until expiry. SQLite and memory mode use a process local table | Add `renew_run_lease` plus a heartbeat task; shorten TTL to a few heartbeats; fencing token on every state write | Expiry and reacquisition, renewal keeps a long run, stale holder write is rejected |
| Abandoned run detection (enabled only together with the operation ledger, section 2.3) | `TaskDispatcher` reconciler calls `store.reconcile_stranded_tasks` (300 s stale threshold); `services/orchestrator_supervisor.py` requeues stalled runs with no LLM dependency | Two detectors with different thresholds. Interaction between the 300 s reconciler and the 3600 s lease is not verified | One detector driven by lease expiry; the reconciler and supervisor call it | Kill a worker mid run, second worker claims after expiry |
| Queue durability | `services/orchestrator_queue.py` | In process `deque`. Queued runs are lost on restart unless the supervisor finds a checkpoint | Queue state derives from persisted `QUEUED` run records; the deque becomes a cache | Restart with queued runs, none lost, none duplicated |
| Checkpoints (orchestrator) | `services/orchestrator_checkpoint.py` persists to the shared store, `restore_in_flight_runs()` at boot | Falls back to `_NoopDB`, so a deploy with no durable store silently checkpoints nowhere. No schema version | Version field, corruption check, health flag when the store is a no op | Corrupt checkpoint, version migration, no op store reported in health |
| Checkpoints (agent loop) | `agent/checkpoint.py`, called from `agent/loop.py` after plan, after each step and on error | File backed under `.data/checkpoints`, so it does not survive a container replacement. A corrupt latest file returns `None` and does not fall back to the previous file. No schema version | Storage backed checkpoint store behind the same functions; fall back to last good file; version field | Corrupt latest falls back, restore after simulated new container |
| Side effect safety on replay | `agent/action_hash.py` (`action_hash`, `already_executed`) with tests | Not wired into `agent/loop.py`. `_auto_push_and_pr` pushes to `agent/task-{uuid4}` (a new branch per attempt) and opens the PR outside the tool path, so a replay opens a second PR | Durable operation record keyed by action hash; check before push, PR create, email, delete | Recovery after an uncertain push does not push twice |
| Graceful shutdown | `worker_main.py` handles SIGTERM and SIGINT and stops background services | Whether in flight runs are checkpointed and leases released on shutdown is not verified | On signal: stop claiming, checkpoint, release leases, mark runs `RECOVERING` | SIGTERM during a run leaves a claimable run |
| Agent contract | `runtimes/base.py` `RuntimeAdapter` (`execute`, `stream_execute`, `health_check`, `start`, `stop`, `supports`), `TaskSpec`, `TaskResult`; `runtimes/registry.py`, `routing.py` | Adapter has no `cancel`, `resume`, `status` or `list_artifacts`. No versioned agent definition found | Optional capability methods with safe defaults so existing adapters keep working; typed `AgentDefinition` | Contract test run against every registered adapter |
| Fan out, join, conditional | `agent/coordinator.py` semaphore; `agents/workflow_engine.py` DAG | Children have no run record of their own. No parent deadline or cancel propagation found | Parent and child run records, bounded concurrency, depth and count caps, cancel propagation | Parallel children, one child fails, parent cancel reaches children, spawn cap |
| Artifacts | `workflow/artifact_store.py` with id, run id, name, path, content hash, size, created at | Content on the local filesystem and metadata in local SQLite. Lost with the container. No MIME type, producing agent, access or retention policy | Put content behind the existing storage layer (`packages/storage`); add the missing metadata fields | Artifact readable after worker replacement, hash mismatch detected |
| Verification | `tasks/independent_verifier.py`, `tasks/verification.py`, `agent/verification_contract.py`, `agent/verification_evidence.py`, `agent/verification_strategies.py` | Already strong: acceptance criteria, evidence report, failing tests force FAIL. Read only guarantee of the verifier context is not verified. Bounded rework exists (`rework_or_park`) | Keep. Add tests that prove the three "must never" rules; confirm the verifier cannot write | Verifier rejection, missing test result is not a pass, verifier error is not a pass |
| Approvals | `packages/governance/approvals.py` (TTL, expiry denies, named resolver); grants persist to `governance_grants`; task level approval lives on the `Task` record | Pending approval requests are in process **by documented design**: a restart expires them (fail closed). No binding of an approval to an action hash found in `packages/governance/` | Decision D2. If durable: persist requests, bind to action hash and target, invalidate on change | Approval survives restart, expiry denies, changed arguments invalidate |
| Kill switch | `packages/config/autonomy_limits.py` (`AGENCY_KILL_SWITCH`); checked in `tasks/dispatcher.py`, `agent/loop.py` (only in `_commit_step`), `packages/ai/agent_budget.py` | A dashboard flip writes only the saving process's environment (`packages/config/control_overrides.py`); the separate worker sees it only after a restart. Same for every live control | Worker refreshes overrides from the DB (`apply_from_db()`) every lease heartbeat; checked at every step boundary and every heartbeat | Kill switch during an active run stops it within one step |
| Budgets | `packages/ai/agent_budget.py` per agent per day; `packages/llm/budget.py` | In memory, per process, cleared by restart. No aggregate across a parent and its children | Run scoped budget stored on the run record, charged by children against the root run | Delegated children exhaust the parent budget |
| Tenant isolation | `Task.company_id`; `_wfo_owned_run_or_404` in `backend/server.py` | `company_id` is optional on `Task`. Coverage across every run route is not verified | Company scope check in one dependency used by all run routes | Cross company read and cancel are refused |
| Skills catalogue | `harness/skills/` with `CATALOG.md`; skill registry tests exist | No version field found in a spot check of `SKILL.md` files. Pinning per run not found | Add version to skill metadata; record resolved skill versions on the run | Run keeps its pinned version after the skill changes |
| Tracing | `services/otel_tracing.py`, `langfuse_obs.py` | Correlation from parent run to child run to tool call is not verified | Carry `run_id` and `parent_run_id` as span attributes; one trace per root run | Trace for a fan out run contains every child |
| Redaction | `packages/security/redact.py` (`redact_secrets`); `agent/verification_evidence.py` redacts | Coverage of artifacts and run events is not verified | Redact at the single write point for run events, artifact **metadata and text content** (`packages/runs/artifacts.py` runs `redact_secrets` on text content before hashing and storing; binary content is stored as is and marked `redacted: false`) and span attributes | Seeded secret placed in an event payload, in artifact text content, in artifact metadata and in a span attribute never appears in the stored record, the API response or the trace |

### 1.3 What already works and should not be rebuilt

* The claim API shape (`claim_task_run` / `release_task_run`); its Mongo path is fixed, not replaced.
* A supervisor with zero LLM dependency (`services/orchestrator_supervisor.py`).
* Evidence based verification with a contract and a report.
* Approval TTL where expiry denies.
* A declared lifecycle registry with a drift check.
* Transient error requeue with a cap (`_is_transient_error`, `_DISPATCH_RETRY_LIMIT`).

## 2. Delivery

One feature branch (`claude/enterprise-reliability-plan`, PR #1965), built in phases. Each
phase is its own commit (or commits), keeps `pytest` green, is behind a live control
registered in `packages/config/control_catalogue.py` (rule 37) whose default keeps today's
behaviour, and is checked by an independent verifier before the next phase builds on it
(rule 49).

### 2.1 Architecture in one picture

```
            HTTP /api/runs/*            Telegram, dashboard, scheduler, CEO
                    |                                 |
                    v                                 v
         packages/runs/service.py  <---------  tasks/service.py  TaskExecutionCoordinator
           (create, cancel, retry,              services/workflow_orchestrator.py
            idempotency, events)                        |
                    |                                   | write RunRecord, events,
                    v                                   | lease heartbeats, operations
   +--------------- packages/runs/ ----------------------------------------------+
   | models.py   RunRecord, RunState, RunEvent, OperationRecord, ArtifactRef      |
   | store.py    RunStore over packages.storage (Mongo or SQLite) + memory        |
   | lease.py    acquire, renew, release, fencing token, heartbeat task           |
   | recovery.py abandoned run detector, claim, reconcile, resume, dead letter    |
   | operations.py durable side effect ledger keyed by agent/action_hash.py       |
   | budget.py   root run budget charged by every descendant                      |
   | composer.py sequential, parallel, join, conditional, approval, failure policy|
   | artifacts.py durable artifacts (content + metadata) with redaction           |
   | approvals.py durable approvals bound to action hash (wraps governance)       |
   | tracing.py  run and parent run ids on spans                                  |
   +------------------------------------------------------------------------------+
                    |
                    v
   runtimes/  (RuntimeAdapter; optional cancel, status, list_artifacts with safe defaults)
```

`packages/runs/` is a persistence and lifecycle layer, not a fifth orchestration engine:
the existing engines keep deciding *what* to do, and record *that it happened* there.
The composer executes each child through the existing `TaskExecutionCoordinator`, so a
child is an ordinary task with a child `RunRecord`.

### 2.2 Phases

| Phase | Content | Controls (default) |
|---|---|---|
| 0 | Test baseline on `master`; decisions recorded; plan reviewed by an independent verifier | none |
| 1 | `packages/runs/` models, store, events, idempotency, lease with renewal and fencing, operation ledger; collections registered for SQLite | `RUNS_LEDGER_ENABLED` (on: record only, changes no decision) |
| 2 | Task path and orchestrator write runs; heartbeat renews lease (TTL 120 s, renew every 30 s); recovery detector **and** operation ledger reconciliation land together; graceful shutdown; versioned checkpoints with corruption fallback | `RUNS_RECOVERY_ENABLED` (off until verified, then on) |
| 3 | `/api/runs` routes: create (returns at once), get, events, artifacts, cancel, retry, capabilities; `Idempotency-Key` | none (new surface) |
| 4 | Composer: fan out with concurrency cap, join, conditional, approval pause, failure policy, deadlines, cancel propagation, depth and child caps; root run budget; kill switch checked at every heartbeat | `RUNS_MAX_CHILDREN`, `RUNS_MAX_DEPTH`, `RUNS_MAX_PARALLEL` |
| 5 | Durable artifacts with redaction; verification hardening tests; durable approvals bound to action hash | `RUNS_DURABLE_APPROVALS` (on) |
| 6 | Skill version pinning on the run; trace correlation; dashboard run view | none |
| 7 | Reference workflows A, B, C on deterministic fixtures; the 24 scenario reliability suite; runbook, configuration and API docs | none |

### 2.3 Recovery protocol (revision 3)

Recovery is never enabled without the operation ledger. The rules, in order:

**One lease, one fencing token.** The lease lives in `task_run_leases`, keyed by `task_id`
for task runs and by `run:<run_id>` for orchestrator runs. The document carries `holder`,
`run_id`, `token` (an integer incremented on every successful acquire) and `expires_at`.
`claim_task_run` returns that token. `packages/runs/lease.py` is the only code that writes
the document; `TaskStore.acquire_run_lease` delegates to it. On Mongo it uses the raw motor
collection (unwrapping `MongoStore`); on SQLite it uses the new single statement helpers,
with `task_run_leases` added to `_COLLECTIONS`; memory mode stays process local. The `shared_state` claim taken first in `claim_task_run`
(Redis when `REDIS_URL` is set) is skipped whenever the durable lease is available, so it
can never hold a recovered task beyond the lease's own expiry.

**Stable run identity.** A dispatch that resumes an interrupted run reuses the same `run_id`
and increments `attempt`. Only an explicit retry of a terminal run (`POST .../retry`)
creates a new `run_id`, linked by `retry_of`. The push branch is derived from `task_id`
(`agent/task-<task_id>`), so every attempt targets the same branch; a reused branch is never
force pushed.

**Ledger records.** Each side effecting call writes an `OperationRecord` keyed by
`(run_id, seq)`. `seq` comes from `atomic_increment` on the run record, so it is monotonic
and never reused across attempts. The record stores `action_hash(tool, args)`, the target
(repository, branch, commit SHA computed before the push, recipient), `token`, `state` and
`op_deadline`.

**Executing a side effect.**
1. Renew the lease. Refuse the call unless the lease has more time left than the
   operation's timeout.
2. Insert the record as `pending`, then compare and set it to `executing` with the current
   token and `op_deadline = now + op_timeout`. A stale token fails the compare and set and
   the worker stops.
3. Re-check `now < op_deadline`, then perform the effect under a hard timeout that kills
   any subprocess it started, then set `committed` (with the result reference) or
   `failed`. `op_deadline` includes a clock skew margin (30 s).
4. A record still `pending` (never moved to `executing`) means the effect never started:
   recovery marks it `failed` and it may run again. Only `executing` records are
   reconciled.

**Recovering a run.**
1. A worker claims the expired lease and gets a higher token. From then on, writes to
   `runs` and `run_operations` with the old token fail.
2. Every record of the run in `pending` or `executing` is reconciled before any step runs.
   The reconciler returns `unknown` until `op_deadline` has passed, so it never races a
   stale holder still inside the call. After the deadline it asks the outside world: git
   push, does the remote branch hold the recorded SHA; PR create, is there an open PR from
   the head branch; anything without a reconciler, `unknown`. A reconciler may answer
   `not_done` only for operations the remote end makes safe to repeat (re-pushing the same
   SHA is a no-op, a non force push that diverges is rejected, GitHub refuses a second PR
   from the same head); every other operation stays `unknown`.
3. `done` marks the record `committed`. `not_done` marks it `failed` so it may run again.
   `unknown` parks the run in `WAITING_FOR_APPROVAL` with reason `uncertain_side_effect`.
4. During replay, the k-th call with a given `action_hash` is skipped when at least k
   records with that hash are `committed` for the run.

**Fenced final write.** `tasks/service.py` writes a task's final status with a filter on
the current lease token (one conditional update, not check then act). A fenced out worker
drops its result and logs it.

**Parked parents.** A parent waiting on children releases its slot and lease and parks in
`WAITING_FOR_AGENT`, with the task flagged `waiting_on_children`. The stranded task
reconciler, the second pass of `reconcile_stranded_tasks` and `_auto_retry_blocked` all skip
flagged tasks. The recovery detector scans parked parents on every tick (level triggered):
it wakes a parent when all its children are terminal, enforces its deadline, and propagates
its cancel. A crash between a child's terminal write and the parent's wake therefore cannot
strand the parent.

**Controls reach every process.** The dispatcher poll loop calls `apply_from_db()` at most
every 15 s, so the worker sees a kill switch flip within one poll even when idle. Active
runs also check it at every step and every heartbeat.

**Superseding note.** Where a row of section 2.4 or 4 differs from this section, this
section wins.

**SQLite uniqueness.** `run_operations` uses the composite `_id` `"<run_id>:<seq>"` with
`insert_if_absent`; the TTL index on `run_idempotency` becomes `purge_expired`.

**Indexes.** `packages/runs/store.py` `ensure_indexes()` creates its indexes and is called
at startup by both `backend/server.py` and `worker_main.py`, and lazily on first use. This
does not depend on the broken `from db import ensure_bootstrap` in `worker_main.py`; that
import is fixed separately.

### 2.4 Verifier rounds 1 and 2 and how the plan absorbs them

Round 2 findings A to E (stable branch, ledger matching, parked parents, stale holder race, two leases) are absorbed in section 2.3 above. Round 1:

An independent verifier returned `FAIL` on the first version of this plan. Each finding is
now part of the design:

| # | Finding | Change |
|---|---|---|
| 1 | Production run lease is process local (`tasks/store.py:152` rejects `MongoStore`) | Phase 1 fixes it first, for Mongo and SQLite (section 2.3 "One lease"); regression tests with real `MongoStore` and `SQLiteStore` types fail before the fix |
| 2 | Dashboard control changes never reach the worker | Phase 2: the dispatcher poll loop refreshes overrides, idle or not (section 2.3 "Controls"); test with two separate environments |
| 3 | `_auto_push_and_pr` uses a random branch and runs outside the tool path | Phase 2: branch name derived from `task_id` (stable across attempts, section 2.3); `_auto_push_and_pr`, `_commit_step`, `agent/github_tools.py` and `services/pr_approval_gate.py` each write an `OperationRecord` |
| 4 | `/api/autonomy/tick` bypasses the coordinator | Phase 2: the tick writes a `RunRecord` and uses the same lease and ledger hooks |
| 5 | Ledger keyed on hash collides on legitimate repeats | Key is `(run_id, seq)` where `seq` is a per run counter; `action_hash` is an attribute. Recovery reconciles **every** `pending` record of the run |
| 6 | SQLite cannot do insert if absent or compare and set | Phase 1 adds `insert_if_absent` and `compare_and_set` single statement helpers to `packages/storage/sqlite_atomic.py`; new tables in `_COLLECTIONS` and `_INDEXED_FIELDS`. With them, SQLite is safe across processes on one host, so D5 drops "single worker" |
| 7 | Uniqueness needs indexes | Unique indexes on `run_idempotency(company_id, key)`, `run_operations(run_id, seq)`; TTL index on `run_idempotency.expires_at`; created by `packages/runs/store.py` `ensure_indexes()` from both processes (section 2.3 "Indexes"); the broken worker import is fixed |
| 8 | Lifecycle mismatch | New `run` lifecycle bound to `packages.runs.models:RunState`; `workflow_run` untouched |
| 9 | Contradictions; rule 40 list missing | Fixed in rows above and section 4.1 |
| 10 | A parent waiting in a dispatcher slot can starve its children | The parent releases slot and lease and parks in `WAITING_FOR_AGENT`; the recovery detector wakes it level triggered (section 2.3) |
| 11 | Fencing scope | Fencing covers writes to `runs`, `run_operations` and the final task settle (section 2.3) |
| 12 | Graceful shutdown | On SIGTERM: one write per active run (`RECOVERING`), lease release in `finally`, inside Render's grace period |
| 13 | Reuse | Root run budget uses `atomic_increment` like `packages/ai/user_token_quota.py` |
| 14 | Rule 5 | All new thresholds (lease TTL 120 s, renew 30 s, caps) read in `packages/config/` |

## 3. Reliability suite: scenario to PR

| Scenarios from the brief | Phase |
|---|---|
| 1, 2, 3, 18, 19 (sequential, parallel, aggregation, partial failure, cancel propagation) | Phase 4 |
| 4, 5, 6 (timeout, runtime unavailable, provider failover) | Phase 2 (most exist; confirm and fill) |
| 7, 8, 9 (worker termination, recovery, lease expiry) | Phase 2 |
| 10, 11 (duplicate request, duplicate side effect) | Phases 1 to 3 |
| 12, 13 (checkpoint corruption, database interruption) | Phase 2 |
| 14, 20 (cancel while running, kill switch) | Phases 3 and 4 |
| 15, 16, 24 (approval pause, expiry, release blocked) | Phase 5 |
| 17 (verifier rejection) | Phase 5 |
| 21 (budget across delegated agents) | Phase 4 |
| 22, 23 (tenant isolation, secret redaction) | Phases 3 and 5 |

All suite tests use mock providers. One `@pytest.mark.live` test exercises a real runtime.

## 4. Decisions

Made on 2026-11-14 under the operator's explicit delegation. Each one is reversible by the
control or the module named.

| # | Decision | Reasoning |
|---|---|---|
| D1 | No engine is replaced and none is added. New `packages/runs/` is the shared persistence and lifecycle layer, served by a new `/api/runs` tree; `tasks/service.py` (the path production tasks take) and `services/workflow_orchestrator.py` both record into it. Composition (`packages/runs/composer.py`) runs each child as an ordinary task through `TaskExecutionCoordinator` | Production work flows through the task dispatcher, not the orchestrator. Recording into one store from both paths gives one run view without migrating either engine |
| D2 | Approvals for run actions become durable (`run_approvals` collection), bound to `action_hash`, target and run id, with wall clock expiry. Expiry still denies. A changed action hash invalidates the approval. The in process `ApprovalStore` keeps working unchanged for callers that do not use runs | The old reason for in process approvals ("after a restart nobody is waiting") stops being true once a recovered run resumes and waits on the same approval |
| D3 | Additive collections only: `runs`, `run_events`, `run_operations`, `run_artifacts`, `run_approvals`, `run_idempotency`. Existing documents gain only optional fields with safe defaults (`Task.waiting_on_children`, lease `token` and `run_id`). SQLite allowlist extended | Backward compatible by construction; old records simply have no run |
| D4 | `agent/loop.py` gets two small hook calls (before and after a side effecting tool) and a lease check per step; the logic lives in new modules so the file does not grow | Keeps the 800 line rule from getting worse on a file already over it |
| D5 | Guarantee by backend, reported by `GET /api/runs/capabilities`: Mongo, recovery across workers and hosts; SQLite (file), recovery across processes on the same host, using the single statement helpers of section 2.4; memory, no recovery | Matches what each store can make atomic; nothing is claimed that is not tested |

All decisions apply before phase 1. Phase 0 (baseline) needs none of them.

### 4.1 Rule 40 gates

| Gate | Where | Cleared by |
|---|---|---|
| Database migration | the six new collections and their Mongo indexes (additive, created by `packages/runs/store.py` `ensure_indexes()`) | operator delegation, 2026-11-14 |
| More than 5 files in `agent/loop.py` scope | none planned: the loop gains hook calls only; `agent/loop.py` is added to the `AGENTS.md` size exception list rather than grown | operator delegation, 2026-11-14 |
| Breaking API or schema change | none: all additive | n/a |
| Risky module (rule 15) | `agent/tools.py` is not touched; if it must be, the `risky-module-review` skill runs first | n/a |

## 5. Known limits of this plan

* The test baseline is recorded in phase 0 (see the PR description for the result).
* Nothing was checked against the live Render deployment.
* Rows marked "not verified" are open questions, not findings.
* Bugs 16 and 17 in `.claude/state/active-tasks.md` (approval gate bypass, merge gate
  coupling) sit on the same path as phase 5 and are checked there.
* Dashboard changes in phase 6 need screenshots as evidence (rule 49).

## 6. Definition of done

Unchanged from the brief, section 17. The plan adds one rule: no item is ticked without
the command output or test name that proves it, and anything that could not be validated
in the environment is reported as unverified with what is needed to validate it.

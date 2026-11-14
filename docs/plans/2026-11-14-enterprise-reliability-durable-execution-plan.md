# Enterprise reliability and durable multi agent execution: implementation plan

**Status:** plan only. Nothing here is implemented. This PR carries the plan and no code.
**Date:** 2026-11-14
**Audited at:** `8075306` on `master`.
**Source brief:** "Autonomous AI Agency: Enterprise Reliability and Durable Multi Agent
Execution Upgrade" (operator brief, 18 sections, 10 priorities, 24 failure scenarios).
**Sensitivity:** touches `agent/loop.py`, the approval path and storage schemas. Rule 40
requires a human decision before several steps. Those gates are listed in section 4.

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
| Run API | `/api/workflow/orchestrator/runs`, `/runs/{run_id}`, `/approve/{run_id}` in `backend/server.py`; `/workflow/{run_id}` with approve, reject, resume, cancel, artifacts, events in `workflow/api.py` | Two run APIs over two engines. No client idempotency key on run creation (only `source_id` dedup on task create in `tasks/store.py`) | Extend the orchestrator routes: events, artifacts, cancel, retry, `Idempotency-Key`. No new `/api/runs` tree unless D1 says so | One test per route, duplicate key returns the same run |
| Run lifecycle states | `packages/lifecycle/` declares 21 lifecycles and guards transitions | Brief's states (`RECOVERING`, `TIMED_OUT`, `WAITING_FOR_AGENT`) are not all declared for the orchestrator run | Declare the missing states in `packages/lifecycle/catalogue.py`. No new enum | `scripts/lifecycles.py check`, legal and illegal move tests |
| Worker ownership and lease | `tasks/run_lease.py`; `TaskStore.acquire_run_lease` / `release_run_lease` (atomic on Mongo) | TTL is a fixed 3600 s and no renewal function exists. A run longer than one hour can be claimed by a second worker. A crashed holder blocks the task until expiry. SQLite and memory mode use a process local table | Add `renew_run_lease` plus a heartbeat task; shorten TTL to a few heartbeats; fencing token on every state write | Expiry and reacquisition, renewal keeps a long run, stale holder write is rejected |
| Abandoned run detection | `TaskDispatcher` reconciler calls `store.reconcile_stranded_tasks` (300 s stale threshold); `services/orchestrator_supervisor.py` requeues stalled runs with no LLM dependency | Two detectors with different thresholds. Interaction between the 300 s reconciler and the 3600 s lease is not verified | One detector driven by lease expiry; the reconciler and supervisor call it | Kill a worker mid run, second worker claims after expiry |
| Queue durability | `services/orchestrator_queue.py` | In process `deque`. Queued runs are lost on restart unless the supervisor finds a checkpoint | Queue state derives from persisted `QUEUED` run records; the deque becomes a cache | Restart with queued runs, none lost, none duplicated |
| Checkpoints (orchestrator) | `services/orchestrator_checkpoint.py` persists to the shared store, `restore_in_flight_runs()` at boot | Falls back to `_NoopDB`, so a deploy with no durable store silently checkpoints nowhere. No schema version | Version field, corruption check, health flag when the store is a no op | Corrupt checkpoint, version migration, no op store reported in health |
| Checkpoints (agent loop) | `agent/checkpoint.py`, called from `agent/loop.py` after plan, after each step and on error | File backed under `.data/checkpoints`, so it does not survive a container replacement. A corrupt latest file returns `None` and does not fall back to the previous file. No schema version | Storage backed checkpoint store behind the same functions; fall back to last good file; version field | Corrupt latest falls back, restore after simulated new container |
| Side effect safety on replay | `agent/action_hash.py` (`action_hash`, `already_executed`) with tests | Not wired into `agent/loop.py` (the changelog says so, pending rule 40 approval) | Durable operation record keyed by action hash; check before push, PR create, email, delete | Recovery after an uncertain push does not push twice |
| Graceful shutdown | `worker_main.py` handles SIGTERM and SIGINT and stops background services | Whether in flight runs are checkpointed and leases released on shutdown is not verified | On signal: stop claiming, checkpoint, release leases, mark runs `RECOVERING` | SIGTERM during a run leaves a claimable run |
| Agent contract | `runtimes/base.py` `RuntimeAdapter` (`execute`, `stream_execute`, `health_check`, `start`, `stop`, `supports`), `TaskSpec`, `TaskResult`; `runtimes/registry.py`, `routing.py` | Adapter has no `cancel`, `resume`, `status` or `list_artifacts`. No versioned agent definition found | Optional capability methods with safe defaults so existing adapters keep working; typed `AgentDefinition` | Contract test run against every registered adapter |
| Fan out, join, conditional | `agent/coordinator.py` semaphore; `agents/workflow_engine.py` DAG | Children have no run record of their own. No parent deadline or cancel propagation found | Parent and child run records, bounded concurrency, depth and count caps, cancel propagation | Parallel children, one child fails, parent cancel reaches children, spawn cap |
| Artifacts | `workflow/artifact_store.py` with id, run id, name, path, content hash, size, created at | Content on the local filesystem and metadata in local SQLite. Lost with the container. No MIME type, producing agent, access or retention policy | Put content behind the existing storage layer (`packages/storage`); add the missing metadata fields | Artifact readable after worker replacement, hash mismatch detected |
| Verification | `tasks/independent_verifier.py`, `tasks/verification.py`, `agent/verification_contract.py`, `agent/verification_evidence.py`, `agent/verification_strategies.py` | Already strong: acceptance criteria, evidence report, failing tests force FAIL. Read only guarantee of the verifier context is not verified. Bounded rework exists (`rework_or_park`) | Keep. Add tests that prove the three "must never" rules; confirm the verifier cannot write | Verifier rejection, missing test result is not a pass, verifier error is not a pass |
| Approvals | `packages/governance/approvals.py` (TTL, expiry denies, named resolver); grants persist to `governance_grants`; task level approval lives on the `Task` record | Pending approval requests are in process **by documented design**: a restart expires them (fail closed). No binding of an approval to an action hash found in `packages/governance/` | Decision D2. If durable: persist requests, bind to action hash and target, invalidate on change | Approval survives restart, expiry denies, changed arguments invalidate |
| Kill switch | `packages/config/autonomy_limits.py` (`AGENCY_KILL_SWITCH`); checked in `tasks/dispatcher.py`, `agent/loop.py`, `packages/ai/agent_budget.py` | Read from the process environment, so flipping it needs each process to see the change. How fast an active run stops is not verified | Read through the live control catalogue; check at each step boundary | Kill switch during an active run stops it within one step |
| Budgets | `packages/ai/agent_budget.py` per agent per day; `packages/llm/budget.py` | In memory, per process, cleared by restart. No aggregate across a parent and its children | Run scoped budget stored on the run record, charged by children against the root run | Delegated children exhaust the parent budget |
| Tenant isolation | `Task.company_id`; `_wfo_owned_run_or_404` in `backend/server.py` | `company_id` is optional on `Task`. Coverage across every run route is not verified | Company scope check in one dependency used by all run routes | Cross company read and cancel are refused |
| Skills catalogue | `harness/skills/` with `CATALOG.md`; skill registry tests exist | No version field found in a spot check of `SKILL.md` files. Pinning per run not found | Add version to skill metadata; record resolved skill versions on the run | Run keeps its pinned version after the skill changes |
| Tracing | `services/otel_tracing.py`, `langfuse_obs.py` | Correlation from parent run to child run to tool call is not verified | Carry `run_id` and `parent_run_id` as span attributes; one trace per root run | Trace for a fan out run contains every child |
| Redaction | `packages/security/redact.py`; `agent/verification_evidence.py` redacts | Coverage of artifacts and run events is not verified | Redact at the single write point for events and artifact metadata | Seeded secret never appears in logs, artifacts or traces |

### 1.3 What already works and should not be rebuilt

* Atomic cross process checkout on Mongo (`tasks/run_lease.py`).
* A supervisor with zero LLM dependency (`services/orchestrator_supervisor.py`).
* Evidence based verification with a contract and a report.
* Approval TTL where expiry denies.
* A declared lifecycle registry with a drift check.
* Transient error requeue with a cap (`_is_transient_error`, `_DISPATCH_RETRY_LIMIT`).

## 2. Delivery: twelve small PRs, not one refactor

Each PR is independently revertible, ships behind a live control registered in
`packages/config/control_catalogue.py` (rule 37), and ends in an independent verifier
verdict (rule 49).

| PR | Phase | Scope | Gate before start |
|---|---|---|---|
| 0 | 0 | Baseline: run `pytest -x`, record pre existing failures, settle every "not verified" row, add `docs/adr/` entry for D1 | D1 |
| 1 | 1 | `RunRecord` model, lifecycle states declared, persisted run events | Migration approval |
| 2 | 1 | Lease renewal, heartbeat, fencing token, single abandoned run detector | none |
| 3 | 1 | Run routes: events, artifacts, cancel, retry, idempotency key | none |
| 4 | 1 | Durable queue, graceful shutdown, versioned checkpoints with corruption fallback | none |
| 5 | 1 | Wire `agent/action_hash.py` into the loop with durable operation records | Rule 40 (`agent/loop.py`) |
| 6 | 2 | Parent and child runs, bounded fan out, join, cancel propagation, spawn caps | none |
| 7 | 2 | Run scoped budgets across children; kill switch as a live control | none |
| 8 | 3 | Artifact store on the storage layer with full metadata | Migration approval |
| 9 | 3 | Verification hardening tests; verifier read only proof | none |
| 10 | 4 | Durable approvals bound to action hash | D2, rule 15 if `agent/tools.py` is touched |
| 11 | 4 | Skill versions and pinning; trace correlation; dashboard run view | none |
| 12 | 5 | Three reference workflows on deterministic fixtures; the 24 scenario reliability suite; runbooks | none |

Runtime contract work (optional `cancel`, `resume`, `status` on `RuntimeAdapter`) rides in
PR 3 and PR 6 where it is first needed, so no adapter changes without a caller.

## 3. Reliability suite: scenario to PR

| Scenarios from the brief | Lands in |
|---|---|
| 1, 2, 3, 18, 19 (sequential, parallel, aggregation, partial failure, cancel propagation) | PR 6 |
| 4, 5, 6 (timeout, runtime unavailable, provider failover) | PR 0 (most exist; confirm and fill) |
| 7, 8, 9 (worker termination, recovery, lease expiry) | PR 2 and PR 4 |
| 10, 11 (duplicate request, duplicate side effect) | PR 3 and PR 5 |
| 12, 13 (checkpoint corruption, database interruption) | PR 4 |
| 14, 20 (cancel while running, kill switch) | PR 3 and PR 7 |
| 15, 16, 24 (approval pause, expiry, release blocked) | PR 10 |
| 17 (verifier rejection) | PR 9 |
| 21 (budget across delegated agents) | PR 7 |
| 22, 23 (tenant isolation, secret redaction) | PR 3 and PR 8 |

All suite tests use mock providers. One `@pytest.mark.live` test exercises a real runtime.

## 4. Decisions a human must make first

| # | Decision | Why it cannot be assumed |
|---|---|---|
| D1 | Which engine is canonical for new run work. Plan assumes `services/workflow_orchestrator.py` | Four engines exist; extending the wrong one deepens the split |
| D2 | Should pending approvals survive a restart | `packages/governance/approvals.py` records the opposite as a deliberate fail closed choice. A durable approval is only meaningful once a run can resume (after PR 4) |
| D3 | New collections and fields (run records, run events, operation records, artifact metadata) | Rule 40: database migration |
| D4 | Wiring into `agent/loop.py` (PR 5) | Rule 40, and the file is already 3879 lines against an 800 line limit |
| D5 | Recovery guarantee on SQLite and memory mode | Lease is process local there. Proposal: report "single process, no cross worker recovery" in runtime health and do not claim more |

## 5. Known limits of this plan

* The test baseline was **not** run for this plan. PR 0 does that.
* Nothing was checked against the live Render deployment.
* Rows marked "not verified" are open questions, not findings.
* Bugs 16 and 17 in `.claude/state/active-tasks.md` (approval gate bypass, merge gate
  coupling) sit on the same path as PR 10 and should be closed in it or before it.
* Dashboard changes in PR 11 need screenshots as evidence (rule 49).

## 6. Definition of done

Unchanged from the brief, section 17. The plan adds one rule: no item is ticked without
the command output or test name that proves it, and anything that could not be validated
in the environment is reported as unverified with what is needed to validate it.

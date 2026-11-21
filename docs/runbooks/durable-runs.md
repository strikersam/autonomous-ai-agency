# Durable runs: operating runbook

Audience: the operator on call. Scope: the run layer in `packages/runs/` (plan:
`docs/plans/2026-11-14-enterprise-reliability-durable-execution-plan.md`). Every
statement below names the test or file that backs it; anything not exercised in
the sandbox is marked **unverified**.

## 1. What a run is

A run is the durable record (`RunRecord`, collection `runs`) of one unit of work.
The task path writes one per dispatch; the composer (`packages/runs/composer.py`)
writes a root run and one child run per step. Events, operations, artifacts,
approvals and idempotency keys live in their own collections (`run_events`,
`run_operations`, `run_artifacts`, `run_approvals`, `run_idempotency`). All are
additive; old tasks simply have no run.

## 2. States

`created`, `queued`, `starting`, `running`, `waiting_for_agent`,
`waiting_for_approval`, `retrying`, `recovering`, `verifying` are live.
`succeeded`, `failed`, `cancelled`, `timed_out`, `dead_letter` are terminal.
Legal moves are the `run` lifecycle (`python scripts/lifecycles.py check`); an
illegal move is refused and never silently applied.

| State | Meaning | What to do |
|---|---|---|
| `queued` | waiting for a worker | nothing; check the dispatcher if it stays |
| `running` | a worker holds the lease and renews it | nothing |
| `waiting_for_approval` | parked at an approval step, or at an operation whose outcome is unknown after a crash | a person decides (section 6) |
| `recovering` | a worker shut down cleanly (SIGTERM) and released the run | recovery or the next dispatch resumes it |
| `dead_letter` | `RUNS_MAX_ATTEMPTS` crashes | read the events, fix the cause, then `POST /api/runs/{id}/retry` |

## 3. Recovery

A worker holds a lease on the task (TTL `RUNS_LEASE_TTL_SEC`, renewed every
`RUNS_LEASE_RENEW_SEC`) and every write carries its fencing token. If the worker
dies, the lease expires and the recovery tick (`RUNS_RECOVERY_TICK_SEC`, in the
dispatcher loop) takes the run over with a higher token: the dead worker's late
write is rejected. Operations that had started are reconciled against the outside
world before the run resumes; an unknown outcome parks the run for a person.
Switch: `RUNS_RECOVERY_ENABLED` (default `false`). Proven by
`test_scenario_07`, `test_scenario_08`, `test_scenario_09`, `test_scenario_11`
(`tests/reliability/`) and `tests/test_runs_recovery.py`.

Capabilities by backend (`GET /api/runs/capabilities`, decision D5):

| Backend | Recovery | Lease shared across processes |
|---|---|---|
| MongoDB | across workers and hosts | yes (**unverified** against a real MongoDB here; the suite uses the hermetic Motor fake) |
| SQLite file | across processes on one host | yes (tested with two connections on one file) |
| memory | none | no (a restart loses the runs) |

## 4. Cancel, kill switch, caps

* Cancel: `POST /api/runs/{id}/cancel`. A queued or waiting run is cancelled at
  once; a running one stops at the worker's next heartbeat. For a composition the
  cancel reaches every descendant (`test_scenario_14`, `test_scenario_19`).
* Kill switch: `AGENCY_KILL_SWITCH=true` (also under Settings, Platform controls).
  The composer and the recovery tick stop; running children are cancelled within one
  poll (`test_scenario_20`); the task path stops within one lease renewal
  (`tests/test_runs_budget.py::test_kill_switch_during_an_active_run_stops_it_within_one_heartbeat`).
  Only a person turns it off.
* Caps (live controls): `RUNS_MAX_CHILDREN` per parent, `RUNS_MAX_DEPTH` of the tree,
  `RUNS_MAX_PARALLEL` children at once. A refused spawn writes a `spawn_refused`
  event and fails that step.
* Deadline: a composition's `deadline_s` ends it `timed_out` and cancels the
  outstanding children (`test_scenario_04`).

## 5. Budgets

A root run may carry `budget` (`max_cost_usd`, `max_tokens`, `max_steps`). Every
child charges the root. With a cost cap the composer reserves each child's
estimated cost before it starts, so parallel children cannot overspend; a child
that does not fit is cancelled with a `budget_exhausted` event and the
composition ends `failed` (`test_scenario_21`, `tests/test_runs_composer_phase4_fixes.py`).

## 6. Approvals

An approval step parks the parent in `waiting_for_approval`
(`Composer.approve` then `run` resumes it: `test_scenario_15`). A durable
approval (`packages/runs/approvals.py`, `RUNS_DURABLE_APPROVALS`) binds one run,
one action hash and one target; changing either invalidates it; a pending request
past its expiry is `expired` and can no longer be approved (`test_scenario_16`).
A release, deploy or merge must pass `require_release_approval`; agents never
merge (`agent/autonomy_gate.py`) (`test_scenario_24`). **Limitation:** deciding an
approval is a Python call (`RunApprovals.decide`); there is no HTTP route for it
yet (section 9).

## 7. Artifacts and redaction

`ArtifactStore.put` redacts text before hashing and storing, refuses a binary
artifact containing a secret pattern, and enforces `RUNS_ARTIFACT_MAX_BYTES`.
Reads verify the sha256; a mismatch is a `409` from the API. Events, approvals,
artifact metadata and span attributes are redacted at their single write point
(`test_scenario_23`). Artifacts live in the storage backend, so they survive a
container replacement on MongoDB or SQLite and not on the memory backend.

## 8. Reference workflows

`packages/runs/reference_workflows/` holds three fixture driven compositions
(no network, no LLM) used as smoke tests of the platform:
A `BugToPrWorkflow` (ends parked at human approval, never merges or deploys),
B `QaInvestigationWorkflow` (typed `QualityReport`), C `QaFanoutWorkflow`
(parallel, tolerates one failed agent). Tests: `tests/test_reference_workflows.py`.

## 9. Troubleshooting

| Symptom | Likely cause | Check |
|---|---|---|
| A run stays `running` after a deploy | worker killed without releasing | `GET /api/runs/{id}/events`; is `RUNS_RECOVERY_ENABLED` on; is the lease expired (`RUNS_LEASE_TTL_SEC`) |
| Run parked `waiting_for_approval`, reason `uncertain_side_effect` | a push or PR was in flight at the crash | check the remote by hand, then approve or retry; never repeat blindly |
| `409` reading an artifact | stored content fails its hash | treat as tampering or corruption; the artifact is not served |
| Spawn refused | child or depth cap | `spawn_refused` event names the cap |
| Recovery does nothing | memory backend, kill switch on, or recovery off | `GET /api/runs/capabilities` (`recovery`, `recovery_enabled`) |
| Everything blocked at release | `RUNS_DURABLE_APPROVALS` off, or no matching approval | by design: off means nothing is approved |

Known gaps: composer and approval decisions are not exposed over HTTP; the
`@pytest.mark.live` test needs `NVIDIA_API_KEY` and was not run here.

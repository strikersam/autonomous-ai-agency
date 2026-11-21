# Reliability delivery report: durable multi agent execution (phases 1 to 7)

Date: 2026-11-21. Branch `claude/runs-phase7` (phases 1 to 6 plus phase 7). Plan:
`docs/plans/2026-11-14-enterprise-reliability-durable-execution-plan.md`. Operating
guide: `docs/runbooks/durable-runs.md`.

Rule for this report: every claim cites a test name or a command whose output is
pasted below. Anything not run in the sandbox is marked **unverified**. Nothing was
checked against a live Render deployment, a real MongoDB, or a real LLM provider.

## 1. Audit and gap matrix status

Status: done (built and a named test proves it), partial (built, part open), deferred.
Test paths are under `tests/`; `rel/` is `tests/reliability/`.

| # | Capability | Status | Proof |
|---|---|---|---|
| 1 | Stable run identity | done | `test_runs_store.py::test_create_is_insert_if_absent_and_get_round_trips`, `test_runs_task_binding.py::test_a_failed_execution_records_the_run_and_releases_the_lease` |
| 2 | Run API with idempotency | done | `test_runs_api.py::test_same_idempotency_key_same_run_no_second_task`, `rel/test_scenarios_10_18.py::test_scenario_10_*` |
| 3 | Run lifecycle states | done | `test_runs_store.py::test_transitions_follow_the_run_lifecycle_and_are_logged`; `python scripts/lifecycles.py check` printed `OK: 22 lifecycles, docs/lifecycles.md is current, 11 status types match` |
| 4 | Worker ownership, lease, fencing | done on SQLite and memory; MongoDB path unverified against a real server | `test_runs_lease.py` (renewal, expiry, race), `rel/test_scenarios_01_09.py::test_scenario_09_*` |
| 5 | Abandoned run detection | done | `test_runs_recovery.py::test_a_dead_worker_is_recovered_and_its_late_settle_is_fenced`, `test_scenario_07_*`, `test_scenario_08_*` |
| 6 | Queue durability | partial | recovery requeues from persisted runs (`test_runs_recovery.py::test_backoff_delays_the_requeue_until_not_before`); `services/orchestrator_queue.py` still holds an in process deque and imports nothing from `packages/runs` (grep). Deferred |
| 7 | Orchestrator checkpoints | partial | `schema_version` and `is_durable()` exist in `services/orchestrator_checkpoint.py`; `tests/test_orchestrator_checkpoint.py` passed (37 passed with the two files in row 8). Whether `/api/runs/capabilities` `checkpoint_durable` is honest on the memory backend: unverified (it returned `true` on memory in my probe) |
| 8 | Agent loop checkpoints | done | `test_checkpoint_fallback.py`, `rel/test_scenarios_10_18.py::test_scenario_12_*` |
| 9 | Side effect safety on replay | done | `test_runs_side_effects.py::test_a_pull_request_is_not_opened_again_on_replay`, `test_scenario_11_*`; `agent/loop.py` calls `recorded_effect` for push and PR (grep, lines 3649 and 3670) |
| 10 | Graceful shutdown | done | `test_runs_shutdown.py::test_shutdown_marks_the_run_recovering_and_releases_the_lease` |
| 11 | Agent contract (runtime cancel, status) | deferred | `runtimes/base.py` has no `cancel`, `status`, `list_artifacts` (grep found none); the composer cancels the in process work instead |
| 12 | Fan out, join, conditional | done | `test_runs_composer.py`, `test_scenario_01..03`, `18`, `19`, reference workflow C |
| 13 | Artifacts | done | `test_runs_artifacts.py`, `test_reference_workflows.py::test_a_bug_to_pr_stops_at_human_approval_with_a_complete_draft_pr` |
| 14 | Verification | done | `test_verification_hardening.py`, `test_scenario_17_*`, `test_reference_workflows.py::test_a_verifier_fails_on_a_missing_or_failing_test_result` |
| 15 | Approvals | done | `test_runs_approvals.py`, `test_scenario_15_*`, `test_scenario_15b_*`, `test_scenario_16_*` |
| 16 | Kill switch | done | `test_runs_budget.py::test_kill_switch_during_an_active_run_stops_it_within_one_heartbeat`, `test_scenario_20_*` |
| 17 | Budgets across children | done | `test_runs_budget.py`, `test_runs_composer_phase4_fixes.py`, `test_scenario_21_*` |
| 18 | Tenant isolation | partial | owner scoped: `test_scenario_22_*` (cross owner reads, cancel, retry give 404); children inherit `company_id` (`test_scenario_22b_*`). The API check compares the owner, not the company, so two users of one company cannot see each other's runs and there is no company wide role |
| 19 | Skill version pinning | done | `test_runs_skill_versions.py` |
| 20 | Trace correlation | done for attributes; export to a collector unverified | `test_runs_tracing.py` |
| 21 | Redaction | done | `test_runs_redaction.py`, `test_scenario_23_*` (fails when `redact_text` is made a no op: confirmed by mutation, section 6) |

## 2. Architecture (text)

```
 HTTP /api/runs/*  ---------------------------+      Composer (packages/runs/composer.py)
 (create, get, events, artifacts, cancel,     |        root run -> child runs (one task each)
  retry, capabilities; Idempotency-Key)       v        sequence | parallel | approval | conditional
                                     packages/runs/store.py  (RunStore over memory | SQLite | Mongo)
 tasks/service.py (task path) ------>  runs, run_events, run_operations, run_artifacts,
 services/workflow_orchestrator ----->  run_approvals, run_idempotency (+ run_checkpoints, lease)
                                              ^
 lease.py (token, heartbeat) recovery.py (tick) side_effects.py + operations.py (ledger)
 budget.py (root cap, reservations) approvals.py artifacts.py redaction.py tracing.py
                                              ^
 packages/runs/reference_workflows/  A bug to PR | B QA investigation | C QA fan out
   (CompositionSpec + deterministic executors; no new engine)
```

## 3. Changed files (phase 7)

`git diff --stat 138346c..HEAD` before the docs commit: 15 files, 1467 insertions.
New: `packages/runs/reference_workflows/` (`__init__`, `models`, `common`, `bug_to_pr`,
`qa_investigation`, `qa_fanout`), `tests/test_reference_workflows.py`,
`tests/reliability/` (`conftest`, `_helpers`, three scenario files, `test_live_runtime`),
`docs/runbooks/durable-runs.md`, this report. Edited: `pytest.ini` (registers the
`live` marker), `docs/api-surfaces.md`, `CHANGELOG.md`, `docs/changelog.md`.
The file list of the earlier phases is `git log --name-only` on their merged PRs
(#2006, #2007 and the phase 1 to 3 and 5 commits).

## 4. Migrations and compatibility

Phase 7 adds no collection, no field and no env var. The run layer overall is additive
(decision D3): collections `runs`, `run_events`, `run_operations`, `run_artifacts`,
`run_approvals`, `run_idempotency`, `run_checkpoints`; old documents carry only optional
fields with safe defaults (`test_runs_skill_versions.py::test_old_documents_without_the_field_still_validate`).
All `RUNS_*` controls are already in `docs/configuration-reference.md` and
`packages/config/control_catalogue.py` (13 each, checked by grep), so no doc change was needed.

## 5. APIs and example requests

No new route in phase 7. Captured from the test client (memory backend):

```
POST /api/runs  {"title": "Nightly report"}  Idempotency-Key: k1
  -> 201 {'run_id': 'run_e86a3b23...', 'task_id': 'task_521e7cc1f0110926', 'state': 'queued', 'created': True}
same request again -> 200 {... same ids ..., 'created': False}
GET /api/runs/capabilities -> {'backend': 'memory', 'durable_lease': False, 'recovery': 'none',
  'recovery_enabled': False, 'ledger_enabled': True, 'checkpoint_durable': True}
POST /api/runs/{id}/cancel -> {'run_id': ..., 'state': 'cancelled', 'cancel_requested': True, 'settled': True}
GET /api/runs/run_nope -> 404
```

## 6. Test results (real output)

```
$ TESTING=true python -m pytest -q -p no:cacheprovider tests/test_runs_*.py tests/reliability \
    tests/test_reference_workflows.py tests/test_platform_controls.py tests/test_task_run_lease.py \
    tests/test_verification_hardening.py | tail -3
349 passed, 1 deselected, 3 warnings in 18.44s
```
(The brief's command also named `tests/test_reliability*`; no such file exists and pytest
exits with "file or directory not found", so it was dropped. The 1 deselected is the live test.)

```
$ pytest --collect-only -q -k scenario tests/reliability | tail -3
28/29 tests collected (1 deselected) in 0.17s
$ bandit -q -r packages/runs            -> no output, exit 0
$ python -m compileall -q packages tests -> exit 0
$ python scripts/check_changelog_parity.py -> PARITY OK: bodies match across 5.0.0, Unreleased, v4.1.0
$ ast check (functions over 50 lines, files over 800) on the 14 touched Python files -> none
```

Scenario map (all passing in the run above; `T01_09`, `T10_18`, `T19_24` are the files
`tests/reliability/test_scenarios_01_09.py` and so on):

| # | Test |
|---|---|
| 1 | `T01_09::test_scenario_01_normal_sequential_execution` |
| 2 | `T01_09::test_scenario_02_two_or_more_agents_execute_in_parallel` |
| 3 | `T01_09::test_scenario_03_parent_workflow_aggregates_child_results_and_cost` |
| 4 | `T01_09::test_scenario_04_agent_timeout_cancels_the_child_and_times_out_the_parent` (+ `04b` task path) |
| 5 | `T01_09::test_scenario_05_runtime_unavailable_before_execution_requeues_then_blocks` |
| 6 | `T01_09::test_scenario_06_provider_failure_fails_over_and_the_run_still_succeeds` |
| 7 | `T01_09::test_scenario_07_worker_termination_leaves_a_running_run_with_a_held_lease` |
| 8 | `T01_09::test_scenario_08_another_worker_recovers_the_abandoned_run_and_finishes_it` |
| 9 | `T01_09::test_scenario_09_an_expired_lease_is_reacquired_with_a_higher_token` |
| 10 | `T10_18::test_scenario_10_duplicate_request_with_the_same_idempotency_key_returns_one_run` |
| 11 | `T10_18::test_scenario_11_a_side_effect_committed_before_a_crash_is_not_repeated` |
| 12 | `T10_18::test_scenario_12_a_corrupt_checkpoint_falls_back_to_the_previous_good_one` |
| 13 | `T10_18::test_scenario_13_a_database_interruption_fails_safe_and_the_run_recovers` (+ `13b`) |
| 14 | `T10_18::test_scenario_14_cancellation_while_an_agent_is_running_stops_it` |
| 15 | `T10_18::test_scenario_15_a_run_pauses_for_approval_and_resumes_after_a_human_decides` (+ `15b`) |
| 16 | `T10_18::test_scenario_16_an_expired_approval_denies` |
| 17 | `T10_18::test_scenario_17_independent_verifier_rejection_blocks_the_draft_pr` |
| 18 | `T10_18::test_scenario_18_a_failed_child_does_not_cost_its_successful_sibling` |
| 19 | `T19_24::test_scenario_19_parent_cancellation_propagates_to_every_descendant` |
| 20 | `T19_24::test_scenario_20_the_kill_switch_stops_active_execution` |
| 21 | `T19_24::test_scenario_21_budget_exhaustion_across_delegated_agents_stops_the_composition` |
| 22 | `T19_24::test_scenario_22_tenant_isolation_denies_cross_company_access` (+ `22b`) |
| 23 | `T19_24::test_scenario_23_secrets_never_reach_events_artifacts_traces_or_logs` |
| 24 | `T19_24::test_scenario_24_release_or_deploy_is_blocked_without_a_durable_human_approval` |

Live: `tests/reliability/test_live_runtime.py` (`@pytest.mark.live`, `integration`, skipped
without `NVIDIA_API_KEY`). `pytest -m integration` printed `1 skipped`. **Never run against
a real provider here: unverified.**

Mutation check (test is not vacuous): with `redact_text` changed to return its input,
`test_scenario_23_*` failed (`1 failed, 28 deselected`); the file was restored afterwards.

Baseline note: `tests/test_failover_client_shared.py` fails 28 tests when run alone, on the
untouched baseline commit `138346c` as well (`AttributeError: type object '_Client' has no
attribute '_send_single_request'`, raised when `packages/ai/brain.py` is first imported
under the test's patched `httpx.AsyncClient`). It is import order dependent and unrelated
to runs; not fixed here. Scenario 6 uses its own scripted transport and passes.

## 7. Failure injection evidence

* Worker killed mid run, recovered by another worker, late write fenced: scenarios 7, 8, 11.
* Lease expiry and takeover with a higher token, stale renew refused: scenario 9.
* Database interruption: scenario 13 makes `append_event` raise `ConnectionError` mid
  composition: `run` raises, the parent stays `running` (never falsely succeeded), and
  running it again finishes without redoing step `a`. Step `b`, whose settle was lost, runs
  again (at least once for a child that never recorded a result; external effects are
  protected by the ledger, scenario 11). Scenario 13b: a dead lease table makes the
  heartbeat give up after a TTL without raising; a dead checkpoint table returns `False`.
* Provider failure: a 429 then a connection error then a 200 across three providers (scenario 6).
* Corrupt checkpoint file and a replaced container (scenario 12).
* Tampered artifact: `test_runs_artifacts.py::test_hash_mismatch_is_detected_on_read`.

## 8. Security and governance impact

No endpoint, env var, auth path or risky module (rule 15) was touched. The reference
workflow A never merges or deploys: its draft step fails if the merge gate
(`agent/autonomy_gate.assert_agent_can_merge`) or the durable deploy approval
(`require_release_approval`) is open (`test_a_draft_step_fails_when_a_release_guard_is_open`,
`test_a_never_merges_or_deploys_without_approval`). Workflows read fixtures only, make no
network call and use no LLM. Verifiers are evidence based: a missing, incomplete or
failing test result fails workflow A's verifier; workflow B's verifier fails on an
unclassified failure, on a classification without log evidence, and on a failed pipeline
with no failure record; workflow C's verifier fails on a completed agent with no test
result and on an overall verdict the evidence does not support.

## 9. Known limitations and deferred work

* Workflow C: failing tests in one agent give an honest `fail` assessment that the
  verifier accepts as consistent; only a missing result or an unsupported claim fails the
  verifier. This is a design choice, not a brief requirement either way.
* Composer and approval decisions have no HTTP route (runbook section 9).
* Runtime adapters have no `cancel`, `status` or `list_artifacts` (matrix row 11).
* The orchestrator queue is still an in process deque (row 6).
* Tenant isolation is per owner, not per company (row 18).
* Real MongoDB, real Render, a real provider and an OpenTelemetry collector were not
  exercised (unverified). The suite uses the hermetic Motor fake and SQLite files.
* `graphify update .` (rule 39) was not run; no code under `agent/`, `router/` or `proxy.py` changed.
* The full test suite was not run (it hangs on a Mongo test in this sandbox).
* Scheduled reporting reuse: no scheduled reporting capability was built or changed; the
  three workflows run through the existing composer, which is what a schedule would call.
  Wiring a schedule to it is unverified and not done.

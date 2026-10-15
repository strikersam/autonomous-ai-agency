# Evidence-driven verification

An agent's statement that its work is correct is never proof. This page
describes how the agent loop establishes, from observed evidence, that a run
met the acceptance criteria fixed before it started, and how the task workflow
enforces that decision. It builds on rule 49 (`tasks/verification.py`) and the
empirical checks (`agent/empirical_verify.py`); it does not replace them.

## Lifecycle

```
plan ──► contract ──► execute steps ──► checks per step ──► judge ──► evidence report ──► task gate
          (persisted       (workspace or      (structured          (independent   (deterministic     (rework, review,
           with spec)       E2B sandbox)       results)             reviewer)      decision)          approval, done)
```

1. **Plan.** The planner produces an `AgentPlan` (`agent/models.py`).
2. **Contract.** `build_contract()` (`agent/verification_contract.py`) turns it
   into a `VerificationContract`: one acceptance criterion per step (the
   planner's `acceptance` text, or a recorded conservative default when it gave
   none), a goal criterion, invariants, the risk tier and reasons, the selected
   strategies (each mandatory or advisory, with why), pass and failure
   conditions, and the retry budget. It is persisted with the plan's spec in
   `agent_specs` (`services/spec_store.py`) **before any file is changed**.
3. **Execute.** Unchanged: the executor writes, the step verifier and local
   syntax/safety checks gate each file (3 attempts per file).
4. **Checks.** After a step's files are applied, `agent/empirical_verify.py`
   byte-compiles the changed Python files and runs the matching
   `tests/test_<module>*.py`, in the E2B sandbox when one is attached, else on
   the host. Every check is recorded as a `CheckResult` and bound to a SHA-256
   fingerprint of the exact content it checked.
5. **Independent review.** The judge (a separate role and model setting)
   reviews the diff against the goal, as before.
6. **Evidence report.** `build_report()` (`agent/verification_evidence.py`)
   folds the step outcomes, check results and judge verdict into an
   `EvidenceReport` and decides one verdict. The report is appended to the
   spec (`evidence_reports`, atomic `$push`, last 20 kept) and returned in the
   run result as `verification_report`, with the contract as
   `verification_contract`.
7. **Task gate.** `tasks/verification.py::apply_evidence` combines the judge's
   verdict with the evidence decision. It can only make the verdict stricter.
   Then the existing gate applies: a FAIL is sent back for rework (at most
   `MAX_AUTO_REWORK` = 2 times in a row, then parked for a person), a missing
   verdict waits in review, a PASS completes, and a verified high-risk change
   waits for a person.

## Check statuses

| Status | Meaning | Counts as evidence? |
|--------|---------|--------------------|
| `passed` | Ran and passed on the content it is bound to | Yes, until that content changes |
| `failed` | Ran and failed | It is evidence the change is broken |
| `not_run` | Deliberately not run (no matching test, `AGENT_EMPIRICAL_VERIFY` off) | No |
| `unavailable` | Could not run (sandbox down, import/collection error, interpreter missing) | No |
| `timed_out` | Exceeded `AGENT_EMPIRICAL_VERIFY_TIMEOUT` | No |
| `untrusted` | Ran, but the result cannot be trusted: flaky (failed, then passed on identical code), stale (the file changed later), or superseded by a fresh pass | No |

A failing test run is re-run once on identical code. If it passes the second
time the check is `untrusted` (flaky): the step still fails, but the failure is
classed as flakiness, not as a defect in the change, and it is never counted as
proof. Nothing retries a test until it goes green.

## Verdicts

| Verdict | When | What the task does |
|---------|------|--------------------|
| `VERIFIED` | Every step applied, every mandatory check has a fresh `passed` result, the reviewer approved, and every criterion passed | The judge's PASS stands (a high-risk change also waits for a person) |
| `FAILED` | A step or check failed, the reviewer rejected, or the reviewer approved work the evidence shows is broken (`contract_violation`) | FAIL: sent back for rework with the classified defects as a comment |
| `BLOCKED` | A check could not run or timed out, or the reviewer produced no usable verdict | An approval is withheld; the task waits in review with the reason logged |
| `INCONCLUSIVE` | A mandatory check is missing, stale or flaky, planned steps did not run (time budget), UI evidence is missing, or the report is not bound to the run's contract | As `BLOCKED` |

Failures are classified as `implementation_defect`, `contract_violation`,
`environment`, `timeout`, `verifier_infrastructure`, `flaky`,
`stale_evidence` or `incomplete`. Only the first two make a run `FAILED`; the
next three make it `BLOCKED`; the rest make it `INCONCLUSIVE`.

The decision never treats any of these as success: the agent saying it is
finished, the code compiling, a subset of tests passing, a positive review on
its own, or a pass recorded against different content.

## Strategy selection and risk

Risk is classified from file paths (`classify_risk`), never from the task's
wording, and re-classified at the end of the run from the files actually
changed; the stricter tier wins. A planner-flagged risky step is high risk.

| Tier | Paths | Mandatory strategies |
|------|-------|----------------------|
| low | Documentation and text only (`*.md`, `*.rst`, `*.txt`, `docs/`) | `static` for any Python, `independent_review` |
| medium | Anything else | `static` + `unit` for Python, `ui` for frontend files, `independent_review` |
| high | The risky-module list (`agent/verification_strategies.py`), `packages/auth/`, governance, deployment, migrations, CI workflows, `render.yaml`, `proxy.py`, anything named `secret` | As medium, plus `human_approval` |

`property`, `differential` and `regression` are recorded as **advisory** when
they apply (deterministic logic; refactors and migrations; every confirmed
defect). The loop does not generate property or differential tests by itself;
the report lists them under `not_executed` and lists `regression_candidates`
for each confirmed defect, so the next attempt or a person can add one.

Verification is not authorization. A verified high-risk change is moved to
`in_review` with the reason "a person must approve it", and tagged
`risk:high-change`; the review autopilot (`tasks/review_autopilot.py`) never
acts on tasks tagged `risk:*`.

## The contract cannot be moved by the agent

The report records the contract's id, version and fingerprint (a hash of the
goal, criteria, invariants, risk tier and strategies). `check_binding()`
rejects a report produced against a different contract, so such a run is
`INCONCLUSIVE`. `amend_contract()` / `spec_store.amend_spec_contract()` refuse
any agent, runtime or system actor (`PermissionError`); a person's amendment
creates a new version, records who and why, and keeps the old contract in
`contract_history`.

## Where things are stored

| What | Where |
|------|-------|
| Contract | `agent_specs.contract` (and `contract_history`), rendered into the spec's markdown under "Verification contract" |
| Evidence reports | `agent_specs.evidence_reports` (last 20 per spec), `agent_specs.latest_verdict` |
| Run result | `verification_contract`, `verification_report` in the `AgentRunner.run` result (and in a task's `raw_result`) |
| Task verdict | `task.verification` (the evidence line `Evidence report <id>: <verdict>, … revision <sha>` is added to its evidence) |
| Session signal | a `verification_failed` session event for every non-`VERIFIED` run, clustered by `services/session_retro.py` |

Both are readable through the existing authenticated `GET /api/specs` and
`GET /api/specs/{spec_id}`. Check output, commands, reasons, judge notes and
findings are passed through `redact_secrets()` before they are stored; output
is kept to the last 2,000 characters.

## Learning from failures

A non-`VERIFIED` run logs `verification_failed` with its verdict and failure
class. The session retrospective clusters these by
`verification_failed:<verdict>:<class>` and, once a cluster reaches
`SESSION_RETRO_MIN_CLUSTER`, files an issue through the improvement loop for
a person to act on. No verification rule or policy is changed automatically.

## Running it yourself

```bash
# The change's verification plan, using the loop's own checks and decision engine:
python scripts/verify_change.py --base origin/master --out /tmp/verify.json
python scripts/verify_change.py --files services/calc.py
python scripts/verify_change.py --from-report /tmp/verify.json   # reproduce a run
```

Exit code 0 means every executable mandatory check passed, 1 means a check
failed, 2 means a check could not run, timed out, was flaky or is missing. The
harness has no reviewer model, so its report's verdict is `BLOCKED`, never
`VERIFIED`: a passing harness run is not a verified change.

Tests: `tests/test_verification_contract.py`,
`tests/test_verification_evidence.py`, `tests/test_verification_properties.py`
(seeded property and differential tests), `tests/test_verification_lifecycle_integration.py`
(the real `AgentRunner` with real pytest subprocesses), and
`tests/test_verify_change_script.py`.

## Configuration

| Control | Default | Effect |
|---------|---------|--------|
| `VERIFICATION_POLICY_ENFORCED` | `true` | The evidence decision gates the task verdict and high-risk approval. Off: the report is still produced and stored, the old rule-49 verdict applies |
| `TASK_VERIFICATION_REQUIRED` | `true` | Rule 49 gate (unchanged) |
| `AGENT_EMPIRICAL_VERIFY` | `true` | Run the checks at all. Off: every check is `not_run`, so no run is `VERIFIED` |
| `AGENT_EMPIRICAL_VERIFY_TIMEOUT` | `120` | Seconds per check command |
| `AGENT_TIME_BUDGET_S` | `0` | Run time budget; steps cut by it leave criteria unverified |

All are live controls under Settings → Platform controls. The retry budget is
`MAX_AUTO_REWORK` (2) task-level reworks and 3 attempts per file within a step.
Model cost per run is governed by the existing governance and token-quota
controls; the report lists the models each step used.

## Examples

**A run that verifies.** Plan: "Make `add` return the sum", file `calc.py`,
acceptance `add(2, 3) == 5`. The step applies, `static:py_compile` passes,
`unit:pytest` runs `tests/test_calc.py` and passes, both bound to the
fingerprint of the new `calc.py`. The judge approves. Report: `VERIFIED`,
criteria `step-1` and `goal` passed. Task: `done`, verdict PASS, with the
evidence line naming the report, contract and git revision.

**A failed run, then a correction.** First attempt writes `return a * b`. The
real pytest run fails (`assert 6 == 5`), the confirmation re-run fails too, so
the step fails with `failure_phase: empirical_verification`. The judge,
reviewing only the diff, approves. Report: `FAILED` with findings
`implementation_defect` (the failing test, with its output) and
`contract_violation` ("the reviewer approved, but the evidence contradicts
it"). Task: FAIL, sent back with the failing assertion in a comment. Second
attempt writes `return a + b`; the same checks pass; the report is `VERIFIED`
and the task completes. This exact scenario is
`tests/test_verification_lifecycle_integration.py::test_failed_attempt_is_corrected_and_then_verified`.

## Not yet supported

- **Parallel step execution.** When the planner's steps run in parallel
  (`_maybe_run_parallel`), the run returns early without a contract or report,
  and the previous rule-49 rules apply unchanged.
- **Other runtimes.** Claude Code, Hermes and the other prose runtimes are
  checked by `tasks/independent_verifier.py`, which does not yet produce an
  `EvidenceReport`; the previous rules apply to them.
- **Non-Python checks in the loop.** The loop executes checks for Python only;
  UI changes rely on the existing screenshot evidence; other files rely on the
  reviewer. The harness also parses changed JSON and YAML.
- **Generated property and differential tests.** Selected as advisory and
  reported as not executed; they are not generated automatically.
- **In-run correction of a failing test.** A failing check ends the step; the
  correction happens in the next task-level run, which reads the defects.
- **Scoped tests only.** Only `tests/test_<module>*.py` matching the changed
  file runs; a file with no matching test is reported as an untested remaining
  risk, and for medium/high risk the step's `unit` criterion stays unmet.
- **Cost.** Per-run token cost is not yet recorded in the report; the models
  used are.

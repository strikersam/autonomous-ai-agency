# Plan: agent pull requests that are right before a human sees them

From [`docs/intent/2026-10-08-agent-pr-quality.md`](../intent/2026-10-08-agent-pr-quality.md).

## Files that change

- `agent/pr_gate.py`: new checks and a `GateReport` with evidence; `pr_blockers()` kept as a wrapper.
- `agent/loop.py`: pass goal, planned files and base to the gate; give the judge the diff; a
  rejecting judge blocks the PR; PR body built from the gate report.
- `tests/test_agent_pr_gate.py`: one regression test per check, including replays of #1694 and #1696.
- `CHANGELOG.md`, `docs/changelog.md`: one entry.

## Order of work

1. Gate checks, each a small pure function over `(root, changed files, numstat)`:
   - changelog required for any change outside tests, docs and agent state (was: `.py` source only);
   - protected paths blocked outright;
   - destructive change: a file that loses at least 40 lines and more than twice what it gains, or is
     deleted, unless the goal asks for removal;
   - scope: files changed that no plan step named (changelogs, tests and generated graph exempt);
   - guard tests chosen by path (the model catalogue tests whenever model config changes);
   - frontend tests for changed `frontend/src` files when `node_modules` is present, recorded as
     "not run" otherwise.
2. `GateReport(blockers, evidence)`; evidence lines are what actually ran and how it ended.
3. Loop: resolve the base (`origin/<base>`, else `HEAD~<commits>`), feed the gate, feed the judge a
   truncated diff, treat `REJECTED` / `BLOCKED` / correctness `FAIL` as a blocker, render the PR body.

## Risks

- A too-strict gate stops all agent PRs. Mitigation: thresholds chosen from the two real failures
  (#1696 App.js: -62/+26; index.html: -1490/+51) and replayed in tests alongside legitimate changes.
- Judge fails to answer (provider down) → `BLOCKED` → no PR. That is the intended fail-closed outcome.

## Proof

`pytest tests/test_agent_pr_gate.py` covers every check, including #1694 and #1696 replays that are
blocked; the existing gate tests still pass; full `pytest -x` green before push.

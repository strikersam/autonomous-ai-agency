# Plan: adopt the rest of the AI-native SDLC playbook

From [`docs/intent/2026-10-08-playbook-adoption.md`](../intent/2026-10-08-playbook-adoption.md).

## Files that change

- `CLAUDE.md` → rules, commands with healthy output, reference index; `docs/reference/repo-reference.md` (new) takes §3–§5, §7.
- `scripts/claude_setup_audit.py`, `tests/test_daily_automation_2026_09_13.py`, `tests/test_cerebras_catalogue.py`: follow the moved sections.
- `REVIEW.md` (new); `agent/pr_gate.py` (`review_policy`, `plan_artifact`, tests-weakened check); `agent/loop.py` (judge reads REVIEW.md, plan committed before push).
- `tests/evals/` (new) and `.github/workflows/agent-evals.yml` (new).
- `loops/bands.yaml`, `scripts/control_bands.py`, `.github/workflows/control-bands.yml` (new); `loops/registry.yaml`.
- Tests: `tests/test_agent_pr_gate.py`, `tests/test_control_bands.py`; docs and changelogs.

## Order of work

1. Split CLAUDE.md without touching §1–§2; prove the context generator still carries all 48 rules.
2. REVIEW.md, judge wiring, plan artifact, tests-weakened check.
3. Evals as data plus config checks; the workflow and registry entry.
4. Control bands: config, detector, workflow, registry entry.

## Risks

- The tests-weakened check could block a legitimate test refactor. It only fires when an existing
  test file loses more assertions than it gains or gains a skip marker; a human can still make that change.
- A control-band false alarm files an issue; one issue is reused, never one per day.

## Proof

`pytest tests/evals tests/test_agent_pr_gate.py tests/test_control_bands.py`, the full suite,
`agent/loop_registry.py audit --check` showing no drift.

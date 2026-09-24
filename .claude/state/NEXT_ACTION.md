# Next Action

**Updated:** 2026-09-24

## Current state (2026-09-24)

Daily automation: session start had zero open PRs and zero `routine-backlog`
issues (clean slate after 2026-09-23's cleanup). Picked up the "next daily
run" pointer below about cost-tracker catalog-coverage gaps, cross-checked
every model id in `config/models.yaml` against `packages/ai/cost_tracker.py`,
and found a real bug: TokenIn (a fully free gateway) had no entries in the
cost table at all, so two of its ten `myt/*-free` ids
(`myt/claude-opus-4-8-free`, `myt/gpt-5.6-sol-free`) were fuzzy-matched by
`cost_for_tokens()`'s substring fallback to the paid `claude-opus-4-8` and
`gpt-5.6-sol` entries — free traffic billed at $5+/MTok in cost attribution.
Fixed with explicit `(0.0, 0.0)` entries for all ten TokenIn ids. PR
[#1566](https://github.com/strikersam/autonomous-ai-agency/pull/1566),
see active-tasks.md row 78 for full verification detail. Watching for CI.

## Prior state (2026-09-23)

Cleanup session 2026-09-23 (branch `claude/cleanup-open-prs-issues-kdzv7g`): drove every
open PR and issue to closed.

- **#1561** Langfuse session headers: branch was stale (missing master's brain_config
  nvidia entry, so `test_one_model_catalogue` failed). Merged master in, merged.
- **#1544** langfuse pin bump: green, merged.
- **#1541** frontend patch bumps: `npm ci` failed on an out-of-sync lockfile
  (`yaml@2.9.1` missing). Regenerated the lockfile and merged it.
- **#1536** 12 GLM/Qwen/Kimi catalog entries: merged master in twice (cost_tracker
  kept both sides; its active-tasks row renumbered 70 -> 74). Driven to merge.
- **#1553** draft context plan: closed as superseded (#1561 + #1555).
- **#1552** W39 backlog: closed, both items shipped.
- **#1559** "Cannot fix tests": the backoff test patched the global `time.sleep` and
  counted other threads' calls. Fixed plus a regression test.
- **#1557** trend digest: triaged, no action, closed.
- **#1505** CRISPY burn-in tracker: closed. `crispy-burn-in-check.yml` no longer opens a
  standing "not ready" issue; the gap goes to the job summary until CRISPY is ready.

## Workflow hardening (same day, second PR)

- `auto-merge.yml` had never merged anything: no checkout, no `--repo`, so every
  `gh` call failed and was swallowed. Now fixed via `GH_REPO`. **Check next session:**
  the first green non-draft `claude/*` PR should auto-merge; if not, read that run's log.
- The Dependabot sweep now regenerates out-of-sync frontend lockfiles (hourly).
- The agency-cycle escalation titles order-dependent failures as such, and a fix
  attempt that adds failures is reset to the pre-fix SHA and never pushed.
- Trend digest: issue only for `action-required` alerts. Orphaned-PR sweep: closes
  the plan PR of a `quick-note:rejected` issue.
- `.gitattributes` merge strategies for the tracker files and the graph report;
  `.claude/hooks/git-merge-drivers` registers the driver at SessionStart.

## Next daily run (2026-09-25)

- Watch PR #1566 to green/merge (see row 78 in active-tasks.md).
- Check for new models from DeepSeek, Google, Groq, Anthropic.
- Consider a general `TestNoFuzzyCollisionWithPaidModels`-style invariant in
  `tests/test_cost_attribution.py`: for every id in `_DEFAULT_COST_TABLE` at
  `(0.0, 0.0)`, assert no *other* table key's fuzzy substring match would
  return a nonzero cost for it — would have caught today's TokenIn bug (and
  any future one of the same shape) without needing to spot it by hand.
- Consider a `TestPaidModelsCostTrackerCoverage`-style invariant for models in routing candidates but absent from the llm catalog.
- Consider extending `TestTheCopiesMayNotDriftFurther`-style CI feedback earlier: a
  pre-commit or PR-description checklist item for "if you touch a reconciled provider's
  candidates in `config/models.yaml`, also update `packages/ai/brain_config.py`" would
  have caught a prior day's bug before it ever reached CI.

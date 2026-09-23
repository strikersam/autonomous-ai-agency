# Next Action

**Updated:** 2026-09-23

## Current state

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

## Next daily run (2026-09-24)

- Check for new models from DeepSeek, Google, Groq, Anthropic.
- Consider a `TestPaidModelsCostTrackerCoverage`-style invariant for models in routing candidates but absent from the llm catalog.
- Consider extending `TestTheCopiesMayNotDriftFurther`-style CI feedback earlier: a
  pre-commit or PR-description checklist item for "if you touch a reconciled provider's
  candidates in `config/models.yaml`, also update `packages/ai/brain_config.py`" would
  have caught today's bug before it ever reached CI.

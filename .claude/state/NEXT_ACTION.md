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

Daily automation 2026-09-24 (branch `routine/daily-2026-09-24`): PR open for CI.

**What was done:**
- Claude Opus 5.5 (`claude-opus-5-5`, released 2026-09-22) added to all 4 config
  files: `config/llm/models.yaml`, `packages/ai/cost_tracker.py`,
  `config/models.yaml`, `packages/ai/brain_config.py`.
- Pricing: $4/$20 per MTok (20% cheaper than Opus 5 at same capability tier).
- Opus 5.5 is now the first Anthropic routing candidate and the default
  planner/judge preset for the Anthropic provider.
- New `TestCandidatesAreDeclaredInLlmCatalog` CI invariant: all direct-API
  routing candidates must have a `config/llm/models.yaml` entry.
- 25 new tests in `tests/test_daily_automation_2026_09_24.py`, all passing.

## Next daily run (2026-09-25)

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
- Check for Claude Sonnet 5.5 or Haiku 5.5 releases (Anthropic announced they
  are "coming in the coming weeks" alongside Opus 5.5).
- Consider updating `role_presets` for the `aerolink` provider as well
  (currently still uses `claude-opus-5` as planner/judge — Opus 5.5 is
  cheaper and available via the Aerolink gateway too).
- Check for new NVIDIA NIM model additions (Nemotron 4 family rumoured).
- Check for new Groq models.
- Row 50 (provider/model source-of-truth + admin UI): still IN_PROGRESS, P1-P4
  remain; requires full backend deps in the sandbox.

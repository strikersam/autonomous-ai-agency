# Next Action

**Updated:** 2026-09-25

## #1565 nightly regression (2026-09-25, row 80)

Root-caused and reproduced locally: the browser-login flake was the test's own
wait (`networkidle` resolves instantly in the SPA → 500ms for login + redirect);
the Telegram approval e2e had failed every night behind `continue-on-error`
(wrong localStorage key, dead route, unwrapped response). Both fixed in
`tests/e2e/`; hermetic guards in `tests/test_nightly_e2e_helpers.py`.
**Open, not fixed:** `/api/auth/refresh` calls `ObjectId()` on SQLite UUID ids and
always 401s there, so on SQLite any expired access token logs the user out.
Production (Mongo) is unaffected.

## QA pass 2026-09-23 (branch `claude/autonomous-agency-qa-bugs-ut12ye`)

Live QA against a SQLite backend: route map vs every frontend call, anonymous probe of
every route, Playwright crawl + click-through of all 19 screens, status and schema
fuzzing. Fixed and tested: six routers and the OpenClaw pairing token open to anonymous
callers; `/api/activity` decorator on the unauthenticated impl; SQLite ignoring
projections (`secret_hash` leak); People & access hiding new sign-ups; ObjectId-on-UUID
500s (sources, authorize-repos); company domain 500; "Internal server error" on 4xx
rule violations and provider outages; Doctor "Fix all" hitting a nonexistent endpoint;
`wont_do` handling; 422 detail arrays crashing error banners.

**Follow-up (2026-09-24, same branch):** closed the open items — throttled anonymous
ticks + constant-time `CRON_SECRET`, anonymous `/api/doctor` without `GH_PAT`, Ollama
probe SSRF guard, OAuth-unconfigured redirect, fixed-message HTTP details, dead `api.js`
wrappers. Also found and fixed two more SSRFs (Knowledge URL ingest; scanner/SEO
redirects). Deliberately left: onboarding toggle still accepts unknown ids (pre-approval
by email); the "No schedules registered" alert (in production an empty scheduler does
mean a wipe).

## Previous state
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
[#1566](https://github.com/strikersam/autonomous-ai-agency/pull/1566) —
**merged to master as `74e2c96`, CI green.** See active-tasks.md row 78 for
full verification detail.

CI on this PR caught a real gap from the Opus 5.5 change below: 8
pre-existing regression assertions across three older daily-automation test
files hardcoded the previous `claude-opus-5` default/first-candidate value.
Fixed and pushed before merge — see active-tasks.md row 79's final note.

**Also today (2026-09-24), same branch/PR:** a second, concurrent
daily-automation session (deterministic `routine/daily-YYYY-MM-DD` branch
naming collided — not a duplicate pick of the same work) independently
added Claude Opus 5.5 (`claude-opus-5-5`, released 2026-09-22, $4/$20 per
MTok, 20% cheaper than Opus 5) to `config/llm/models.yaml`,
`packages/ai/cost_tracker.py`, `config/models.yaml` (first Anthropic
candidate, new planner/judge preset), and `packages/ai/brain_config.py`
(mirrored per rule 4), plus a new `TestCandidatesAreDeclaredInLlmCatalog`
CI invariant. See active-tasks.md row 79. Reconciled on discovery: fetched
the combined branch, verified no file-level conflict with the TokenIn fix,
and re-ran the full relevant check set on the merged tree — 118/118 tests
pass, `compileall` clean, `check_changelog_parity.py` PARITY OK,
`check_model_catalog_consistency.py` 75 ids/no drift. PR #1566 now carries
both changes. Watching for CI.

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

## Quick notes #1569 / #1570 (2026-09-25)

- Both had been auto-rejected **without the source being fetched**. Fixed the cause:
  `.github/scripts/github_source.py` reads GitHub repos/files; any verdict on an unread
  quick note becomes `unverified` → `quick-note:needs-source` (sweep skips it).
- #1569 → `agent/code_graph.py` (opt-in, `CODE_GRAPH_ENABLED` + `pip install codebase-memory-mcp`).
- #1570 → `agents/persona_library.py`: specialists now get a persona system prompt.
- **Check next session:** the next quick note linking a GitHub repo should show
  `✅ fetched` in its draft PR's Source Grounding table.

## Next daily run (2026-09-25)

- PR #1566 merged to master as `74e2c96` — done (rows 78 and 79 in
  active-tasks.md). The now-fully-merged branch `routine/daily-2026-09-24`
  could not be deleted this session (`git push origin --delete` was blocked
  by the auto-mode permission classifier as a destructive action); it is
  harmless left in place, but a future session with the right permission
  posture should clean it up (`branch-cleanup` skill).
- **Branch-naming collision (root cause worth fixing):** two daily-automation
  sessions ran the same day and both used the deterministic
  `routine/daily-2026-09-24` branch name, so their commits interleaved on one
  branch/PR instead of getting separate PRs — required manual reconciliation
  of `active-tasks.md`/`NEXT_ACTION.md` mid-session (one session's state-tracker
  commit silently overwrote the other's "Prior state" section and duplicated a
  row number) and, separately, CI on the shared PR caught a real cross-change
  regression (8 stale test assertions) that either change alone would not have
  triggered. If the same trigger is firing more than once a day (or two
  triggers point at the same routine), suffix the branch name with a short
  session id (`routine/daily-2026-09-24-<suffix>`) to avoid this recurring.
- Check for new models from DeepSeek, Google, Groq, Anthropic, NVIDIA NIM
  (Nemotron 4 family rumoured); Claude Sonnet 5.5 / Haiku 5.5 (Anthropic said
  "coming in the coming weeks" alongside Opus 5.5).
- Consider updating `role_presets` for the `aerolink` provider (still uses
  `claude-opus-5` as planner/judge — Opus 5.5 is cheaper and available via
  Aerolink too).
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
- Row 50 (provider/model source-of-truth + admin UI): still IN_PROGRESS, P1-P4
  remain; requires full backend deps in the sandbox.

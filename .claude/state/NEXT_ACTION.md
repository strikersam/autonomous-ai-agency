# Next Action

**Updated:** 2026-09-25

## SAM acts on alerts (branch claude/sam-request-handling-fvfk05)

SAM's `/agent/sam/chat` path had no tools, so "look into the alerts and fix
them" got a deflection. `agent/sam_actions.py` now reads the alerts feed and
queues fix tasks; LiveKit worker got `check_alerts`/`fix_alerts` and its
`create_task` now sets `pending_agent_run`. Next: confirm on the deployed
dashboard that a fix request shows new `alert-fix` tasks under Work.

## Daily automation 2026-09-25 (row 81)

Session start: 0 open PRs, 0 `routine-backlog` issues (clean slate). Picked
the still-open suggestion from the "Next daily run" section below rather
than inventing new work: a `TestNoFuzzyCollisionWithPaidModels`-style CI
invariant in `tests/test_cost_attribution.py` that generalizes row 78's
TokenIn fix — it scans every zero-cost cost-table id for a substring
collision with a paid id (the same check `cost_for_tokens()`'s fuzzy
fallback performs) and fails on anything not explicitly documented as a
legitimate same-model/different-provider pair. Verified it fails first
(emptied the allowlist, reran, caught 4 real live collisions) before
documenting them. PR [#1576](https://github.com/strikersam/autonomous-ai-agency/pull/1576)
— open, CI pending; auto-merge to be armed once green. See
active-tasks.md row 81 for full verification detail.

**The other "Next daily run" suggestion below about a
`TestPaidModelsCostTrackerCoverage`-style routing-candidates-vs-catalog
invariant was already shipped 2026-09-24** (row 79,
`TestCandidatesAreDeclaredInLlmCatalog`) — checked before picking today's
item to avoid duplicating it.

**Update:** PR #1576 merged to master as `fd9f838`, CI green (row 81 marked
DONE). No further action needed on this branch.

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

## Daily automation 2026-09-25 — DONE (row 80)
## Prior "next daily run" notes (2026-09-25, mostly resolved — see row 81 above)

PR [#1578](https://github.com/strikersam/autonomous-ai-agency/pull/1578) open,
auto-merge armed (squash). Two changes:

1. **Aerolink role_presets aligned to `claude-opus-5-5`** — `config/models.yaml` +
   `packages/ai/brain_config.py` (rule 4). 11 regression tests in
   `tests/test_daily_automation_2026_09_25.py`.
2. **`TestNoFuzzyCollisionWithPaidModels` merged** — two concurrent sessions both
   added the class independently; merge commit `3f0fc89` reconciles the allowlist
   approach (other session) with the behavioral `cost_for_tokens()` test (this
   session). 3 tests total, 47/47 passing. PARITY OK.

## Next daily run (2026-09-26)

- Watch for PR #1578 merging to master.
- Check for new models from DeepSeek, Google, Groq, Anthropic, NVIDIA NIM
  (Nemotron 4 family rumoured); Claude Sonnet 5.5 / Haiku 5.5 (Anthropic said
  "coming in the coming weeks" alongside Opus 5.5).
- **Branch-naming collision (root cause still open):** two daily-automation sessions
  ran the same day on 2026-09-24 AND 2026-09-25 and both used the deterministic
  `routine/daily-YYYY-MM-DD` branch name. If the same trigger fires more than once
  a day, consider suffixing with a short session id. The collisions have been benign
  (merge-resolvable) but they cost a cycle each time.
- Consider updating `role_presets` for the `aerolink` provider (still uses
  `claude-opus-5` as planner/judge — Opus 5.5 is cheaper and available via
  Aerolink too).
- ~~Consider a general `TestNoFuzzyCollisionWithPaidModels`-style invariant~~
  **Done 2026-09-25, row 81, PR #1576.**
- ~~Consider a `TestPaidModelsCostTrackerCoverage`-style invariant for models
  in routing candidates but absent from the llm catalog.~~ **Already done
  2026-09-24, row 79** (`TestCandidatesAreDeclaredInLlmCatalog`) — this note
  was stale by the time it was written; checked before starting today's work.
- Consider extending `TestTheCopiesMayNotDriftFurther`-style CI feedback earlier: a
  pre-commit or PR-description checklist item for "if you touch a reconciled provider's
  candidates in `config/models.yaml`, also update `packages/ai/brain_config.py`" would
  have caught a prior day's bug before it ever reached CI.
- Row 50 (provider/model source-of-truth + admin UI): still IN_PROGRESS, P1-P4
  remain; requires full backend deps in the sandbox.
- `/api/auth/refresh` always 401s on SQLite (ObjectId on UUID ids); production
  (Mongo) unaffected, but self-hosters see automatic logouts on token expiry.

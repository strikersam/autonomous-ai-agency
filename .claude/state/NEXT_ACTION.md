# Next Action

_Updated 2026-09-21._

> **2026-09-21 daily automation (this run):** Session-start HEAD already
> matched `origin/master` (`7b52c77d`) exactly — nothing to fast-forward.
> 12 open PRs: 11 routine Dependabot security-update PRs (`#1541`-`#1551`,
> left to the existing hourly Dependabot-sweep automation) and one stale
> catalog PR (`#1536`, CI green since 2026-09-20, not opened by this run,
> left for a human/future session). One `routine-backlog` issue, `#1552`
> ("Routine backlog — 2026-W39"), already had an auto-generated **draft**
> context-plan PR `#1553` attached that explicitly flags its own source as
> unfetched/unverified — left alone, not built on top of; read `#1552`'s own
> body instead, which does real `git grep`-verified root-causing.
>
> `#1552` shortlists two items. **Picked item 2** (Bedrock provider forcing
> empty-string static credentials onto every `boto3.client()` call, which
> disables boto3's own default credential chain — env vars, shared
> credentials file, SSO profile, or an IAM instance/task role) as the
> single highest-value, best-scoped fix; item 1 (Langfuse session-header
> propagation, a larger multi-path feature-completion task) left open.
>
> Root-caused beyond the issue's own framing: `_post_bedrock_converse`
> (`packages/ai/router.py` ~line 2017) is the actual bug (fixed here), but
> `ProviderRouter.from_env()` (~line 1013) separately never registers a
> `bedrock` provider *at all* unless both `AWS_ACCESS_KEY_ID`/
> `BEDROCK_ACCESS_KEY` and the matching secret env var are set — so an
> instance-role-only deployment still can't reach Bedrock via the env
> bootstrap after this fix, only via an admin-configured DB provider
> record (`from_provider_records`) with no key. Documented as a follow-up
> in the CHANGELOG entry and the PR body rather than fixed here: widening
> `from_env()`'s gating needs a new explicit opt-in env var (rule 37), a
> separate design decision.
>
> Fix: `_post_bedrock_converse` now only passes `aws_access_key_id`/
> `aws_secret_access_key` to `boto3.client()` when both `provider.api_key`
> and the `X-Bedrock-Secret` header are actually set — matching the
> existing `bool(api_key and secret)` convention already used one function
> away at `health_check`. 2 new regression tests, verified failing against
> the pre-fix code first. Verified: `pytest --noconftest
> tests/test_bedrock_provider.py` 39/39 relevant tests passed (3 unrelated
> pre-existing sandbox-dependency failures, reproduced identically against
> unmodified master); `compileall` clean; `check_changelog_parity.py`
> PARITY OK; `loop_registry.py audit --check` no drift. **Could not run:**
> full `pytest -x` (same recurring sandbox constraint — no full `motor`/
> `fastapi` app stack here; ran the directly relevant test file instead).
> PR [#1555](https://github.com/strikersam/autonomous-ai-agency/pull/1555)
> → `routine/daily-2026-09-21`, squash auto-merge armed (diff fully within
> the daily-automation guardrails: not a risky module, no migration, no
> breaking change, ≤5 files, no security-header/CORS change). **All required
> checks passed and auto-merge fired: squash-merged to master as `90b1eb7`
> at 07:32 UTC.** `.claude/state/active-tasks.md` row 70 has full detail.
>
> **Not done today, flagged for a human/future session:** issue `#1552`
> item 1 (Langfuse session-header propagation + the false changelog claim
> it corrects); the `from_env()` Bedrock-without-static-keys gap above;
> PR `#1536` (12-model catalog addition, CI green, sitting unmerged since
> 2026-09-20 — not opened by this run, left for a human or a future
> session to land); the still-open older `IN_PROGRESS` rows (2, 6, 8, 11,
> 27, 32, 50, 53) — not re-verified this session, per the same
> single-focused-item rationale as prior daily runs.

_Previous (2026-09-20):_

> **2026-09-20 daily automation — final state (supersedes the entry this
> replaces, written mid-session before the regression below was found):**
> No open PRs and no `routine-backlog` issues at session start. CI fully
> green on master `250b4d0` — checked workflow run history (not just the
> latest push) and confirmed both previously-known scheduled-workflow bugs
> (nightly-regression login-timing flakiness, the catalogue-probe daily red)
> were already fixed by other sessions earlier the same day (PRs #1533/#1534
> and #1525 respectively; latest runs of each are green).
>
> Picked up the one still-open, explicitly documented follow-up instead:
> the `POST /api/tasks` `405` that the 2026-09-19 and 2026-09-20 CHANGELOG
> entries both named and explicitly left unfixed. Root cause:
> `backend/server.py`'s SPA fallback was registered as
> `@app.get("/{full_path:path}")` — a route matching every path — which
> Starlette's router treats as a same-path/wrong-method partial match on any
> non-GET request, and serves that (a 405) *before* its own trailing-slash
> redirect check ever runs. Fixed by installing the fallback as
> `app.router.default` instead of a route. PR #1535 opened, local checks
> green, auto-merge (squash) enabled.
>
> **Auto-merge race:** #1535's auto-merge fired on its *second* push (the
> first fix plus a CI-driven bandit/hermetic-env follow-up) before its
> *third* push — a fix for a regression CI had just caught in the second —
> could be evaluated. Branch protection's required checks don't include the
> Playwright job that caught it, so that failure never blocked the merge.
> Master briefly carried a real regression: any frontend SPA route sharing a
> bare path with an API router's GET-only trailing-slash listing endpoint
> (e.g. `/runtimes` vs. `runtimes/api.py`'s `GET /runtimes/`) 307-redirected
> into that API's raw JSON instead of rendering the SPA, because leaving
> Starlette's own `redirect_slashes` on let a bare GET fall through to its
> redirect check and find the API route there. Confirmed live via
> `tests/e2e/test_browser.py`'s "Runtimes — empty page title" Playwright
> failure, then directly via `git show origin/master:backend/server.py`.
>
> Per the already-merged-PR protocol: restarted
> `routine/daily-2026-09-20-spa-trailing-slash` from the new `origin/master`
> and cherry-picked the fix (`app.router.redirect_slashes = False`,
> reimplemented scoped to non-GET/HEAD only — restores pre-#1535 GET/HEAD
> behavior exactly) rather than reusing #1535. Opened PR #1537; this time
> deliberately did **not** enable auto-merge — waited for every check,
> including both Playwright job instances, to complete green
> (`mergeable_state: clean`) before merging manually. Merged as `e32a948`.
> Master's `backend/server.py` verified post-merge to contain the
> `redirect_slashes` fix.
>
> 8 regression tests total in `tests/test_spa_trailing_slash_redirect.py`
> (6 for the original bug, 2 for the `/runtimes`-class regression); the
> `/runtimes` test verified failing against the incomplete first fix. Also
> fixed on the way: a missing `# nosec` on the new test's own
> `subprocess.run` (one new Bandit alert) and a per-key
> `env.setdefault("ADMIN_EMAIL", ...)` in that same test file tripping
> `tests/test_conftest_hermetic_env.py`'s repo-wide textual guard (restructured
> into a loop). Full detail in `.claude/state/active-tasks.md` row 69.
>
> **Not done today:** the older, still-`IN_PROGRESS` rows (2, 6, 8, 11, 27,
> 32, 50, 53) were not re-verified this session — today's pick was the
> single highest-value, best-scoped item per the daily-automation mandate
> (one focused fix, not a backlog sweep). **Worth flagging to a human:**
> branch protection's required-checks set doesn't include the Playwright
> browser job, which is how a real regression reached master via auto-merge
> today — may be worth adding it to required checks.

> **2026-09-19 health-check (this run):** No red CI on master (all checks on
> HEAD `79937c82` green). One open routine-owned PR,
> [#1529](https://github.com/strikersam/autonomous-ai-agency/pull/1529) →
> `routine/daily-2026-09-19`, had `mergeable_state: dirty` — a real merge
> conflict, even though its own CI was green — because its nightly-regression
> fix commit duplicated work already merged to master via #1530/#1531 (see
> below). Merged `origin/master` into `routine/daily-2026-09-19`; the only
> conflicts were in `.claude/state/NEXT_ACTION.md`, `.claude/state/active-tasks.md`
> and `graphify-out/GRAPH_REPORT.md` (no code conflicts — the duplicated
> workflow/test files merged cleanly since both sides carried identical
> content). Resolved state-file conflicts by keeping master's authoritative
> `DONE`/collision narrative for row 68. After the merge, #1529's diff against
> master is just its unique contribution — the 10-model catalog addition —
> since the nightly-regression fix part now matches master exactly. Pushed
> the merge commit to `routine/daily-2026-09-19`; CI will re-run and, once
> green, the PR's existing auto-merge (if armed) or a human can land it.

> **2026-09-19 daily automation (earlier run):** No open PRs and no
> `routine-backlog` issues at session start (CI green on master `b6731be4`).
> Reviewed recent workflow run history (not just the latest push) and found
> a real, reproducible bug: `.github/workflows/nightly-regression.yml`'s
> "Analyze failures" step — the step whose whole job is to classify and act
> on a real regression failure — crashes on the common case of a failure
> with no console/CRUD/server-error markers, because a `grep -c PATTERN
> FILE 2>/dev/null || echo 0` idiom doubles its own output whenever grep
> finds zero matches (grep -c already prints "0" and exits 1). Since that
> job only runs after a regression failure, this has been silently
> disabling both auto-fix and issue-filing for every real nightly
> regression failure. Reproduced directly in a sandbox script before
> touching the workflow. Fixed by moving the `|| echo 0` fallback onto the
> assignment itself. 5 new regression tests run the actual shell from the
> workflow file; 4/5 fail against the pre-fix script. PR
> [#1530](https://github.com/strikersam/autonomous-ai-agency/pull/1530) →
> `routine/daily-2026-09-19-nightly-regression-fix`, **merged to master as
> `e0e9960`.** See `.claude/state/active-tasks.md` row 68 for full detail.
>
> **Branch-name collision mid-session:** first pushed this work to
> `routine/daily-2026-09-19` as PR #1529, but a second, independent same-day
> session derived the identical branch name from the standard convention
> and, on its own push, fetched/merged this branch into theirs — silently
> carrying these commits into their PR (unrelated model-catalog work) and
> overwriting its title/body. Recovered onto a distinctly-named branch and
> reopened as #1530; #1529 was left alone (commented explaining what
> happened) rather than force-pushed over, since it's a still-active
> session's PR. Worth a naming-convention fix (e.g. append a short session
> id to `routine/daily-YYYY-MM-DD`) so two same-day sessions can't collide.
>
> **Not done today, flagged for a human/future session:** the underlying
> `405 Method Not Allowed` that the crashing step was trying to classify —
> `backend/server.py`'s catch-all SPA route `@app.get("/{full_path:path}")`
> (registered after `task_router`) intercepts Starlette's trailing-slash
> redirect for any bare `POST /api/tasks` (the router only registers
> `/api/tasks/`), so callers get a `405` instead of a `307` redirect.
> `tests/e2e/test_telegram_approval_e2e.py::_seed_requires_approval_task`
> hits this directly. Documented in the PR body as a follow-up; not fixed
> here since today's fix (the analyze-step crash) was the higher-value,
> better-scoped single item and both together would have widened the PR
> beyond one focused change.

_Previous (2026-09-18):_

> **2026-09-18 daily automation (this run):** No open PRs and no
> `routine-backlog` issues at session start (issue #1499 fully drained — see
> 2026-09-16 note below). CI green on master (`d01bae0`). Reviewed scheduled
> workflow run history and found `.github/workflows/catalogue-probe.yml`
> failing on every scheduled run since at least 2026-09-13 — pure noise: the
> follow-up `probe_report.py` step already correctly classified every failure
> as account/transient (cerebras billing hold, nvidia 503, anthropic 400) and
> deliberately did not file a drift issue, but the probe step's own exit code
> still turned the whole job red daily. Fixed with `continue-on-error: true`
> on the scheduled step only (manual dispatch untouched). PR
> [#1525](https://github.com/strikersam/autonomous-ai-agency/pull/1525)
> → `routine/daily-2026-09-18`, squash-merged to master as `63a6e0d`; see
> `.claude/state/active-tasks.md` row 67 for full detail, including the one
> documented non-blocking trade-off (masks a genuine script crash in that
> step too, not only the transient case) and the merge-conflict resolution
> against the other same-day session's PR (#1524, row 66).
>
> **Correction:** issue #1499 itself is `closed` (`state_reason: completed`,
> closed by the maintainer on 2026-09-16) — not open as a prior NEXT_ACTION
> note implied. Item 4 (MCP 2026-07-28 stateless-core migration) was never
> implemented; whether the closure means the maintainer decided against it
> or simply closed the tracker with it still on record is not something this
> session can infer — left as-is, no further action taken on it.

> **2026-09-18 daily automation (a separate, parallel run):** Three model catalog gaps closed —
> (1) `deepseek-flash` (DeepSeek V4.1-Flash, released 2026-09-10): 1M context,
> multimodal, MIT licence, $0.30/$1.20/MTok; added as first DeepSeek candidate and
> planner/verifier/judge preset across `config/models.yaml`, `packages/ai/brain_config.py`,
> and `packages/ai/cost_tracker.py`; (2) `qwen/qwen3.8-27b`: already in Groq
> candidates since 2026-09-14 but no `config/llm/models.yaml` entry, causing
> `supports_tools: false` default and silent exclusion from every tool-calling request;
> (3) `deepseek-chat`, `deepseek-coder`, `deepseek-reasoner`: same catalog-gap issue;
> `deepseek-reasoner` correctly set to `supports_tools: false` (R1's reasoning-trace
> format is incompatible with `tool_calls` output).
> 32 new tests in `tests/test_daily_automation_2026_09_18.py` — all pass.
> `check_model_catalog_consistency.py` → `CATALOGUE OK: 47 declared ids, no drift`.
> `compileall` clean. Changelog parity OK.
> PR opened on `claude/intelligent-gates-frwr3p`, auto-merge enabled (SQUASH).
> **Not done today:** MCP 2026-07-28 stateless-core migration (issue #1499 item 4) —
> rule 40 gated, needs human decision.

_Previous (2026-09-16):_

> **2026-09-16 daily automation (this run):** One open PR at session start —
> [#1516](https://github.com/strikersam/autonomous-ai-agency/pull/1516)
> ("web_reach domain allow/block list", issue #1499 item 2) had been opened
> by another run just minutes before this session started, already complete
> (13 tests, changelog, risky-module-review done) with CI still in progress —
> not duplicated (see that run's own note just below). `routine-backlog`
> issue #1499 now has only item 4 left (MCP 2026-07-28 stateless-core
> migration), explicitly rule-40-gated and not for autonomous pickup. With
> the backlog otherwise spoken for, picked Bug Log #18 instead
> (`.claude/state/active-tasks.md`, `BUG_FOUND` since 2026-07-22, never
> fixed): `CompanyGraphPanel` in `KnowledgeScreen.jsx` re-validated the
> persisted `COMPANY_ID_KEY` against `listCompanies()`'s default `limit=100`
> page **unconditionally**, unlike `CompanyScreen.jsx` (PR #962), which only
> does that when there is no stored ID at all. An admin/owner with >100
> companies whose stored ID fell outside the first page got it wrongly
> cleared and replaced with `list[0]`. Fixed by mirroring `CompanyScreen.jsx`'s
> gating (`if (!selectedCompanyId && list.length > 0)`). 1 new regression
> test (verified failing against the pre-fix condition first, rule 31); full
> frontend suite 24/24 suites, 158/158 tests passing; `CI=true npm run build`
> clean; `compileall` clean; changelog parity OK. PR
> [#1517](https://github.com/strikersam/autonomous-ai-agency/pull/1517) →
> `routine/daily-2026-09-16`. **#1516 merged to master as `80bbb03`** while
> this PR was open — merged master back into this branch, resolving
> conflicts in `.claude/state/*` and `graphify-out/GRAPH_REPORT.md` (no code
> conflicts). CI green on the merge commit, auto-merge fired —
> **squash-merged to master as `dbfb5d6`.** Both of today's PRs (#1516,
> #1517) are done. **Not done today, still open:** issue #1499 item 4 (MCP
> 2026-07-28 stateless-core migration) — explicitly rule-40 gated, needs a
> human decision on whether/how to adopt the breaking protocol change;
> issue #1499 itself can be closed once that decision is made, or left open
> as the tracker for it.

> **2026-09-16 daily automation:** One open `routine-backlog` issue (#1499) and
> no open PRs at session start. Items 1 and 3 were already done (rows 61, 62);
> item 4 (MCP 2026-07-28 stateless migration) is explicitly rule-40 gated —
> not for autonomous implementation.
>
> Implemented **issue #1499 item 2** — optional domain allow/block list for
> `agent/web_reach.py` (`WEB_REACH_ALLOWED_DOMAINS` / `WEB_REACH_BLOCKED_DOMAINS`).
> risky-module-review completed (rule 15). 13 new tests added (43/43 passing).
> `compileall` clean. `check_changelog_parity.py` PARITY OK. graphify updated.
>
> PR [#1516](https://github.com/strikersam/autonomous-ai-agency/pull/1516) opened
> on `claude/intelligent-gates-tzazv0`, auto-merge enabled (SQUASH), subscribed to
> PR activity. Waiting for CI to go green.
>
> **Issue #1499** remains open — item 4 (MCP stateless migration) was deliberately
> not implemented; needs a human decision per rule 40. Issue can be closed once
> PR #1516 merges (items 1-3 done, item 4 deferred to human).
>
> **Not done today:** MCP 2026-07-28 stateless-core migration (issue #1499 item 4) —
> rule 40 gated, needs human decision on whether to adopt the breaking protocol
> change.

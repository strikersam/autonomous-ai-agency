# Next Action

_Updated 2026-09-22._

> **2026-09-22 daily automation (this run):** Session-start HEAD matched
> `origin/master` (`b40fbde9`) exactly. Open PRs at session start: five —
> `#1554` (cost-tracker gap fill, opened 2026-09-21, CI green,
> `mergeable_state: dirty` against current master — a real conflict, not a
> flake, since master had advanced with `#1555`/`#1556` and 8 Dependabot
> bumps in the meantime), `#1553` (draft, self-flagged unfetched/unverified
> context plan for issue `#1552`, correctly left alone), `#1536` (stale
> catalog PR, CI green since 2026-09-20, still not opened by any daily run,
> still left for a human), and two routine Dependabot security-update PRs
> (`#1541`, `#1544`, left to the existing hourly sweep). No open
> `routine-backlog` issues (`#1552` carries only `quick-note:rejected` now).
>
> Rather than starting new work, rescued `#1554`: a real, small, tested fix
> (`packages/ai/cost_tracker.py`, 14 lines — 9 model ids present in
> `config/llm/models.yaml` but absent from the cost table, including the
> paid `claude-sonnet-4-5` at $3/$15 per MTok silently billing as $0) that
> had been sitting open with green CI for over 24h purely because of a
> **row-70 numbering collision** in `.claude/state/active-tasks.md`: two
> independent 2026-09-21 sessions (this one and the Bedrock-fix session,
> `#1555`) both wrote a new row 70, and whichever merged first — the
> Bedrock one — made every subsequent commit on `#1554`'s branch conflict
> on the state files it touches (`NEXT_ACTION.md`, `active-tasks.md`,
> `graphify-out/GRAPH_REPORT.md`), even though **`cost_tracker.py` itself
> had zero code conflicts** — confirmed via
> `git log 7b52c77d..origin/master -- packages/ai/cost_tracker.py
> tests/test_daily_automation_2026_09_21.py config/llm/models.yaml`
> (empty). Merged `origin/master` into `claude/intelligent-gates-0ia6n2`,
> resolved the three state-file conflicts (this file, `active-tasks.md`
> renumbered to row 71, `GRAPH_REPORT.md` regenerated fresh rather than
> merged by hand), re-ran the full local check set against the merged
> tree, and pushed. See `.claude/state/active-tasks.md` row 71 for the
> rescue detail and row 70 (Bedrock, `#1555`) for what it collided with.

_Previous (2026-09-21, Bedrock credential fix):_

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

_Previous (2026-09-21, cost-tracker gap fill):_

> **2026-09-21 daily automation — final state:**
>
> No open PRs at session start; CI green on master `7b52c77d`.
>
> Found 9 models in `config/llm/models.yaml` with no entry in
> `packages/ai/cost_tracker.py` — `cost_for_tokens()` silently returns 0.0
> for any model not in its table. Critical: `claude-sonnet-4-5` is a paid
> model at $3/$15/MTok that was never tracked.
>
> Fixed all 9 gaps. New invariant test `TestPaidModelsCostTrackerCoverage`
> prevents this class of regression: CI fails if any paid catalog model
> has no cost_tracker entry.
>
> PR [#1554](https://github.com/strikersam/autonomous-ai-agency/pull/1554)
> opened on `claude/intelligent-gates-0ia6n2`, CI green same day. Went
> stale (`mergeable_state: dirty`) once `#1555` merged first and claimed
> the same `active-tasks.md` row number — rescued the next day, see the
> 2026-09-22 entry above.

_Previous (2026-09-20):_

## Carry-over items (from prior sessions)

- Row 53 (`IN_PROGRESS`): catalogue probe fix for disabled local providers.
  Branch `claude/upbeat-goodall-gm78vl`, PR [#1443](https://github.com/strikersam/autonomous-ai-agency/pull/1443).
  Auto-merge may have fired — verify.

- Row 50 (`IN_PROGRESS`): central provider/model source of truth. Phase 0
  done. P1–P4 require the full pytest suite (real MongoDB).

- Rows 2, 6, 8, 11, 27, 32: stale `IN_PROGRESS` from June–July 2026.
  Branches may be merged or abandoned. Verify before picking up.

## Routine to pick up next session

- PR #1554 rescued and pushed 2026-09-22 — check CI on the merge commit;
  merge if green (see the 2026-09-22 entry above for the row-70 collision
  it recovered from).
- PR #1536 (12-model catalog addition) still open, CI green since
  2026-09-20, still not picked up by any daily run — consider landing it.
- Consider: a `TestPaidModelsCostTrackerCoverage`-style invariant for models
  in routing candidates but absent from the llm catalog (the inverse of the
  catalogue probe — ensures new candidates are always declared).
- Consider a branch-naming convention that includes a short session id, to
  avoid the `routine/daily-YYYY-MM-DD` collisions documented in rows 68/69,
  and this session's `active-tasks.md` row-70 collision.

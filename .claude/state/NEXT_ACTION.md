# NEXT_ACTION — updated 2026-11-10 (lifecycle status types validated)

**What shipped:** `packages/lifecycle/` declares 21 app lifecycles as validated data, with a registry, a guard and a generated map (`docs/lifecycles.md`); the task lifecycle and the workflow run's status now follow their declarations (slice stages `executing -> reviewing -> verifying -> executing`, no undeclared `report`, phase-driven status writes guarded). The two workspace managers now share one lifecycle declaration: `RESUMABLE_STATES` and `ACTIVE_STATES` live in `workspace/manifest.py` and `agent/workspace.py` imports them, so resuming an active workspace is an idempotent heartbeat in both. Company onboarding now writes the granular states it declares (scanning/detected/configured) and the progress view reports them. Findings: 6 -> 2. Ten lifecycles now also bind the enum or `Literal` that types their field, and `scripts/lifecycles.py check` fails when either side drifts.

## Open items

1. Consider driving `clarify_task` through `TaskWorkflowService.transition` once needs_clarification has an incoming edge.
2. Eleven lifecycles are still typed by plain strings (agent job, CEO goal/subtask/attempt, approval gate, onboarding, onboarding progress, scan, spec, specialist, task queue); declare a `status_type` when one gains an enum.

---
# NEXT_ACTION — updated 2026-11-06 (daily automation, branch `claude/intelligent-gates-x7y1ze`)

**What shipped:** Mistral Large 4 (`mistral-large-4-0`) catalogue update — context window corrected to 524 288 (was 131 072), cache-read fraction added at 10 % (was missing, so cached tokens had 0 % discount). Open weights released 2026-10-29 noted in comments. 14 tests pass; all gates green. PR #1902 open, auto-merge armed (SQUASH).

## Open items for next daily run

1. **Confirm PR #1902 merged** — if CI is green it auto-merges. If red, investigate.
2. **Gemini 4 Argon pricing** — introductory $2/$10/MTok ends 2026-11-30; standard $4/$20 starts 2026-12-01. Update `packages/ai/cost_tracker.py` before December.
3. **Mistral Large 4 API context window** — currently 524 288; monitor Mistral's docs for an increase to the full 1 M. Raise priority from 62 once confirmed probed and not "public preview".
4. **November model releases check** — no confirmed new text LLMs beyond what's in the catalogue as of 2026-11-06. Re-check on next run (Qwen 4, any OpenAI Nov release).
5. **Render quota** — quota reset 2026-11-01; quiet-hours in keepalive/worker prevent repeat exhaustion. Monitor Render logs.
# NEXT_ACTION — updated 2026-11-08 (free sandbox: Freestyle + provider chain)

**Update:** chain is now freestyle → daytona → instabox → e2b (`SANDBOX_PROVIDERS`). Set `DAYTONA_API_KEY` / `INSTABOX_API_KEY` in Render to enable the fallbacks; none was exercised live (hosts blocked from the build container).

**What shipped:** sandbox provider registry (`services/sandbox_providers.py`) with ordered failover (`SANDBOX_PROVIDER`, default `auto` = Freestyle first, then E2B); Freestyle VMs via REST (`services/freestyle_sandbox.py`). Branch `claude/optimistic-hawking-yrb1qe`.

## Open items

1. **Operator:** create a Freestyle account (Free plan, $1 refundable card check), put `FREESTYLE_API_KEY` in Render, keep `E2B_ENABLED=true`.
2. First live run on Render: Freestyle's API was unreachable from the build container, so request shapes are verified only against the official TS SDK source (`freestyle@0.2.21`). Watch logs for `Sandbox opened on provider freestyle` / `Sandbox provider freestyle failed to open`.
3. Freestyle caps one exec at 5 minutes; `AGENT_SANDBOX_INSTALL_DEPS` installs can hit it on big repos — a `FREESTYLE_SNAPSHOT` with deps baked in avoids that.

---
# NEXT_ACTION — updated 2026-11-07 (Hallmark redesign, PR #1910)

**What shipped:** landing page redesigned and dashboard tokens restyled with Hallmark's Console theme; public autonomy claims corrected to match full autonomy mode; `og.jpg` re-captured without its slop tells. PR #1910, auto-merge (squash) armed.

## Open items

1. `brag-output/composition/index.html` (the feature-tour video) still uses tracked-caps scene labels and a coloured headline word, and its leash scene predates full autonomy mode. Re-cut it if the video is published again.

---
# NEXT_ACTION — updated 2026-11-07 (agent memory)

**What shipped:** per-agent memory with offline dreaming (`services/agent_memory/`) on branch `claude/loving-planck-s0bzrc` (`7c12f6a`, `3a4189e`). Independent verifier: FAIL round 1 (4 defects, fixed with regression tests), PASS round 2.

## Open items

1. **Open a PR** when the operator asks; CI (with Mongo) is the authority on the full suite.
2. Watch the first real dream cycles on Render: check the judge model returns usable JSON ops (`agent_memory: dream for … returned no usable ops` in logs means it does not).
3. Not built: wiki-style linked memory pages and a dashboard view of agent memory (API exists: `GET /api/agents/{id}/memory`).
4. Agents only write notes if they follow the `REMEMBER(kind):` convention; measure adoption from episode `notes_written` after a week.

---
# NEXT_ACTION — updated 2026-11-02 (daily routine)
# NEXT_ACTION

> Updated: 2026-11-07 (daily automation session)

## Just completed

**Daily automation 2026-11-07** — PR #1903 open, auto-merge armed (squash):
- `tencent/hy4-preview` added to cost_tracker.py + models.yaml ($0.83/$2.50, 5% cache, 1,048,576 ctx, priority 99)
- `google/gemini-3.1-pro-preview` OpenRouter alias added to cost_tracker.py ($2.00/$12.00)
- 25 tests pass; compileall clean; PARITY OK; CATALOGUE OK (104 ids)

## For the next daily automation run

Candidates deferred — verify before next run:
1. **`gemini-omni-flash-preview`** (Vertex AI `$1.50/$9.00`): No OpenRouter listing as of 2026-11-07; check openrouter.ai/models for `google/gemini-omni*` slug before adding.
2. **GPT-6 Astra Ultrafast tier**: Mentioned at DevDay Sept 2026; listed in cost_tracker as `gpt-6-astra` at $10/$50 — verify if a separate `ultrafast` variant has a different API ID or pricing.
3. **Gemini 3.1 Pro cache fraction**: May be 10% (not 25% generic) per OpenRouter page $0.20/MTok cache read; needs confirmation from ai.google.dev/pricing directly before adding an override.

## Open tasks requiring human action

- Row 50 (provider source of truth): P1-P4 require full pytest suite — needs backend deps.
- Row 34 (TokenIn): blocked on Render billing.
- Bug 16/17 (gate bypass, orchestrator): architecturally significant, needs human decision.

## 2026-11-08 daily routine

- Shipped: `verifier_reject` safety_event from `agent/write_gate.py::gated_write` (backlog #1892 item 1, second half; web_reach half was #1894). 2 tests in `tests/test_safety_events.py`.
- Still open from #1892: item 1 workspace-boundary events (needs `agent/tools.py` = risky, rule 15), item 3 doctor `--network-only`, item 2 per-role effort, item 4 symlink audit (audit only, human gate).
- Sandbox note: no MongoDB, so `tests/test_auth_me_regression.py` errors (pymongo connection refused) on master too. Use a venv (`python -m venv`) since Debian packages block pip.

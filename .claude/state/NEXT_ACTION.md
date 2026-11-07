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

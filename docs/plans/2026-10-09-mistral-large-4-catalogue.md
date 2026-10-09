# Plan: Mistral Large 4 ("Le Chonk") — model catalogue addition

**Date:** 2026-10-09  
**Session:** daily-automation  
**Branch:** claude/intelligent-gates-rfkpo8

## Goal

Add Mistral Large 4 (`mistral-large-4-0`) to the model catalogue so the router
and cost-tracker can attribute spend and try the model as a routing candidate.

## Background

Mistral AI released "Le Chonk" on 2026-10-06 as a public API preview:
- 1.05 T-parameter mixture-of-experts, 49 B active parameters
- Multimodal; native function calling and tool use
- Context window: up to 1 M tokens (API: 131 072 for safety)
- Preview list price: $1.36 / $4.18 per MTok input / output
- Open weights promised ~2026-10-31
- Available via api.mistral.ai and OpenRouter (`mistralai/mistral-large-4-0`)

## Files changed

| File | Change |
|------|--------|
| `config/llm/models.yaml` | New `mistral-large-4-0` entry, priority 62, speed_tier slow |
| `packages/ai/cost_tracker.py` | `"mistral-large-4-0": (1.36, 4.18)` |
| `config/models.yaml` | Added to Mistral `candidates` list |
| `packages/ai/brain_config.py` | Added to `PROVIDER_CANDIDATES["mistral"]` |
| `tests/test_daily_automation_2026_10_09.py` | 17 new tests (all pass) |
| `CHANGELOG.md` / `docs/changelog.md` | Unreleased entry added |

## Acceptance criteria

- [x] `cost_for_tokens("mistral-large-4-0", 1_000_000, 0)` ≈ $1.36
- [x] `cost_for_tokens("mistral-large-4-0", 0, 1_000_000)` ≈ $4.18
- [x] Cheaper per-token than `mistral-large-latest` (Large 2) on both input and output
- [x] Declared in `config/llm/models.yaml` with `supports_tools: true`
- [x] Listed in `config/models.yaml` Mistral candidates
- [x] Listed in `brain_config.PROVIDER_CANDIDATES["mistral"]`
- [x] `python -m compileall -q .` clean
- [x] `python scripts/check_changelog_parity.py` passes
- [x] `python agent/loop_registry.py audit --check` no drift

## Notes

- Model not yet probed on this account; live health checks in the router will
  validate it before sending traffic. A failed probe leaves it in the dead-model
  list until the next health-check cycle.
- Pricing uses the full list price, not the launch-discount rate, to avoid
  overstating revenue when the discount expires.
- Context window is conservatively set to 131 072 matching other Mistral entries;
  update to 524 K or 1 M once the API limit is confirmed in the Mistral docs.

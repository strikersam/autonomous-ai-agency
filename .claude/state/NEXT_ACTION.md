# Next Action

**Updated:** 2026-09-23

## Current state

Daily automation 2026-09-23: PR #1560 (yesterday's daily automation) was CI red on
`Test (Python 3.13)` at session start, not auto-merging as row 72's note assumed. Fixed
and pushed to the same PR branch (`claude/intelligent-gates-akgaus`, commit `27a8996`);
CI should re-run on the new head. Subscribed to PR activity.

## PR #1560 — daily-2026-09-22 catalog updates + 2026-09-23 CI fix

- `deepseek-ai/deepseek-v4.1-flash` added to NVIDIA NIM candidates (last position, conservative `supports_tools:false`)
- `moonshotai/kimi-k2-instruct` pricing corrected $0.00 → $1.00/$3.00 per MTok
- `gemini-omni-1.1-flash` added to catalog (no routing candidates — video model)
- **2026-09-23 fix:** the NVIDIA candidate addition above was never mirrored into
  `packages/ai/brain_config.py`'s hardcoded `PROVIDER_CANDIDATES["nvidia"]`, which
  `tests/test_one_model_catalogue.py::TestTheCopiesMayNotDriftFurther` requires to stay
  reconciled with `config/models.yaml` (rule 4). That's what was actually failing CI.
  Fixed by adding the same id in the same position to the Python list. 81/81 relevant
  tests pass (`test_one_model_catalogue.py` + `test_nvidia_default_model.py` +
  `test_daily_automation_2026_09_22.py`); consistency/parity/compile/loop-registry gates
  all clean. See `.claude/state/active-tasks.md` row 73 for full detail.
- **Check next session:** did CI go green on `27a8996` and did the PR merge (auto-merge
  was not armed by this session — verify the repo's branch protection / auto-merge
  settings before assuming it will merge unattended)?

## Recently merged

- **#1554** `fix(cost-tracker): fill 9 missing model entries including paid claude-sonnet-4-5` — merged 2026-09-22 as `12565bb`. Adds `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `claude-sonnet-4-5` ($3/$15), and 7 others plus local Ollama entries. Merge conflict with PR #1560 resolved (cost_tracker end-of-table section, state files).

## Outstanding PRs (not this session's)

- **#1553** draft context plan for issue #1552 (W39 backlog) — draft, explicitly unfetched/unverified (R1 unmet). Not merged.
- **#1536** 12 ZhipuAI/DashScope/Moonshot model entries — CI green since 2026-09-20 (checked again 2026-09-23, still green modulo an old, likely-unrelated Playwright failure from that date not re-investigated this session), still not opened by any daily run. Left for human or future session — consider landing.

## Next daily run (2026-09-24)

- Confirm PR #1560 merged (or address any new CI failure on it — this is the second
  round of CI catching a real gap on this PR, so re-verify carefully rather than
  assuming green).
- Check for new models from DeepSeek, Google, Groq, Anthropic.
- Issue #1552 (W39 backlog) still has `quick-note:rejected` label from the draft plan — re-read the issue body directly (not the draft PR) for actionable items; item 1 (Langfuse session-header propagation) is still open and unimplemented.
- Consider landing PR #1536 (12 ZhipuAI/DashScope/Moonshot entries, CI green since 2026-09-20 — now 3+ daily runs without being picked up).
- Consider a `TestPaidModelsCostTrackerCoverage`-style invariant for models in routing candidates but absent from the llm catalog.
- Consider extending `TestTheCopiesMayNotDriftFurther`-style CI feedback earlier: a
  pre-commit or PR-description checklist item for "if you touch a reconciled provider's
  candidates in `config/models.yaml`, also update `packages/ai/brain_config.py`" would
  have caught today's bug before it ever reached CI.

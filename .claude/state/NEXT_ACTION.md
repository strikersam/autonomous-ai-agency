# NEXT_ACTION — updated 2026-11-12 (retired-model auto-replacement, same branch)

**What shipped:** `packages/ai/model_retirement.py` + live control `MODEL_AUTO_HEAL_ENABLED`: stored model choices move off provider-retired ids for every provider, from 404/410 evidence plus the provider's `/models` listing. Two verifier rounds, both PASS+NOTES; deny-list and id-spelling notes fixed with tests.

## Open items

1. Strikes and replacements live in process memory; after a restart a retired id costs two failed calls (about 30 min apart) before it is replaced again. The brain config change is persisted.
2. A replacement is never undone automatically if the original id comes back.
3. `docs/configuration-reference.md` lines for `AGENT_PLANNER_MODEL` / `AGENT_EXECUTOR_MODEL` / `AGENT_VERIFIER_MODEL` still name the retired `nvidia/nemotron-3-super-120b-a12b` as the default.
4. Not verified here: frontend tests/build (no node_modules), anything needing MongoDB or a live provider.

---
# NEXT_ACTION — updated 2026-11-12 (task failure rate, branch `claude/epic-hopper-mwe63w`)

**What shipped (pushed, no PR yet):** `agent/capacity_backoff.py` — a rate-limited brain is waited out (20 s, 40 s) instead of retried after 0.5 s; planning retries a capacity failure twice. `tasks/service.py` `_is_transient_error` — 429/5xx/sandbox-provider errors re-queue instead of failing. Independent verifier: PASS+NOTES (notes on loose markers fixed with tests).

**Evidence (Render logs, 2026-11-12, via the Render connector):** tasks end in `All brain providers exhausted` / `nvidia HTTP 429`; Groq key quota exhausted; ~20 adaptive-halter trips in under 3 h, each three steps failing ~5 s apart.

## Open items

1. **Not shipped, needs a live probe:** `gpt-oss-20b` re-sends an identical prompt up to 4x per tool selection (reasoning-only replies, no JSON). Candidates: `reasoning_effort: low` for gpt-oss on NVIDIA/Groq, and `response_format: json_object` in `AgentRunner._chat_json`. Neither could be tested from the build container.
2. **Operator:** capacity is one free NVIDIA key. Add Cerebras/TokenIn keys or a second NVIDIA key; Freestyle allowance is used up (`429 LIMIT_EXCEEDED`), Daytona returns HTML errors, E2B auth returned 503.
3. Stored `nvidia-nim` provider record still defaults to retired `nvidia/nemotron-3-super-120b-a12b` (404 every 30 min); `frontend/src/pages/SetupWizardPage.js` and `frontend/src/v5/screens/ProvidersScreen.jsx` still offer it.
4. After deploy, re-check halter trips and `brain capacity error, waiting` log lines to confirm the effect.
5. Full suite cannot run here (no MongoDB); CI is the gate.

---
# NEXT_ACTION — 2026-11-11

No pending action from this session. #1923 (`f7b5bc83`) and #1913 (`825f71ee`) are merged and master is green.

The follow-ups that must outlive `update_next_action` live in `.claude/state/active-tasks.md` row 117 (decide the DeepSeek rate precision); the graph-report task (row 116) closed in #1947. This file is intentionally a pointer: the runner replaces its contents wholesale.

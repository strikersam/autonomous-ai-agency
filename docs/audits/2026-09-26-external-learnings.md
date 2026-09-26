# External learnings audit — 2026-09-26

Sources compared against this repo:

- `rohitg00/ai-engineering-from-scratch`, a 523-lesson curriculum. Relevant phases: 14 (agent engineering), 15 (autonomous systems), 17 (production).
- `vectorize-io/hindsight`, an agent memory system built on retain, recall and reflect.
- `paperclipai/paperclip`, an agent-company orchestrator with org charts, budgets and heartbeats.

Each "exists" entry was checked by `grep` against `agent/`, `packages/`, `services/`, `router/` and `tasks/`.

## Already covered — no work needed

| Pattern | Source | Where it already lives |
|---|---|---|
| Reflexion, where failures become context for the next run | curriculum 14/03 | `agent/lessons.py`, `agent/harness_spec.py` |
| Hybrid recall with RRF fusion | Hindsight recall | `agent/rag_context.py` (`_rrf`, BM25-style keyword scoring) |
| Response / prompt caching | curriculum 17/14, 11/15 | `packages/ai/response_cache.py`, `agent/inference_cache.py` |
| Circuit breakers and stuck-loop detection | curriculum 15/14 | `agent/stuck_detector.py`, `agent/adaptive_halting.py`, `router/circuit_breaker.py` |
| Checkpoints | curriculum 15/16 | `agent/checkpoint.py` |
| Per-session token caps | curriculum 15/13 | `agent/token_budget.py` |
| Propose-then-commit | curriculum 15/15 | `agent/autonomy_gate.py` (agents open PRs, humans merge) |
| Sleep-time memory consolidation | curriculum 14/08 | `memory-consolidation` skill, `agent/procedural_memory.py` |

## Shipped in this change

- **Memory Defense** (Hindsight). All four agent memory stores now call `redact_secrets()` before writing. See the CHANGELOG entry dated 2026-09-26.

- **Global kill switch** (curriculum 15/14). `AGENCY_KILL_SWITCH`, a live Platform Control. Built after the owner approved it.
- **Per-agent daily spend cap** (Paperclip; curriculum 15/13). `AGENT_DAILY_KTOKENS_CAP` / `AGENT_DAILY_USD_CAP`, enforced in `ProviderRouter.chat_completion`.

  *Correction to the first draft of this audit:* it said "nothing enforces a limit". In fact `packages/llm/budget.py` already
  tracks spend per agent and has an opt-in global daily/monthly hard stop. But agent traffic goes through
  `packages/ai/router.py`, which never reaches that tracker, so the existing caps did not cover agents.

See `docs/configuration-reference.md` → "Hard stops on autonomous work".

- **Evidence-weighted lessons** (Hindsight). `agent/lessons.py`: success on the same goal counts against lessons; ranking decays with a 14-day half-life.
- **Canary credential** (curriculum 15/14). `LEGACY_DEPLOY_TOKEN` decoy, checked in agent LLM requests and `web_reach` URLs.
- **Atomic task checkout** (Paperclip). `tasks/run_lease.py`. This fixed a real double-execution path: `/api/autonomy/tick` bypassed the coordinator's claim.
- **Goal ancestry** (Paperclip). `Task.goal` / `goal_chain`, rendered into the runtime instruction.

## Gaps still open

None from this audit. Known limits of what shipped:
- The spend-cap ledger is per process and resets on restart.
- On SQLite the run lease is process-local; SQLite deployments are single-process.
- Only the create API and scheduled jobs populate `goal` today; other intake paths (issues, portfolio) already carry their context in the prompt.

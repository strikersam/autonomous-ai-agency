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

## Gaps still open
1. **Atomic task checkout** (Paperclip). `services/shared_state.claim()` exists, but task pickup was not audited to confirm every worker path goes through it. Double-work across workers is the failure mode.
2. **Goal ancestry on tasks** (Paperclip). `tasks/` has no `parent_goal` / `goal_id` chain, so an executor sees a task title without the goal that produced it.
3. **Evidence-counted observations** (Hindsight). Lessons count `hits`, but a newer, contradicting lesson does not weaken an old one. Refining lessons instead of just counting them would stop stale lessons from ranking highest indefinitely.
4. **Canary tokens** (curriculum 15/14). A fake credential in the agent's environment whose use raises an alert. This is cheap and catches exfiltration that composes from allowed actions.

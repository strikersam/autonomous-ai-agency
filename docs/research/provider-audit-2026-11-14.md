# Provider audit — 2026-11-14

Why the brain failover was effectively one provider deep, and what changed.
Evidence: Render logs of `local-llm-server` (srv-d7cb43beo5us73e1leug),
`/api/doctor/public` at 2026-11-14 17:02 UTC, and `catalogue-probe.yml` runs
43598099666 (scheduled), 43619238209 (NVIDIA, `--tools`) and 43619248638 (Groq,
`--tools`). No key values were read. **K** = known from that evidence,
**I** = inferred, **NV** = not verified.

## Why "All 1 brain provider attempt(s) failed"

Production routes through `LLMRouter` (`llm.router:` log lines). It loaded
8 providers: anthropic, cerebras, google, groq, mistral, nvidia, openrouter,
siliconflow (K). At 16:32:02 one `nvidia/nemotron-3-ultra-550b-a55b` 429 cooled
the NVIDIA key for 30 s (K, log `llm.keys: nvidia key #0 cooling for 30s`), so
NVIDIA's other model, `openai/gpt-oss-20b`, which answered throughout, was
skipped (K). Groq's key was cooling 982 s on a daily quota and Gemini 1800 s (K).
Cerebras, siliconflow, mistral and openrouter were switched off in the durable
store (K, doctor). Skipped candidates are not attempts, so the error counted 1.

## Providers

| Provider | Key in prod | State | Evidence | Action |
|---|---|---|---|---|
| nvidia | yes (K) | working; per-model 429s on nemotron-3-ultra (I: per-model metering) | logs 16:32–17:01; probe 43619238209: nemotron-3-ultra, gpt-oss-20b, mistral-large-4-1t-a52b → 200 + tool_calls | `rate_limit_scope: model`; added mistral-large-4-1t-a52b |
| nvidia deepseek-ai/deepseek-v4-pro | — | dead | probe 43619238209: HTTP 410 | removed from catalogue, added to RETIRED |
| groq | yes (K) | working, free daily quota exhausted until reset | `429 (quota exhausted)`, key cooling 982 s; probe 43619248638: gpt-oss-120b, gpt-oss-20b, qwen/qwen3.8-27b → 200 + tool_calls | stays in loop; stray-tool-call 400 now request-scoped |
| google | yes (K) | free quota exhausted, cooling 1800 s | brief + logs | stays in loop (resetting quota, not funds) |
| mistral | yes (K) | switched OFF in store; last call 2026-11-12 23:24 succeeded | doctor; log `attempt mistral/codestral-latest ok` | reason not visible (NV) — operator re-enable |
| openrouter | yes (K) | switched OFF; 429s on 2026-11-09 | doctor; logs | reason NV — operator re-enable |
| cerebras | yes (K) | key invalid | log 2026-11-12 23:24 `HTTP 401 Wrong API Key` | operator: replace key |
| siliconflow | yes (K) | needs credits | logs 2026-11-09 `402 out of credit`, then 403 | out of loop (quarantine on next 402) |
| anthropic | yes (K) | paid, switched OFF | doctor | stays out (free-only policy) |
| browserbase | yes (K) | free plan minutes exhausted | log 16:17/16:51 `402 Payment Required - Free plan browser minutes limit reached` | quarantined, local Chromium serves |

The legacy registry reports 16 configured providers and 5 usable (doctor); 2 of
the usable ones are not in `config/llm/providers.yaml` and so never reach
`LLMRouter`. Which two is NV (candidates: tokenin, omniroute, dashscope, zai).

## Changes

- Per-model 429 for NVIDIA (`rate_limit_scope: model`), next model tried at once.
- Funds refusals quarantined for `PROVIDER_FUNDS_QUARANTINE_HOURS` (live, 24 h),
  distinct from resetting quotas; doctor/Providers show the return time.
- Groq "Tool choice is none, but model called a tool" → next candidate, no penalty.
- Browserbase 402 → Browserbase skipped for the window; local Chromium serves.
- Exhaustion log names providers skipped without a call.

## Not changed, needs evidence

- `qwen/qwen3.8-27b` on Groq answers with tools but carries a $0.80/$4.00 price
  in `config/llm/models.yaml`, so the free-only router excludes it. Confirm the
  Groq account is on the free plan before zeroing it.
- `router/model_router.py` and `router/harness_routing.py` still map aliases to
  `deepseek-ai/deepseek-v4-pro` (410) and `meta/llama-3.3-70b-instruct` (RETIRED).
- NVIDIA `z-ai/glm-5.3-flash`, `deepseek-ai/deepseek-v4.1-flash` timed out,
  `minimaxai/minimax-m3.1-flash` 503, `moonshotai/kimi-k2.6` 404 (run 43619238209).

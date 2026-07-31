# LLM Router — migration guide

The routing layer ships **off**. Nothing changes until you turn it on, and
turning it off again is one environment variable.

## What changes for callers

Nothing. `failover_chat_completion()` keeps its exact signature, return type,
and raised exception. `agent/loop.py`, `proxy.py`, and `backend/server.py` are
unmodified apart from the router API being mounted.

```python
# unchanged — works on both paths
from packages.ai.failover_client import failover_chat_completion

result = await failover_chat_completion({
    "model": "z-ai/glm-5.2",
    "messages": [{"role": "user", "content": "hello"}],
})
result.text, result.provider_id, result.prompt_tokens
```

With `LLM_ROUTER_ENABLED=true` that call is served by `LLMRouter` and adapted
back into a `FailoverResult`. The caller cannot tell.

## Rollout

### 1. Verify the router sees your providers

Before enabling anything:

```bash
curl -s localhost:8001/api/llm/config | jq '.providers[] | {id, tier, key_count}'
```

Every provider you expect should appear with `key_count >= 1`. A provider whose
keys resolve to nothing is skipped at startup — that is the most common reason
one is missing.

### 2. Enable on one instance

```bash
export LLM_ROUTER_ENABLED=true
```

Restart. Watch:

```bash
curl -s localhost:8001/api/llm/status | jq '{strategy, providers: [.providers[] | {id, state: .health.state}]}'
```

Or open the Providers page — the SERVING badge shows what is handling traffic.

### 3. Watch for a few hours

The signals that matter:

```bash
curl -s localhost:8001/api/llm/metrics | grep -E 'llm_(requests|fallbacks|rate_limits|failures)_total'
```

- `llm_fallbacks_total` climbing is **good** — those are requests that would
  previously have failed.
- `llm_failures_total` with `scope="provider"` climbing on one provider means
  that provider is genuinely unwell; check its breaker state.
- Any request failing outright means the whole candidate set was exhausted.
  Add a provider or a key.

### 4. Roll out or roll back

Roll forward by setting the variable everywhere. Roll back by setting
`LLM_ROUTER_ENABLED=false` — the legacy path resumes immediately, and the flag
is read per call, so this needs no restart.

## Adding the config files

You do not need them. With none present the router derives providers from the
environment variables the platform already reads.

Add them when you want:

- providers the environment defaults do not cover (LM Studio, vLLM, LiteLLM)
- per-agent routing policies
- explicit model capability declarations
- non-default retry, breaker, or cache behaviour

Start by copying the shipped `config/llm/*.yaml` and editing. Every file is
independently optional.

## Migrating a caller to the router directly

Only worth doing when you want features the shim cannot express — streaming,
per-agent policies, priorities, cost attribution.

```python
from packages.llm import LLMRequest, Priority, get_router

response = await get_router().chat(LLMRequest(
    messages=messages,
    agent="planner",          # picks up routing.yaml → agents.planner
    workflow="nightly-audit", # cost attribution
    priority=Priority.HIGH,
    tools=tools,              # passed through untouched
))

response.text
response.provider          # which provider actually served it
response.fallback_count    # how many failed first
response.cost_usd
```

Streaming:

```python
async for chunk in get_router().stream(LLMRequest(messages=messages, stream=True)):
    print(chunk.text, end="")
    if chunk.done:
        break
```

Failover applies until the first chunk is delivered. After the caller has seen
output, switching providers mid-stream would splice two different generations
together, so a later failure surfaces as an error instead.

## Gateway mode

To let *other* applications use this routing layer:

```bash
export LLM_GATEWAY_ENABLED=true
```

```bash
curl https://your-host/api/llm/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"model": "z-ai/glm-5.2", "messages": [{"role": "user", "content": "hi"}]}'
```

Off by default: exposing the platform's keys to other applications should be a
deliberate act.

## Rollback checklist

| Symptom | Action |
|---------|--------|
| Requests failing that previously worked | `LLM_ROUTER_ENABLED=false`; check `/api/llm/status` for the reason |
| A provider never used | Check `key_count` in `/api/llm/config`; check its breaker state |
| Higher latency | Check `llm_queue_depth`; raise `global_max_concurrency` |
| Unexpected spend | `allow_paid: false`, or set `budget.enforce: true` |
| Config file rejected | Check logs for `llm config:` warnings; a malformed file degrades to defaults |

## What is not migrated

`packages/ai/` still serves every caller that has not been switched over. The
new model registry seeds itself from `packages/ai/registry.py`, so no model
disappears — there is a test asserting exactly that.

The freellmapi catalog sync (`packages/ai/model_catalog.py`) is untouched and
still default-on. Set `FREELLM_CATALOG_INCLUDE_ROUTER=true` if you also want it
to publish the router's providers.

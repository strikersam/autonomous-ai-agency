# LLM Router — configuration guide

Six files under `config/llm/`. **Every one is optional.** With none present the
router derives providers from the same environment variables the platform
already reads, so an existing deployment works unchanged.

Point `LLM_CONFIG_DIR` elsewhere to use a different directory.

| File | Controls |
|------|----------|
| `providers.yaml` | which endpoints exist, their kind, tier, limits |
| `models.yaml` | model capabilities, context windows, pricing |
| `routing.yaml` | strategy, retry, queue, per-agent policies, budgets |
| `keys.yaml` | provider → environment variable **names** |
| `health.yaml` | circuit breaker thresholds |
| `cache.yaml` | cache layers and TTLs |

## Environment variables

| Variable | Default | Effect |
|----------|---------|--------|
| `LLM_ROUTER_ENABLED` | `false` | Route through `LLMRouter` instead of the legacy path |
| `LLM_GATEWAY_ENABLED` | `false` | Serve the OpenAI-compatible passthrough at `/api/llm/v1/*` |
| `LLM_CONFIG_DIR` | `config/llm` | Where to read the YAML from |
| `LLM_ROUTER_STRATEGY` | *(from YAML)* | Override the routing strategy |
| `LLM_ROUTER_PREFER_LOCAL` | `false` | Try local providers first |
| `LLM_ROUTER_MAX_ATTEMPTS` | `6` | Attempt ceiling for one request |
| `LLM_ROUTER_BUDGET_SEC` | `300` | Wall-clock ceiling for one request |
| `LLM_BUDGET_DAILY_USD` | `0` | Daily spend ceiling (0 = unlimited) |
| `LLM_BUDGET_MONTHLY_USD` | `0` | Monthly spend ceiling |
| `ALLOW_PAID_BRAIN` | `false` | Permit paid tiers (shared with the legacy policy) |
| `FREELLM_CATALOG_INCLUDE_ROUTER` | `false` | Publish router providers in the freellmapi catalog |

Environment variables override YAML.

## providers.yaml

```yaml
providers:
  my-provider:
    kind: openai              # canonical: openai | anthropic | gemini | ollama
                              # aliases (lmstudio, vllm, litellm, groq, …)
                              # are accepted and map to these four
    base_url: ${MY_BASE_URL}
    key_env: [MY_API_KEY]     # NAMES, never values
    tier: free                # local | free | cheap | premium
    priority: 25              # lower wins ties
    weight: 1.0               # for the weighted strategy
    enabled: true
    max_concurrency: 4        # this provider's bulkhead size
    requests_per_minute: 30   # 0 = unmetered
    timeout_sec: 120
    auth_style: bearer        # bearer | x-api-key | api-key | none
    requires_key: true
    default_model: my-model
```

`${VAR}` and `${VAR:-default}` are expanded at load time. Note that
`${X:-false}` expands to the *string* `"false"`, which the loader coerces to a
real boolean for boolean fields — so a provider you switched off really is off.

**Adding a provider requires no Python.** Anything speaking the OpenAI REST
shape uses `kind: openai`. Readability aliases (`lmstudio`, `vllm`, `groq`,
`together`, …) all resolve to the same adapter.

### Tiers

`tier` drives graceful degradation. The `automatic_failover` strategy walks
`local → free → cheap → premium`, and `allow_paid: false` excludes `cheap` and
`premium` entirely.

### Bulkhead sizing

`max_concurrency` is the isolation boundary, not a throughput target:

- Local Ollama / LM Studio: **1–2**. A single GPU serialises; a bigger pool
  just queues while holding router slots.
- vLLM: **8–16**. Continuous batching genuinely benefits from concurrency.
- Free cloud tiers: **4–6**. Usually the RPM limit binds first.
- Paid cloud: **8+**.

## models.yaml

```yaml
models:
  my-model:
    provider: my-provider
    context_window: 32768
    max_output_tokens: 8192
    supports_tools: true
    supports_function_calling: true
    supports_json: true
    supports_images: false
    supports_reasoning: false
    supports_streaming: true
    supports_embeddings: false
    supports_chat: true         # false for embedding-only models
    input_cost_per_1m: 0.0      # USD; 0 = free
    output_cost_per_1m: 0.0
    priority: 20
    speed_tier: fast            # fast | medium | slow
    aliases: [short-name]
```

**Declare capabilities conservatively.** A false `supports_tools: true`
produces a confusing runtime failure; a false `false` only costs one routing
option.

**Set `supports_chat: false` on embedding models.** Otherwise the router will
happily offer `nomic-embed-text` as a chat candidate, and it will accept the
request and return something useless.

Models discovered at runtime through `/models` endpoints are registered with
cautious defaults. Entries here always win.

## routing.yaml

```yaml
routing:
  strategy: adaptive
  fallback_chain: [cerebras, groq, nvidia, google, ollama]
  prefer_local: false
  allow_paid: false

  max_providers_per_request: 6
  max_models_per_provider: 3

  graceful_degradation: true
  escalate_context: true
  downgrade_on_exhaustion: true

  retry:
    max_attempts: 6
    base_delay_sec: 0.5
    max_delay_sec: 30.0
    multiplier: 2.0
    jitter: 0.3
    respect_retry_after: true
    retry_statuses: [408, 409, 425, 429, 500, 502, 503, 504, 529]
    budget_sec: 300.0

  queue_enabled: true
  queue_max_depth: 512
  global_max_concurrency: 32
  dedupe_window_sec: 30.0

  agents:
    planner:
      strategy: model_capability
      min_context_window: 32768
      priority: HIGH

  budget:
    daily_usd: 0.0
    monthly_usd: 0.0
    alert_at: [0.5, 0.8, 0.95]
    enforce: false
```

Never add 400/401/403/404/422 to `retry_statuses`. They cannot succeed on
retry, and retrying them burns the wall-clock budget a genuinely transient
failure needs.

`retry_statuses` governs retries against the *current* candidate only. A
400/404 that names a missing model is still classified model-scoped, so the
router moves on to sibling models and other providers before giving up — it
just does not re-send the identical request to the same place.

`budget_sec` is the hard ceiling for one request across every attempt. Six
providers × three models is eighteen possible attempts; this is what actually
bounds the worst case.

### Per-agent policies

Different agents want different things. A `default` entry applies to any agent
not named. Fields: `strategy`, `prefer_providers`, `exclude_providers`,
`prefer_models`, `allow_paid`, `require_tools`, `min_context_window`,
`priority` (`CRITICAL`/`HIGH`/`NORMAL`/`LOW`/`BULK`).

An explicit `LLMRequest.strategy` always beats the policy — the policy is a
default for that agent, not a constraint on the caller.

### Budgets

Advisory by default: crossing a threshold logs and emits an alert, and the
request still runs. Set `enforce: true` to make a breach raise
`BudgetExceeded`.

Advisory is the default deliberately. An autonomous agency that silently stops
working at month-end because of a misconfigured ceiling is a worse failure than
an overspend the operator can see coming from the 50% alert onward.

## keys.yaml

**This file contains no secrets and must never contain any.** It lists variable
*names*. Values are read from the environment at call time, so a rotated key
takes effect without a reload and no key material is written to disk.

```yaml
keys:
  cerebras:
    env: [CEREBRAS_API_KEY, CEREBRAS_API_KEY_2, CEREBRAS_API_KEY_3]
```

The loader also auto-detects `NAME`, `NAME_2` … `NAME_10`, `NAME_S`, and
`NAME_POOL` without them being listed. A single variable may hold several
comma- or whitespace-separated keys.

Multiple keys per provider is the single highest-leverage change for surviving
429s: a rate-limited key costs you a key, not a provider, and the router
retries the same provider with the next key before moving on.

## health.yaml

```yaml
health:
  failure_threshold: 5          # consecutive failures before tripping
  failure_rate_threshold: 0.5   # or this rolling failure rate
  min_samples: 10
  open_duration_sec: 60.0
  backoff_multiplier: 2.0
  max_open_duration_sec: 900.0
  half_open_probes: 1
  window_sec: 300.0
  probe_enabled: false
  probe_interval_sec: 120.0
```

`failure_threshold: 5` is deliberately not 1. A single 500 is noise, and
tripping on noise costs more capacity than the failures do.

`failure_rate_threshold` catches the provider that fails 60% of the time but
never five times in a row — which a consecutive-only rule misses entirely.

`probe_enabled` is off by default: live traffic already measures health, and
probing free providers on a timer spends quota to learn what the next real
request would have told you. Turn it on for a mostly-idle deployment where
providers must be known healthy before traffic arrives.

## cache.yaml

```yaml
cache:
  response:  { enabled: true,  ttl_sec: 300,   max_entries: 512 }
  prompt:    { enabled: true,  ttl_sec: 900,   max_entries: 256 }
  embedding: { enabled: true,  ttl_sec: 86400, max_entries: 4096 }
  tool:      { enabled: false, ttl_sec: 60,    max_entries: 256 }
  semantic:  { enabled: false, ttl_sec: 600,   max_entries: 512 }
  semantic_threshold: 0.94
```

Regardless of this file, the router refuses to cache a request that streams,
carries tools, or has `temperature > 0.2`. Caching a sampled response would
silently make a "creative" agent deterministic — a behaviour change, not an
optimisation.

`tool` is off by default because a tool result depends on the state of the
world, not just its arguments. `semantic` is off because it returns an answer
written for a *different* question; 0.94 is strict on purpose, since "how do I
deploy this?" and "how do I delete this?" score high on most embedding models.

## Reloading

```bash
curl -X POST https://your-host/api/llm/config/reload \
  -H "Authorization: Bearer $TOKEN"
```

Or use **Reload config** on the Providers page. This re-reads every YAML file
and rebuilds the router without a restart.

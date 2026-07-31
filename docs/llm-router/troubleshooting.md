# LLM Router — troubleshooting

## First three commands

```bash
curl -s localhost:8001/api/llm/status  | jq '{enabled, strategy, providers: [.providers[] | {id, state, key_count}]}'
curl -s localhost:8001/api/llm/health  | jq '.providers[] | {provider, state, success_rate, last_error}'
curl -s localhost:8001/api/llm/metrics | grep -E 'llm_(failures|rate_limits|fallbacks)_total'
```

`status.enabled: false` means the router is off and the legacy path is running.
That is the default, not a fault.

---

## A provider never gets used

**Check it exists at all.**

```bash
curl -s localhost:8001/api/llm/config | jq '.providers[] | {id, enabled, key_count}'
```

| Cause | Fix |
|-------|-----|
| Missing from the list | Its keys resolve to nothing. Providers with no key are skipped at startup. |
| `enabled: false` | `${X:-false}` in YAML, or an explicit `enabled: false`. |
| `key_count: 0` | The env var named in `keys.yaml` is unset or empty. |
| Present but never chosen | Its breaker is open — see below. |
| Only a *keyless* provider is missing | Its base URL env var is unset. A hardcoded default alone does not create a provider. |

**Check the breaker.**

```bash
curl -s localhost:8001/api/llm/health | jq '.providers[] | select(.state != "closed")'
```

`state: "open"` with `open_for_sec` counting down: it will half-open on its
own. Force it now:

```bash
curl -X PUT localhost:8001/api/llm/providers/<id>/enabled \
  -H "Authorization: Bearer $TOKEN" -d '{"enabled": true}'
```

If it re-trips immediately, `last_error` says why.

---

## Still getting 429s

The router cannot create quota. It can spread load, and there are four levers.

**1. Add keys.** The single highest-leverage change.

```bash
export GROQ_API_KEY=key-one
export GROQ_API_KEY_2=key-two
```

Verify they were picked up:

```bash
curl -s localhost:8001/api/llm/status | jq '.providers[] | {id, key_count, keys: [.keys[] | {index, healthy, rate_limits}]}'
```

**2. Add providers.** Two free providers survive twice the traffic. Cerebras,
Groq, NVIDIA NIM, and Gemini all have usable free tiers.

**3. Add a local model.** No quota can exhaust it. See the
[local model guide](local-models.md).

**4. Switch strategy.**

```bash
curl -X PUT localhost:8001/api/llm/config/strategy \
  -H "Authorization: Bearer $TOKEN" -d '{"strategy": "token_budget_optimized"}'
```

Also set `requests_per_minute` on the provider so the router paces itself
*before* the provider has to say no.

---

## Requests fail with "All LLM candidates exhausted"

The message names what was tried. Common reasons:

| Reason in the message | Meaning |
|-----------------------|---------|
| `no providers configured` | No key set and no local base URL. |
| `no configured model supports tool calling` | Set `supports_tools: true` on a model that does. |
| `model X is not available on any configured provider` | `pin_model` was set for an unregistered model. |
| `no free provider is available` | All free providers are down; set `ALLOW_PAID_BRAIN=true` to permit paid fallback. |
| `attempt budget exhausted` | Raise `retry.max_attempts` or add providers. |
| `time budget exhausted` | Raise `retry.budget_sec` or `LLMRequest.timeout_sec`. |

---

## Latency got worse

**Check the queue.**

```bash
curl -s localhost:8001/api/llm/status | jq .queue
```

`depth` near `max_depth` means you are concurrency-bound. Raise
`global_max_concurrency`.

**Check bulkheads.**

```bash
curl -s localhost:8001/api/llm/status | jq .bulkheads
```

Non-zero `rejected` for a provider means its `max_concurrency` is too small and
requests are being redirected elsewhere.

**Check which provider is serving.** `adaptive` weights reliability over speed,
so a slow-but-reliable provider can win. Use `lowest_latency` for interactive
surfaces, or a per-agent policy so only that agent changes.

---

## `QueueFull` errors

Backpressure, working as designed — the queue refused work rather than growing
without bound.

```yaml
routing:
  queue_max_depth: 1024
  global_max_concurrency: 64
```

If it recurs, the bottleneck is downstream: providers are too slow or too few.

---

## The cache never hits

The router refuses to cache when the request streams, carries tools, or has
`temperature > 0.2` — regardless of `cache.yaml`.

**The default `LLMRequest.temperature` is 0.3, which is deliberately not
cacheable.** Pass `temperature=0.0` for deterministic calls you want cached.

```bash
curl -s localhost:8001/api/llm/cache | jq '.layers[] | {name, enabled, hits, misses, hit_rate}'
```

---

## Costs are higher than expected

```bash
curl -s localhost:8001/api/llm/usage | jq '{by_provider, by_agent, budget}'
```

`by_agent` shows which agent is spending. Then:

- `allow_paid: false` in `routing.yaml` stops paid selection entirely.
- Give the expensive agent a `cost_optimized` policy.
- Set `budget.daily_usd` with `enforce: true` for a hard stop.

Budgets are advisory by default — an agency that silently halts at month-end is
worse than an overspend you saw coming from the 50% alert.

---

## Context-window errors

The router shrinks conversations automatically. If you still see overflow:

- Confirm `escalate_context: true` in `routing.yaml`.
- Confirm at least one large-context model is registered and reachable
  (Gemini's 1M window is the usual escalation target).
- Check `context_window` in `models.yaml` is accurate — an over-declared window
  makes the router believe a prompt fits when it does not.

---

## Config changes have no effect

```bash
curl -X POST localhost:8001/api/llm/config/reload -H "Authorization: Bearer $TOKEN"
```

Then check for parse warnings:

```bash
grep 'llm config' /path/to/logs
```

A malformed file degrades to defaults rather than failing startup, so a silent
fallback to defaults is the expected symptom of a YAML syntax error.

Also confirm you are editing the directory actually in use —
`/api/llm/config` reports `source_dir`.

---

## The Providers page shows nothing

- `enabled: false` in `/api/llm/status` — the router is off. The page renders a
  reason and stays usable.
- All read endpoints answer even when the router is off, so a blank page means
  a network or auth failure, not a router failure. Check the browser console.

---

## Streaming stops mid-response

Failover applies only until the first chunk is delivered. Once output has
reached the caller, switching providers would splice two different generations
together, so a later failure surfaces as an error instead of a silent restart.

For long generations, prefer a provider with a healthy breaker and adequate
`timeout_sec`.

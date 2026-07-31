# LLM Router — routing guide

How the router picks a provider, and which strategy to use when.

## Candidate selection

Before any strategy runs, the router builds the candidate set — every
(provider, model) pair that *could* serve the request:

1. Drop disabled providers and anything in `exclude_providers`.
2. Drop paid tiers unless `allow_paid` is true.
3. Drop models that cannot do what the request needs — tool calling, vision,
   streaming, embeddings.
4. Drop embedding-only models (`supports_chat: false`).
5. Prefer models whose context window fits the prompt; keep the rest as a tail
   so a context-overflow retry still has somewhere to go.
6. Cap breadth at `max_providers_per_request` × `max_models_per_provider`.

Capability filtering happens *before* ranking, so no strategy can propose a
model that cannot do the job.

## The fifteen strategies

Set globally in `routing.yaml`, per agent in `routing.agents`, per request via
`LLMRequest.strategy`, or at runtime from the Providers page.

### adaptive *(default)*

Scores every candidate live and picks the best. Lower is better:

| Signal | Weight | Why |
|--------|--------|-----|
| failure rate | 3.0 | historical reliability dominates everything else |
| 429 frequency | 2.0 | a provider that rate-limits is nearly useless |
| load | 1.5 | spread work across free bulkhead capacity |
| latency (p95, normalised to 10s) | 1.0 | speed matters, but less than working |
| cost | 0.5 | a tie-break, not a driver |

A tripped breaker adds 100 — it goes last, not merely low. `prefer_local`
subtracts 1.

Unlike a static priority list, this reacts within one rolling window: a
provider that starts failing sinks without anyone editing YAML, and climbs back
as soon as it recovers.

**Use it unless you have a specific reason not to.**

### priority

Strict configured order. Predictable and completely blind to live health —
a dead provider stays first until its breaker trips.

Use for reproducible behaviour in tests, or when you know your ordering is
right and want no surprises.

### round_robin

Even rotation; the starting point advances every request. Use to spread load
evenly across providers of equal quality.

### random

Uniform shuffle. Like round-robin but with no shared counter, so it behaves
identically across multiple instances without coordination.

### weighted

Randomised order biased by each provider's `weight`, using an exponential race
so the whole ordering is a valid fallback chain rather than one pick. Use for
deliberate traffic splits — 70/30 between two providers.

### least_loaded

Prefers whichever provider has the most free bulkhead capacity. Use when
providers have very different concurrency limits and you want to keep them all
busy.

### lowest_latency

Fastest observed p95 first. Providers with no samples sort *first* — an
unmeasured provider gets one chance to prove itself rather than being starved
forever by an incumbent.

Use for interactive surfaces where a human is waiting.

### highest_success_rate

Most reliable provider in the rolling window first. Use when correctness
matters more than speed and some providers are flaky.

### cost_optimized

Cheapest first; free before any paid. Use for background work — digests,
summarisation, batch jobs.

### context_length_optimized

Smallest context window that still fits the prompt. Reserving the 1M-token
model for prompts that need it keeps it available when something actually
overflows, and large-context models are usually slower and dearer per token.

### token_budget_optimized

Most quota headroom first, measured by observed 429 frequency rather than
configured limits — a provider that is 429ing has no headroom whatever its
documentation claims.

Use when you are close to free-tier limits across several providers.

### model_capability

Closest capability match to what the request actually needs. Exact matches
sort first; over-capable models sort behind, because those are normally the
expensive ones.

Use for agents whose requests vary a lot in what they need.

### provider_health

Strict breaker state, then failure rate. A blunter `adaptive` that ignores
cost, latency, and load entirely. Use when you only care about reachability.

### fallback_chain

Walks the explicit `fallback_chain` list in order; anything unlisted follows by
priority. Use when you want a hand-written order and a safety net for providers
you forgot to list.

### automatic_failover

Tiered degradation: `local → free → cheap → premium`, health-first within each
tier. Paid tiers are *appended*, never skipped, so when every free option is
exhausted the request still completes if the operator opted into paid.

Use as the "keep working no matter what" strategy.

## Choosing one

| Situation | Strategy |
|-----------|----------|
| General use | `adaptive` |
| Human waiting on the response | `lowest_latency` |
| Background/batch work | `cost_optimized` |
| Near free-tier limits | `token_budget_optimized` |
| Long documents | `context_length_optimized` |
| Reproducible test behaviour | `priority` |
| Deliberate traffic split | `weighted` |
| Survive anything | `automatic_failover` |

## Per-agent policies

```yaml
routing:
  agents:
    planner:
      strategy: model_capability
      prefer_models: [z-ai/glm-5.2]
      min_context_window: 32768
      priority: HIGH
    telegram:
      strategy: lowest_latency
      priority: CRITICAL      # a human is waiting
    digest:
      strategy: cost_optimized
      priority: BULK          # yields to interactive work
```

Pass `agent="planner"` on the request and the policy applies. Priority feeds
the request queue, so `CRITICAL` work is served ahead of `BULK` work when the
queue is deep.

## Retry and failover, step by step

A request fails over like this:

1. Try the top candidate.
2. On **429**: cool that key, retry the *same provider* with the next healthy
   key. Only when every key is cooling does the router move on.
3. On a **model error**: skip that model, try the next model on the same
   provider.
4. On **5xx/timeout**: count a breaker failure, move to the next provider,
   sleep the backoff interval (exponential, jittered, capped, and never longer
   than the remaining budget).
5. On **401/403/402** (or a 4xx body that says the account is out of credit):
   no retry against that provider, and the provider is switched off durably —
   only a new key or more credit fixes it, so leaving it in rotation costs
   latency on every later request and never succeeds.
6. On **413**: it depends on what the body says. When it names a per-minute
   budget — Groq answers "Request too large ... on tokens per minute (TPM):
   Limit 12000" — it is a rate limit wearing a payload status code, and it is
   treated exactly like a 429: cool that key, rotate, move on. Otherwise it
   describes one provider's context window, not the request, so the next
   provider is tried — a prompt that overflows a 32k model fits a 200k one.
7. On **414/422**: stop entirely. The request itself is malformed, and every
   provider will reject it identically.
8. Repeat until something succeeds, the attempt budget is spent, or the
   wall-clock budget expires.

## Watching it work

```bash
curl -s localhost:8001/api/llm/status | jq '.providers[] | {id, state: .health.state, success: .health.success_rate}'
curl -s localhost:8001/api/llm/metrics | grep -E 'llm_(fallbacks|rate_limits)_total'
```

Or open the Providers page: rows are ranked healthiest-first, the SERVING badge
marks what would handle the next request, and the row detail shows per-key
cooldowns.

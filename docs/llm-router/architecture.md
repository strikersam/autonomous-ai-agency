# LLM Router — architecture

The routing layer (`packages/llm/`) owns every LLM call the platform makes.
Agents do not talk to OpenAI, Anthropic, Gemini, or Ollama; they talk to
`LLMRouter`, and it decides where the request actually goes.

Design rationale lives in [ADR-008](../adr/008-llm-router-multi-provider.md).
This document describes what was built.

## What problem it solves

A long-running autonomous agency dies from a thousand small outages: a free
tier's 429, a key that ran out of quota at 3 a.m., a model that was
decommissioned, a provider that started timing out. Each is individually
survivable and collectively fatal, because before this layer each was handled
in a different module with a different policy — or not at all.

The router turns all of them into the same thing: a failed attempt against one
candidate, followed by an attempt against the next.

It cannot give you unlimited tokens. What it gives you is that no single
provider, key, model, or quota can stop the platform.

## Request lifecycle

```
LLMRequest
    │
    ├─ policy      per-agent overrides merge in (routing.yaml → agents)
    ├─ budget      pre-flight spend check
    ├─ cache       exact-key lookup, then optional semantic lookup
    ├─ dedupe      collapse onto an identical in-flight call
    ├─ queue       admission control, global concurrency, backpressure
    │
    ├─ candidates  (provider × model) pairs that satisfy the capabilities
    ├─ strategy    order the candidates
    │
    └─ for each candidate, until one succeeds:
           breaker   is this provider admitting traffic?
           bulkhead  is a slot free for this provider?
           pace      is there rate-limit headroom?
           key       take the next healthy key
           context   shrink the conversation if it overflows this model
           HTTP      call the provider
           classify  permanent? transient? which scope?
           record    health, keys, metrics, budget
```

A request fails only when every candidate is exhausted, the retry budget is
spent, or the error was permanent and fatal.

## Modules

| Module | Responsibility |
|--------|----------------|
| `types.py` | `LLMRequest`, `LLMResponse`, `StreamChunk`, `ToolCall`, error hierarchy |
| `config.py` | Loads the six YAML files; the only module reading env for config |
| `registry.py` | Model capabilities, context windows, pricing; capability filtering |
| `providers/` | Four adapters covering every supported endpoint |
| `strategies.py` | Fifteen pure ranking functions over candidates |
| `health.py` | Rolling health per provider + the circuit breaker |
| `keys.py` | Multi-key rotation with per-key cooldowns |
| `retry.py` | Backoff with jitter, retry classification, shared budget |
| `queue.py` | Priority queue, bulkheads, deduplication |
| `cache.py` | Five cache layers with independent TTLs |
| `context.py` | The context-fitting ladder |
| `budget.py` | Token/cost accounting with threshold alerts |
| `metrics.py` | Prometheus exposition, no client library |
| `distributed.py` | Shared rate limiting and durable queue (Redis, optional) |
| `router.py` | `LLMRouter` — the gateway that composes all of the above |
| `gateway.py` | The `/api/llm/*` REST surface |
| `compat.py` | Bridges to the legacy call paths |

## The three failure scopes

This is the design decision that matters most. A failure is attributed to the
narrowest scope that explains it:

| Signal | Scope | Effect | Recovery |
|--------|-------|--------|----------|
| 429 (+ `retry-after`) | **key** | that key cools down | other keys keep serving; the request retries the same provider with the next key |
| 404/400 naming a model | **model** | that model is skipped | sibling models on the same provider keep serving |
| 5xx, timeout, reset | **provider** | breaker counts a failure | half-open probe after the open window |
| 401/403/413/422 | none — permanent | no retry | fix the request or the credential |

Getting this wrong is not academic. Marking a whole provider dead because one
model was decommissioned is precisely the failure that caused the schedule
multiplication incident described in `CLAUDE.md` §7.

The breaker is only allowed to open on provider-scoped failures, and on 429s
*only* once every key for that provider is already cooling.

## Circuit breaker

```
CLOSED ──(5 consecutive failures, or >50% failure rate)──▶ OPEN
OPEN ──(open window elapses)──▶ HALF_OPEN
HALF_OPEN ──(probe succeeds)──▶ CLOSED
HALF_OPEN ──(probe fails)──▶ OPEN, window × 2 (capped at 15 min)
```

Half-open admits exactly `half_open_probes` requests (default 1). A recovering
provider is tested with one request, not the full firehose. Repeated trips
lengthen the window geometrically, so a provider that is genuinely down stops
being probed every minute while one that merely blipped recovers in a minute.

## Bulkheads

Every provider gets its own concurrency semaphore, sized by
`max_concurrency` in `providers.yaml`. A provider that stops responding can
exhaust only its own slots.

Without this, one provider timing out at 60 seconds drains the shared worker
pool and stalls providers that are perfectly healthy — the outage spreads
instead of being contained. Local providers get small bulkheads (a GPU
serialises anyway); vLLM gets a large one (it batches well).

## Context management

The escalation ladder, cheapest and least lossy first:

1. Fits as-is — nothing to do
2. Escalate to a larger-context model
3. Prune — truncate oversized tool results, drop duplicate turns
4. Sliding window — keep the system prompt, the first turn, and the newest turns
5. Summarise the dropped span with a cheap model
6. Retrieve the dropped turns relevant to the current question
7. Chunk an oversized single document

The first turn is always preserved because it almost always carries the task
definition. Dropping it makes an agent forget what it was asked to do while
remembering the last six steps of doing it.

**Message text is never rewritten.** Steps 3–7 are lossy at the *conversation*
level and lossless at the *message* level. This is the deliberate divergence
from OmniRoute's token-compression engines: lossy rewriting corrupts code
blocks, tool-call JSON, and structured outputs, and this platform's agents
depend on all three.

## Configuration

Six optional files under `config/llm/`. All are optional — absent files fall
back to defaults derived from the environment variables the platform already
reads, so an untouched deployment behaves identically with no config at all.

See the [configuration guide](configuration.md).

## Compatibility

`failover_chat_completion()` keeps its exact signature, return type, and raised
exception. With `LLM_ROUTER_ENABLED` unset (the default) the legacy
implementation runs unchanged. With it set, the call is served by `LLMRouter`
and adapted back into a `FailoverResult`.

Rollback is one environment variable, not a revert.

## What this does not do

- It does not give you unlimited tokens. Quotas are real.
- It does not compress prompts lossily. See "Context management" above.
- It does not replace `packages/ai/`. That layer still serves every caller
  that has not been migrated, and the model registry seeds itself from it so
  no model disappears during migration.
- It does not make paid providers free. `allow_paid` defaults to false and
  paid tiers are never auto-selected without explicit opt-in.

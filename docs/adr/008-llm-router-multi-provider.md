# ADR-008: LLMRouter — the single multi-provider routing gateway

## Status
Accepted

## Context

Autonomous AI Agency already survives most provider failures. `packages/ai/`
carries a mature resilience layer: `failover_client.py` walks the brain-failover
chain, `key_pool.py` rotates API keys, `rate_limiter.py` paces requests against
observed quota headers, `traffic_director.py` orders providers by utilisation
and latency, `response_cache.py` de-duplicates identical payloads, and
`watchdog.py` flips the active brain after repeated failures.

Three problems remain, and all three are architectural rather than missing
features:

1. **There is no single gateway.** Fifteen modules import LLM plumbing
   directly — `agent/loop.py` calls `failover_chat_completion`, `proxy.py`
   builds its own `ProviderRouter`, `runtimes/routing.py` and
   `router/model_router.py` each hold their own selection logic. A resilience
   improvement made in one path does not reach the others.
2. **Adding a provider means writing code.** Provider knowledge is spread
   across `ProviderRouter.from_env` (~400 lines of env parsing),
   `packages/ai/registry.py` (hardcoded `ModelInfo` registrations), and
   `services/brain_failover.py`. Supporting LM Studio or vLLM today means
   editing Python in three places.
3. **Failure isolation is coarse.** Cooldowns are per-provider and
   time-based. One slow provider still consumes the shared concurrency budget,
   a half-recovered provider gets full traffic immediately, and there is no
   per-agent policy — every caller shares one global fallback chain.

OmniRoute solves an adjacent problem (a standalone Node/Electron gateway
fronting 290 providers) and is worth studying, but it is not a drop-in.

## Comparison with OmniRoute

### Similarities — convergent design we can validate against

| Concern | OmniRoute | Autonomous AI Agency (today) |
|---------|-----------|------------------------------|
| Unified OpenAI-compatible surface | `/v1/chat/completions`, `/v1/models` | `proxy.py` exposes the same routes |
| Provider fallback chain | 4-tier Subscription → API → Cheap → Free | free → local → paid in `services/brain_failover.py` |
| Per-key cooldown | Exponential backoff, 3s API-key base | `packages/ai/key_pool.py` |
| Per-model lockout on 429 | Model locked without affecting siblings | `_mark_model_dead()` in `packages/ai/router.py` |
| Prompt caching | Prefix-pinned cache-optimised routing | `packages/ai/response_cache.py` (exact-match) |
| Cost-aware selection | Live pricing, cost-optimised strategy | `packages/ai/cost_tracker.py` |

### Differences — why a port was rejected

| Dimension | OmniRoute | This repo | Consequence |
|-----------|-----------|-----------|-------------|
| Language / runtime | TypeScript, Node, Electron | Python 3.13, FastAPI, asyncio | No code is portable; only design is |
| Deployment shape | Standalone desktop/daemon gateway | In-process library inside one FastAPI app | We need a library first, a gateway second |
| State store | SQLite + optional Redis | MongoDB (prod) / SQLite (dev) via `packages/storage` | Must reuse the existing duck-typed store (ADR-007) |
| Config | `.env` + dashboard-authored combos in SQLite | Repo-committed YAML, env for secrets only | Constitution forbids secrets on disk |
| Provider count | 290 adapters | 7 configured | Breadth is a config problem, not a code problem |
| Compression | 12-engine token compressor (Caveman, OmniGlyph, LLMLingua-2) | none | Lossy prompt rewriting is unacceptable for agents that emit code and tool calls |

### Reusable components (ideas adopted)

- **Three-tier resilience** — provider circuit breaker, per-key cooldown, and
  per-model lockout as *separate* mechanisms rather than one cooldown clock.
  This repo had tiers 2 and 3; tier 1 is genuinely new.
- **Half-open probing.** A tripped breaker admits exactly one probe request
  before restoring full traffic, instead of a flat timed cooldown.
- **Live multi-factor scoring** for automatic strategy selection (health,
  quota headroom, cost, latency, success rate) rather than static priority.
- **Tiered fallback taxonomy** (local → free → cheap → premium) as a
  first-class config concept, which makes graceful degradation expressible.
- **Named profiles** → adopted as per-agent routing policies.

### Incompatible components (explicitly rejected)

- **The 12-engine compression pipeline.** Caveman/OmniGlyph-style lossy
  rewriting corrupts tool-call arguments and JSON-mode payloads, and this
  platform's agents depend on both. We implement lossless context management
  instead (§ Context strategy below).
- **The Electron desktop shell and 80-command CLI.** No user need; the
  platform is a hosted FastAPI service.
- **SQLite-authored routing combos.** Routing that lives only in a database
  is not reviewable, not diffable, and not reproducible across the
  Render/Cloudflare deploy. Routing config is committed YAML here.
- **290 bundled provider adapters.** Most are OpenAI-compatible with a
  different base URL. Bundling 290 hand-written adapters is maintenance debt;
  one generic adapter plus YAML entries covers them.
- **Zero-config keyless free providers.** Silently calling unaudited third
  parties conflicts with the free-brain policy in `packages/ai/brain.py`,
  which requires explicit operator opt-in for every egress path.

## Decision

Introduce `packages/llm/` — a new package that owns **all** LLM egress —
and route every existing caller through it without changing their signatures.

### 1. `LLMRouter` is the only gateway

```python
from packages.llm import get_router

response = await get_router().chat(LLMRequest(messages=[...], agent="planner"))
```

No module outside `packages/llm/providers/` may construct an HTTP client aimed
at a model endpoint. The Repository Constitution rule "no new provider
implementation may bypass `ProviderManager`" is widened to `LLMRouter`.

**Why a new package instead of extending `packages/ai/`:** `packages/ai/router.py`
is 1988 lines with 15 importers and production behaviour we may not change
(Golden Rule). A parallel package lets the new layer be built, tested, and
enabled behind a flag while the old path stays byte-identical. `packages/ai/`
becomes the compatibility surface, not the implementation.

### 2. Providers are data, not code

One `OpenAICompatibleProvider` serves OpenAI, Groq, Cerebras, OpenRouter,
Together, Fireworks, DeepInfra, Mistral, Azure, NVIDIA NIM, LM Studio, vLLM,
LiteLLM, LocalAI, and any other OpenAI-shaped REST endpoint. Only Anthropic,
Gemini, and Ollama get bespoke adapters, because their wire formats differ.
Adding a provider is an entry in `config/llm/providers.yaml`.

**Why:** the 290-vs-7 provider gap is entirely a configuration gap. Writing
one adapter per vendor would triple the code for zero capability.

### 3. Secrets stay in the environment

`config/llm/keys.yaml` maps a provider to *environment variable names*
(`OPENAI_API_KEY`, `OPENAI_API_KEY_2`, …), never to key material. The loader
expands `${VAR}` at read time and refuses to persist resolved values.

**Why:** the Constitution forbids writing secrets to disk, and committed YAML
is in git.

### 4. Three independent failure scopes

A failure is attributed to the narrowest scope that explains it:

| Signal | Scope penalised | Recovery |
|--------|-----------------|----------|
| 429 with `retry-after` | the **key** | key cooldown, other keys keep serving |
| 429/404 naming one model | the **model** | model lockout, siblings keep serving |
| 5xx, timeout, connection reset | the **provider** | circuit breaker, half-open probe |
| 401/403, malformed request, content filter | nothing — permanent | no retry |

**Why:** a single cooldown clock over-penalises. Marking a whole provider dead
because one model was decommissioned is the specific failure this repo hit
(NVIDIA 410 → schedule multiplication, § CLAUDE.md 7).

### 5. Bulkhead isolation

Each provider gets its own concurrency semaphore sized from
`providers.yaml`. A provider that stops responding can exhaust only its own
slots.

**Why:** without bulkheads, one provider timing out at 60 s drains the global
worker pool and stalls providers that are perfectly healthy — the outage
spreads instead of being contained.

### 6. Context is managed losslessly

Escalate to a larger-context model → drop old turns by sliding window →
summarise the dropped span with a cheap model → retrieve semantically relevant
history → chunk oversized documents. Never rewrite the live turn's text.

**Why:** agents in this repo emit code, tool-call JSON, and structured outputs.
Lossy compression breaks all three, and the Golden Rule makes that a
regression, not a trade-off.

### 7. Configuration is six committed YAML files

`providers.yaml`, `routing.yaml`, `models.yaml`, `keys.yaml`, `health.yaml`,
`cache.yaml` under `config/llm/`. All are optional — absent files fall back to
built-in defaults derived from the current environment variables, so an
existing deploy behaves identically with no config at all.

**Why:** "no code changes to add a provider" was an explicit requirement, and
committed config is reviewable in the same PR as the code that consumes it.

### 8. Backwards compatibility by shim, not by rewrite

`failover_chat_completion()` keeps its exact signature and return type. When
`LLM_ROUTER_ENABLED=false` (the default until the new path is verified in
production), it runs the existing implementation unchanged. When enabled, it
delegates to `LLMRouter` and adapts the result back into a `FailoverResult`.

**Why:** Golden Rule. Every caller — `agent/loop.py`, `proxy.py`,
`backend/server.py` — must observe identical behaviour, and rollback must be a
single environment variable rather than a revert.

## Consequences

**Positive**
- One place to improve resilience; every agent benefits at once.
- New providers, models, and routing policies ship without Python changes.
- Failures are isolated to key, model, or provider — never escalated.
- Per-agent policies let the planner prefer a reasoning model while the
  verifier prefers a fast free one.
- Prometheus metrics and the dashboard read one coherent state, not five.

**Negative**
- Two routing implementations coexist during migration. Mitigated by the
  feature flag and by `packages/ai/` becoming a thin shim.
- Six YAML files are more surface to get wrong. Mitigated by every file being
  optional with defaults, plus schema validation at load.
- Semantic caching and summarisation add latency on the paths that use them.
  Both are opt-in per `cache.yaml` and `routing.yaml`.

**Neutral**
- "Unlimited tokens" remains impossible. What this buys is continuous
  operation: when one path is exhausted, another is already warm.

## References
- ADR-003 (provider abstraction) — this ADR supersedes its scope.
- ADR-006 (strangler-fig shims) — the migration pattern used here.
- ADR-007 (storage duck typing) — the queue and stats stores follow it.
- OmniRoute (github.com/diegosouzapw/OmniRoute) — studied for design, not code.

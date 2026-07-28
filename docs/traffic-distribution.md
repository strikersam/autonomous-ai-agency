# Traffic Distribution Across Providers

How the agency spreads LLM traffic over several providers so free-tier keys
stop taking turns being the one that returns `429`.

Implemented in [`packages/ai/traffic_director.py`](../packages/ai/traffic_director.py),
wired into [`packages/ai/router.py`](../packages/ai/router.py).

---

## The problem this solves

The router walks its provider list in strict priority order. Provider #1
absorbs **every** request until it fails, and only then does traffic move to
provider #2. On a paid tier that is exactly right — you want the best model
first. On the free tiers this agency runs on (NVIDIA NIM, Cerebras, Groq) it
is the main cause of `429` cascades: the first key is driven into its
per-minute ceiling while two idle keys sit behind it.

Everything the router already had is *reactive* — it learns about a limit by
eating a `429` first:

| Mechanism | Where | What it does |
|-----------|-------|--------------|
| Exponential backoff on repeated 429s | `router.py` | Doubles the provider cooldown per consecutive 429 |
| `Retry-After` honoured | `router.py` | Uses the provider's own stated wait |
| Per-model skip on 419 | `router.py` | NVIDIA NIM concurrency limit — try the next model, not the next provider |
| Dead-model memory on 410 | `router.py` | Skips a permanently removed model without cooling the provider |
| Probe lock (half-open circuit breaker) | `router.py` | One request probes a recovered provider; the rest skip it |
| Header-driven pre-flight | `rate_limiter.py` | Sleeps when `x-ratelimit-remaining-*` is nearly spent |
| Token-bucket pacing | `rate_limiter.py` | Paces to a configured RPM instead of bursting |
| Response cache | `response_cache.py` | Removes duplicate calls entirely |

None of those *spread* load. That is what the traffic director adds.

---

## Strategies

Set `LLM_ROUTING_STRATEGY` to one of:

| Strategy | Behaviour | LiteLLM equivalent |
|----------|-----------|--------------------|
| `priority` **(default)** | Strict priority order — the historical behaviour, unchanged | — |
| `weighted-shuffle` | Weighted random pick by `<PROVIDER>_WEIGHT`, else remaining RPM headroom, else an equal share | `simple_shuffle` |
| `least-busy` | Fewest in-flight requests first | `least_busy` |
| `usage-based` | Lowest fraction of its RPM/TPM budget spent this minute | `lowest_tpm_rpm_v2` |
| `latency-based` | Lowest EWMA response latency; never-sampled providers go first so they can earn a sample | `lowest_latency` |

An unrecognised value logs a warning once and behaves as `priority` — a typo
must not silently pick a different distribution.

### What is safe about switching one on

**Reordering never crosses an access tier.** The router passes the tier rank
from `provider_sort_key` as a grouping key, and distribution happens strictly
*within* each group. No strategy can promote a paid commercial provider ahead
of a free one, so turning on `least-busy` cannot start spending money the
moment the free tier gets busy.

**Which providers actually share a group.** Grouping is by access tier, over
the priority-sorted list. In the default fleet that gives one large free-cloud
run — `deepseek`, `groq`, `sambanova`, `cerebras`, `qwen-dashscope`,
`together-free`, `mistral`, `google-gemini-free` — which is the pool a
strategy spreads across. `nvidia-nim` is alone in its own tier at priority
`-10`, so it is always tried first whatever the strategy says. **To get
NVIDIA to yield to the pool, give it a budget** (`NVIDIA_NIM_MAX_RPM`); the
pre-call check is what moves traffic off it, the strategy is what spreads the
traffic once it lands.

**Ties are broken randomly, deliberately.** At cold start every provider
scores zero on every metric. A stable sort would hand the whole opening burst
to whichever provider happened to be first — reintroducing the pile-up by the
back door.

**A provider that just returned a 429 carries a penalty** for the rest of the
window under `usage-based`, so it sorts behind its healthy siblings for a
minute after its cooldown expires rather than being the first one probed
again.

---

## Pre-call budget checks

`rate_limiter.pace()` already paces requests when `<PROVIDER>_MAX_RPM` is set,
but pacing **blocks the caller**. That is right only when there is nowhere
else to go. When a sibling provider is idle, skipping to it is strictly
better.

`TrafficDirector.over_budget()` reports whether a provider has already spent
its configured budget for the current 60-second window, and the router routes
around it — the same trick as LiteLLM's `async_pre_call_check`, which raises a
synthetic rate-limit error so the caller falls through to another deployment
rather than spending a real request to be told `429`.

Three conditions, checked in order:

1. `in_flight >= <PROVIDER>_MAX_PARALLEL` → `max-parallel`
2. requests this minute `>= <PROVIDER>_MAX_RPM` → `rpm`
3. tokens this minute `>= <PROVIDER>_MAX_TPM` → `tpm`

**With a single configured provider the check is disabled.** Skipping the only
provider would convert a slow request into a failed one; pacing stays the
right tool there.

A provider that is over budget is treated exactly like one on cooldown — it
still gets tried by the router's last-resort bypass if *every* provider is
out of budget, so a saturated fleet degrades to "slow" rather than "down".

---

## Configuration

All budgets are per provider id, read through `packages/ai/brain_config.py`.
None of them is set by default, and none of them hardcodes a provider's
"current" free-tier limit — those change over time and are account-specific.
Check the provider's own dashboard, or the `x-ratelimit-*` headers on a live
response, and set the real number.

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_ROUTING_STRATEGY` | `priority` | Which distribution strategy the router uses |
| `<PROVIDER>_MAX_RPM` | unset | Requests/minute ceiling — used for pacing *and* for routing away |
| `<PROVIDER>_MAX_TPM` | unset | Tokens/minute ceiling — what large-context agent calls hit first |
| `<PROVIDER>_WEIGHT` | unset | Share weight for `weighted-shuffle` (weight 3 ≈ three times the traffic of weight 1) |
| `<PROVIDER>_MAX_PARALLEL` | unset | In-flight ceiling — the limit NVIDIA NIM enforces with `419` |

Unset means "no limit". So does zero, a negative number, `inf`, `nan`, or
anything unparseable — a limit of zero would wedge a provider out of rotation
permanently, which is never what a malformed value should mean.

### Provider ids contain dashes

The router's provider ids are slugs like `nvidia-nim`. Naively upper-casing
one gives `NVIDIA-NIM_MAX_RPM`, which shells refuse to export and most
dashboards refuse to store. Every budget variable accepts the
dash-to-underscore form and still reads the literal name first:

```bash
NVIDIA_NIM_MAX_RPM=40      # works
NVIDIA-NIM_MAX_RPM=40      # also still works, if your platform allows it
```

### A worked example

Three free keys, roughly equal limits, wanting even spread. The
`NVIDIA_NIM_*` budgets are the ones that make NVIDIA hand off to the free-cloud
pool at all — without them it is tried first on every request, because it sits
alone in its own tier:

```bash
LLM_ROUTING_STRATEGY=usage-based
CEREBRAS_MAX_RPM=28
GROQ_MAX_RPM=30
NVIDIA_NIM_MAX_RPM=40
NVIDIA_NIM_MAX_PARALLEL=4
```

One fast key you want to favour, two as spill-over:

```bash
LLM_ROUTING_STRATEGY=weighted-shuffle
CEREBRAS_WEIGHT=5
GROQ_WEIGHT=1
NVIDIA_NIM_WEIGHT=1
```

---

## Observability

```text
GET /api/metrics/traffic-distribution     (authenticated)
```

Returns the active strategy and, per provider: in-flight count, requests and
tokens used in the current window, the configured budgets, EWMA latency,
seconds since the last `429`, and how many requests were routed away for being
over budget.

It is the counterpart to `GET /api/metrics/rate-limits`: that endpoint reports
what providers *told us* about their quota via `x-ratelimit-*` headers, this
one reports what the router actually did with it.

---

## Failure behaviour

Accounting can never fail a request. The director is fetched through a helper
that returns `None` on any import error, every call site swallows exceptions,
and `record_end` runs in a `finally` — so a successful early return can never
leak an in-flight count and pin a provider at its concurrency ceiling.

State is in-process and best-effort: a 60-second sliding window of request
timestamps and token counts, plus in-flight counts and a latency EWMA. A
restart clears it, which is fine — the window is a minute long. Across
multiple web/worker processes each one paces its own share; the shared
cooldown state in `services/shared_state.py` remains the cross-process
mechanism.

---

## Attribution

The strategies are ports of the ones
[LiteLLM's `Router`](https://github.com/BerriAI/litellm) exposes in
`litellm/router_strategy/`, adapted to this codebase's provider model
(providers with access tiers and a fallback chain, rather than interchangeable
deployments of one model group).

---

## Adding capacity: multi-key rotation

Everything above *rations* a fixed budget. Distribution spreads it, pacing
meters it, backoff waits for it — none of them raise the ceiling. When the fleet
is genuinely at its limit, the only code-level fix that adds capacity is using
more than one free-tier account per provider.

Free tiers are rate-limited **per key**, not per provider. Three Groq keys is
three times the requests per minute, and the provider only goes into cooldown
once *all* of its keys are spent.

Configure with a numbered suffix on the provider's existing key variable:

```bash
GROQ_API_KEY=gsk_first
GROQ_API_KEY_2=gsk_second
GROQ_API_KEY_3=gsk_third
```

The scan stops at the first gap, so a typo'd `_4` cannot silently promote itself
into the `_2` slot and leave you believing three keys are live when two are.
Duplicate keys are collapsed — the same key twice is one budget, not two.

**With one key the pool is a pass-through.** `next_key` always returns it,
`all_cooling` is immediately true, and the provider-level cooldown behaves
exactly as it did before rotation existed. Rotation only engages from two keys
up, so this is inert until you opt in.

On a 429 the refused key rests (honouring `Retry-After`, clamped) while its
siblings keep serving. Only when every key is resting does the provider itself
get cooled.

### The gain is across requests, not within one

Be precise about what this buys. When a key is refused, `failover_client` has
already added that provider to the request's `tried` set, so the *current*
request moves on to the next provider rather than immediately retrying the same
one with the sibling key. Spending several keys on a single request would be
the wrong trade anyway.

What changes is the provider's **state afterwards**. Without rotation one 429
cools the whole provider for 30–480s, so every request in that window skips it.
With rotation the provider stays `CLOSED` and the *next* request reaches it on
the next key. Across a stream of requests that is the difference between a
provider being available and being benched — which is the whole point — but a
single request does not get a second bite at the same provider.

> **Check the provider's terms.** Several free tiers permit multiple accounts;
> some do not. This gives you the mechanism — whether a given provider allows it
> is your call, and not something the code can verify.

Key material never reaches a log or an API response: keys are identified in
diagnostics by a short salted digest, never by a prefix or suffix of the key
itself (a leading fragment identifies the account outright for some providers).

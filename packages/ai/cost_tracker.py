"""Per-model cost attribution for the LLM provider router.

Maintains in-memory per-model token and cost aggregates so operators can see
which models are consuming the most spend.  The store is best-effort (no
persistence across restarts, no locking) and is never on the critical path —
all accounting is fire-and-forget.

Cost table (USD per million tokens) is approximate and covers the free/low-cost
providers this platform uses.  Operators can override via ``MODEL_COST_INPUT``
and ``MODEL_COST_OUTPUT`` env vars (comma-separated ``model_id=price`` pairs).

Usage:
    from packages.ai.cost_tracker import record_usage, get_stats, clear_stats

    record_usage("gpt-4o-mini", provider_id="openai", prompt_tokens=1200, completion_tokens=80)
    stats = get_stats()  # {"gpt-4o-mini": {"calls": 1, "prompt_tokens": 1200, ...}}
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict
from typing import Any

log = logging.getLogger("llm-cost-tracker")

# ── Per-million-token cost table (USD) ────────────────────────────────────────
# Pricing as of 2026-09-06; free-tier providers are listed at $0.00.
# Anthropic source: platform.claude.com/docs/en/about-claude/pricing
_DEFAULT_COST_TABLE: dict[str, tuple[float, float]] = {
    # (input_per_M, output_per_M)
    # --- NVIDIA NIM (free tier) ---
    "meta/llama-4-maverick-17b-128e-instruct": (0.0, 0.0),
    "meta/llama-4-scout-17b-16e-instruct": (0.0, 0.0),
    "meta/llama-3.3-70b-instruct": (0.0, 0.0),
    "nvidia/llama-3.1-nemotron-70b-instruct": (0.0, 0.0),
    "deepseek-ai/deepseek-r1": (0.0, 0.0),
    "z-ai/glm-5.2": (0.0, 0.0),
    "nvidia/nemotron-3-super-120b-a12b": (0.0, 0.0),
    # Mistral NeMo-Tron on NVIDIA NIM — Mistral NeMo 12B instruction-tuned by NVIDIA.
    "mistralai/mistral-nemotron": (0.0, 0.0),
    # Nemotron 3 Ultra 550B on NVIDIA NIM — intermittent (404'd on some probes).
    "nvidia/nemotron-3-ultra-550b-a55b": (0.0, 0.0),
    # DeepSeek V4 Pro — live in NIM catalog Aug 2026 (free tier).
    "deepseek-ai/deepseek-v4-pro": (0.0, 0.0),
    # --- TokenIn (tokenin.my.id, free frontier gateway) ---
    # All ids are the gateway's own free-tier aliases (`myt/...-free`) for
    # frontier models it re-serves at no cost — not the underlying paid
    # models. Explicit here because the fuzzy substring fallback below would
    # otherwise match e.g. "myt/claude-opus-4-8-free" against the paid
    # "claude-opus-4-8" entry and "myt/gpt-5.6-sol-free" against the paid
    # "gpt-5.6-sol" entry, billing free traffic at $5+/MTok.
    "myt/glm-5.3-free": (0.0, 0.0),
    "myt/deepseek-v4-pro-free": (0.0, 0.0),
    "myt/MiniMax-M3-free": (0.0, 0.0),
    "myt/mimo-v2.5-free": (0.0, 0.0),
    "myt/qwen3.8-max-free": (0.0, 0.0),
    "myt/kimi-k3-free": (0.0, 0.0),
    "myt/gemini-3.5-flash-free": (0.0, 0.0),
    "myt/grok-4.6-free": (0.0, 0.0),
    "myt/gpt-5.6-sol-free": (0.0, 0.0),
    "myt/claude-opus-4-8-free": (0.0, 0.0),
    # --- Cerebras (free/paid tier) ---
    # Probed 2026-08-29: this account's catalogue is exactly these two. The
    # three ids that were here — qwen-3-coder-480b, llama-3.3-70b,
    # llama-3.1-8b — all answer 404.
    # gpt-oss-120B — Cerebras's 120B OSS model, ~3000 tok/s (Aug 2026).
    "gpt-oss-120b": (0.85, 1.20),
    # Rate not established: the account returns 402, so nothing has been
    # billed to read a rate off. Zero matches every other free-tier entry here
    # and the documented default for an unlisted model, so it adds no claim.
    "gemma-4-31b": (0.0, 0.0),
    # --- Groq (free/paid tier) ---
    "llama-3.3-70b-versatile": (0.0, 0.0),
    "deepseek-r1-distill-llama-70b": (0.0, 0.0),
    "llama-3.1-8b-instant": (0.0, 0.0),
    # Kimi K2 on Groq — Moonshot AI MoE, ~1M context. Groq self-serve pricing:
    # $1.00/$3.00 per MTok (most expensive self-serve model on Groq Sep 2026).
    # Source: Groq pricing aggregators, 2026-09-22.
    "moonshotai/kimi-k2-instruct": (1.0, 3.0),
    # Qwen3 32B on Groq — strong coder, free tier (Aug 2026).
    "qwen-qwq-32b": (0.0, 0.0),
    # GPT-OSS 120B / 20B — served on both NVIDIA NIM and Groq free tier.
    "openai/gpt-oss-120b": (0.0, 0.0),
    "openai/gpt-oss-20b": (0.0, 0.0),
    # GPT-OSS-Safeguard: OpenAI safety-reasoning models (Oct 2025). Fine-tuned
    # from gpt-oss-20b / gpt-oss-120b respectively; purpose-built for safety
    # classification — follows explicit user-provided policies and explains
    # decisions. Not in routing candidates (specialised, not general-purpose).
    # safeguard-20b: GroqCloud at 1000+ t/s, context 131K, 65K output.
    # Pricing source: console.groq.com/docs/model/openai/gpt-oss-safeguard-20b, 2026-10-02.
    "openai/gpt-oss-safeguard-20b": (0.075, 0.30),
    # safeguard-120b: Amazon Bedrock / Opper; not on Groq self-serve as of 2026-10-02.
    # Pricing source: futureagi.com/llm-cost-calculator/bedrock, 2026-10-02.
    "openai/gpt-oss-safeguard-120b": (0.15, 0.60),
    # Amazon Bedrock gpt-oss (OpenAI-compatible endpoint), on-demand standard
    # tier, per 1M tokens (checked 2026-10-04).
    "openai.gpt-oss-120b-1:0": (0.15, 0.60),
    "openai.gpt-oss-20b-1:0": (0.07, 0.30),
    # Qwen3 Coder Next on Bedrock (Mantle endpoint), per 1M tokens (checked 2026-10-04).
    "qwen.qwen3-coder-next": (0.50, 1.20),
    # --- Google Gemini ---
    # Gemini 2.5 Flash: AI Studio free tier for low-RPM usage; usage through
    # the paid API is charged at $0.075/$0.30 per MTok (non-thinking, ≤200K).
    # This repo routes through the free tier; tracking at $0 until an account
    # with a billing relationship is configured.
    "gemini-2.5-flash": (0.0, 0.0),
    "gemini-2.0-flash": (0.0, 0.0),
    # Gemini 2.5 Pro: paid model used by the "google" BRAIN_PRESET as planner
    # and judge. Tiered pricing — $1.25/$10.0 per MTok (≤200K-token requests),
    # $2.50/$15.0 (>200K). Lower bound tracked here; the router does not model
    # per-request tiers. Source: ai.google.dev/pricing, 2026-09-11.
    "gemini-2.5-pro": (1.25, 10.0),
    # Gemini 3.x family (Aug–Sep 2026). Source: ai.google.dev/pricing, 2026-09-13.
    # 3.1 Pro: frontier reasoning, $2.00/$12.00 per MTok (≤200K lower bound).
    "gemini-3.1-pro": (2.0, 12.0),
    # 3.5 Flash Lite: cheapest tier, $0.30/$2.50 per MTok.
    "gemini-3.5-flash-lite": (0.30, 2.50),
    # 3.7 Flash / 3.8 Flash: introductory $0.75/$3.75 through 2026-12-31;
    # standard $1.50/$7.50 from 2027-01-01. Intro price tracked here.
    "gemini-3.7-flash": (0.75, 3.75),
    "gemini-3.8-flash": (0.75, 3.75),
    # --- Anthropic (paid) — Claude 5 family + Sonnet 4.x / Opus 4.x ---
    # Prices verified from platform.claude.com/docs/en/about-claude/pricing 2026-09-06.
    "claude-opus-5": (5.0, 25.0),          # Opus 5 — $5/$25 per MTok
    "claude-opus-5-5": (4.0, 20.0),        # Opus 5.5 — $4/$20 per MTok (released 2026-09-22; 20% cheaper than Opus 5)
    "claude-opus-5-5-20260922": (4.0, 20.0),  # Opus 5.5 versioned ID
    "claude-sonnet-5": (2.0, 10.0),        # Sonnet 5 — $2/$10 per MTok (introductory price made permanent 2026-09-01)
    "claude-sonnet-5-20260501": (2.0, 10.0),
    "claude-sonnet-5-5": (2.0, 10.0),     # Sonnet 5.5 — $2/$10 per MTok (released 2026-09-29; same price as Sonnet 5)
    "claude-sonnet-5-5-20260929": (2.0, 10.0),  # Sonnet 5.5 versioned ID
    "claude-fable-5": (10.0, 50.0),        # Fable 5 — $10/$50 per MTok (gated flagship)
    "claude-fable-5-1": (10.0, 50.0),      # Fable 5.1 — $10/$50; cache reads 2.5 % (see _CACHE_READ_FRACTIONS)
    "claude-mythos-5": (10.0, 50.0),       # Mythos 5 — same as Fable 5 (restricted)
    "claude-mythos-5-1": (10.0, 50.0),     # Mythos 5.1 — $10/$50; cache reads 2.5 % (see _CACHE_READ_FRACTIONS)
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5": (3.0, 15.0),        # Sonnet 4.5 — $3/$15 per MTok (same tier as 4.6)
    "claude-opus-4-8": (5.0, 25.0),        # Opus 4.8 — $5/$25 per MTok (same tier as Opus 5)
    "claude-opus-4-7": (5.0, 25.0),        # Opus 4.7 — $5/$25 per MTok
    "claude-opus-4-6": (5.0, 25.0),        # Opus 4.6 — $5/$25 per MTok
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-haiku-4-5": (1.0, 5.0),        # Haiku 4.5 — $1/$5 per MTok
    "claude-3-5-sonnet-20241022": (3.0, 15.0),
    "claude-3-5-haiku-20241022": (0.8, 4.0),
    # --- OpenAI (paid) — GPT-5.5 family (May 2026) ---
    # Source: platform.openai.com/docs/models, openrouter.ai/openai/gpt-5.5, 2026-10-04.
    # 1,050,000-token context; 128K max output. gpt-5.5-pro is the extended-thinking
    # variant at $30/$180 per MTok. Not yet on NVIDIA NIM; entries cover
    # direct-OpenAI or proxied usage via OpenRouter.
    "gpt-5.5": (5.0, 30.0),               # GPT-5.5 — $5/$30 per MTok
    "gpt-5.5-pro": (30.0, 180.0),         # GPT-5.5-pro (extended thinking) — $30/$180 per MTok
    # --- OpenAI (paid) — GPT-5.6 family (GA July 9 2026) + legacy ---
    "gpt-5.6-sol": (5.0, 30.0),            # Sol: complex reasoning/coding, o3 successor
    "gpt-5.6-terra": (1.5, 7.5),           # Terra: balanced/lower cost
    "gpt-5.6-luna": (0.5, 2.0),            # Luna: fast/high-volume
    # --- OpenAI Realtime 2.1 family (October 2026) ---
    # Text-input pricing only (audio billed separately via Realtime API).
    # Source: developers.openai.com/api/docs/models, 2026-10-04.
    # Context: 128K tokens; max output: 32K tokens. WebRTC / WebSocket / SIP.
    "gpt-realtime-2.1": (4.0, 24.0),       # Realtime 2.1 — $4/$24 per MTok (text)
    "gpt-realtime-2.1-mini": (0.60, 2.40), # Realtime 2.1 Mini — $0.60/$2.40 per MTok (text)
    # --- OpenAI (paid) — GPT-6 family (September 2026) ---
    # Source: platform.openai.com/docs/models, 2026-09-30. Not yet on NVIDIA NIM;
    # entries here cover direct-OpenAI or proxied usage via OpenRouter/similar.
    "gpt-6-astra": (10.0, 50.0),           # Astra: frontier reasoning, $10/$50 per MTok (released Sept 4)
    "gpt-6-luna": (0.1, 0.5),              # Luna: fast/high-volume, $0.1/$0.5 per MTok (released Sept 22)
    "gpt-6.1-sol": (2.0, 10.0),            # gpt-6.1-sol: $2/$10 per MTok (released Sept 29)
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "o1": (15.0, 60.0),
    "o3": (10.0, 40.0),                    # Deprecating late August 2026; migrate to gpt-5.6-sol
    "o3-mini": (1.1, 4.4),
    # --- North Mini Code (local/OpenRouter free) ---
    "north-mini-code-1.0": (0.0, 0.0),
    "cohere/north-mini-code:free": (0.0, 0.0),
    # --- DeepSeek ---
    "deepseek-chat": (0.27, 1.10),
    "deepseek-coder": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
    # DeepSeek V4.1-Flash (released 2026-09-10): $0.30/$1.20 per MTok peak.
    # Off-peak is half; cache-hit is 1/50th. Using peak as the conservative floor.
    # Source: api-docs.deepseek.com/quick_start/pricing, 2026-09-18.
    "deepseek-flash": (0.30, 1.20),
    # --- Groq: Llama 4 Scout 17B 16E (added 2026-10-04) ---
    # Distinct from NVIDIA NIM's free "meta/llama-4-scout-17b-16e-instruct" ($0/$0).
    # Groq serves this as "meta-llama/llama-4-scout-17b-16e-instruct" (different prefix).
    # 128K context on Groq (full 10M window not available on LPU hardware), Preview tier.
    # Pricing: $0.11/$0.34 per MTok. Source: pricepertoken.com/pricing-page/model/
    # meta-llama-llama-4-scout, 2026-10-04.
    "meta-llama/llama-4-scout-17b-16e-instruct": (0.11, 0.34),
    # --- Groq: Qwen 3.8 27B (added 2026-09-18) ---
    "qwen/qwen3.8-27b": (0.80, 4.00),
    # --- Mistral API (added 2026-09-19) ---
    # Pricing approximate; verify at mistral.ai/pricing before billing-sensitive use.
    "mistral-large-latest": (3.00, 9.00),   # Mistral Large 2 — $3/$9 per MTok
    "mistral-small-latest": (0.10, 0.30),   # Mistral Small 3 — $0.10/$0.30 per MTok
    "codestral-latest": (0.30, 0.90),       # Codestral — $0.30/$0.90 per MTok
    "mistral-nemo": (0.15, 0.15),           # NeMo 12B — free/ultra-cheap tier
    # Devstral (added 2026-10-05) — estimated at Mistral Small's $0.10/$0.30;
    # not on the pricing page this was sourced from, so treat as an estimate.
    "devstral-latest": (0.10, 0.30),
    # Pixtral Large / Ministral family (added 2026-10-03).
    # Pricing source: mistral.ai/technology/#pricing, 2026-10-03.
    "pixtral-large-latest": (2.00, 6.00),   # Pixtral Large 124B — $2/$6 per MTok
    "ministral-8b-latest": (0.10, 0.10),    # Ministral 8B — flat $0.10 per MTok
    "ministral-3b-latest": (0.04, 0.04),    # Ministral 3B — flat $0.04 per MTok
    # --- Together AI (free tier, added 2026-09-19) ---
    "Llama-3.3-70B-Instruct-Turbo-Free": (0.0, 0.0),
    "Mixtral-8x7B-Instruct-v0.1-Free": (0.0, 0.0),
    # --- Google Gemini 1.5 (added 2026-09-19) ---
    # Pricing from ai.google.dev/pricing, 2026-09-19 (≤128K-token tier).
    "gemini-1.5-flash": (0.075, 0.30),     # Gemini 1.5 Flash
    "gemini-1.5-pro": (1.25, 5.00),        # Gemini 1.5 Pro
    # --- ZhipuAI / GLM (added 2026-09-20) ---
    # Free-credits trial plan; $0 until a billing relationship is confirmed.
    # Covers zhipu and zai providers (same model ids, different endpoints).
    "glm-5.2": (0.0, 0.0),
    "glm-5.1": (0.0, 0.0),
    "glm-4": (0.0, 0.0),
    "glm-4-flash": (0.0, 0.0),
    "glm-4-air": (0.0, 0.0),
    # --- DashScope / Alibaba Qwen (added 2026-09-20) ---
    # Conservative CNY→USD floor from dashscope.aliyuncs.com/pricing, 2026-09-20.
    # Operators should verify before billing-sensitive use.
    "qwen-plus": (0.40, 1.20),             # Qwen2.5-Plus — balanced frontier
    "qwen-max": (2.40, 9.60),             # Qwen2.5-Max — highest capability
    "qwen-turbo": (0.05, 0.10),            # Qwen2.5-Turbo — fast / 1M context
    "qwen-coder-plus": (0.40, 1.20),       # Qwen2.5-Coder-Plus — code executor preset
    # --- Moonshot / Kimi (added 2026-09-20) ---
    # Approximate pricing from platform.moonshot.cn/pricing, 2026-09-20.
    "moonshot-v1-8k": (1.40, 1.40),       # 8K context — cheapest/fastest
    "moonshot-v1-32k": (1.40, 1.40),      # 32K context — balanced
    "moonshot-v1-128k": (1.68, 1.68),     # 128K context — planner/judge preset
    # --- OpenAI embeddings ---
    "text-embedding-3-small": (0.02, 0.0),  # OpenAI text-embedding-3-small (no output cost)
    # --- Ollama (local, no cost) ---
    "deepseek-r1:32b": (0.0, 0.0),          # DeepSeek R1 32B (local Ollama)
    "qwen3-coder:30b": (0.0, 0.0),          # Qwen3 Coder 30B (local Ollama)
    "nomic-embed-text": (0.0, 0.0),         # Nomic Embed Text (local Ollama, embeddings)
    # --- Google Gemini Omni 1.1 Flash (added 2026-09-22) ---
    # Video generation / editing model — pricing not yet published; tracked at $0.
    "gemini-omni-1.1-flash": (0.0, 0.0),
    # --- NVIDIA NIM: DeepSeek V4.1-Flash (added 2026-09-22) ---
    # Same model as deepseek-flash on the DeepSeek API, served via NIM for free.
    "deepseek-ai/deepseek-v4.1-flash": (0.0, 0.0),
}


def _load_env_overrides() -> dict[str, tuple[float, float]]:
    """Parse MODEL_COST_INPUT / MODEL_COST_OUTPUT env overrides.

    Format: ``MODEL_COST_INPUT=gpt-4o=2.5,gpt-4o-mini=0.15``
            ``MODEL_COST_OUTPUT=gpt-4o=10.0,gpt-4o-mini=0.6``
    """
    overrides: dict[str, tuple[float, float]] = {}
    try:
        raw_in = os.environ.get("MODEL_COST_INPUT", "")
        raw_out = os.environ.get("MODEL_COST_OUTPUT", "")
        in_map: dict[str, float] = {}
        out_map: dict[str, float] = {}
        for pair in raw_in.split(","):
            pair = pair.strip()
            if "=" in pair:
                k, v = pair.split("=", 1)
                in_map[k.strip()] = float(v.strip())
        for pair in raw_out.split(","):
            pair = pair.strip()
            if "=" in pair:
                k, v = pair.split("=", 1)
                out_map[k.strip()] = float(v.strip())
        for model in set(in_map) | set(out_map):
            overrides[model] = (in_map.get(model, 0.0), out_map.get(model, 0.0))
    except Exception as exc:
        log.debug("MODEL_COST env override parse error (ignored): %s", exc)
    return overrides


def _build_cost_table() -> dict[str, tuple[float, float]]:
    table = dict(_DEFAULT_COST_TABLE)
    table.update(_load_env_overrides())
    return table


_COST_TABLE: dict[str, tuple[float, float]] = _build_cost_table()

# Cache-read discount fraction per model-id prefix (multiplied against the input rate).
# Anthropic: most Claude models bill cache reads at 10 % of the input rate.
#   Exceptions (per platform.claude.com/docs/en/about-claude/pricing, 2026-09-30):
#     Fable 5.1 / Mythos 5.1 — 2.5 % ($0.25/MTok on a $10/MTok input rate).
#     Opus 5.5              — 5 %   ($0.20/MTok on a $4/MTok input rate).
# Google Gemini: cached content billed at 25 % of the input rate (ai.google.dev/gemini-api/docs/caching).
# DeepSeek API: cache hit at 1/50th of the input rate (api-docs.deepseek.com/quick_start/pricing).
# Groq: implicit caching (automatic, 5-min TTL) discounts repeat inputs 50 %
#   (console.groq.com/docs/prompt-caching, 2026-07).  Applies to qwen/ and
#   meta-llama/ ids (the free openai/gpt-oss-* ids cost $0, fraction is moot).
# Per-model overrides must appear before the generic "claude-" prefix below.
_CACHE_READ_FRACTIONS: tuple[tuple[str, float], ...] = (
    # Per-model Anthropic overrides (more-specific prefixes before "claude-").
    ("claude-fable-5-1", 0.025),   # Fable 5.1 — 2.5 % of input rate
    ("claude-mythos-5-1", 0.025),  # Mythos 5.1 — same gated tier as Fable 5.1
    ("claude-opus-5-5", 0.05),     # Opus 5.5  — 5 % of input rate
    # Generic fallbacks.
    ("claude-", 0.10),
    ("gemini-", 0.25),
    ("deepseek-chat", 0.02),
    ("deepseek-reasoner", 0.02),
    ("deepseek-flash", 0.02),
    # Groq: qwen/ and meta-llama/ are paid models with 50 % implicit cache discount.
    ("qwen/", 0.50),
    ("meta-llama/", 0.50),
)


def _cache_read_fraction(model: str) -> float:
    """Return the cache-read cost fraction for *model* (1.0 = no discount known)."""
    ml = model.lower()
    for prefix, frac in _CACHE_READ_FRACTIONS:
        if ml.startswith(prefix):
            return frac
    return 1.0


def cost_for_tokens(
    model: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0
) -> float:
    """Return the USD cost for (prompt_tokens, completion_tokens) on *model*.

    ``cached_tokens`` are a subset of ``prompt_tokens`` that the provider served
    from its prompt cache.  Supported providers bill cache reads at a fraction of
    the standard input rate (see ``_CACHE_READ_FRACTIONS``); unsupported providers
    treat cached tokens as ordinary input tokens (fraction = 1.0).

    Returns 0.0 for unknown / free-tier models.
    """
    costs = _COST_TABLE.get(model)
    if costs is None:
        # Fuzzy fallback: check if any key is a prefix / suffix match
        model_lower = model.lower()
        for key, val in _COST_TABLE.items():
            if key.lower() in model_lower or model_lower in key.lower():
                costs = val
                break
    if costs is None:
        return 0.0
    input_per_m, output_per_m = costs
    # Price cached and non-cached input tokens separately.
    cached = max(0, min(cached_tokens, prompt_tokens))
    non_cached = prompt_tokens - cached
    frac = _cache_read_fraction(model)
    return (
        non_cached * input_per_m
        + cached * input_per_m * frac
        + completion_tokens * output_per_m
    ) / 1_000_000.0


# ── Aggregate store ───────────────────────────────────────────────────────────
# Dict[model_id, Dict[field, value]]; no locking (best-effort counters).

_stats: dict[str, dict[str, Any]] = defaultdict(
    lambda: {
        "calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
        "providers": set(),
    }
)
# Per-task-category breakdown (e.g. "code_generation", "reasoning",
# "fast_response" — see router/classifier.py). Populated only for callers
# that pass ``tag``; existing untagged calls roll up under "untagged" so
# totals still reconcile against get_stats()["totals"].
_tag_stats: dict[str, dict[str, Any]] = defaultdict(
    lambda: {"calls": 0, "total_tokens": 0, "estimated_cost_usd": 0.0}
)
_total_calls: int = 0
_total_cost_usd: float = 0.0


def record_usage(
    model: str,
    *,
    provider_id: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cached_tokens: int = 0,
    tag: str = "untagged",
) -> None:
    """Record token usage for *model* (fire-and-forget, never raises).

    ``tag`` is a coarse task-category label (see router/classifier.py's
    ``classify_task()``) used to break down spend by kind of work, not just
    by model — callers that don't have a category default to "untagged".
    ``cached_tokens`` is the subset of ``prompt_tokens`` served from cache;
    see ``cost_for_tokens`` for how providers discount them.
    """
    global _total_calls, _total_cost_usd
    try:
        cost = cost_for_tokens(model, prompt_tokens, completion_tokens, cached_tokens)
        entry = _stats[model]
        entry["calls"] += 1
        entry["prompt_tokens"] += prompt_tokens
        entry["completion_tokens"] += completion_tokens
        entry["total_tokens"] += prompt_tokens + completion_tokens
        entry["estimated_cost_usd"] += cost
        if provider_id:
            entry["providers"].add(provider_id)
        tag_entry = _tag_stats[tag or "untagged"]
        tag_entry["calls"] += 1
        tag_entry["total_tokens"] += prompt_tokens + completion_tokens
        tag_entry["estimated_cost_usd"] += cost
        _total_calls += 1
        _total_cost_usd += cost
    except Exception as exc:
        log.debug("cost_tracker.record_usage error (ignored): %s", exc)


def get_stats() -> dict[str, Any]:
    """Return a JSON-serialisable snapshot of per-model cost attribution."""
    result: dict[str, Any] = {}
    for model, entry in _stats.items():
        result[model] = {
            "calls": entry["calls"],
            "prompt_tokens": entry["prompt_tokens"],
            "completion_tokens": entry["completion_tokens"],
            "total_tokens": entry["total_tokens"],
            "estimated_cost_usd": round(entry["estimated_cost_usd"], 6),
            "providers": sorted(entry["providers"]),
        }
    by_tag = {
        tag: {
            "calls": entry["calls"],
            "total_tokens": entry["total_tokens"],
            "estimated_cost_usd": round(entry["estimated_cost_usd"], 6),
        }
        for tag, entry in _tag_stats.items()
    }
    return {
        "models": result,
        "by_tag": by_tag,
        "totals": {
            "calls": _total_calls,
            "estimated_cost_usd": round(_total_cost_usd, 6),
        },
    }


def clear_stats() -> None:
    """Reset all aggregates (intended for testing)."""
    global _total_calls, _total_cost_usd
    _stats.clear()
    _tag_stats.clear()
    _total_calls = 0
    _total_cost_usd = 0.0


def get_cost_table() -> dict[str, dict[str, float]]:
    """Return the active cost table as a JSON-serialisable dict."""
    return {
        model: {"input_per_million_usd": inp, "output_per_million_usd": out}
        for model, (inp, out) in _COST_TABLE.items()
    }

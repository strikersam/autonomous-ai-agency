"""packages/llm/config.py — YAML configuration for the routing layer.

Six optional files under ``config/llm/``:

    providers.yaml   which endpoints exist, their kind, tier, and limits
    models.yaml      model capabilities, context windows, pricing, priority
    routing.yaml     strategy, retry policy, fallback chain, per-agent policies
    keys.yaml        provider -> environment variable NAMES (never key material)
    health.yaml      circuit breaker and health-probe thresholds
    cache.yaml       cache layers and TTLs

Every file is optional. With none present the router falls back to defaults
derived from the same environment variables the existing stack already reads,
so an untouched deployment behaves exactly as before (ADR-008 §8).

This module is the only place in ``packages/llm`` that touches the filesystem
or ``os.environ`` for configuration, mirroring the rule that keeps env access
inside config modules.
"""
from __future__ import annotations

import logging
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("llm.config")

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")

CONFIG_DIR_ENV = "LLM_CONFIG_DIR"
DEFAULT_CONFIG_DIR = "config/llm"

_CONFIG_FILES = (
    "providers", "models", "routing", "keys", "health", "cache",
)


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class ProviderConfig:
    """One configured endpoint.

    ``kind`` selects the adapter: ``openai`` (any OpenAI-compatible REST API),
    ``anthropic``, ``gemini``, or ``ollama``. Everything else — auth header
    style, base URL, limits — is data.
    """

    id: str
    kind: str = "openai"
    base_url: str = ""
    key_env: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    default_model: str = ""
    tier: str = "free"                  # local | free | cheap | premium
    priority: int = 100                 # lower = preferred
    weight: float = 1.0                 # for weighted strategy
    enabled: bool = True
    max_concurrency: int = 8            # bulkhead size
    requests_per_minute: int = 0        # 0 = unmetered
    tokens_per_minute: int = 0
    timeout_sec: float = 120.0
    auth_style: str = "bearer"          # bearer | x-api-key | query | none
    auth_header: str = ""               # explicit override
    extra_headers: dict[str, str] = field(default_factory=dict)
    api_version: str = ""               # Azure OpenAI
    deployment: str = ""                # Azure OpenAI
    requires_key: bool = True
    # Send OpenAI's `stream_options` on streaming calls. Off by default:
    # only genuine OpenAI-compatible servers accept the field.
    stream_options: bool = False
    notes: str = ""
    # Anthropic-specific feature flags (silently ignored by all other providers).
    prompt_caching: bool = True    # adds anthropic-beta: prompt-caching-2024-07-31
    thinking_budget: int = 0       # >0 enables extended thinking with that token budget
    default_effort: str = ""       # provider-level effort default for adaptive-thinking models

    @property
    def is_local(self) -> bool:
        return self.tier == "local"

    @property
    def is_paid(self) -> bool:
        return self.tier in {"cheap", "premium"}


@dataclass
class ModelConfig:
    """Capability and pricing metadata for one model id."""

    id: str
    provider: str = ""
    display_name: str = ""
    context_window: int = 8192
    max_output_tokens: int = 4096
    supports_tools: bool = False
    supports_json: bool = False
    supports_images: bool = False
    supports_reasoning: bool = False
    supports_streaming: bool = True
    supports_function_calling: bool = False
    supports_embeddings: bool = False
    # Embedding-only models must never be offered as chat candidates: they
    # accept the request shape and return something useless.
    supports_chat: bool = True
    input_cost_per_1m: float = 0.0
    output_cost_per_1m: float = 0.0
    priority: int = 100
    speed_tier: str = "medium"          # fast | medium | slow
    max_requests_per_minute: int = 0
    max_tokens_per_minute: int = 0
    max_tokens: int = 0                 # hard per-request ceiling; 0 = unset
    aliases: list[str] = field(default_factory=list)

    @property
    def is_free(self) -> bool:
        return self.input_cost_per_1m == 0.0 and self.output_cost_per_1m == 0.0


@dataclass
class RetryConfig:
    """Backoff policy for retryable failures."""

    max_attempts: int = 6
    base_delay_sec: float = 0.5
    max_delay_sec: float = 30.0
    multiplier: float = 2.0
    jitter: float = 0.3                 # fraction of the delay, +/-
    respect_retry_after: bool = True
    retry_statuses: list[int] = field(default_factory=lambda: [408, 409, 425, 429, 500, 502, 503, 504, 529])
    budget_sec: float = 300.0           # wall-clock ceiling for one request


@dataclass
class AgentPolicy:
    """Per-agent routing overrides (ADR-008 §"named profiles")."""

    name: str
    strategy: str = ""
    prefer_providers: list[str] = field(default_factory=list)
    exclude_providers: list[str] = field(default_factory=list)
    prefer_models: list[str] = field(default_factory=list)
    allow_paid: bool | None = None
    max_cost_per_request_usd: float = 0.0
    require_tools: bool = False
    min_context_window: int = 0
    priority: str = ""                  # Priority enum name


@dataclass
class RoutingConfig:
    """Strategy selection and degradation behaviour."""

    strategy: str = "adaptive"
    fallback_chain: list[str] = field(default_factory=list)
    prefer_local: bool = False
    allow_paid: bool = False
    retry: RetryConfig = field(default_factory=RetryConfig)
    max_providers_per_request: int = 6
    max_models_per_provider: int = 3
    graceful_degradation: bool = True
    escalate_context: bool = True       # jump to a larger-context model on overflow
    downgrade_on_exhaustion: bool = True
    queue_enabled: bool = True
    queue_max_depth: int = 512
    global_max_concurrency: int = 32
    dedupe_window_sec: float = 30.0
    agents: dict[str, AgentPolicy] = field(default_factory=dict)


@dataclass
class HealthConfig:
    """Circuit breaker + health tracking thresholds."""

    failure_threshold: int = 5          # consecutive failures before tripping
    failure_rate_threshold: float = 0.5 # or this rolling failure rate
    min_samples: int = 10               # before the rate rule can trip
    open_duration_sec: float = 60.0
    half_open_probes: int = 1
    backoff_multiplier: float = 2.0     # per consecutive trip
    max_open_duration_sec: float = 900.0
    window_sec: float = 300.0           # rolling stats window
    probe_interval_sec: float = 120.0   # background health probe cadence
    probe_enabled: bool = False


@dataclass
class CacheLayerConfig:
    enabled: bool = False
    ttl_sec: float = 300.0
    max_entries: int = 512


@dataclass
class CacheConfig:
    response: CacheLayerConfig = field(default_factory=lambda: CacheLayerConfig(enabled=True))
    prompt: CacheLayerConfig = field(default_factory=lambda: CacheLayerConfig(enabled=True, ttl_sec=900.0))
    embedding: CacheLayerConfig = field(default_factory=lambda: CacheLayerConfig(enabled=True, ttl_sec=86400.0, max_entries=4096))
    tool: CacheLayerConfig = field(default_factory=lambda: CacheLayerConfig(enabled=False, ttl_sec=60.0))
    semantic: CacheLayerConfig = field(default_factory=lambda: CacheLayerConfig(enabled=False, ttl_sec=600.0))
    semantic_threshold: float = 0.94    # cosine similarity to count as a hit


@dataclass
class BudgetConfig:
    """Spend ceilings with alert thresholds."""

    daily_usd: float = 0.0              # 0 = unlimited
    monthly_usd: float = 0.0
    alert_at: list[float] = field(default_factory=lambda: [0.5, 0.8, 0.95])
    enforce: bool = False               # True = raise BudgetExceeded at 100%


@dataclass
class LLMConfig:
    """The fully-resolved routing configuration."""

    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    models: dict[str, ModelConfig] = field(default_factory=dict)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    health: HealthConfig = field(default_factory=HealthConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    source_dir: str = ""

    def enabled_providers(self) -> list[ProviderConfig]:
        return [p for p in self.providers.values() if p.enabled]

    def models_for(self, provider_id: str) -> list[ModelConfig]:
        return [m for m in self.models.values() if m.provider == provider_id]

    def policy_for(self, agent: str | None) -> AgentPolicy | None:
        if not agent:
            return None
        return self.routing.agents.get(agent) or self.routing.agents.get("default")


# ── Loading ──────────────────────────────────────────────────────────────────

def expand_env(value: Any) -> Any:
    """Recursively expand ``${VAR}`` / ``${VAR:-default}`` in loaded YAML."""
    if isinstance(value, str):
        def _sub(match: re.Match[str]) -> str:
            # Shell `:-` semantics: the default applies when the variable is
            # unset OR empty. `os.environ.get(name, default)` only covers
            # unset, so `OLLAMA_BASE=` would yield an empty base URL.
            current = os.environ.get(match.group(1), "")
            return current if current else (match.group(2) or "")
        return _ENV_PATTERN.sub(_sub, value)
    if isinstance(value, dict):
        return {k: expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_env(v) for v in value]
    return value


def config_dir() -> Path:
    """Directory holding the YAML files."""
    override = os.environ.get(CONFIG_DIR_ENV, "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / DEFAULT_CONFIG_DIR


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml
    except ImportError:  # pragma: no cover - PyYAML is a hard requirement
        log.warning("PyYAML missing — ignoring %s", path)
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        log.error("llm config: failed to parse %s: %s", path.name, exc)
        return {}
    if not isinstance(raw, dict):
        log.error("llm config: %s must contain a mapping at the top level", path.name)
        return {}
    return expand_env(raw)


def _fields_of(cls: type) -> set[str]:
    return {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]


_FALSEY = {"0", "false", "no", "off", "none", ""}


def _coerce(cls: type, name: str, value: Any) -> Any:
    """Coerce a YAML value to the field's declared type.

    Env expansion turns ``${LMSTUDIO_ENABLED:-false}`` into the *string*
    ``"false"``, which is truthy in Python. Without this coercion an
    unconfigured provider would be enabled by a config file that plainly says
    it is off.
    """
    field = cls.__dataclass_fields__.get(name)  # type: ignore[attr-defined]
    if field is None or not isinstance(value, str):
        return value
    declared = field.type if isinstance(field.type, str) else getattr(field.type, "__name__", "")
    if declared.startswith("bool"):
        return value.strip().lower() not in _FALSEY
    if declared.startswith("int"):
        try:
            return int(float(value.strip()))
        except ValueError:
            return field.default if field.default is not None else 0
    if declared.startswith("float"):
        try:
            return float(value.strip())
        except ValueError:
            return field.default if field.default is not None else 0.0
    return value


def _build(cls: type, data: dict[str, Any], **overrides: Any) -> Any:
    """Instantiate a config dataclass, ignoring unknown keys with a warning."""
    allowed = _fields_of(cls)
    kwargs = {k: _coerce(cls, k, v) for k, v in data.items() if k in allowed}
    unknown = set(data) - allowed
    if unknown:
        log.warning("llm config: ignoring unknown keys for %s: %s",
                    cls.__name__, ", ".join(sorted(unknown)))
    kwargs.update(overrides)
    return cls(**kwargs)


def _load_providers(raw: dict[str, Any]) -> dict[str, ProviderConfig]:
    entries = raw.get("providers") or {}
    out: dict[str, ProviderConfig] = {}
    if isinstance(entries, list):
        entries = {e.get("id"): e for e in entries if isinstance(e, dict) and e.get("id")}
    for pid, body in (entries or {}).items():
        if not isinstance(body, dict):
            continue
        key_env = body.get("key_env") or []
        if isinstance(key_env, str):
            key_env = [key_env]
        provider = _build(
            ProviderConfig, body, id=str(pid), key_env=[str(k) for k in key_env]
        )
        if provider.enabled and not provider.base_url.strip():
            # `base_url: ${VAR}` with VAR unset yields "". Admitting it gives a
            # provider every request routed to it will fail against, which the
            # env-derived path already refuses.
            log.warning("llm config: provider %r has no base_url — disabling it", pid)
            provider.enabled = False
        out[str(pid)] = provider
    return out


def _load_models(raw: dict[str, Any]) -> dict[str, ModelConfig]:
    entries = raw.get("models") or {}
    out: dict[str, ModelConfig] = {}
    if isinstance(entries, list):
        entries = {e.get("id"): e for e in entries if isinstance(e, dict) and e.get("id")}
    for mid, body in (entries or {}).items():
        if not isinstance(body, dict):
            continue
        out[str(mid)] = _build(ModelConfig, body, id=str(mid))
    return out


def _load_routing(raw: dict[str, Any]) -> RoutingConfig:
    body = dict(raw.get("routing") or raw or {})
    body.pop("providers", None)
    body.pop("models", None)
    body.pop("budget", None)  # read separately into BudgetConfig
    retry = _build(RetryConfig, body.pop("retry", None) or {})
    agents_raw = body.pop("agents", None) or {}
    agents: dict[str, AgentPolicy] = {}
    for name, policy in agents_raw.items():
        if isinstance(policy, dict):
            agents[str(name)] = _build(AgentPolicy, policy, name=str(name))
    return _build(RoutingConfig, body, retry=retry, agents=agents)


def _load_cache(raw: dict[str, Any]) -> CacheConfig:
    body = dict(raw.get("cache") or raw or {})
    layers: dict[str, Any] = {}
    for layer in ("response", "prompt", "embedding", "tool", "semantic"):
        if isinstance(body.get(layer), dict):
            layers[layer] = _build(CacheLayerConfig, body.pop(layer))
        else:
            body.pop(layer, None)
    threshold = body.get("semantic_threshold")
    if threshold is not None:
        try:
            layers["semantic_threshold"] = float(threshold)
        except (TypeError, ValueError):
            log.warning(
                "llm config: semantic_threshold=%r is not a number — using the default",
                threshold,
            )
    defaults = CacheConfig()
    return CacheConfig(
        response=layers.get("response", defaults.response),
        prompt=layers.get("prompt", defaults.prompt),
        embedding=layers.get("embedding", defaults.embedding),
        tool=layers.get("tool", defaults.tool),
        semantic=layers.get("semantic", defaults.semantic),
        semantic_threshold=layers.get("semantic_threshold", defaults.semantic_threshold),
    )


def load_config(directory: str | Path | None = None) -> LLMConfig:
    """Read every YAML file and merge it over the environment-derived defaults."""
    base = Path(directory) if directory else config_dir()
    raw: dict[str, dict[str, Any]] = {
        name: _read_yaml(base / f"{name}.yaml") for name in _CONFIG_FILES
    }

    providers = _load_providers(raw["providers"])
    models = _load_models(raw["models"])
    routing = _load_routing(raw["routing"])
    health = _build(HealthConfig, raw["health"].get("health") or raw["health"] or {})
    cache = _load_cache(raw["cache"])
    # Budgets may sit at the top of routing.yaml or nested under `routing:`.
    # Both spellings are natural, so both are accepted.
    routing_section = raw["routing"].get("routing")
    budget_body = (
        (routing_section.get("budget") if isinstance(routing_section, dict) else None)
        or raw["routing"].get("budget")
        or raw["cache"].get("budget")
        or {}
    )
    budget = _build(BudgetConfig, budget_body if isinstance(budget_body, dict) else {})

    _apply_key_env(providers, raw["keys"])
    _merge_env_defaults(providers, models)
    _apply_env_overrides(routing, budget)

    cfg = LLMConfig(
        providers=providers,
        models=models,
        routing=routing,
        health=health,
        cache=cache,
        budget=budget,
        source_dir=str(base),
    )
    log.info(
        "llm config loaded: %d provider(s), %d model(s), strategy=%s, dir=%s",
        len(providers), len(models), routing.strategy, base,
    )
    return cfg


def _apply_key_env(providers: dict[str, ProviderConfig], raw: dict[str, Any]) -> None:
    """Merge ``keys.yaml`` env-var NAMES into the provider configs.

    Values are never read here — only the variable names. Resolution happens in
    ``packages/llm/keys.py`` at call time so a rotated key takes effect without
    a reload, and so no key material is ever held by a config object.
    """
    entries = raw.get("keys") or raw or {}
    for pid, body in entries.items():
        if pid in {"providers", "models", "routing"}:
            continue
        names: list[str] = []
        if isinstance(body, str):
            names = [body]
        elif isinstance(body, list):
            names = [str(n) for n in body]
        elif isinstance(body, dict):
            raw_names = body.get("env") or body.get("key_env") or []
            names = [raw_names] if isinstance(raw_names, str) else [str(n) for n in raw_names]
        if not names:
            continue
        provider = providers.get(str(pid))
        if provider is None:
            log.warning("keys.yaml: no provider named %r — ignoring its keys", pid)
            continue
        merged = list(dict.fromkeys([*provider.key_env, *names]))
        provider.key_env = merged

    # Auto-detect NAME_2 … NAME_10 / NAME_S / NAME_POOL for every provider,
    # including those declared in providers.yaml. Without this the numbered
    # pool convention worked only for env-derived providers — and since every
    # shipped provider is declared in YAML, setting CEREBRAS_API_KEY_4 added
    # nothing to the rotation and logged no warning. Key rotation is the
    # headline 429 defence; it must not depend on remembering to list each
    # variable in keys.yaml.
    for provider in providers.values():
        expanded = list(provider.key_env)
        for name in list(provider.key_env):
            expanded.extend(_env_key_names(name))
        provider.key_env = list(dict.fromkeys(expanded))


# ── Environment-derived defaults (zero-config path) ──────────────────────────

# provider id -> (kind, base url env, default base url, key env prefix, tier,
#                 priority, default model env, default model)
_ENV_PROVIDERS: tuple[tuple[str, str, str, str, str, str, int, str, str], ...] = (
    ("ollama",    "ollama",    "OLLAMA_BASE",        "http://localhost:11434", "",                 "local",   10, "OLLAMA_DEFAULT_MODEL",   "qwen3-coder:30b"),
    ("lmstudio",  "openai",    "LMSTUDIO_BASE_URL",  "",                       "LMSTUDIO_API_KEY", "local",   12, "LMSTUDIO_DEFAULT_MODEL", ""),
    ("vllm",      "openai",    "VLLM_BASE_URL",      "",                       "VLLM_API_KEY",     "local",   14, "VLLM_DEFAULT_MODEL",     ""),
    ("localai",   "openai",    "LOCALAI_BASE_URL",   "",                       "LOCALAI_API_KEY",  "local",   16, "LOCALAI_DEFAULT_MODEL",  ""),
    ("litellm",   "openai",    "LITELLM_BASE_URL",   "",                       "LITELLM_API_KEY",  "local",   18, "LITELLM_DEFAULT_MODEL",  ""),
    ("cerebras",  "openai",    "CEREBRAS_BASE_URL",  "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", "free", 20, "CEREBRAS_DEFAULT_MODEL", "qwen-3-coder-480b"),
    ("groq",      "openai",    "GROQ_BASE_URL",      "https://api.groq.com/openai/v1", "GROQ_API_KEY", "free", 22, "GROQ_DEFAULT_MODEL",   "llama-3.3-70b-versatile"),
    ("nvidia",    "openai",    "NVIDIA_BASE_URL",    "https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY", "free", 24, "NVIDIA_DEFAULT_MODEL", "nvidia/nemotron-3-ultra-550b-a55b"),
    ("google",    "gemini",    "GEMINI_BASE_URL",    "https://generativelanguage.googleapis.com/v1beta", "GEMINI_API_KEY", "free", 26, "GEMINI_DEFAULT_MODEL", "gemini-2.5-flash"),
    ("openrouter","openai",    "OPENROUTER_BASE_URL","https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "cheap", 40, "OPENROUTER_DEFAULT_MODEL", ""),
    ("together",  "openai",    "TOGETHER_BASE_URL",  "https://api.together.xyz/v1", "TOGETHER_API_KEY", "cheap", 42, "TOGETHER_DEFAULT_MODEL", ""),
    ("fireworks", "openai",    "FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1", "FIREWORKS_API_KEY", "cheap", 44, "FIREWORKS_DEFAULT_MODEL", ""),
    ("deepinfra", "openai",    "DEEPINFRA_BASE_URL", "https://api.deepinfra.com/v1/openai", "DEEPINFRA_API_KEY", "cheap", 46, "DEEPINFRA_DEFAULT_MODEL", ""),
    ("mistral",   "openai",    "MISTRAL_BASE_URL",   "https://api.mistral.ai/v1", "MISTRAL_API_KEY", "cheap", 48, "MISTRAL_DEFAULT_MODEL", ""),
    ("openai",    "openai",    "OPENAI_BASE_URL",    "https://api.openai.com/v1", "OPENAI_API_KEY", "premium", 60, "OPENAI_DEFAULT_MODEL", "gpt-4o-mini"),
    ("azure",     "openai",    "AZURE_OPENAI_BASE_URL", "",                    "AZURE_OPENAI_API_KEY", "premium", 62, "AZURE_OPENAI_DEPLOYMENT", ""),
    ("anthropic", "anthropic", "ANTHROPIC_BASE_URL", "https://api.anthropic.com", "ANTHROPIC_API_KEY", "premium", 64, "ANTHROPIC_DEFAULT_MODEL", "claude-sonnet-5"),
)


def _merge_env_defaults(
    providers: dict[str, ProviderConfig], models: dict[str, ModelConfig]
) -> None:
    """Add providers that are configured in the environment but absent from YAML.

    This is what makes ``config/llm/`` optional: a deploy that only sets
    ``NVIDIA_API_KEY`` still gets a working NVIDIA provider. YAML always wins —
    an entry already present is left untouched.
    """
    for (pid, kind, base_env, base_default, key_prefix, tier, priority,
         model_env, model_default) in _ENV_PROVIDERS:
        if pid in providers:
            continue
        configured_base = os.environ.get(base_env, "").strip()
        base_url = configured_base or base_default
        keys = _env_key_names(key_prefix) if key_prefix else []
        requires_key = bool(key_prefix)
        if requires_key and not keys:
            continue
        if not requires_key and not configured_base:
            # A keyless provider whose base URL was never set. Conjuring one
            # from a hardcoded default would add a phantom provider pointing at
            # localhost on every deploy, which then fails every request routed
            # to it. Operator intent is required: set the base URL env var, or
            # declare the provider in providers.yaml (where the shipped config
            # does exactly that, with the localhost default spelled out).
            continue
        if not base_url:
            continue
        default_model = os.environ.get(model_env, "").strip() or model_default
        providers[pid] = ProviderConfig(
            id=pid,
            kind=kind,
            base_url=base_url,
            key_env=keys,
            default_model=default_model,
            models=[default_model] if default_model else [],
            tier=tier,
            priority=priority,
            requires_key=requires_key,
            auth_style="x-api-key" if kind == "anthropic" else ("none" if not requires_key else "bearer"),
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "") if pid == "azure" else "",
            deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "") if pid == "azure" else "",
            notes="auto-configured from environment",
        )
    _seed_model_defaults(providers, models)


def _env_key_names(prefix: str) -> list[str]:
    """Return the env var NAMES that hold keys for ``prefix``.

    Matches ``PREFIX``, ``PREFIX_2`` … ``PREFIX_10``, and ``PREFIX_S`` for the
    numbered-pool convention already used by ``packages/ai/key_pool.py``.
    """
    names: list[str] = []
    if os.environ.get(prefix, "").strip():
        names.append(prefix)
    for suffix in [*(str(i) for i in range(2, 11)), "S", "POOL"]:
        candidate = f"{prefix}_{suffix}"
        if os.environ.get(candidate, "").strip():
            names.append(candidate)
    return names


def _seed_model_defaults(
    providers: dict[str, ProviderConfig], models: dict[str, ModelConfig]
) -> None:
    """Give every provider's default model a registry entry if YAML omitted it."""
    for provider in providers.values():
        for model_id in provider.models or ([provider.default_model] if provider.default_model else []):
            if not model_id or model_id in models:
                continue
            models[model_id] = ModelConfig(
                id=model_id,
                provider=provider.id,
                display_name=model_id,
                context_window=32768,
                priority=provider.priority,
                supports_streaming=True,
            )


def _apply_env_overrides(routing: RoutingConfig, budget: BudgetConfig) -> None:
    """Let a handful of env vars override routing knobs without editing YAML."""
    strategy = os.environ.get("LLM_ROUTER_STRATEGY", "").strip().lower()
    if strategy:
        routing.strategy = strategy
    if os.environ.get("ALLOW_PAID_BRAIN", "").strip().lower() in {"1", "true", "yes", "on"}:
        routing.allow_paid = True
    prefer_local = os.environ.get("LLM_ROUTER_PREFER_LOCAL", "").strip().lower()
    if prefer_local in {"1", "true", "yes", "on"}:
        routing.prefer_local = True
    for env_name, attr, cast in (
        ("LLM_ROUTER_MAX_ATTEMPTS", "max_attempts", int),
        ("LLM_ROUTER_BUDGET_SEC", "budget_sec", float),
    ):
        raw = os.environ.get(env_name, "").strip()
        if raw:
            try:
                setattr(routing.retry, attr, cast(raw))
            except ValueError:
                log.warning("%s=%r is not a valid %s — ignoring", env_name, raw, cast.__name__)
    for env_name, attr in (
        ("LLM_BUDGET_DAILY_USD", "daily_usd"),
        ("LLM_BUDGET_MONTHLY_USD", "monthly_usd"),
    ):
        raw = os.environ.get(env_name, "").strip()
        if raw:
            try:
                setattr(budget, attr, float(raw))
            except ValueError:
                log.warning("%s=%r is not a number — ignoring", env_name, raw)


# ── Process-wide singleton ───────────────────────────────────────────────────

_config: LLMConfig | None = None
_lock = threading.Lock()


def get_config() -> LLMConfig:
    """Return the process-wide configuration, loading it on first use."""
    global _config
    if _config is None:
        with _lock:
            if _config is None:
                _config = load_config()
    return _config


def reload_config(directory: str | Path | None = None) -> LLMConfig:
    """Re-read configuration from disk. Used by the admin API and by tests."""
    global _config
    with _lock:
        _config = load_config(directory)
    return _config


def reset() -> None:
    """Drop the cached config (test hook)."""
    global _config
    with _lock:
        _config = None


def gateway_enabled() -> bool:
    """Whether the OpenAI-compatible passthrough routes accept traffic.

    Off by default: exposing the platform's provider keys to other
    applications must be a deliberate act. Lives here rather than in
    ``gateway.py`` so every environment read for this package stays in the
    config module.
    """
    return os.environ.get("LLM_GATEWAY_ENABLED", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def router_enabled() -> bool:
    """Whether callers should route through ``LLMRouter`` (ADR-008 §8).

    Defaults to ``False`` so an existing deployment keeps the legacy path until
    the operator opts in. Set ``LLM_ROUTER_ENABLED=true`` to switch over.
    """
    return os.environ.get("LLM_ROUTER_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}

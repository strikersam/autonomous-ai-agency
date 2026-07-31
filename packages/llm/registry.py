"""packages/llm/registry.py — the model registry.

One queryable index of every model the platform can reach, built from
``config/llm/models.yaml`` plus the provider defaults derived from the
environment. Capability filtering happens here so the router never proposes a
model that cannot do what the request needs — a tool-calling request is never
sent to a model without tool support, and a 200k-token prompt is never sent to
an 8k-context model.

The registry deliberately mirrors, rather than replaces,
``packages/ai/registry.py``: the legacy registry keeps serving legacy callers
untouched (Golden Rule), and this one seeds itself from it so no model
disappears during migration.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import replace

from packages.llm.config import LLMConfig, ModelConfig, get_config

log = logging.getLogger("llm.registry")


class ModelRegistry:
    """Capability-aware lookup over the configured models."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self._config = config or get_config()
        self._models: dict[str, ModelConfig] = dict(self._config.models)
        self._aliases: dict[str, str] = {}
        self._lock = threading.Lock()
        self._index_aliases()
        self._seed_from_legacy()

    def _index_aliases(self) -> None:
        for model in self._models.values():
            for alias in model.aliases:
                self._aliases[alias.strip().lower()] = model.id

    def _seed_from_legacy(self) -> None:
        """Import any model known to ``packages/ai/registry.py`` but not to YAML.

        Import failures are non-fatal: the legacy registry is a convenience
        source, not a dependency.
        """
        try:
            from packages.ai import registry as legacy
        except Exception as exc:  # pragma: no cover - defensive
            log.debug("llm.registry: legacy registry unavailable (%s)", exc)
            return
        for info in legacy.all_models():
            if info.model_id in self._models:
                continue
            self._models[info.model_id] = ModelConfig(
                id=info.model_id,
                provider=info.provider_id,
                display_name=info.display_name,
                context_window=info.context_window,
                max_output_tokens=info.max_output_tokens,
                supports_tools=info.supports_tools,
                supports_function_calling=info.supports_tools,
                supports_images=info.supports_vision,
                supports_streaming=info.supports_streaming,
                supports_embeddings=info.supports_embeddings,
                input_cost_per_1m=info.input_cost_per_1m,
                output_cost_per_1m=info.output_cost_per_1m,
                priority=info.priority,
                speed_tier=info.speed_tier,
            )

    # ── Lookup ───────────────────────────────────────────────────────────────

    def get(self, model_id: str) -> ModelConfig | None:
        if not model_id:
            return None
        with self._lock:
            direct = self._models.get(model_id)
            if direct is not None:
                return direct
            aliased = self._aliases.get(model_id.strip().lower())
            return self._models.get(aliased) if aliased else None

    def all(self) -> list[ModelConfig]:
        with self._lock:
            return list(self._models.values())

    def for_provider(self, provider_id: str) -> list[ModelConfig]:
        with self._lock:
            return [m for m in self._models.values() if m.provider == provider_id]

    def register(self, model: ModelConfig) -> None:
        """Add or replace a model (used by runtime discovery)."""
        with self._lock:
            self._models[model.id] = model
            for alias in model.aliases:
                self._aliases[alias.strip().lower()] = model.id

    def register_discovered(self, provider_id: str, model_ids: list[str]) -> int:
        """Record models found by a provider's ``/models`` endpoint.

        Discovered models inherit conservative defaults — no tool support, a
        modest context window — so capability filtering never over-promises on
        a model we know nothing about. YAML entries always win.
        """
        added = 0
        with self._lock:
            for model_id in model_ids:
                if not model_id or model_id in self._models:
                    continue
                self._models[model_id] = ModelConfig(
                    id=model_id,
                    provider=provider_id,
                    display_name=model_id,
                    context_window=8192,
                    priority=200,
                )
                added += 1
        if added:
            log.info("llm.registry: discovered %d new model(s) on %s", added, provider_id)
        return added

    # ── Capability filtering ────────────────────────────────────────────────

    def candidates(
        self,
        *,
        provider_id: str | None = None,
        require_tools: bool = False,
        require_json: bool = False,
        require_images: bool = False,
        require_streaming: bool = False,
        require_embeddings: bool = False,
        require_chat: bool = True,
        min_context: int = 0,
        allow_paid: bool = True,
        max_cost_per_1m: float = 0.0,
    ) -> list[ModelConfig]:
        """Models satisfying every stated requirement, best first.

        Ordering is by ``priority`` then by cost, so the caller gets a list it
        can walk in order without re-sorting.
        """
        with self._lock:
            models = list(self._models.values())

        def keeps(model: ModelConfig) -> bool:
            if provider_id and model.provider != provider_id:
                return False
            if require_tools and not (model.supports_tools or model.supports_function_calling):
                return False
            if require_json and not model.supports_json:
                return False
            if require_images and not model.supports_images:
                return False
            if require_streaming and not model.supports_streaming:
                return False
            if require_embeddings and not model.supports_embeddings:
                return False
            if require_chat and not model.supports_chat:
                return False
            if min_context and model.context_window < min_context:
                return False
            if not allow_paid and not model.is_free:
                return False
            # Combined, matching the sort key below: output pricing is
            # normally the larger half, so an input-only cap admits models
            # far above the intended ceiling.
            if max_cost_per_1m and (
                model.input_cost_per_1m + model.output_cost_per_1m
            ) > max_cost_per_1m:
                return False
            return True

        return sorted(
            (m for m in models if keeps(m)),
            key=lambda m: (m.priority, m.input_cost_per_1m + m.output_cost_per_1m),
        )

    def largest_context(
        self, *, allow_paid: bool = True, provider_id: str | None = None,
        require_tools: bool = False,
    ) -> ModelConfig | None:
        """The biggest-context model available — the context-overflow escape hatch."""
        pool = self.candidates(
            provider_id=provider_id, allow_paid=allow_paid, require_tools=require_tools
        )
        if not pool:
            return None
        return max(pool, key=lambda m: m.context_window)

    def cheapest(self, *, min_context: int = 0, require_tools: bool = False) -> ModelConfig | None:
        """The lowest-cost model that still meets the requirements."""
        pool = self.candidates(min_context=min_context, require_tools=require_tools)
        if not pool:
            return None
        return min(pool, key=lambda m: (m.input_cost_per_1m + m.output_cost_per_1m, m.priority))

    def fastest(self, *, min_context: int = 0, allow_paid: bool = True) -> ModelConfig | None:
        """The fastest model by declared speed tier."""
        order = {"fast": 0, "medium": 1, "slow": 2}
        pool = self.candidates(min_context=min_context, allow_paid=allow_paid)
        if not pool:
            return None
        return min(pool, key=lambda m: (order.get(m.speed_tier, 1), m.priority))

    def snapshot(self) -> list[dict[str, object]]:
        """Serialisable view for the dashboard and the ``/v1/models`` route."""
        return [
            {
                "id": m.id,
                "provider": m.provider,
                "display_name": m.display_name or m.id,
                "context_window": m.context_window,
                "max_output_tokens": m.max_output_tokens,
                "supports_tools": m.supports_tools or m.supports_function_calling,
                "supports_json": m.supports_json,
                "supports_images": m.supports_images,
                "supports_reasoning": m.supports_reasoning,
                "supports_streaming": m.supports_streaming,
                "supports_embeddings": m.supports_embeddings,
                "supports_chat": m.supports_chat,
                "input_cost_per_1m": m.input_cost_per_1m,
                "output_cost_per_1m": m.output_cost_per_1m,
                "free": m.is_free,
                "priority": m.priority,
                "speed_tier": m.speed_tier,
            }
            for m in sorted(self.all(), key=lambda m: (m.priority, m.id))
        ]

    def with_provider(self, model: ModelConfig, provider_id: str) -> ModelConfig:
        """A copy of ``model`` bound to a different provider (cross-provider reuse)."""
        return replace(model, provider=provider_id)


_registry: ModelRegistry | None = None
_lock = threading.Lock()


def get_registry() -> ModelRegistry:
    """The process-wide model registry."""
    global _registry
    if _registry is None:
        with _lock:
            if _registry is None:
                _registry = ModelRegistry()
    return _registry


def reset() -> None:
    """Test hook — rebuild the registry on next access."""
    global _registry
    with _lock:
        _registry = None

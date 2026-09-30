"""packages/gateway/usage_metrics.py — per-request usage metrics for the proxy path.

Feeds the shared Prometheus registry (:mod:`packages.llm.metrics`) and the
in-process cost tracker (:mod:`packages.ai.cost_tracker`) with one record per
proxied chat request: provider, model, prompt/completion tokens, latency, cost
and outcome. Off unless ``GATEWAY_USAGE_METRICS_ENABLED`` is set.

The ``agent`` label carries the consumer. Consumers are opaque key ids or key
digests, and the label set is capped at ``MAX_CONSUMER_LABELS`` distinct values;
any later consumer is folded into ``other`` so a key-per-request client cannot
inflate the series count.
"""

from __future__ import annotations

import logging
import threading

from packages.ai.cost_tracker import cost_for_tokens, record_usage
from packages.gateway import config
from packages.llm.metrics import get_metrics, sanitize_label

log = logging.getLogger("qwen-proxy")

MAX_CONSUMER_LABELS = 50
_OVERFLOW_LABEL = "other"

_lock = threading.Lock()
_seen_consumers: set[str] = set()


def reset() -> None:
    """Forget the consumer label set (test hook)."""
    with _lock:
        _seen_consumers.clear()


def consumer_label(consumer: str) -> str:
    """A bounded label for *consumer*: itself while under the cap, else ``other``."""
    label = sanitize_label(consumer, limit=24)
    with _lock:
        if label in _seen_consumers:
            return label
        if len(_seen_consumers) < MAX_CONSUMER_LABELS:
            _seen_consumers.add(label)
            return label
    return _OVERFLOW_LABEL


def provider_for(model: str) -> str:
    """Best-effort provider name: the ``vendor/`` prefix of the model, else ``ollama``."""
    if "/" in model:
        return sanitize_label(model.split("/", 1)[0], limit=32) or "ollama"
    return "ollama"


def record_call(
    *,
    consumer: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_sec: float,
    outcome: str,
) -> None:
    """Record one finished proxy request. Never raises."""
    if not config.usage_metrics_enabled():
        return
    try:
        provider = provider_for(model)
        model_label = sanitize_label(model)
        cost = cost_for_tokens(model, prompt_tokens, completion_tokens)
        metrics = get_metrics()
        metrics.record_request(
            provider=provider,
            model=model_label,
            outcome=outcome,
            latency_sec=latency_sec,
            agent=consumer_label(consumer),
        )
        metrics.record_tokens(
            provider=provider,
            model=model_label,
            prompt=prompt_tokens,
            completion=completion_tokens,
            cost_usd=cost,
        )
        record_usage(
            model,
            provider_id=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            tag="gateway",
        )
    except Exception as exc:  # metrics must never fail a request
        log.warning("Gateway usage metrics error: %s", exc)


def record_cache(hit: bool) -> None:
    """Count a proxy-cache lookup on the shared ``llm_cache_events_total`` counter."""
    if config.usage_metrics_enabled():
        get_metrics().record_cache(layer="gateway_proxy", hit=hit)

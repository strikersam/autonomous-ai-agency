from __future__ import annotations

"""Per-Model Cost Attribution (G1 roadmap item).

Provides per-model cost breakdown from Langfuse traces and cost estimation
tables, with per-phase token count + latency attribution.

Components:
- CostTable: per-model pricing lookup (token costs, local vs cloud)
- CostAttributor: aggregates usage by model/provider/phase
- CostReport: structured cost breakdown for dashboard rendering

Usage::

    from services.cost_attribution import get_cost_attributor

    attr = get_cost_attributor()
    attr.record_usage(model="qwen3-coder:30b", prompt_tokens=500, completion_tokens=200, phase="execute")
    report = attr.generate_report()
    # → per-model cost breakdown
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("qwen-proxy")


# ── Cost table ────────────────────────────────────────────────────────────────

LOCAL_COST_PER_1M_TOKEN = 2.0    # ~$2 per 1M tokens local
CLOUD_COST_PER_1M_TOKEN = 15.0   # ~$15 per 1M tokens cloud


# Per-model estimated cost in USD per 1M tokens (cloud prices approximate)
_MODEL_COSTS: dict[str, float] = {
    # Local Ollama models (electricity + hardware amortization)
    "qwen3-coder:30b": 2.0,
    "qwen3-coder:7b": 1.0,
    "qwen3-coder:235b": 4.0,
    "deepseek-r1:32b": 3.0,
    "deepseek-r1:671b": 5.0,
    "deepseek-r1:32b-16k": 2.5,
    "gemma4:27b": 2.0,
    "gemma4:9b": 1.0,
    "gemma4:2b": 0.5,
    "llama4-maverick:17b": 2.0,
    "llama4-scout:17b": 1.5,
    "deepseek-v3:685b": 5.0,
    "tinyllama:latest": 0.3,
    # Cloud NVIDIA NIM models (free tier = $0, else approximate)
    "nvidia/nemotron-3-super-120b-a12b": 0.0,
    "nvidia/llama-3.3-nemotron-super-49b-v1": 0.0,
    "qwen/qwen2.5-coder-32b-instruct": 0.0,
    "meta/llama-3.3-70b-instruct": 0.0,
    "meta/llama-3.1-8b-instruct": 0.0,
    "deepseek-ai/deepseek-r1": 0.0,
    "deepseek-ai/deepseek-v4-pro": 0.0,
    # Cloud Anthropic models
    "claude-opus-4-8": 75.0,
    "claude-sonnet-4-6": 15.0,
    "claude-haiku-4-5-20251001": 3.0,
}


@dataclass
class UsageRecord:
    """A single LLM call usage record."""

    model: str
    phase: str           # plan / execute / verify / chat
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int = 0
    cost_usd: float = 0.0
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class CostReport:
    """Structured cost report for admin dashboard rendering."""

    total_cost_usd: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_calls: int
    per_model: list[dict[str, Any]]   # Breakdown by model
    per_phase: list[dict[str, Any]]   # Breakdown by phase
    per_provider: list[dict[str, Any]] # Local vs cloud
    estimated_savings_usd: float      # Savings vs all-cloud

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_cost_usd": round(self.total_cost_usd, 4),
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_calls": self.total_calls,
            "per_model": self.per_model,
            "per_phase": self.per_phase,
            "per_provider": self.per_provider,
            "estimated_savings_usd": round(self.estimated_savings_usd, 4),
        }


class CostAttributor:
    """Tracks and attributes LLM costs per model, phase, and provider.

    Usage::

        attr = CostAttributor()
        attr.record_usage(
            model="qwen3-coder:30b",
            prompt_tokens=1200,
            completion_tokens=800,
            phase="execute",
        )
        report = attr.generate_report()
    """

    def __init__(self) -> None:
        self._records: list[UsageRecord] = []
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_calls = 0

    def record_usage(
        self,
        *,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        phase: str = "chat",
        latency_ms: int = 0,
    ) -> None:
        """Record a single LLM call's usage."""
        cost = self.estimate_cost(model, prompt_tokens + completion_tokens)

        record = UsageRecord(
            model=model,
            phase=phase,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            cost_usd=cost,
        )
        self._records.append(record)
        self._total_prompt_tokens += prompt_tokens
        self._total_completion_tokens += completion_tokens
        self._total_calls += 1

    def record_batch(
        self,
        entries: list[dict[str, Any]],
    ) -> int:
        """Batch record multiple usage entries. Returns number recorded."""
        count = 0
        for entry in entries:
            self.record_usage(
                model=entry.get("model", ""),
                prompt_tokens=entry.get("prompt_tokens", 0),
                completion_tokens=entry.get("completion_tokens", 0),
                phase=entry.get("phase", "chat"),
                latency_ms=entry.get("latency_ms", 0),
            )
            count += 1
        return count

    def estimate_cost(self, model: str, total_tokens: int) -> float:
        """Estimate USD cost for a given model and token count.

        Looks up the per-model cost table; falls back to local cost
        for unknown models.
        """
        cost_per_1m = _MODEL_COSTS.get(model, LOCAL_COST_PER_1M_TOKEN)
        return (total_tokens / 1_000_000) * cost_per_1m

    def generate_report(self) -> CostReport:
        """Generate a full per-model cost attribution report."""
        total_cost = sum(r.cost_usd for r in self._records)

        # Per-model breakdown
        model_usage: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.model not in model_usage:
                model_usage[r.model] = {"model": r.model, "calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}
            model_usage[r.model]["calls"] += 1
            model_usage[r.model]["prompt_tokens"] += r.prompt_tokens
            model_usage[r.model]["completion_tokens"] += r.completion_tokens
            model_usage[r.model]["cost_usd"] += r.cost_usd

        per_model = sorted(model_usage.values(), key=lambda x: x["cost_usd"], reverse=True)

        # Per-phase breakdown
        phase_usage: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.phase not in phase_usage:
                phase_usage[r.phase] = {"phase": r.phase, "calls": 0, "tokens": 0, "cost_usd": 0.0}
            phase_usage[r.phase]["calls"] += 1
            phase_usage[r.phase]["tokens"] += r.prompt_tokens + r.completion_tokens
            phase_usage[r.phase]["cost_usd"] += r.cost_usd

        per_phase = sorted(phase_usage.values(), key=lambda x: x["cost_usd"], reverse=True)

        # Per-provider breakdown (local vs cloud)
        local_cost = sum(r.cost_usd for r in self._records if "/" not in r.model)
        cloud_cost = sum(r.cost_usd for r in self._records if "/" in r.model)
        local_tokens = sum(r.prompt_tokens + r.completion_tokens for r in self._records if "/" not in r.model)
        cloud_tokens = sum(r.prompt_tokens + r.completion_tokens for r in self._records if "/" in r.model)

        per_provider = [
            {
                "provider": "local",
                "calls": sum(1 for r in self._records if "/" not in r.model),
                "tokens": local_tokens,
                "cost_usd": round(local_cost, 4),
            },
            {
                "provider": "cloud",
                "calls": sum(1 for r in self._records if "/" in r.model),
                "tokens": cloud_tokens,
                "cost_usd": round(cloud_cost, 4),
            },
        ]

        # Estimated savings vs all-cloud
        all_cloud_cost = sum(
            (r.prompt_tokens + r.completion_tokens) / 1_000_000 * CLOUD_COST_PER_1M_TOKEN
            for r in self._records
        )
        estimated_savings = max(0, all_cloud_cost - total_cost)

        return CostReport(
            total_cost_usd=total_cost,
            total_prompt_tokens=self._total_prompt_tokens,
            total_completion_tokens=self._total_completion_tokens,
            total_calls=self._total_calls,
            per_model=per_model,
            per_phase=per_phase,
            per_provider=per_provider,
            estimated_savings_usd=estimated_savings,
        )

    def recent_usage(self, window_seconds: float = 3600) -> list[dict[str, Any]]:
        """Return usage records from the last N seconds."""
        cutoff = time.monotonic() - window_seconds
        return [
            {
                "model": r.model,
                "phase": r.phase,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "latency_ms": r.latency_ms,
                "cost_usd": round(r.cost_usd, 6),
            }
            for r in self._records
            if r.timestamp >= cutoff
        ]

    def clear(self) -> None:
        """Clear all usage records."""
        self._records.clear()
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_calls = 0


# ── Module-level singleton ─────────────────────────────────────────────────────

_attributor: CostAttributor | None = None


def get_cost_attributor() -> CostAttributor:
    """Return the module-level CostAttributor singleton."""
    global _attributor
    if _attributor is None:
        _attributor = CostAttributor()
    return _attributor

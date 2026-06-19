"""Shared free-brain policy helpers (issue #656).

Single source of truth for "is the agent allowed to use a paid brain?" and
"what free NVIDIA brain should we route to instead?". Imported by both
``services/workflow_orchestrator.py`` (orchestrator brain resolver) and
``agent/loop.py`` (the ``internal_agent`` runtime) so neither can silently call
paid Anthropic when the operator has not opted in.

Design invariants:
  - Free-first by default. ``ALLOW_PAID_BRAIN`` must be explicitly truthy for any
    paid (Anthropic / Bedrock) call path to run.
  - No heavy imports here (only ``os``) so this module is safe to import from
    anywhere, including risky low-level modules, without circular-import risk.
"""
from __future__ import annotations

import os

# Default free NVIDIA NIM brain. The operator points this at the most capable
# free cloud model via NVIDIA_DEFAULT_MODEL; this fallback is the documented
# default (see .env.example / render.yaml).
#
# We default to the Nemotron-3 *super* 120B-a12b MoE rather than the 550B-a55b
# "ultra": it activates only ~12B params/token (vs ~55B for the ultra), so it is
# several times faster per call while staying a same-generation Nemotron-3
# reasoning model — the right balance for the plan→execute→verify→judge loop on a
# free, no-rate-limit NIM endpoint. (It briefly 404'd around issue #656, which is
# why the ultra was pinned then; the endpoint is live again.)
DEFAULT_FREE_NVIDIA_MODEL = "nvidia/nemotron-3-super-120b-a12b"

_TRUTHY = {"1", "true", "yes", "on"}


def allow_paid_brain() -> bool:
    """True only when the operator explicitly opted into a paid (Anthropic) brain.

    Default ``False``: the free-brain policy (Autonomy Charter / issue #656)
    means no runtime silently calls a paid API. Set ``ALLOW_PAID_BRAIN=true`` to
    permit paid Anthropic / Bedrock as a last resort.
    """
    return os.environ.get("ALLOW_PAID_BRAIN", "").strip().lower() in _TRUTHY


def is_anthropic_model(model: str | None) -> bool:
    """True when *model* names a paid Anthropic/Bedrock-Claude model.

    Covers native Anthropic ids (``claude-*``), Bedrock ids
    (``us.anthropic.claude-*``), and the generic ``opus`` alias the agent uses.
    """
    m = (model or "").strip().lower()
    if not m:
        return False
    return (
        m.startswith("claude")
        or m.startswith("us.anthropic")
        or m.startswith("anthropic")
        or "anthropic." in m
        or "opus" in m
    )


def resolve_free_nvidia_brain() -> tuple[str, dict, str] | None:
    """Resolve the free NVIDIA NIM brain from env, or ``None`` if unconfigured.

    Returns ``(openai_compatible_base_url, auth_headers, model)`` where the base
    URL already ends in ``/v1`` so the OpenAI-compatible client can append
    ``/chat/completions`` directly. Returns ``None`` when ``NVIDIA_API_KEY`` is
    not set — callers must then refuse to fall back to paid Anthropic.
    """
    key = (os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey") or "").strip()
    if not key:
        return None
    base = (os.environ.get("NVIDIA_BASE_URL") or "").strip().rstrip("/") or "https://integrate.api.nvidia.com"
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    model = (os.environ.get("NVIDIA_DEFAULT_MODEL") or "").strip() or DEFAULT_FREE_NVIDIA_MODEL
    return base, {"Authorization": f"Bearer {key}"}, model

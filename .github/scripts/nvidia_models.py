"""Shared NVIDIA NIM model source for the autonomous agent scripts.

This module used to be a hand-maintained list, "live-verified 2026-06-14". By
2026-08-27 two of its three ids answered ``410 Gone`` — end-of-life on
2026-05-12, 2026-06-11 and 2026-08-26 — and the agency had stopped producing
work four separate times for the same reason. Each fix was another hand-edit
that would rot on NVIDIA's next retirement.

NVIDIA's own documentation says to find the model id by querying the models
endpoint, so that is what happens here: the catalogue is read from the provider
and ranked, and the static list below is only the floor for when discovery
cannot run (no key, no network, an unreadable response).

Ranking prefers Nemotron, then other instruct models, and drops families that
cannot drive a tool-calling loop at all (embedding, rerank, OCR, guard/safety).
Nothing in this file asserts that a particular model is live — that was the
claim that kept going stale.
"""
from __future__ import annotations

import json
import os
import urllib.request

__all__ = [
    "NVIDIA_CANDIDATE_MODELS",
    "NVIDIA_MODEL_IDS",
    "CANDIDATE_MODELS",
    "rank_models",
    "live_model_ids",
    "resolve_model_ids",
    "resolve_candidates",
    "reset_cache",
]

NVIDIA_BASE_URL = (
    os.environ.get("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com"
).rstrip("/")

# Substrings marking a model that cannot serve a chat/tool-calling loop. Cheaper
# and more durable than an allow-list, which would need editing for every new
# family NVIDIA publishes.
_NOT_A_CHAT_MODEL = (
    "embed", "rerank", "ocr", "guard", "safety", "reward", "speech", "tts",
    "asr", "diffusion", "image", "video", "vision", "vl-", "-vl", "parse",
    "retriever", "classif",
)

# Preference tiers. Lower sorts first.
_PREFERRED = ("nemotron", "instruct", "coder", "chat")

# Rough capability ordering within Nemotron, largest/most capable first.
_SIZE_HINTS = ("ultra", "253b", "super", "120b", "70b", "49b", "30b", "12b", "9b", "8b")


def _is_chat_model(model_id: str) -> bool:
    lowered = model_id.lower()
    return not any(marker in lowered for marker in _NOT_A_CHAT_MODEL)


def _rank_key(model_id: str) -> tuple[int, int, str]:
    lowered = model_id.lower()
    tier = next(
        (i for i, word in enumerate(_PREFERRED) if word in lowered),
        len(_PREFERRED),
    )
    size = next(
        (i for i, hint in enumerate(_SIZE_HINTS) if hint in lowered),
        len(_SIZE_HINTS),
    )
    return (tier, size, model_id)


def rank_models(model_ids: list[str]) -> list[str]:
    """Drop what cannot drive the loop, then order Nemotron-first."""
    seen: list[str] = []
    for model_id in model_ids:
        if model_id and _is_chat_model(model_id) and model_id not in seen:
            seen.append(model_id)
    return sorted(seen, key=_rank_key)


def _fetch_models_json(api_key: str, timeout: float = 15.0) -> dict:
    """GET /v1/models. Split out so tests can drive it without a network."""
    request = urllib.request.Request(  # noqa: S310 - fixed https base URL
        f"{NVIDIA_BASE_URL}/v1/models",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def live_model_ids(api_key: str, timeout: float = 15.0) -> list[str]:
    """Ranked ids the provider currently serves, or ``[]``.

    Never raises: discovery failing must not be the reason a run dies, since the
    static list below can still carry it.
    """
    if not api_key:
        return []
    try:
        payload = _fetch_models_json(api_key, timeout)
        entries = payload.get("data") or []
        return rank_models([str(e.get("id") or "") for e in entries])
    except Exception:
        return []


_RESOLVED: list[str] | None = None


def resolve_model_ids(api_key: str | None = None, timeout: float = 15.0) -> list[str]:
    """The ids a caller should try, in order.

    Memoised: the agent loop asks once per turn and runs up to 120 turns, so an
    uncached lookup would be 120 catalogue requests per issue.
    """
    global _RESOLVED
    if _RESOLVED is not None:
        return list(_RESOLVED)
    if api_key is None:
        api_key = os.environ.get("NVIDIA_API_KEY", "")
    _RESOLVED = live_model_ids(api_key, timeout) or list(NVIDIA_MODEL_IDS)
    return list(_RESOLVED)


def resolve_candidates(api_key: str | None = None) -> list[tuple[str, str]]:
    """``(model_id, label)`` pairs, for callers that log a label."""
    labels = dict(NVIDIA_CANDIDATE_MODELS)
    return [(m, labels.get(m, "discovered")) for m in resolve_model_ids(api_key)]


def reset_cache() -> None:
    """Drop the memoised result. For tests."""
    global _RESOLVED
    _RESOLVED = None


# ── Static floor ────────────────────────────────────────────────────────────
# Only reached when discovery cannot run. Every id observed returning 410/404 on
# 2026-08-27 has been removed rather than left in to waste an attempt; what
# remains is the one entry from the previous list not seen failing. This list is
# deliberately not padded with ids nobody has verified — discovery is the
# mechanism now, and a short honest floor beats a long speculative one.
NVIDIA_CANDIDATE_MODELS: list[tuple[str, str]] = [
    ("meta/llama-4-maverick-17b-128e-instruct", "Llama 4 Maverick (static fallback)"),
]

NVIDIA_MODEL_IDS: list[str] = [model_id for model_id, _label in NVIDIA_CANDIDATE_MODELS]

# Old name, kept so existing imports keep working.
CANDIDATE_MODELS = NVIDIA_CANDIDATE_MODELS

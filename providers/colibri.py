"""providers/colibri.py — Free local GLM-5.2 brain served by JustVugg/colibri.

Mirrors ``providers/kimi_local_llama.py`` for parity: registers a free OAI-compat
provider that points at a locally-running ``coli serve`` instance loading the
GLM-5.2 (744B MoE, ~370 GB int4) SD checkpoint downloaded to
``D:\\hfkld-qg7ky\\local-models\\glm-5.2\\``.

Operators can route ``model: glm-5.2`` requests through the qwen-server
proxy (port 8000) without an external API key — fully offline, on the local
machine. Server comes up via ``scripts\\start_colibri_server.ps1``.

Env vars (all optional):
  COLIBRI_ENABLED   truthy to register the provider              (default: off)
  COLIBRI_URL       OAI-compat base URL                          (default: http://localhost:8081/v1)
  COLIBRI_MODEL     model id to request                         (default: glm-5.2)
  COLIBRI_PRIORITY  routing priority int                         (default: -10)
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from packages.ai.router import ProviderConfig

log = logging.getLogger("colibri_local")

COLIBRI_PROVIDER_ID = "colibri"

_DEFAULT_URL = "http://localhost:8081/v1"
_DEFAULT_MODEL = "glm-5.2"
# Below the cloud nvidia (-10 within NVIDIA env-block) but still under paid
# providers so that — on this machine — colibri beats NVIDIA NIM when both
# are configured. Operators raising the priority (e.g. -50) push colibri
# ahead of every cloud record.
_DEFAULT_PRIORITY = -10

_TRUTHY = {"1", "true", "yes", "on"}


def colibri_enabled() -> bool:
    """Return True iff the operator opted in via ``COLIBRI_ENABLED=true``."""
    raw = os.environ.get("COLIBRI_ENABLED", "")
    return raw.strip().lower() in _TRUTHY


def colibri_status() -> dict[str, object]:
    """Cheap status snapshot for tests + admin UI."""
    return {
        "provider_id": COLIBRI_PROVIDER_ID,
        "enabled": colibri_enabled(),
        "url": os.environ.get("COLIBRI_URL", _DEFAULT_URL).strip() or _DEFAULT_URL,
        "model": os.environ.get("COLIBRI_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL,
        "priority": _safe_priority(),
    }


def _safe_priority() -> int:
    raw = os.environ.get("COLIBRI_PRIORITY", str(_DEFAULT_PRIORITY))
    try:
        return int(raw) if str(raw).strip() else _DEFAULT_PRIORITY
    except ValueError:
        return _DEFAULT_PRIORITY


def colibri_provider_config() -> Optional[ProviderConfig]:
    """Return the ``ProviderConfig`` for the local colibri server, or ``None`` when disabled."""
    if not colibri_enabled():
        return None

    base_url = (os.environ.get("COLIBRI_URL", _DEFAULT_URL).strip() or _DEFAULT_URL)
    model = (os.environ.get("COLIBRI_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL)
    priority = _safe_priority()

    return ProviderConfig(
        provider_id=COLIBRI_PROVIDER_ID,
        type="openai-compatible",
        base_url=base_url,
        api_key="",
        default_model=model,
        priority=priority,
    )

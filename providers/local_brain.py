"""providers/local_brain.py — Free local brain served by the local llama-server.exe on :8072.

Mirrors ``providers/colibri.py`` for parity: registers a free OAI-compat
provider that points at the locally-running ``llama-server.exe`` loading the
GLM-5.2 Q4_K_M GGUF downloaded to ``D:\\hfkld-qg7ky\\local-models\\GLM-5.2\\``.

The actual llama-server process is owned by ``scripts/local_controller.py``
(the cloud-admin SPA toggle daemon) — this file is purely the provider
registration glue so the qwen-server proxy (port 8000) routes
``model: glm-5.2`` requests to localhost:8072/v1 without an external API key.

Operators can flip the toggle from the Cloudflare-deployed admin Providers
page; the local controller starts/stops llama-server on this machine and
the brain resolver / ProviderRouter pick this provider up on the next
``BRAIN_PREFERENCE=local-brain`` cycle.

Env vars (all optional, but typically the local_controller sets them when
the toggle flips on):
  LOCAL_BRAIN_ENABLED          truthy to register the provider            (default: off)
  LOCAL_BRAIN_URL              OAI-compat base URL                        (default: http://127.0.0.1:8072/v1)
  LOCAL_BRAIN_MODEL_ID         model id to register with llama-server     (default: glm-5.2)
  LOCAL_BRAIN_PRIORITY         routing priority int                       (default: -10)

The defaults deliberately mirror what ``scripts/local_controller.py``
writes: 127.0.0.1 (NEVER expose publicly), port 8072, model id "glm-5.2".
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from packages.ai.router import ProviderConfig

log = logging.getLogger("local_brain")

LOCAL_BRAIN_PROVIDER_ID = "local-brain"

# 127.0.0.1 (NEVER public), port from scripts/local_controller.py DEFAULT_HTTP_PORT
_DEFAULT_URL = "http://127.0.0.1:8072/v1"
# Default model id matches local_controller.DEFAULT_MODEL_ID + .env.example
_DEFAULT_MODEL = "glm-5.2"
# Mirrors colibri: tier sort would otherwise drop us to windows_server (because
# 127.0.0.1 doesn't match the Ollama-LAN whitelist), so we declare -10 to beat
# every cloud record except nvidia-nim env.
_DEFAULT_PRIORITY = -10

_TRUTHY = {"1", "true", "yes", "on"}


def local_brain_enabled() -> bool:
    """Return True iff the operator opted in via ``LOCAL_BRAIN_ENABLED=true``."""
    raw = os.environ.get("LOCAL_BRAIN_ENABLED", "")
    return raw.strip().lower() in _TRUTHY


def local_brain_status() -> dict[str, object]:
    """Cheap status snapshot for tests + admin UI."""
    return {
        "provider_id": LOCAL_BRAIN_PROVIDER_ID,
        "enabled": local_brain_enabled(),
        "url": (os.environ.get("LOCAL_BRAIN_URL", _DEFAULT_URL).strip() or _DEFAULT_URL),
        "model": (os.environ.get("LOCAL_BRAIN_MODEL_ID", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL),
        "priority": _safe_priority(),
    }


def _safe_priority() -> int:
    raw = os.environ.get("LOCAL_BRAIN_PRIORITY", str(_DEFAULT_PRIORITY))
    try:
        return int(raw) if str(raw).strip() else _DEFAULT_PRIORITY
    except ValueError:
        return _DEFAULT_PRIORITY


def local_brain_provider_config() -> Optional[ProviderConfig]:
    """Return the ``ProviderConfig`` for the local brain, or ``None`` when disabled.

    ``scripts/local_controller.py`` is the source of truth for whether the
    llama-server process is actually running on the box — this only governs
    whether the qwen-server proxy should *attempt* to route to localhost:8072.
    A wrong-port result is harmless: the ProviderRouter will get a connection
    error from the OAI-compat client and failover to the next provider.
    """
    if not local_brain_enabled():
        return None

    base_url = (
        os.environ.get("LOCAL_BRAIN_URL", _DEFAULT_URL).strip() or _DEFAULT_URL
    )
    model = (
        os.environ.get("LOCAL_BRAIN_MODEL_ID", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL
    )
    priority = _safe_priority()

    return ProviderConfig(
        provider_id=LOCAL_BRAIN_PROVIDER_ID,
        type="openai-compatible",
        base_url=base_url,
        api_key="",
        default_model=model,
        priority=priority,
    )

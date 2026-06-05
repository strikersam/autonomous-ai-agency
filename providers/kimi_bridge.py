"""Free Kimi (Moonshot) **web-bridge** provider.

Why this exists
---------------
The agency's routing policy refuses *paid* escalation ("policy prevents paid
escalation").  The only built-in Kimi path is the **commercial** Moonshot API
(`MOONSHOT_API_KEY`), so when no free runtime/provider is configured every task
fails with "All runtimes failed and policy prevents paid escalation."

This module registers a Kimi provider that is classified **free** (see
``_FREE_CLOUD_PROVIDER_IDS`` in ``provider_router.py``) and reaches Kimi through an
**OpenAI-compatible bridge endpoint** rather than the paid API.  The bridge can be:

  * ``endpoint`` mode (default, safe): an external OpenAI-compatible service you run
    (e.g. a small Playwright/Browserbase shim that drives kimi.com, or any
    OpenAI-compatible gateway).  This module only emits the ``ProviderConfig`` that
    points at it — it never launches a browser itself.
  * ``browser`` mode (opt-in): documents the local shim contract.  It is **disabled
    by default**, requires ``KIMI_BRIDGE_BROWSER=true``, and is never auto-started —
    in particular it must never run on the stateless Render backend.

Environment
-----------
  KIMI_BRIDGE_ENABLED   truthy to register the provider at all (default: off)
  KIMI_BRIDGE_URL       OpenAI-compatible base URL (default: http://localhost:8011/v1)
  KIMI_BRIDGE_MODEL     model id to request           (default: kimi-k2.6)
  KIMI_BRIDGE_TOKEN     optional bearer token for the bridge (default: none)
  KIMI_BRIDGE_MODE      "endpoint" | "browser"        (default: endpoint)
  KIMI_BRIDGE_BROWSER   truthy to acknowledge browser mode (default: off)
  KIMI_BRIDGE_PRIORITY  routing priority int          (default: 5)
"""

from __future__ import annotations

import logging
import os

from provider_router import ProviderConfig

log = logging.getLogger("qwen-proxy")

#: Stable provider id — also listed in ``_FREE_CLOUD_PROVIDER_IDS`` so the routing
#: policy treats the bridge as a non-paid provider.
KIMI_BRIDGE_PROVIDER_ID = "kimi-web-bridge"

_DEFAULT_URL = "http://localhost:8011/v1"
_DEFAULT_MODEL = "kimi-k2.6"


def _enabled() -> bool:
    return os.environ.get("KIMI_BRIDGE_ENABLED", "").strip().lower() in {
        "true",
        "1",
        "yes",
    }


def kimi_bridge_status() -> dict[str, object]:
    """Lightweight status used by the Providers UI / Doctor."""
    return {
        "provider_id": KIMI_BRIDGE_PROVIDER_ID,
        "enabled": _enabled(),
        "mode": os.environ.get("KIMI_BRIDGE_MODE", "endpoint"),
        "base_url": os.environ.get("KIMI_BRIDGE_URL", _DEFAULT_URL),
        "model": os.environ.get("KIMI_BRIDGE_MODEL", _DEFAULT_MODEL),
        "tier": "free_cloud",
        "browser_mode_ack": os.environ.get("KIMI_BRIDGE_BROWSER", "").lower()
        in {"true", "1", "yes"},
    }


def kimi_bridge_provider_config() -> ProviderConfig | None:
    """Return a free, OpenAI-compatible ``ProviderConfig`` for the Kimi bridge.

    Returns ``None`` when ``KIMI_BRIDGE_ENABLED`` is not set, so callers can append
    unconditionally:  ``if (cfg := kimi_bridge_provider_config()): providers.append(cfg)``.
    """
    if not _enabled():
        return None

    mode = os.environ.get("KIMI_BRIDGE_MODE", "endpoint").strip().lower()
    if mode == "browser" and os.environ.get("KIMI_BRIDGE_BROWSER", "").lower() not in {
        "true",
        "1",
        "yes",
    }:
        # Browser mode must be explicitly acknowledged; otherwise we refuse to
        # register it (it implies a headless browser session we never auto-start).
        log.warning(
            "Kimi bridge KIMI_BRIDGE_MODE=browser requires KIMI_BRIDGE_BROWSER=true; "
            "refusing to register the bridge until acknowledged."
        )
        return None

    base_url = (os.environ.get("KIMI_BRIDGE_URL") or _DEFAULT_URL).strip()
    try:
        priority = int(os.environ.get("KIMI_BRIDGE_PRIORITY", "5"))
    except ValueError:
        priority = 5

    log.info(
        "Kimi web-bridge provider enabled (mode=%s, base_url=%s) — free-tier",
        mode,
        base_url,
    )
    return ProviderConfig(
        provider_id=KIMI_BRIDGE_PROVIDER_ID,
        type="openai-compatible",
        base_url=base_url,
        api_key=os.environ.get("KIMI_BRIDGE_TOKEN") or None,
        default_model=os.environ.get("KIMI_BRIDGE_MODEL", _DEFAULT_MODEL),
        # below Nvidia NIM (-10) but above the generic paid cloud fallbacks so a
        # configured free Kimi bridge is preferred over commercial escalation.
        priority=priority,
    )

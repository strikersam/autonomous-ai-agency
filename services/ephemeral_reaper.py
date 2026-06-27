"""services/ephemeral_reaper.py — destroy expired ephemeral companies.

The platform runs on a free Render backend, so agencies created by non-admin
(GitHub/Google) users are *ephemeral*: they carry ``persistent=False`` and an
``expires_at`` timestamp. This reaper periodically deletes companies whose TTL
has elapsed. **Admin-created companies are ``persistent=True`` and are never
touched.**

Gated by ``EPHEMERAL_COMPANY_REAPER_ENABLED`` (default on). The loop is fully
defensive — a transient store error never stops it.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

log = logging.getLogger("qwen-proxy")

# Default sweep cadence — 15 minutes is frequent enough that a 24h TTL is
# honoured to within ~1% without hammering the store.
_DEFAULT_SWEEP_SEC = 900.0
_DEFAULT_WARMUP_SEC = 90.0


def reaper_enabled() -> bool:
    val = os.environ.get("EPHEMERAL_COMPANY_REAPER_ENABLED", "true").strip().lower()
    return val not in ("0", "false", "no", "off")


def _as_aware_utc(dt: datetime) -> datetime:
    """Treat naive datetimes as UTC so comparisons never raise."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def reap_expired_companies(now: datetime | None = None) -> int:
    """Delete all expired ephemeral companies. Returns the number deleted.

    A company is reaped when ``persistent`` is False AND ``expires_at`` is set
    AND ``expires_at <= now``. Persistent companies (admins) are skipped.
    """
    from services.company_graph_store import get_company_graph_store

    now = _as_aware_utc(now or datetime.now(timezone.utc))
    store = get_company_graph_store()

    deleted = 0
    offset = 0
    page = 200
    # Snapshot candidate IDs first (paging the full list), then delete — so we
    # never mutate the collection mid-iteration.
    to_delete: list[str] = []
    while True:
        companies = await store.list_companies(limit=page, offset=offset)
        if not companies:
            break
        for c in companies:
            if getattr(c, "persistent", True):
                continue
            exp = getattr(c, "expires_at", None)
            if not exp:
                continue
            if _as_aware_utc(exp) <= now:
                to_delete.append(c.id)
        if len(companies) < page:
            break
        offset += page

    for cid in to_delete:
        try:
            if await store.delete_company(cid):
                deleted += 1
                log.info("Ephemeral reaper destroyed expired company %s", cid)
        except Exception as exc:  # noqa: BLE001 — one bad row must not abort the sweep
            log.warning("Ephemeral reaper failed to delete company %s: %s", cid, exc)

    if deleted:
        log.info("Ephemeral reaper sweep complete — %d company(ies) destroyed", deleted)
    return deleted


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        log.warning("Invalid %s=%r; using default %s", name, raw, default)
        return default


async def ephemeral_reaper_loop() -> None:
    """Run the reaper forever on a fixed cadence. Never raises out of the loop."""
    await asyncio.sleep(_env_float("EPHEMERAL_REAPER_WARMUP_SEC", _DEFAULT_WARMUP_SEC))
    while True:
        try:
            await reap_expired_companies()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("Ephemeral reaper cycle error: %s", exc)
        await asyncio.sleep(_env_float("EPHEMERAL_REAPER_SWEEP_SEC", _DEFAULT_SWEEP_SEC))

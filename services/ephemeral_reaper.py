"""services/ephemeral_reaper.py — destroy expired ephemeral companies.

The platform runs on a free Render backend, so agencies created by non-admin
(GitHub/Google) users are *ephemeral*: they carry ``persistent=False`` and an
``expires_at`` timestamp. This reaper periodically deletes companies whose TTL
has elapsed. **Admin-created companies are ``persistent=True`` and are never
touched.**

Gated by ``EPHEMERAL_COMPANY_REAPER_ENABLED`` (default on). The loop is fully
defensive — a transient store error never stops it.

The same loop also runs ``reap_orphaned_agents`` each cycle, which cleans up
specialist agents left registered by company deletions that predate the
agency-teardown fix in ``CompanyGraphService.delete_company``.
"""

from __future__ import annotations

import asyncio
import logging
import math
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
    from services.company_graph import CompanyGraphService
    from services.company_graph_store import get_company_graph_store

    now = _as_aware_utc(now or datetime.now(timezone.utc))
    store = get_company_graph_store()
    # Delete through the service, not the store: the service also tears down the
    # company's live agency (schedules + registered agents), which a raw store
    # delete would leave orphaned and running. Bind it to this exact store so we
    # reap from the same backend we listed from.
    service = CompanyGraphService(store=store)

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
            if await service.delete_company(cid):
                deleted += 1
                log.info("Ephemeral reaper destroyed expired company %s", cid)
        except Exception:  # noqa: BLE001 — one bad row must not abort the sweep
            log.exception("Ephemeral reaper failed to delete company %s", cid)

    if deleted:
        log.info("Ephemeral reaper sweep complete — %d company(ies) destroyed", deleted)
    return deleted


def _company_id_for_agent(agent: object) -> str | None:
    """Return the company id an auto-provisioned specialist belongs to, else None.

    Onboarding tags every specialist agent it registers with both
    ``auto-provisioned`` and ``company:<id>`` (see
    ``CompanyAgencyService.activate_company``). Requiring the
    ``auto-provisioned`` tag guarantees this sweep only ever considers
    company specialists — a user's personal agent, which carries neither tag,
    is never a candidate for deletion.
    """
    tags = getattr(agent, "tags", None) or []
    if "auto-provisioned" not in tags:
        return None
    for tag in tags:
        if tag.startswith("company:"):
            return tag.split(":", 1)[1] or None
    return None


async def _company_alive(company_store: object, company_id: str, cache: dict) -> bool:
    """Whether *company_id* still exists, cached per sweep.

    A lookup error returns ``True`` ("assume alive") so a transient store
    failure can never cause the reaper to delete an agent.
    """
    if company_id not in cache:
        try:
            cache[company_id] = await company_store.get_company(company_id) is not None
        except Exception:  # noqa: BLE001 — never delete on a lookup error
            log.exception("Orphan-agent reaper: company lookup failed for %s", company_id)
            cache[company_id] = True
    return cache[company_id]


async def reap_orphaned_agents() -> int:
    """Delete registered specialist agents whose owning company no longer exists.

    Before ``delete_company`` learned to tear the agency down, deleting an
    onboarded company left its AgentStore agents behind — orphans that kept
    showing in the dashboard. This sweep removes any auto-provisioned company
    specialist whose ``company:<id>`` no longer resolves to a live company.
    User-owned agents are never touched. Returns the number of agents removed.
    """
    from agents.store import get_agent_store
    from services.company_graph_store import get_company_graph_store

    agent_store = get_agent_store()
    company_store = get_company_graph_store()

    try:
        agents = await agent_store.list_all()
    except Exception:  # noqa: BLE001 — a listing failure must not abort the loop
        log.exception("Orphan-agent reaper: failed to list agents")
        return 0

    alive_cache: dict[str, bool] = {}
    removed = 0
    for agent in agents:
        company_id = _company_id_for_agent(agent)
        if company_id is None or await _company_alive(company_store, company_id, alive_cache):
            continue
        agent_id = getattr(agent, "agent_id", "")
        try:
            if await agent_store.delete(agent_id):
                removed += 1
                log.info(
                    "Orphan-agent reaper: removed agent %s (company %s is gone)",
                    agent_id, company_id,
                )
        except Exception:  # noqa: BLE001 — one bad row must not abort the sweep
            log.exception("Orphan-agent reaper: failed to delete agent %s", agent_id)

    if removed:
        log.info(
            "Orphan-agent reaper sweep complete — %d agent(s) with no company removed",
            removed,
        )
    return removed


def _env_float(name: str, default: float) -> float:
    """Parse a positive, finite float env var (seconds), else the default.

    Rejects ``0``, negatives, ``inf`` and ``nan`` — any of which would turn the
    reaper's ``asyncio.sleep`` into an immediate/tight loop hammering the store.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        val = float(raw)
    except (TypeError, ValueError):
        log.warning("Invalid %s=%r; using default %s", name, raw, default)
        return default
    if not math.isfinite(val) or val <= 0:
        log.warning("Non-positive/invalid %s=%r; using default %s", name, raw, default)
        return default
    return val


async def ephemeral_reaper_loop() -> None:
    """Run the reaper forever on a fixed cadence. Never raises out of the loop."""
    await asyncio.sleep(_env_float("EPHEMERAL_REAPER_WARMUP_SEC", _DEFAULT_WARMUP_SEC))
    while True:
        try:
            await reap_expired_companies()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("Ephemeral reaper cycle error")
        # Reconcile agents left orphaned by past company deletions (pre-fix).
        try:
            await reap_orphaned_agents()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("Orphan-agent reaper cycle error")
        await asyncio.sleep(_env_float("EPHEMERAL_REAPER_SWEEP_SEC", _DEFAULT_SWEEP_SEC))

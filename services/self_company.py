"""The platform's own company: exactly one, connected to its repo, staffed right.

The platform onboards itself as a company (``services/self_bootstrap.py``) so
the agency always has something to run. That identity used to be the website
domain alone, and the domain differs by surface and by process: the Cloudflare
Worker frontend (``*.workers.dev``), the Render backend (``*.onrender.com``),
a process without ``RENDER_EXTERNAL_URL``. Each produced its own company, each
activated its own agents and schedules, and the frontend copy was "archived"
as stale even though it is the live frontend.

``consolidate_self_companies`` runs at startup and makes it one company again:

1. **Find** every company that is the platform (a known platform domain, the
   platform repo, or a platform name) *and* is owned by the operator or the
   system — a real user's company is never touched.
2. **Keep** the best one (connected to the repo, onboarded, most specialists,
   oldest) and delete the rest through ``CompanyGraphService.delete_company``,
   which also stops their schedules, cancels their tasks and removes their agents.
3. **Repair** the survivor: canonical name and domain, the repo connected with
   its real default branch, the repo rescanned, and the right technical
   specialists (backend, frontend, devops, security, QA, data) in place of
   generic marketing ones; then re-activate it so agents and schedules match.

Idempotent: with one healthy company it changes nothing. Never raises.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from packages.config.self_company import (
    admin_email, public_site_url, self_company_consolidate_enabled)

log = logging.getLogger("qwen-proxy")

COMPANY_NAME = "Autonomous AI Agency"
REPO_FULL_NAMES = frozenset({"strikersam/autonomous-ai-agency", "strikersam/local-llm-server"})
# Every surface the platform has been served from. workers.dev is the live
# frontend (the Worker proxies /api to Render), not a stale copy.
KNOWN_DOMAINS = frozenset({
    "autonomous-ai-agency.strikersam.workers.dev",
    "local-llm-server.strikersam.workers.dev",
    "local-llm-server.onrender.com",
    "autonomous-ai-agency.onrender.com",
})
KNOWN_NAMES = frozenset({
    "autonomous ai agency", "autonomous ai agency (self)", "autonomous-ai-agency",
    "local-llm-server", "local llm server", "agency core platform",
})
# The platform is a Python/FastAPI + React codebase on Render, Cloudflare and
# GitHub Actions; these are the specialists that can actually work on it. SEO
# stays: the public site has to rank and be cited (SEO, GEO, AEO, AIO), and
# the fixes are code in this repo (frontend/public, index.html).
TECH_FAMILIES = ("backend", "frontend", "devops", "security", "qa", "data", "seo")
NON_TECH_FAMILIES = frozenset({
    "analytics", "marketing", "content", "merchandising", "pim", "oms",
    "dam", "crm", "support", "trading", "ecommerce",
})
REPO_DEFAULT_BRANCH = "master"  # used only if GitHub can't be asked
_SCAN_TIMEOUT_S = 90.0
_DELETE_TIMEOUT_S = 60.0
# Startup, the agency cycle and the background loop all call the bootstrap;
# concurrent runs raced each other deleting the same duplicates.
_LOCK = asyncio.Lock()


def _domain_of(url: str) -> str:
    return (urlparse(url).netloc or url or "").lower().strip()


def self_domains(current_url: str) -> frozenset[str]:
    """Known platform domains plus the one this process is configured with."""
    found = {_domain_of(current_url), _domain_of(public_site_url())} - {""}
    return KNOWN_DOMAINS | found


def _repo_full_name(company: Any) -> str:
    conn = getattr(company, "repo_connection", None)
    if conn is None:
        return ""
    return f"{conn.owner}/{conn.repo}".lower()


def looks_like_self(company: Any, domains: frozenset[str]) -> bool:
    """True when *company* is a copy of the platform (by domain, repo or name)."""
    return (
        (company.domain or "").lower() in domains
        or _repo_full_name(company) in REPO_FULL_NAMES
        or (company.name or "").strip().lower() in KNOWN_NAMES
    )


async def _owner_is_platform(owner_id: str | None) -> bool:
    """The operator, the system, or an admin — never an ordinary user's company."""
    if owner_id in (None, "", "system", "self-bootstrap", admin_email(), "admin@llmrelay.local"):
        return True
    try:
        from services.agent_memory.service import _user_identities  # id/email lookup

        identities = await _user_identities(owner_id)
        if admin_email() in identities:
            return True
        from db import get_store

        users = get_store().users
        doc = await users.find_one({"email": owner_id})
        return bool(doc) and doc.get("role") == "admin"
    except Exception as exc:  # noqa: BLE001 - unknown owner: leave the company alone
        log.debug("self-company: owner lookup failed for %s: %s", owner_id, exc)
        return False


def _created_ts(company: Any) -> float:
    created = getattr(company, "created_at", None)
    if isinstance(created, datetime):
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return created.timestamp()
    return float("inf")


def pick_canonical(companies: list[Any], specialist_counts: dict[str, int]) -> Any:
    """Connected to the repo, then onboarded, then most specialists, then oldest."""
    return max(
        companies,
        key=lambda c: (
            _repo_full_name(c) in REPO_FULL_NAMES,
            c.onboarding_status == "complete",
            specialist_counts.get(c.id, 0),
            -_created_ts(c),
            c.id,  # last resort, so every process picks the same company
        ),
    )


async def _platform_companies(store: Any, domains: frozenset[str]) -> list[Any]:
    from services.self_bootstrap import _list_companies_safe

    found = []
    for company in await _list_companies_safe():
        if looks_like_self(company, domains) and await _owner_is_platform(company.owner_id):
            found.append(company)
    return found


async def _adopt_priorities(store: Any, keep: Any, duplicates: list[Any]) -> Any:
    """Carry the duplicates' recorded priorities onto the kept company first.

    Priorities are the operator's own input (onboarding, the Priorities tab);
    deleting a duplicate used to delete them with it.
    """
    from services.onboarding_questions import clean_priorities

    current = list(getattr(keep, "priorities", None) or [])
    merged = clean_priorities(current + [p for c in duplicates for p in (getattr(c, "priorities", None) or [])])
    if merged == current:
        return keep
    keep = keep.model_copy(update={"priorities": merged})
    await store.update_company(keep)
    log.info("self-company: kept %d priorities on %s from duplicates", len(merged), keep.id)
    return keep


async def _delete_one(graph: Any, store: Any, company: Any) -> bool:
    """Full teardown, bounded. On timeout delete the row itself: the company is
    already recorded as deleted, so the orphan reaper finishes its schedules,
    tasks and agents, and one slow teardown no longer stalls the repair."""
    try:
        return bool(await asyncio.wait_for(graph.delete_company(company.id),
                                           timeout=_DELETE_TIMEOUT_S))
    except asyncio.TimeoutError:
        log.warning("self-company: teardown of %s timed out after %.0fs; deleting the row, "
                    "the orphan reaper finishes the rest", company.id, _DELETE_TIMEOUT_S)
        return bool(await store.delete_company(company.id))


async def _delete_duplicates(store: Any, duplicates: list[Any]) -> list[str]:
    from services.company_graph import get_company_graph_service

    graph = get_company_graph_service()
    removed = []
    for company in duplicates:
        try:
            if await _delete_one(graph, store, company):
                removed.append(company.id)
                log.info("self-company: removed duplicate %s (%s, %s)",
                         company.id, company.name, company.domain)
        except Exception as exc:  # noqa: BLE001 - one failed delete must not stop the rest
            log.warning("self-company: could not remove duplicate %s: %s", company.id, exc)
    return removed


async def _normalise_company(store: Any, company: Any, domain: str) -> Any:
    """Canonical name, domain and lifecycle on the surviving company."""
    update: dict[str, Any] = {}
    if company.name != COMPANY_NAME:
        update["name"] = COMPANY_NAME
    if domain and company.domain != domain:
        update["domain"] = domain
    if not company.is_active:
        update["is_active"] = True
    if company.onboarding_status != "complete":
        update.update(onboarding_status="complete", onboarding_progress=1.0)
    if company.owner_id in (None, ""):
        update["owner_id"] = admin_email()
    if not update:
        return company
    company = company.model_copy(update=update)
    await store.update_company(company)
    log.info("self-company: normalised %s (%s)", company.id, sorted(update))
    return company


async def _connect_repo(store: Any, company: Any, repo_url: str) -> bool:
    """Attach the repo when missing, pointed elsewhere, or on a guessed branch."""
    from services.repo_connection import attach_repo_connection, parse_repo_url

    parsed = parse_repo_url(repo_url)
    if parsed is None:
        return False
    conn = company.repo_connection
    wanted = f"{parsed[0]}/{parsed[1]}".lower()
    branch_guessed = conn is not None and conn.policy is not None and "uncertain" in (
        conn.policy.detection_note or "")
    if conn is not None and _repo_full_name(company) == wanted and not (
            branch_guessed and conn.default_branch != REPO_DEFAULT_BRANCH):
        return False
    # Keep what the old connection carried: the token reference and any
    # first-merge consent the operator already gave.
    await attach_repo_connection(company.id, repo_url, store=store,
                                 token_ref=conn.token_ref if conn else None,
                                 fallback_branch=REPO_DEFAULT_BRANCH)
    if conn is not None and conn.policy is not None and conn.policy.first_merge_consent:
        from services.repo_connection import record_first_merge_consent

        fresh = await store.get_company(company.id)
        if fresh is not None and fresh.repo_connection is not None:
            await store.update_company(fresh.model_copy(update={
                "repo_connection": record_first_merge_consent(fresh.repo_connection)}))
    return True


async def _rescan_repo(company_id: str, repo_url: str) -> bool:
    """Refresh the detected stack from the repo (bounded; a failure is logged)."""
    from services.onboarding import get_onboarding_service

    try:
        await asyncio.wait_for(
            get_onboarding_service()._scan_repo(company_id, repo_url), timeout=_SCAN_TIMEOUT_S)
        return True
    except Exception as exc:  # noqa: BLE001 - scan is best-effort
        log.warning("self-company: repo rescan failed for %s: %s", company_id, exc)
        return False


async def _remove_agent(specialist_id: str) -> None:
    try:
        from agents.store import get_agent_store

        await get_agent_store().delete(f"specialist:{specialist_id}", owner_id=None)
    except Exception as exc:  # noqa: BLE001 - activation re-syncs the rest
        log.debug("self-company: agent removal failed for %s: %s", specialist_id, exc)


async def reconcile_specialists(store: Any, company_id: str) -> dict[str, list[str]]:
    """Provision missing technical families and retire non-technical ones."""
    from models.company_graph import SpecialistProvisionRequest
    from services.specialist import get_specialist_service

    svc = get_specialist_service()
    existing = await store.list_specialists(company_id)
    have = {s.family for s in existing}
    added, removed = [], []
    for family in TECH_FAMILIES:
        if family in have:
            continue
        result = await svc.provision_specialist(SpecialistProvisionRequest(
            company_id=company_id, specialist_family=family, auto_provision=True))
        if getattr(result, "status", "") == "success":
            added.append(family)
    seen: set[str] = set()
    # Healthy specialists first, so a duplicate retires the broken copy.
    healthy_first = sorted(existing, key=lambda sp: (
        getattr(sp, "is_provisioned", True) is False, getattr(sp, "status", "") == "disabled"))
    for spec in healthy_first:
        # Two concurrent runs once staffed the same family twice: keep one.
        duplicate = spec.family in seen
        seen.add(spec.family)
        if (spec.family in NON_TECH_FAMILIES or duplicate) and await svc.deprovision_specialist(spec.id):
            await _remove_agent(spec.id)
            removed.append(spec.family)
    return {"added": added, "removed": removed}


async def _activate(company_id: str) -> str:
    from services.company_agency import get_company_agency_service

    try:
        result = await get_company_agency_service().activate_company(
            company_id, start_runtimes=True, create_schedules=True)
        return str(result.get("status", "activated"))
    except Exception as exc:  # noqa: BLE001 - startup must not fail on activation
        log.warning("self-company: activation failed for %s: %s", company_id, exc)
        return "activation_failed"


async def repair_company(store: Any, company: Any, *, domain: str, repo_url: str,
                         duplicates_removed: bool = False) -> dict[str, Any]:
    """Bring the surviving company to the canonical, staffed, connected state.

    Re-activates whenever anything changed, including duplicates removed: a
    same-named duplicate may have owned the schedules this company was using.
    """
    company = await _normalise_company(store, company, domain)
    repo_changed = await _connect_repo(store, company, repo_url)
    # The connection alone is not the graph: the Company page counts scanned
    # repos and detected systems, which earlier unauthenticated scans never wrote.
    needs_scan = (repo_changed or not await store.list_repos(company.id)
                  or not await store.list_detected_systems(company_id=company.id))
    rescanned = await _rescan_repo(company.id, repo_url) if needs_scan else False
    staffing = await reconcile_specialists(store, company.id)
    changed = (duplicates_removed or repo_changed or rescanned
               or staffing["added"] or staffing["removed"])
    activation = await _activate(company.id) if changed else "unchanged"
    return {"repo_connected": repo_changed, "repo_rescanned": rescanned,
            "specialists": staffing, "activation": activation}


async def consolidate_self_companies(*, website_url: str, repo_url: str) -> dict[str, Any]:
    """Leave exactly one platform company, repaired. Returns a status dict; never raises."""
    if not self_company_consolidate_enabled():
        return {"status": "disabled"}
    if _LOCK.locked():
        return {"status": "in_progress"}
    async with _LOCK:
        return await _consolidate(website_url=website_url, repo_url=repo_url)


async def _consolidate(*, website_url: str, repo_url: str) -> dict[str, Any]:
    try:
        from services.company_graph_store import get_company_graph_store

        store = get_company_graph_store()
        domains = self_domains(website_url)
        companies = await _platform_companies(store, domains)
        if not companies:
            return {"status": "none"}
        counts = {c.id: len(await store.list_specialists(c.id)) for c in companies}
        keep = pick_canonical(companies, counts)
        duplicates = [c for c in companies if c.id != keep.id]
        log.info("self-company: keeping %s (%s); removing %d duplicate(s): %s",
                 keep.id, keep.name, len(duplicates), [c.id for c in duplicates])
        keep = await _adopt_priorities(store, keep, duplicates)
        removed = await _delete_duplicates(store, duplicates)
        # The company's domain is its public site, not the API host behind it:
        # health and SEO schedules target the domain.
        repair = await repair_company(store, keep, domain=_domain_of(public_site_url()), repo_url=repo_url,
                                      duplicates_removed=bool(removed))
        log.info("self-company: kept %s, removed %d duplicate(s): %s",
                 keep.id, len(removed), repair)
        return {"status": "consolidated", "company_id": keep.id, "removed": removed, **repair}
    except Exception as exc:  # noqa: BLE001 - must never break startup
        log.warning("self-company: consolidation deferred: %s", exc)
        return {"status": "deferred"}

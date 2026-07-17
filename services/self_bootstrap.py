"""Self-onboarding bootstrap.

On startup the platform registers *itself* as a company — linked to its own
GitHub repo — so the agency immediately has something to operate on without a
human clicking through onboarding. The actual "connect & verify the repo" work is
handed to the platform's own agents as a Task (which flows through the working
dispatcher and the PR-autonomy gate), so the agents do the connecting.

Design notes:
  * Idempotent: keyed on the self domain. A second run no-ops when a self company
    already exists AND has specialists AND the domain matches the current config.
    If the domain is stale (e.g. the platform was rebranded), the old company is
    deactivated and a fresh one is created with the correct URLs.
  * Never blocks or crashes startup: callers should fire it as a background task and
    it swallows/logs all errors (a missing DB at boot must not take the server down).
  * Gated by SELF_BOOTSTRAP_ENABLED (default on; tests turn it off).
"""

from __future__ import annotations

import asyncio
import logging
import os
from urllib.parse import urlparse

log = logging.getLogger("qwen-proxy")

# ── Stale domains / repos from the pre-rebrand era ───────────────────────────
# Render's dashboard keeps env vars from the first deploy; render.yaml changes
# don't auto-sync. So SELF_BOOTSTRAP_URL / SELF_BOOTSTRAP_REPO on Render are
# still the old values (local-llm-server.strikersam.workers.dev /
# github.com/strikersam/local-llm-server). These domains are stale — the repo
# was rebranded to autonomous-ai-agency. Detect them and override with the
# correct values derived from GITHUB_REPOSITORY (which IS set correctly on
# Render via render.yaml line 34-35 as a `value:`, not `sync: false`).
_STALE_DOMAINS = {
    "local-llm-server.strikersam.workers.dev",
    # NOTE: 'local-llm-server.onrender.com' is NOT stale — it's the current
    # Render service URL (the service hasn't been renamed yet). Treat it as
    # the valid self-bootstrap target.
}
_STALE_REPO_FRAGMENTS = ("strikersam/local-llm-server",)  # only the old repo path is stale


def _resolve_website_url() -> str:
    """Return the correct self-bootstrap website URL.

    Priority:
    1. SELF_BOOTSTRAP_URL env var IF it doesn't point at a stale domain.
    2. RENDER_EXTERNAL_URL env var (set by Render automatically).
    3. Fallback: autonomous-ai-agency.onrender.com (the current Render deploy).
    """
    raw = os.environ.get("SELF_BOOTSTRAP_URL", "").strip()
    if raw:
        domain = (urlparse(raw).netloc or raw).lower()
        if domain not in _STALE_DOMAINS:
            return raw
        log.warning(
            "Self-bootstrap: SELF_BOOTSTRAP_URL=%s is stale (pre-rebrand) — ignoring",
            raw,
        )
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "").strip()
    if render_url:
        return render_url
    return "https://autonomous-ai-agency.onrender.com"


def _resolve_repo_url() -> str:
    """Return the correct self-bootstrap repo URL.

    Priority:
    1. SELF_BOOTSTRAP_REPO env var IF it doesn't contain a stale fragment.
    2. GITHUB_REPOSITORY env var (set correctly on Render via render.yaml).
    3. Fallback: github.com/strikersam/autonomous-ai-agency.
    """
    raw = os.environ.get("SELF_BOOTSTRAP_REPO", "").strip()
    if raw:
        if not any(frag in raw.lower() for frag in _STALE_REPO_FRAGMENTS):
            return raw
        log.warning(
            "Self-bootstrap: SELF_BOOTSTRAP_REPO=%s is stale (pre-rebrand) — ignoring",
            raw,
        )
    gh_repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if gh_repo:
        return f"https://github.com/{gh_repo}"
    return "https://github.com/strikersam/autonomous-ai-agency"


SELF_WEBSITE_URL = _resolve_website_url()
SELF_REPO_URL = _resolve_repo_url()
SELF_COMPANY_NAME = os.environ.get("SELF_BOOTSTRAP_NAME", "Autonomous AI Agency (self)")


def self_bootstrap_enabled() -> bool:
    return os.environ.get("SELF_BOOTSTRAP_ENABLED", "true").strip().lower() in {
        "true",
        "1",
        "yes",
    }


def _self_domain() -> str:
    netloc = urlparse(SELF_WEBSITE_URL).netloc or SELF_WEBSITE_URL
    return netloc.lower()


async def _list_companies_safe():
    """List companies, skipping any that fail to deserialize.

    A previous deploy wrote onboarding_status='archived' which is not a valid
    Literal value — store.list_companies() raises ValidationError on that row.
    This wrapper skips bad rows so the self-bootstrap can still find/create the
    correct company instead of crashing on stale data.
    """
    from services.company_graph_store import get_company_graph_store

    store = get_company_graph_store()
    try:
        return await store.list_companies(limit=500)
    except Exception as exc:
        log.warning("Self-bootstrap: list_companies failed (%s) — trying raw query", exc)
        # Fall back to a raw query that skips the problematic rows
        try:
            # CompanyGraphStore wraps either MongoDBStore or SQLiteStore
            if hasattr(store, '_mongodb_store') and store._mongodb_store is not None:
                db = store._mongodb_store._get_db()
                cursor = db.companies.find({})
                docs = await cursor.to_list(length=500)
                companies = []
                for doc in docs:
                    try:
                        from models.company_graph import Company
                        companies.append(Company.model_validate({k: v for k, v in doc.items() if k != '_id'}))
                    except Exception:
                        continue
                return companies
            elif hasattr(store, '_sqlite_store') and store._sqlite_store is not None:
                # SQLite path — query directly
                conn = await store._sqlite_store._get_connection()
                cursor = await conn.execute("SELECT * FROM companies")
                rows = await cursor.fetchall()
                companies = []
                for row in rows:
                    try:
                        from models.company_graph import Company
                        # SQLite rows are tuples — convert to dict via column names
                        cols = [desc[0] for desc in cursor.description]
                        doc = dict(zip(cols, row))
                        companies.append(Company.model_validate(doc))
                    except Exception:
                        continue
                return companies
        except Exception as exc2:
            log.warning("Self-bootstrap: raw query fallback also failed: %s", exc2)
        return []


async def _find_self_company():
    """Return the existing self company (matched by domain), or None."""
    companies = await _list_companies_safe()
    domain = _self_domain()
    for company in companies:
        if (company.domain or "").lower() == domain:
            return company
    return None


async def _find_stale_self_companies():
    """Return companies that look like a previous self-bootstrap run but have
    a stale domain (pre-rebrand workers.dev only — NOT the current Render URL).

    Note: 'local-llm-server.onrender.com' is the CURRENT Render service URL
    (the service hasn't been renamed yet), so it must NOT be treated as stale.
    Only 'local-llm-server.strikersam.workers.dev' (the pre-Render Cloudflare
    Workers URL) is stale.
    """
    stale = []
    current_domain = _self_domain()
    companies = await _list_companies_safe()
    for company in companies:
        domain = (company.domain or "").lower()
        # Only the workers.dev URL is stale. The onrender.com URL is the
        # current Render service (it hasn't been renamed) so we must NOT
        # archive companies with that domain — otherwise the self-bootstrap
        # archives the company it just created.
        if domain == "local-llm-server.strikersam.workers.dev" and domain != current_domain:
            stale.append(company)
    return stale


async def _count_specialists(company_id: str) -> int:
    """Return the number of provisioned specialists for a company."""
    try:
        from services.company_graph_store import get_company_graph_store
        store = get_company_graph_store()
        specialists = await store.list_specialists(company_id)
        return len(specialists)
    except Exception:
        return 0


async def _create_company_directly(owner_id: str) -> str:
    """Fallback: create the company directly via the graph service.

    Used when start_onboarding times out or fails — the agency still needs a
    company record to attach specialists, schedules, and tasks to. This bypasses
    the full onboarding flow (scan, detect systems, etc.) and creates a minimal
    company with the correct domain, then provisions baseline specialists.
    """
    from services.company_graph import get_company_graph_service
    from services.company_graph_store import get_company_graph_store

    graph_svc = get_company_graph_service()
    store = get_company_graph_store()

    # Check if a company with this domain already exists (maybe onboarding
    # created it before timing out)
    existing = await _find_self_company()
    if existing is not None:
        log.info("Self-bootstrap fallback: company %s already exists", existing.id)
        return existing.id

    # Create the company directly
    company = await graph_svc.create_company(
        name=SELF_COMPANY_NAME,
        domain=_self_domain(),
        owner_id=owner_id,
    )
    # Mark onboarding as complete so the agency activation runs
    company = company.model_copy(update={
        "onboarding_status": "complete",
        "onboarding_progress": 1.0,
    })
    await store.update_company(company)
    log.info("Self-bootstrap fallback: created company %s (domain=%s)",
             company.id, company.domain)

    # Provision baseline specialists directly
    await _reprovision_specialists(company.id, owner_id)
    return company.id


async def _reprovision_specialists(company_id: str, owner_id: str) -> int:
    """Re-run specialist provisioning for an existing company that has 0 specialists.

    Returns the number of specialists provisioned.
    """
    try:
        from services.specialist import get_specialist_service
        from services.company_graph_store import get_company_graph_store

        store = get_company_graph_store()
        svc = get_specialist_service()

        # Gather detected system types from websites + repos
        websites = await store.list_websites(company_id)
        repos = await store.list_repos(company_id)

        detected_system_types: set[str] = set()
        for website in websites:
            if website.detected_systems:
                for system in website.detected_systems:
                    detected_system_types.add(system.system_type)
            if website.inferred_stack:
                stack = website.inferred_stack
                if stack.cms:
                    detected_system_types.add("CMS")
                if stack.analytics:
                    detected_system_types.add("analytics")
                if stack.frameworks:
                    for fw in stack.frameworks:
                        if fw.lower() in ["react", "vue", "angular", "svelte"]:
                            detected_system_types.add("frontend")
                        elif fw.lower() in ["django", "flask", "rails", "laravel", "express"]:
                            detected_system_types.add("backend")
        for repo in repos:
            if repo.inferred_stack:
                stack = repo.inferred_stack
                if stack.frameworks:
                    for fw in stack.frameworks:
                        if fw.lower() in ["django", "flask", "rails", "laravel", "express"]:
                            detected_system_types.add("backend")
                        elif fw.lower() in ["react", "vue", "angular", "svelte"]:
                            detected_system_types.add("frontend")
                if stack.databases:
                    detected_system_types.add("database")

        # Baseline fallback so we always provision at least a few useful specialists
        if not detected_system_types:
            log.info(
                "Self-bootstrap re-provision: no system types detected for %s — "
                "using baseline fallback (backend, frontend, analytics, security, devops).",
                company_id,
            )
            detected_system_types = {"backend", "frontend", "analytics", "security", "devops"}

        results = await svc.provision_specialists_for_company(
            company_id=company_id,
            system_types=list(detected_system_types),
        )
        count = len(results)
        log.info(
            "Self-bootstrap re-provisioned %d specialists for company %s (types: %s)",
            count, company_id, sorted(detected_system_types),
        )
        return count
    except Exception as exc:
        log.warning("Self-bootstrap re-provision failed for %s: %s", company_id, exc)
        return 0


async def _seed_connect_task(company_id: str, owner_id: str) -> str | None:
    """Hand the 'connect & verify the repo' work to the agency's own agents.

    The task runs through the dispatcher (unblocked) and the PR-autonomy gate, so
    the agents propose a PR rather than pushing master.
    """
    try:
        from tasks.models import Task
        from tasks.service import TaskWorkflowService
        from tasks.store import get_task_store

        wf = TaskWorkflowService(store=get_task_store())
        task = Task(
            owner_id=owner_id,
            title="Connect & verify the platform's own GitHub repo",
            description=(
                "Self-bootstrap: confirm access to the platform's own repository "
                f"{SELF_REPO_URL}, verify CI/health, and open a baseline health PR "
                "with any obvious fixes. Propose changes via a pull request — never "
                "push to the default branch."
            ),
            prompt=(
                f"Connect to the GitHub repository {SELF_REPO_URL}. Verify the agency "
                "can read it, summarise the current health (tests, CI, open issues), "
                "and open a PR proposing one concrete improvement. Do not merge."
            ),
            task_type="self_bootstrap",
            tags=["self-bootstrap", "github", "propose-pr"],
            source="self_bootstrap",
        )
        await wf.create_task(task, actor="system:self_bootstrap")
        log.info("Self-bootstrap seeded connect/verify task %s", task.task_id)
        return task.task_id
    except Exception as exc:  # never let task seeding break bootstrap
        log.warning("Self-bootstrap: could not seed connect task: %s", exc)
        return None


async def ensure_self_company(*, owner_id: str | None = None) -> dict:
    """Idempotently register the platform as its own company and kick off the agency.

    Returns a small status dict; never raises.
    """
    if not self_bootstrap_enabled():
        return {"status": "disabled"}

    try:
        owner_id = owner_id or os.environ.get("ADMIN_EMAIL") or "admin@llmrelay.local"

        # Deactivate stale self-bootstrap companies (wrong domain from a previous
        # deploy with old defaults) so the fresh run creates a new company with
        # the correct URLs.
        stale = await _find_stale_self_companies()
        for old_company in stale:
            try:
                from services.company_graph_store import get_company_graph_store
                store = get_company_graph_store()
                updated = old_company.model_copy(update={
                    "onboarding_status": "cancelled",
                })
                await store.update_company(updated)
                log.info(
                    "Self-bootstrap: archived stale company %s (domain=%s) "
                    "— will create a fresh one with domain=%s",
                    old_company.id, old_company.domain, _self_domain(),
                )
            except Exception as exc:
                log.warning("Self-bootstrap: could not archive stale company %s: %s",
                            old_company.id, exc)

        existing = await _find_self_company()
        # If the company exists and onboarding completed, verify it has specialists.
        # A previous deploy may have completed onboarding with 0 specialists because
        # the repo scan hit a redirect/404. Re-provision if missing.
        if existing is not None and existing.onboarding_status == "complete":
            specialist_count = await _count_specialists(existing.id)
            if specialist_count > 0:
                log.info(
                    "Self-bootstrap: company %s already exists with %d specialist(s) — skipping",
                    existing.id, specialist_count,
                )
                return {
                    "status": "exists",
                    "company_id": existing.id,
                    "onboarding_status": existing.onboarding_status,
                    "specialist_count": specialist_count,
                }
            # 0 specialists — re-provision before returning
            log.info(
                "Self-bootstrap: company %s exists but has 0 specialists — re-provisioning",
                existing.id,
            )
            provisioned = await _reprovision_specialists(existing.id, owner_id)
            # Also seed a connect task so the agency starts doing work immediately
            task_id = await _seed_connect_task(existing.id, owner_id)
            return {
                "status": "reprovisioned",
                "company_id": existing.id,
                "onboarding_status": existing.onboarding_status,
                "specialist_count": provisioned,
                "connect_task_id": task_id,
            }

        # Even when onboarding is "complete", we must verify that specialists
        # were actually provisioned and bridged to AgentStore.  A previous
        # onboarding may have completed the status flag but:
        #   - timed out before specialist provisioning ran (120 s limit)
        #   - the repo scan failed and fell through to baseline, but the
        #     baseline provisioning itself threw (DB error, ImportError)
        #   - activate_company never ran or failed silently
        # In any of those cases the company exists with status "complete" but
        # has 0 specialists and 0 agents — the agency appears healthy but
        # does nothing.  Detect and repair that.
        need_specialist_repair = False
        resolved_company_id: str | None = None

        if existing is not None and existing.onboarding_status == "complete":
            from services.company_graph_store import get_company_graph_store
            store = get_company_graph_store()
            specialists = await store.list_specialists(existing.id)
            if not specialists:
                log.warning(
                    "Self-bootstrap: company %s is 'complete' but has 0 specialists — "
                    "re-provisioning now",
                    existing.id,
                )
                need_specialist_repair = True
                resolved_company_id = existing.id
            else:
                # Specialists exist — also verify they are bridged to AgentStore
                # so the dispatcher can route work to them.
                try:
                    from agents.store import get_agent_store
                    agent_store = get_agent_store()
                    bridged = 0
                    for spec in specialists:
                        agent = await agent_store.get(
                            f"specialist:{spec.id}", owner_id=None,
                        )
                        if agent is not None:
                            bridged += 1
                    if bridged == 0:
                        log.warning(
                            "Self-bootstrap: company %s has %d specialists but "
                            "0 are bridged to AgentStore — re-activating",
                            existing.id, len(specialists),
                        )
                        # Run activate_company to bridge them
                        try:
                            from services.company_agency import get_company_agency_service
                            agency = get_company_agency_service()
                            await agency.activate_company(
                                existing.id,
                                start_runtimes=True,
                                create_schedules=True,
                            )
                            log.info(
                                "Self-bootstrap: re-activated company %s — specialists bridged",
                                existing.id,
                            )
                        except Exception as act_exc:
                            log.warning(
                                "Self-bootstrap: re-activation failed for %s: %s",
                                existing.id, act_exc,
                            )
                except Exception as bridge_check_exc:
                    log.warning(
                        "Self-bootstrap: could not check AgentStore bridge for %s: %s",
                        existing.id, bridge_check_exc,
                    )

            if not need_specialist_repair:
                return {
                    "status": "exists",
                    "company_id": existing.id,
                    "onboarding_status": existing.onboarding_status,
                    "specialist_count": len(specialists),
                }

        # ── Full onboarding (new company, incomplete, or needs specialist repair) ──
        from services.onboarding import get_onboarding_service

        onboarding = get_onboarding_service()
        # start_onboarding creates the company when the id is unknown; pass the
        # existing id when we have one so we resume rather than duplicate.
        company_id = (resolved_company_id
                      or (existing.id if existing is not None else "self-bootstrap"))

        if need_specialist_repair:
            # Onboarding is already complete — only re-run specialist
            # provisioning and activation, not the full scan flow.
            from services.specialist import get_specialist_service
            from services.company_agency import get_company_agency_service
            specialist_svc = get_specialist_service()
            # Use the baseline fallback set: backend, frontend, analytics
            baseline_types = ["backend", "frontend", "analytics"]
            results = await specialist_svc.provision_specialists_for_company(
                company_id=company_id,
                system_types=baseline_types,  # type: ignore[arg-type]
            )
            new_count = sum(1 for r in results if r.status == "success")
            log.info(
                "Self-bootstrap: re-provisioned %d specialists for %s "
                "(%d skipped as existing)",
                new_count, company_id,
                len(results) - new_count,
            )
            # Activate to bridge specialists → AgentStore + create schedules
            try:
                agency = get_company_agency_service()
                activation = await agency.activate_company(
                    company_id,
                    start_runtimes=True,
                    create_schedules=True,
                )
                log.info(
                    "Self-bootstrap: activation for repaired company %s: %s",
                    company_id, activation.get("status"),
                )
            except Exception as act_exc:
                log.warning(
                    "Self-bootstrap: activation after repair failed for %s: %s",
                    company_id, act_exc,
                )

            task_id = await _seed_connect_task(company_id, owner_id)
            return {
                "status": "repaired",
                "company_id": company_id,
                "onboarding_status": "complete",
                "specialists_provisioned": new_count,
                "connect_task_id": task_id,
            }

        # Skip the website scan: SELF_WEBSITE_URL points at *this server*, so
        # scanning it during startup creates a self-referential HTTP request
        # that hangs (the server isn't fully ready to serve yet) and blocks the
        # entire onboarding inside start_onboarding's asyncio.Lock. The repo
        # scan is kept — it detects the tech stack from GitHub and is needed
        # for specialist provisioning. If the repo scan fails (rate-limit,
        # network), the onboarding falls back to the baseline specialist set
        # (backend, frontend, analytics) so the agency still gets 6 cadences.
        #
        # Wrap the entire onboarding in a 120s timeout so a hung repo scan
        # (GitHub rate-limit, network blip) can't block the background task
        # forever. On timeout the company is still created (start_onboarding
        # creates it before scanning), so the agency can still activate.
        try:
            progress = await asyncio.wait_for(
                onboarding.start_onboarding(
                    company_id=company_id,
                    website_urls=[SELF_WEBSITE_URL],
                    repo_urls=[SELF_REPO_URL],
                    skip_website_scan=True,
                    owner_id=owner_id,
                ),
                timeout=120.0,
            )
            resolved_company_id = getattr(progress, "company_id", company_id)
        except asyncio.TimeoutError:
            log.warning(
                "Self-bootstrap: start_onboarding timed out after 120s — "
                "creating company directly as fallback"
            )
            # Fallback: create the company directly so the agency has something
            # to operate on, even if the full onboarding flow didn't complete.
            resolved_company_id = await _create_company_directly(owner_id)
        except Exception as exc:
            log.warning(
                "Self-bootstrap: start_onboarding failed (%s) — "
                "creating company directly as fallback", exc,
            )
            resolved_company_id = await _create_company_directly(owner_id)

        # Verify specialists were provisioned; re-provision if 0 (defensive —
        # the onboarding fallback should have caught this, but a transient
        # store error could leave the company with no specialists).
        specialist_count = await _count_specialists(resolved_company_id)
        if specialist_count == 0:
            log.warning(
                "Self-bootstrap: onboarding completed but 0 specialists — re-provisioning"
            )
            specialist_count = await _reprovision_specialists(resolved_company_id, owner_id)

        task_id = await _seed_connect_task(resolved_company_id, owner_id)

        log.info(
            "Self-bootstrap complete: company=%s status=%s specialists=%d connect_task=%s",
            resolved_company_id,
            getattr(progress, "status", "unknown"),
            specialist_count,
            task_id,
        )
        return {
            "status": "onboarded",
            "company_id": resolved_company_id,
            "onboarding_status": getattr(progress, "status", "unknown"),
            "specialist_count": specialist_count,
            "connect_task_id": task_id,
        }
    except Exception as exc:  # bootstrap must never crash the server
        log.warning("Self-bootstrap deferred (non-fatal): %s", exc)
        return {"status": "deferred", "error": str(exc)}

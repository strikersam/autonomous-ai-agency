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
    "local-llm-server.onrender.com",
}
_STALE_REPO_FRAGMENTS = ("local-llm-server",)


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


async def _find_self_company():
    """Return the existing self company (matched by domain), or None."""
    from services.company_graph_store import get_company_graph_store

    store = get_company_graph_store()
    domain = _self_domain()
    companies = await store.list_companies(limit=500)
    for company in companies:
        if (company.domain or "").lower() == domain:
            return company
    return None


async def _find_stale_self_companies():
    """Return companies that look like a previous self-bootstrap run but have
    a stale domain (pre-rebrand). These get deactivated so the fresh run
    creates a new company with the correct URLs."""
    from services.company_graph_store import get_company_graph_store

    store = get_company_graph_store()
    stale = []
    current_domain = _self_domain()
    companies = await store.list_companies(limit=500)
    for company in companies:
        domain = (company.domain or "").lower()
        # Match any domain that looks like a previous self-bootstrap target:
        # the old workers.dev URL, the old onrender.com URL, or the old repo name.
        if domain in (
            "local-llm-server.strikersam.workers.dev",
            "local-llm-server.onrender.com",
        ) and domain != current_domain:
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
                    "onboarding_status": "archived",
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

        from services.onboarding import get_onboarding_service

        onboarding = get_onboarding_service()
        # start_onboarding creates the company when the id is unknown; pass the
        # existing id when we have one so we resume rather than duplicate.
        company_id = existing.id if existing is not None else "self-bootstrap"
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

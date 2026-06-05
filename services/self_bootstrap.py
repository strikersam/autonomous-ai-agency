"""Self-onboarding bootstrap.

On startup the platform registers *itself* as a company — linked to its own
GitHub repo — so the agency immediately has something to operate on without a
human clicking through onboarding. The actual "connect & verify the repo" work is
handed to the platform's own agents as a Task (which flows through the working
dispatcher and the PR-autonomy gate), so the agents do the connecting.

Design notes:
  * Idempotent: keyed on the self domain. A second run no-ops when a self company
    already exists (re-onboarding only happens if it never completed).
  * Never blocks or crashes startup: callers should fire it as a background task and
    it swallows/logs all errors (a missing DB at boot must not take the server down).
  * Gated by SELF_BOOTSTRAP_ENABLED (default on; tests turn it off).
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

log = logging.getLogger("qwen-proxy")

SELF_WEBSITE_URL = os.environ.get(
    "SELF_BOOTSTRAP_URL", "https://local-llm-server.strikersam.workers.dev"
)
SELF_REPO_URL = os.environ.get(
    "SELF_BOOTSTRAP_REPO", "https://github.com/strikersam/local-llm-server"
)
SELF_COMPANY_NAME = os.environ.get("SELF_BOOTSTRAP_NAME", "Agency Core (self)")


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

        existing = await _find_self_company()
        if existing is not None and existing.onboarding_status == "complete":
            return {
                "status": "exists",
                "company_id": existing.id,
                "onboarding_status": existing.onboarding_status,
            }

        from services.onboarding import get_onboarding_service

        onboarding = get_onboarding_service()
        # start_onboarding creates the company when the id is unknown; pass the
        # existing id when we have one so we resume rather than duplicate.
        company_id = existing.id if existing is not None else "self-bootstrap"
        progress = await onboarding.start_onboarding(
            company_id=company_id,
            website_urls=[SELF_WEBSITE_URL],
            repo_urls=[SELF_REPO_URL],
            owner_id=owner_id,
        )
        resolved_company_id = getattr(progress, "company_id", company_id)

        task_id = await _seed_connect_task(resolved_company_id, owner_id)

        log.info(
            "Self-bootstrap complete: company=%s status=%s connect_task=%s",
            resolved_company_id,
            getattr(progress, "status", "unknown"),
            task_id,
        )
        return {
            "status": "onboarded",
            "company_id": resolved_company_id,
            "onboarding_status": getattr(progress, "status", "unknown"),
            "connect_task_id": task_id,
        }
    except Exception as exc:  # bootstrap must never crash the server
        log.warning("Self-bootstrap deferred (non-fatal): %s", exc)
        return {"status": "deferred", "error": str(exc)}

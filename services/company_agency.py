"""
services/company_agency.py — Company Agency Orchestration Service

After onboarding completes, this service:
1. Assigns the optimal runtime to each provisioned specialist
2. Starts all needed agent runtimes (Hermes, OpenCode, Goose, Aider, Claude Code, etc.)
3. Creates 24x7 recurring schedules: website scan, security audit, stack monitor, etc.
4. Manages the full lifecycle: activate → run 24x7 → deactivate

Architecture:
  Onboarding complete → CompanyAgencyService.activate_company()
    ├── Assign runtimes to specialists (family → optimal runtime mapping)
    ├── Start runtime containers/processes via runtimes/control.py
    ├── Create 24x7 schedules via agent/scheduler.py
    │   ├── Website health scan (every 30 min)
    │   ├── Security audit (daily)
    │   ├── Stack change detection (daily)
    │   ├── Code quality scan (daily)
    │   ├── Trend watch (every 6 hours)
    │   └── Company graph sync (every 30 min)
    └── Track agency status persistently

Usage:
    from services.company_agency import get_company_agency_service

    service = get_company_agency_service()
    status = await service.activate_company("company_123")
    health = await service.get_company_agency_health("company_123")
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

from models.company_graph import SpecialistFamily

log = logging.getLogger("company_graph.agency")

# ── Specialist Family → Optimal Runtime Mapping ──────────────────────────────
# Each specialist family has a preferred runtime based on capability match.
# Ordered by preference: first available runtime wins.
# "internal_agent" is always the final fallback (always available).

FAMILY_RUNTIME_MAP: dict[SpecialistFamily, list[str]] = {
    # Frontend specialist → Goose (web automation, browser testing)
    "frontend":      ["goose", "opencode", "aider", "internal_agent"],
    # Backend specialist → OpenCode (code generation, API work)
    "backend":       ["opencode", "claude_code", "hermes", "internal_agent"],
    # Fullstack specialist → Claude Code (complex multi-file work)
    "fullstack":     ["claude_code", "opencode", "goose", "internal_agent"],
    # Engineering specialist → Claude Code (complex engineering tasks)
    "engineering":   ["claude_code", "opencode", "aider", "internal_agent"],
    # Security specialist → Claude Code (deep security review)
    "security":      ["claude_code", "internal_agent"],
    # DevOps specialist → Aider (pair programming for infra)
    "devops":        ["aider", "hermes", "internal_agent"],
    # QA specialist → OpenCode (test generation) or InternalAgent (quick tests)
    "qa":            ["opencode", "internal_agent"],
    # Docs specialist → Goose (CLI automation for docs)
    "docs":          ["goose", "opencode", "internal_agent"],
    # Analytics specialist → Hermes (data processing)
    "analytics":     ["hermes", "internal_agent"],
    # Data specialist → Hermes (data pipelines)
    "data":          ["hermes", "internal_agent"],
    # ML specialist → Claude Code (complex ML engineering)
    "ml":            ["claude_code", "hermes", "internal_agent"],
    # Cloud specialist → Aider (infra and cloud ops)
    "cloud":         ["aider", "hermes", "internal_agent"],
    # Infra specialist → Aider (infrastructure)
    "infra":         ["aider", "hermes", "internal_agent"],
    # Architecture specialist → Claude Code (system design)
    "architecture":  ["claude_code", "opencode", "internal_agent"],
    # Product specialist → Goose (CLI/product management)
    "product":       ["goose", "internal_agent"],
    # Design specialist → Goose (web/UI tasks)
    "design":        ["goose", "internal_agent"],
    # UX specialist → Goose (web/UI tasks)
    "ux":            ["goose", "internal_agent"],
    # Mobile specialist → OpenCode (code generation)
    "mobile":        ["opencode", "claude_code", "internal_agent"],
    # E-commerce specialist → OpenCode
    "ecommerce":     ["opencode", "claude_code", "internal_agent"],
    # Operations specialist → Goose (CLI automation)
    "operations":    ["goose", "internal_agent"],
    # Agile specialist → InternalAgent (lightweight coordination)
    "agile":         ["internal_agent"],
    # Portfolio specialist → InternalAgent
    "portfolio":     ["internal_agent"],
}

# ── 24x7 Schedule Definitions ────────────────────────────────────────────────
# Each schedule dispatches tasks to the appropriate specialist + runtime.
# Cron format: minute hour day-of-month month day-of-week

COMPANY_SCHEDULES = [
    {
        "name_suffix": "website-health-scan",
        "cron": "*/30 * * * *",                # Every 30 minutes
        "instruction": (
            "Run a health scan on all registered websites for this company. "
            "Check for: HTTP 200 status, TLS certificate expiry, page load "
            "time, broken links, and any detected stack changes. Report any "
            "degradations or new detections. Update the Company Graph with "
            "findings."
        ),
        "specialist_family": "frontend",
        "priority": 4,
    },
    {
        "name_suffix": "security-audit",
        "cron": "0 9 * * *",                   # Daily at 9 AM UTC
        "instruction": (
            "Run a comprehensive security audit for this company. Check: "
            "1) Website security headers (CSP, HSTS, X-Frame-Options), "
            "2) Detected system CVEs against latest disclosures, "
            "3) Repository secret scanning, "
            "4) Dependency vulnerability check. "
            "Create GitHub issues for any HIGH/CRITICAL findings. "
            "Update the Company Graph with audit results."
        ),
        "specialist_family": "security",
        "priority": 2,
    },
    {
        "name_suffix": "stack-change-detection",
        "cron": "0 6 * * *",                   # Daily at 6 AM UTC
        "instruction": (
            "Re-scan all company websites and repositories for technology "
            "stack changes. Compare with the existing Company Graph. "
            "Detect: new frameworks, removed libraries, CMS version changes, "
            "new third-party integrations, analytics platform changes. "
            "Generate a stack change report and update the Company Graph."
        ),
        "specialist_family": "backend",
        "priority": 5,
    },
    {
        "name_suffix": "code-quality-scan",
        "cron": "0 12 * * *",                  # Daily at 12 PM UTC
        "instruction": (
            "Run a code quality analysis across all company repositories. "
            "Check: lint compliance, code duplication, complexity metrics, "
            "test coverage trends, and dependency freshness. Generate a "
            "quality report with actionable recommendations."
        ),
        "specialist_family": "engineering",
        "priority": 6,
    },
    {
        "name_suffix": "trend-watch",
        "cron": "0 */6 * * *",                 # Every 6 hours
        "instruction": (
            "Check for relevant AI/tech trends that could impact this company. "
            "Look for: new model releases, framework updates, security "
            "disclosures, competitor technology changes. If a trend is "
            "actionable, create a GitHub issue with a detailed assessment "
            "and recommended action."
        ),
        "specialist_family": "analytics",
        "priority": 7,
    },
    {
        "name_suffix": "company-graph-sync",
        "cron": "*/30 * * * *",                # Every 30 minutes
        "instruction": (
            "Sync the Company Graph with the latest data. Verify all "
            "specialists are healthy, runtimes are responsive, schedules "
            "are executing on time. Update specialist statistics (success "
            "count, error count, last activity). Generate a health dashboard "
            "summary."
        ),
        "specialist_family": "operations",
        "priority": 8,
    },
]

# ── Runtime IDs that map to runtimes/control.py ──────────────────────────────
# These are the container names used by docker compose and runtimes/control.py
RUNTIME_IDS: dict[str, str] = {
    "hermes":          "hermes",
    "opencode":        "opencode",
    "goose":           "goose",
    "aider":           "aider",
    "claude_code":     "claude_code",
    "jcode":           "jcode",
    "task_harness":    "task_harness",
    "internal_agent":  "internal_agent",
}


class CompanyAgencyService:
    """Orchestrates specialist activation, runtime startup, and 24x7 scheduling
    for a company after onboarding completes."""

    def __init__(self) -> None:
        self._agency_state: dict[str, dict[str, Any]] = {}

        # Lazy imports to avoid circular dependencies
        self._specialist_service = None
        self._onboarding_service = None
        self._scheduler = None

    # ── Properties (lazy) ────────────────────────────────────────────────────

    @property
    def specialist_service(self):
        if self._specialist_service is None:
            from services.specialist import get_specialist_service
            self._specialist_service = get_specialist_service()
        return self._specialist_service

    @property
    def scheduler(self):
        if self._scheduler is None:
            from agent.scheduler import get_scheduler
            self._scheduler = get_scheduler()
        return self._scheduler

    # ── Runtime Resolution ───────────────────────────────────────────────────

    @staticmethod
    def resolve_runtime_for_family(
        family: SpecialistFamily,
    ) -> str:
        """Return the best available runtime for a specialist family.

        Checks available runtimes in preference order. Falls back to
        'internal_agent' which is always available.
        """
        preferences = FAMILY_RUNTIME_MAP.get(family, ["internal_agent"])
        return _pick_available_runtime(preferences)

    @staticmethod
    def get_runtime_preferences(
        family: SpecialistFamily,
    ) -> list[str]:
        """Return the ordered runtime preferences for a specialist family."""
        return list(FAMILY_RUNTIME_MAP.get(family, ["internal_agent"]))

    # ── Company Activation ───────────────────────────────────────────────────

    async def activate_company(
        self,
        company_id: str,
        start_runtimes: bool = True,
        create_schedules: bool = True,
    ) -> dict[str, Any]:
        """Activate a company's AI agency after onboarding completes.

        Steps:
        1. Assign optimal runtimes to all provisioned specialists
        2. Start the required runtime containers/processes
        3. Create 24x7 recurring schedules

        Args:
            company_id: The company to activate
            start_runtimes: Whether to start runtime containers
            create_schedules: Whether to create 24x7 schedules

        Returns:
            Dict with activation status, specialist assignments, and schedule IDs
        """
        log.info("CompanyAgency: activating company %s", company_id)

        from services.company_graph_store import get_company_graph_store
        store = get_company_graph_store()

        company = await store.get_company(company_id)
        if not company:
            return {
                "status": "error",
                "error": f"Company {company_id} not found",
            }

        result: dict[str, Any] = {
            "company_id": company_id,
            "company_name": company.name,
            "status": "activating",
            "activated_at": datetime.utcnow().isoformat(),
            "specialists": [],
            "runtimes_started": [],
            "runtime_errors": [],
            "schedules_created": [],
            "schedule_errors": [],
        }

        # ── Step 1: Assign runtimes to specialists ───────────────────────────
        specialists = await store.list_specialists(company_id)
        runtime_assignments: dict[str, str] = {}

        for specialist in specialists:
            if not specialist.is_provisioned:
                continue
            if specialist.status == "disabled":
                continue

            # Re-resolve runtime using the agency service's availability-aware
            # logic (not whatever was initially set during provisioning).
            best_runtime = self.resolve_runtime_for_family(specialist.family)
            runtime_assignments[specialist.id] = best_runtime

            # Update specialist with assigned runtime
            try:
                updated = specialist.model_copy(update={
                    "runtime": best_runtime,
                    "updated_at": datetime.utcnow(),
                })
                await store.update_specialist(updated)
                result["specialists"].append({
                    "id": specialist.id,
                    "name": specialist.name,
                    "family": specialist.family,
                    "runtime_assigned": best_runtime,
                    "status": specialist.status,
                })
                log.info(
                    "CompanyAgency: assigned %s → %s (family=%s)",
                    specialist.name, best_runtime, specialist.family,
                )
            except Exception as exc:
                log.error(
                    "CompanyAgency: failed to assign runtime for %s: %s",
                    specialist.id, exc,
                )
                runtime_assignments[specialist.id] = "internal_agent"

        # ── Step 2: Start required runtimes ──────────────────────────────────
        if start_runtimes:
            unique_runtimes = set(runtime_assignments.values())
            for runtime_id in unique_runtimes:
                if runtime_id == "internal_agent":
                    continue  # Always available, no need to start
                try:
                    start_result = await self._start_runtime(runtime_id)
                    if start_result.get("status") in ("started", "already_running",
                                                       "remote_managed"):
                        result["runtimes_started"].append({
                            "runtime_id": runtime_id,
                            "status": start_result.get("status"),
                            "details": start_result,
                        })
                    else:
                        result["runtime_errors"].append({
                            "runtime_id": runtime_id,
                            "error": start_result.get("error", "Unknown error"),
                        })
                except Exception as exc:
                    result["runtime_errors"].append({
                        "runtime_id": runtime_id,
                        "error": str(exc),
                    })
                    log.warning(
                        "CompanyAgency: failed to start runtime %s: %s",
                        runtime_id, exc,
                    )

        # ── Step 3: Create 24x7 schedules ────────────────────────────────────
        if create_schedules:
            for schedule_def in COMPANY_SCHEDULES:
                try:
                    family = schedule_def["specialist_family"]
                    runtime_id = self.resolve_runtime_for_family(family)

                    schedule_name = (
                        f"company:{company_id}:{schedule_def['name_suffix']}"
                    )

                    # Build instruction with company context
                    instruction = (
                        f"Company: {company.name} (ID: {company_id})\n"
                        f"Domain: {company.domain}\n"
                        f"Task: {schedule_def['instruction']}"
                    )

                    job = self.scheduler.create(
                        name=schedule_name,
                        cron=schedule_def["cron"],
                        instruction=instruction,
                        runtime_id=runtime_id,
                        tags=[
                            "company-agency",
                            f"company:{company_id}",
                            schedule_def["name_suffix"],
                            f"priority-{schedule_def['priority']}",
                            f"runtime-{runtime_id}",
                        ],
                    )
                    result["schedules_created"].append({
                        "job_id": job.job_id,
                        "name": schedule_name,
                        "cron": schedule_def["cron"],
                        "runtime": runtime_id,
                        "status": job.status,
                    })
                    log.info(
                        "CompanyAgency: created schedule '%s' (cron=%s, runtime=%s)",
                        schedule_name, schedule_def["cron"], runtime_id,
                    )
                except Exception as exc:
                    result["schedule_errors"].append({
                        "schedule": schedule_def["name_suffix"],
                        "error": str(exc),
                    })
                    log.warning(
                        "CompanyAgency: failed to create schedule '%s': %s",
                        schedule_def["name_suffix"], exc,
                    )

        # ── Final status ─────────────────────────────────────────────────────
        error_count = (
            len(result["runtime_errors"]) + len(result["schedule_errors"])
        )
        if error_count == 0:
            result["status"] = "active"
            log.info(
                "CompanyAgency: company %s fully activated — "
                "%d specialists, %d runtimes, %d schedules",
                company_id,
                len(result["specialists"]),
                len(result["runtimes_started"]),
                len(result["schedules_created"]),
            )
        elif len(result["schedules_created"]) > 0:
            result["status"] = "degraded"
            result["degraded_reason"] = (
                f"{error_count} error(s) during activation — "
                "schedules created but some runtimes may be unavailable"
            )
        else:
            result["status"] = "failed"

        # Persist agency state
        self._agency_state[company_id] = result
        return result

    async def deactivate_company(
        self,
        company_id: str,
    ) -> dict[str, Any]:
        """Deactivate a company's AI agency.

        Stops all company-specific schedules and optionally stops runtimes.
        Does NOT delete specialists — they remain provisioned but idle.
        """
        log.info("CompanyAgency: deactivating company %s", company_id)

        result: dict[str, Any] = {
            "company_id": company_id,
            "status": "deactivating",
            "schedules_removed": 0,
            "errors": [],
        }

        # Remove all company schedules
        try:
            all_jobs = self.scheduler.list()
            company_jobs = [
                j for j in all_jobs
                if f"company:{company_id}" in (j.tags or [])
            ]
            for job in company_jobs:
                try:
                    self.scheduler.delete(job.job_id)
                    result["schedules_removed"] += 1
                except Exception as exc:
                    result["errors"].append(
                        f"Failed to delete schedule {job.job_id}: {exc}"
                    )
        except Exception as exc:
            result["errors"].append(f"Schedule cleanup error: {exc}")

        result["status"] = "inactive"
        self._agency_state.pop(company_id, None)
        log.info(
            "CompanyAgency: company %s deactivated — removed %d schedules",
            company_id, result["schedules_removed"],
        )
        return result

    async def get_company_agency_health(
        self,
        company_id: str,
    ) -> dict[str, Any]:
        """Get the current agency health status for a company."""
        from services.company_graph_store import get_company_graph_store
        store = get_company_graph_store()

        company = await store.get_company(company_id)
        if not company:
            return {"status": "error", "error": f"Company {company_id} not found"}

        # Get specialists with their runtime assignments
        specialists = await store.list_specialists(company_id)
        specialist_health = []
        for s in specialists:
            health = await self._check_runtime_health(s.runtime)
            specialist_health.append({
                "id": s.id,
                "name": s.name,
                "family": s.family,
                "runtime": s.runtime,
                "runtime_healthy": health.get("available", False),
                "runtime_error": health.get("error"),
                "status": s.status,
                "success_count": s.success_count,
                "error_count": s.error_count,
                "last_activity": s.last_activity.isoformat() if s.last_activity else None,
            })

        # Get company schedules
        company_schedules = []
        try:
            all_jobs = self.scheduler.list()
            company_schedules = [
                {
                    "job_id": j.job_id,
                    "name": j.name,
                    "cron": j.cron,
                    "enabled": j.enabled,
                    "status": j.status,
                    "last_run": j.last_run.isoformat() if j.last_run else None,
                    "run_count": j.run_count,
                }
                for j in all_jobs
                if f"company:{company_id}" in (j.tags or [])
            ]
        except Exception as exc:
            log.warning("CompanyAgency: schedule health check failed: %s", exc)

        # Count runtimes and their health
        active_runtimes = set(
            s.runtime for s in specialists
            if s.runtime and s.is_provisioned
        )
        runtime_health = {}
        for rt in active_runtimes:
            health = await self._check_runtime_health(rt)
            runtime_health[rt] = health

        # Agency state
        agency = self._agency_state.get(company_id, {})
        active_schedules = sum(1 for s in company_schedules if s.get("enabled"))

        return {
            "company_id": company_id,
            "company_name": company.name,
            "agency_status": agency.get("status", "unknown"),
            "activated_at": agency.get("activated_at"),
            "specialists": {
                "total": len(specialist_health),
                "healthy": sum(1 for s in specialist_health if s["runtime_healthy"]),
                "unhealthy": sum(1 for s in specialist_health if not s["runtime_healthy"]),
                "details": specialist_health,
            },
            "runtimes": {
                "total": len(active_runtimes),
                "healthy": sum(1 for v in runtime_health.values() if v.get("available")),
                "unhealthy": sum(1 for v in runtime_health.values() if not v.get("available")),
                "details": runtime_health,
            },
            "schedules": {
                "total": len(company_schedules),
                "active": active_schedules,
                "details": company_schedules,
            },
            "is_healthy": (
                agency.get("status") == "active"
                and all(s["runtime_healthy"] for s in specialist_health)
                and active_schedules > 0
            ),
        }

    # ── Runtime Management Helpers ────────────────────────────────────────────

    async def _start_runtime(
        self,
        runtime_id: str,
    ) -> dict[str, Any]:
        """Start a runtime container or process.

        Delegates to runtimes/control.py for Docker/local subprocess management.
        """
        if runtime_id == "internal_agent":
            return {"status": "always_available", "message": "Internal agent is always available"}

        try:
            from runtimes.control import start_runtime as _start_rt
            return await _start_rt(runtime_id)
        except ImportError:
            return {
                "status": "unavailable",
                "error": "runtimes/control.py not importable",
            }
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
            }

    async def _check_runtime_health(
        self,
        runtime_id: str | None,
    ) -> dict[str, Any]:
        """Check if a runtime is healthy and available."""
        if not runtime_id or runtime_id == "internal_agent":
            return {"available": True, "message": "Always available"}

        try:
            from runtimes.manager import get_runtime_manager
            manager = get_runtime_manager()
            runtime = manager.get_runtime(runtime_id)
            if runtime is None:
                return {
                    "available": False,
                    "error": f"Runtime '{runtime_id}' not registered",
                }
            health = runtime.get("health", {})
            available = health.get("available", False) if isinstance(health, dict) else False
            return {
                "available": available,
                "latency_ms": health.get("latency_ms") if isinstance(health, dict) else None,
                "error": health.get("error") if isinstance(health, dict) else None,
            }
        except ImportError:
            return {"available": False, "error": "Runtime manager not available"}
        except Exception as exc:
            return {"available": False, "error": str(exc)}

    async def start_all_company_runtimes(
        self,
        company_id: str,
    ) -> dict[str, Any]:
        """Start all runtimes assigned to a company's specialists."""
        from services.company_graph_store import get_company_graph_store
        store = get_company_graph_store()

        specialists = await store.list_specialists(company_id)
        runtimes = set(
            s.runtime for s in specialists
            if s.runtime and s.runtime != "internal_agent" and s.is_provisioned
        )

        results = {}
        for rt in runtimes:
            results[rt] = await self._start_runtime(rt)

        return {
            "company_id": company_id,
            "runtimes": results,
            "started": sum(1 for v in results.values()
                          if v.get("status") in ("started", "already_running",
                                                  "remote_managed", "always_available")),
            "failed": sum(1 for v in results.values()
                         if v.get("status") not in ("started", "already_running",
                                                     "remote_managed", "always_available")),
        }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _pick_available_runtime(preferences: list[str]) -> str:
    """Pick the first runtime from the preference list that is available.

    Checks:
    1. Runtime is registered in the RuntimeManager
    2. Runtime health check passes
    3. Falls back to 'internal_agent' if nothing available
    """
    for runtime_id in preferences:
        if runtime_id == "internal_agent":
            return "internal_agent"
        if _is_runtime_available_sync(runtime_id):
            return runtime_id
    return "internal_agent"


def _is_runtime_available_sync(runtime_id: str) -> bool:
    """Synchronous check if a runtime is available.

    Checks environment flags and registered adapter health.
    """
    # Check env flag (opt-in runtimes)
    env_flags = {
        "hermes":       "RUNTIME_HERMES_ENABLED",
        "opencode":     "RUNTIME_OPENCODE_ENABLED",
        "goose":        "RUNTIME_GOOSE_ENABLED",
        "aider":        "RUNTIME_AIDER_ENABLED",
        "claude_code":  "RUNTIME_CLAUDE_CODE_ENABLED",
        "jcode":        "RUNTIME_JCODE_ENABLED",
        "task_harness": "TASK_HARNESS_ENABLED",
    }
    flag = env_flags.get(runtime_id)
    if flag:
        raw = os.environ.get(flag, "").strip().lower()
        if raw and raw not in ("true", "1", "yes"):
            return False

    # Check if registered in RuntimeManager
    try:
        from runtimes.manager import get_runtime_manager
        manager = get_runtime_manager()
        runtime = manager.get_runtime(runtime_id)
        if runtime is None:
            return False
        health = runtime.get("health", {})
        return health.get("available", False) if isinstance(health, dict) else False
    except Exception:
        # If we can't check, assume it might be available
        return runtime_id in ("internal_agent",)


# ── Singleton ────────────────────────────────────────────────────────────────

_company_agency_service: CompanyAgencyService | None = None


def get_company_agency_service() -> CompanyAgencyService:
    """Get the singleton CompanyAgency service instance."""
    global _company_agency_service
    if _company_agency_service is None:
        _company_agency_service = CompanyAgencyService()
    return _company_agency_service


def set_company_agency_service(service: CompanyAgencyService) -> None:
    """Set the singleton CompanyAgency service instance (for testing)."""
    global _company_agency_service
    _company_agency_service = service

"""
SEO / GEO / AIO Audit API Router

Endpoints for the world-class SEO audit engine (issue #533):

- GET  /api/seo/checks                                     full check catalog
- POST /api/company/{company_id}/seo/audit                 run an audit
- GET  /api/company/{company_id}/seo/audits                list past audits
- GET  /api/company/{company_id}/seo/audits/{audit_id}     full report
- GET  /api/company/{company_id}/seo/audits/{audit_id}/export   csv|json|markdown|urls|issues|pdf
- POST /api/company/{company_id}/seo/audits/{audit_id}/delegate create agent tasks
- POST /api/company/{company_id}/seo/fix                   repo-aware auto-fix
- POST /api/company/{company_id}/seo/audits/{audit_id}/roadmap   Now/Next/Later roadmap from findings
- POST /api/company/{company_id}/seo/audits/{audit_id}/sprint    agile sprint plan from findings
- POST /api/company/{company_id}/seo/audits/{audit_id}/pipeline  full pipeline: roadmap + sprint

Audits are persisted (best-effort) into the Company Graph as KnowledgeItems
so specialists and the orchestrator can build on the evidence.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path as FsPath
from typing import List, Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field

from backend.company_api import _get_current_user_thunk, _resolve_user_id, get_company_access
from models.seo_audit import (
    SeoAuditReport,
    SeoAuditRequest,
    SeoAuditSummary,
    SeoCheckDefinition,
    SeoDelegationTask,
    SeoFixRequest,
    SeoFixResult,
)
from services.seo_audit import (
    SeoAuditEngine,
    get_report,
    list_reports,
    report_to_csv,
    report_to_issues_csv,
    report_to_markdown,
    report_to_pages_csv,
    save_report,
)
from services.seo_checks import list_checks
from services.seo_fixer import run_fixes
from services.seo_report_pdf import report_to_pdf

log = logging.getLogger("seo_api")

router = APIRouter(prefix="/api", tags=["seo"])


def _workspace_root() -> FsPath:
    """Root directory under which repo fixes are allowed to operate."""
    return FsPath(os.environ.get("SEO_FIX_WORKSPACE_ROOT", "workspace")).resolve()


# Background: the SEO audit registry (services.seo_audit.save_report / get_report)
# is an in-memory ``OrderedDict`` keyed by audit_id. If the server restarts
# between POST /audit (which saves a 'pending' stub immediately) and the
# background crawl completing, the in-memory stub is the only record the
# in-flight client ever sees \u2014 and that stub persists as 'pending' forever,
# because nothing on the GET path checks for staleness. This guard converts
# those perpetual 'pending' stubs into a clear 'failed' response so the
# dashboard stops polling forever and the operator gets a clean reason.
_SEO_PENDING_EXPIRY_SECONDS = float(os.environ.get("SEO_AUDIT_PENDING_EXPIRY_SEC", "1800"))  # 30 min default


def _expire_stale_pending_report(report: SeoAuditReport) -> None:
    """Auto-fail a pending SEO audit stub that is older than ``_SEO_PENDING_EXPIRY_SECONDS``.

    Best-effort: any error is logged at WARNING; the function never raises,
    so the GET endpoint can call it unconditionally without risk. ``save_report``
    is locked and idempotent, so concurrent polls racing the expire just
    re-stamp the same 'failed' state.
    """
    if report.status != "pending":
        return
    started = report.started_at
    if started is None:
        return
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    if elapsed < _SEO_PENDING_EXPIRY_SECONDS:
        return
    # SeoAuditReport is a Pydantic frozen model: build the updated copy via
    # model_copy(update=...) (so save_report stores the new 'failed' state) and
    # leave the inbound `report` untouched. The caller can still reference it
    # without seeing the side-effect.
    new_state = report.model_copy(update={
        "status": "failed",
        "error": (
            f"Audit still 'pending' after {elapsed:.0f}s \u2014 likely lost to a "
            "server restart (in-memory registry was cleared). Re-run the audit."
        ),
        "completed_at": datetime.now(timezone.utc),
    })
    try:
        save_report(new_state)
        log.warning(
            "SEO audit %s expired (pending for %.0fs, threshold %.0fs) \u2014 auto-failed and saved.",
            report.audit_id, elapsed, _SEO_PENDING_EXPIRY_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 - stale-state cleanup must never raise
        log.warning("SEO audit %s expire-save failed (non-fatal): %s", report.audit_id, exc)


@router.get("/seo/checks", response_model=List[SeoCheckDefinition])
async def seo_check_catalog(
    user: dict = Depends(_get_current_user_thunk),
) -> List[SeoCheckDefinition]:
    """Return the full SEO/GEO/AIO check catalog.

    Static metadata only, but gated behind authentication like every other
    non-doctor endpoint per the repo's API guidelines.
    """
    return list_checks()


@router.post("/company/{company_id}/seo/audit", response_model=SeoAuditReport)
async def run_seo_audit(
    company_id: str = Path(..., description="Company ID"),
    request: SeoAuditRequest = Body(...),
    user: dict = Depends(_get_current_user_thunk),
) -> SeoAuditReport:
    """Run a full SEO/GEO/AIO audit against a website and persist the evidence."""
    company = await get_company_access(company_id, user)

    engine = SeoAuditEngine()
    report = await engine.run(request, company_id=company.id)
    save_report(report)

    # Best-effort: capture the executive summary into the Company Graph so the
    # orchestrator and specialists can act on it. Never fail the audit on this.
    if report.status == "success":
        try:
            from models.company_graph import KnowledgeItem
            from services.company_graph_store import get_company_graph_store

            store = get_company_graph_store()
            await store.create_knowledge_item(KnowledgeItem(
                title=f"SEO audit {report.audit_id} - {report.website_url} "
                      f"(health {report.health_score}/100)",
                knowledge_type="learning",
                content=report_to_markdown(report),
                tags=["seo-audit", f"company:{company.id}", f"audit:{report.audit_id}"],
                source="automated_scan",
            ))
        except Exception as exc:  # noqa: BLE001 - persistence is best-effort
            log.warning("Could not persist SEO audit %s to company graph: %s",
                        report.audit_id, exc)

    return report


@router.get("/company/{company_id}/seo/audits", response_model=List[SeoAuditSummary])
async def list_seo_audits(
    company_id: str = Path(..., description="Company ID"),
    user: dict = Depends(_get_current_user_thunk),
) -> List[SeoAuditSummary]:
    """List stored audits for this company (most recent first)."""
    company = await get_company_access(company_id, user)
    return list_reports(company_id=company.id)


@router.get("/company/{company_id}/seo/audits/{audit_id}", response_model=SeoAuditReport)
async def get_seo_audit(
    company_id: str = Path(..., description="Company ID"),
    audit_id: str = Path(..., description="Audit ID"),
    user: dict = Depends(_get_current_user_thunk),
) -> SeoAuditReport:
    """Fetch a complete stored audit report.

    Side-effect: an audit whose stub is still 'pending' longer than
    ``SEO_AUDIT_PENDING_EXPIRY_SEC`` (env, default 30 min) is auto-failed
    and persisted so the client sees 'failed' with an explanatory error
    instead of perpetual 'pending' (which happens when the server restarted
    after the stub was written but before the background crawl completed).
    """
    company = await get_company_access(company_id, user)
    report = get_report(audit_id)
    if report is None or report.company_id != company.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit {audit_id} not found for this company",
        )
    _expire_stale_pending_report(report)
    # Refresh the response body from the registry so the client sees the
    # auto-failed state on THIS poll (not just on the next one). Without
    # the re-fetch the current request would still surface 'pending' even
    # though the registry now holds 'failed', which contradicts the
    # docstring above.
    refreshed = get_report(audit_id)
    return refreshed if refreshed is not None else report


@router.get("/company/{company_id}/seo/audits/{audit_id}/export")
async def export_seo_audit(
    company_id: str = Path(..., description="Company ID"),
    audit_id: str = Path(..., description="Audit ID"),
    fmt: Literal["csv", "json", "markdown", "urls", "issues", "pdf"] = Query(
        "csv", description="Export format"
    ),
    user: dict = Depends(_get_current_user_thunk),
):
    """Export a stored audit.

    - ``csv``       aggregated findings, Screaming Frog issues_overview-compatible
    - ``urls``      per-URL inventory (one row per crawled page)
    - ``issues``    every individual issue occurrence
    - ``markdown``  full heavy report: findings, delegation plan, per-page details
    - ``json``      the complete report object
    - ``pdf``       CTO-level report: cover, executive summary, methodology,
                    pillar deep-dives, WSJF roadmap and worst-pages appendices
    """
    company = await get_company_access(company_id, user)
    report = get_report(audit_id)
    if report is None or report.company_id != company.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit {audit_id} not found for this company",
        )
    if fmt == "json":
        return report
    if fmt == "markdown":
        return PlainTextResponse(report_to_markdown(report), media_type="text/markdown")
    if fmt == "pdf":
        return Response(
            content=report_to_pdf(report),
            media_type="application/pdf",
            headers={"Content-Disposition":
                     f'attachment; filename="seo-audit-{audit_id}.pdf"'},
        )
    renderer = {"csv": report_to_csv, "urls": report_to_pages_csv,
                "issues": report_to_issues_csv}[fmt]
    return PlainTextResponse(
        renderer(report),
        media_type="text/csv",
        headers={"Content-Disposition":
                 f'attachment; filename="seo-audit-{audit_id}-{fmt}.csv"'},
    )


class SeoDelegationCreateRequest(BaseModel):
    """Options for turning an audit's delegation plan into real agent tasks."""
    min_priority: Literal["high", "medium", "low"] = Field(
        default="low", description="Only delegate packages at or above this priority"
    )
    task_keys: List[str] = Field(
        default_factory=list,
        description="Restrict to these delegation task_keys; empty = all"
    )


class SeoDelegationCreateResult(BaseModel):
    audit_id: str
    created: int
    tasks: List[dict] = Field(default_factory=list)


@router.post(
    "/company/{company_id}/seo/audits/{audit_id}/delegate",
    response_model=SeoDelegationCreateResult,
)
async def delegate_seo_findings(
    company_id: str = Path(..., description="Company ID"),
    audit_id: str = Path(..., description="Audit ID"),
    request: SeoDelegationCreateRequest = Body(default=SeoDelegationCreateRequest()),
    user: dict = Depends(_get_current_user_thunk),
) -> SeoDelegationCreateResult:
    """Create real agent tasks from the audit's delegation plan.

    Each work package becomes a task on the board (source=seo_audit), ready to
    be picked up by the suggested specialist or the orchestrator.
    """
    company = await get_company_access(company_id, user)
    report = get_report(audit_id)
    if report is None or report.company_id != company.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit {audit_id} not found for this company",
        )

    from tasks.models import Task, TaskPriority
    from tasks.store import get_task_store

    priority_rank = {"high": 0, "medium": 1, "low": 2}
    priority_map = {"high": TaskPriority.HIGH, "medium": TaskPriority.MEDIUM, "low": TaskPriority.LOW}

    owner_id = _resolve_user_id(user)
    store = get_task_store()
    created: List[dict] = []
    for pkg in report.delegation_plan:
        if priority_rank[pkg.priority] > priority_rank[request.min_priority]:
            continue
        if request.task_keys and pkg.task_key not in request.task_keys:
            continue
        description = (
            f"SEO audit `{report.audit_id}` of {report.website_url} "
            f"(health {report.health_score}/100) - {pkg.category} remediation.\n\n"
            f"**Suggested specialist:** {pkg.suggested_specialist}\n"
            f"**WSJF:** {pkg.wsjf_score} | "
            f"**Recoverable revenue:** {pkg.estimated_monthly_value:,.0f}/mo\n"
            f"**Effort:** {pkg.effort} | **Pillar:** {pkg.pillar} | "
            f"**URLs affected:** {pkg.urls_affected}"
            f"{' | **Auto-fixable** via POST /api/company/' + company.id + '/seo/fix' if pkg.auto_fixable else ''}\n\n"
            f"### Instructions\n{pkg.instructions}\n\n"
            f"### Sample URLs\n" + "\n".join(f"- {u}" for u in pkg.sample_urls)
        )
        task = Task(
            owner_id=owner_id,
            title=f"[SEO] {pkg.title}",
            description=description[:32_000],
            priority=priority_map[pkg.priority],
            tags=["seo-audit", pkg.task_key, f"company:{company.id}"][:20],
            source="seo_audit",
            source_id=report.audit_id,
        )
        await store.create(task)
        created.append({
            "task_id": task.task_id,
            "task_key": pkg.task_key,
            "title": task.title,
            "priority": pkg.priority,
            "suggested_specialist": pkg.suggested_specialist,
        })

    log.info("Delegated %d SEO work package(s) from audit %s", len(created), audit_id)
    return SeoDelegationCreateResult(
        audit_id=audit_id, created=len(created), tasks=created,
    )


# =============================================================================
# SEO → PORTFOLIO / AGILE BRIDGE ENDPOINTS
# =============================================================================

class SeoRoadmapRequest(BaseModel):
    """Options for building a Now/Next/Later roadmap from SEO findings."""
    capacity_per_horizon: int = Field(
        default=20, ge=1, le=100,
        description="Job-size capacity for each of Now/Next/Later horizons"
    )
    min_priority: Literal["high", "medium", "low"] = Field(
        default="low", description="Only include packages at or above this priority"
    )


class SeoRoadmapResponse(BaseModel):
    """Response for the SEO roadmap endpoint."""
    audit_id: str
    website_url: str
    total_initiatives: int
    scheduled_initiatives: int
    unscheduled_initiatives: int
    capacity_per_horizon: int
    roadmap: dict[str, List[dict]]
    markdown: str


@router.post(
    "/company/{company_id}/seo/audits/{audit_id}/roadmap",
    response_model=SeoRoadmapResponse,
)
async def build_seo_roadmap(
    company_id: str = Path(..., description="Company ID"),
    audit_id: str = Path(..., description="Audit ID"),
    request: SeoRoadmapRequest = Body(default=SeoRoadmapRequest()),
    user: dict = Depends(_get_current_user_thunk),
) -> SeoRoadmapResponse:
    """Build a Now/Next/Later roadmap from the audit's delegation plan.

    Converts each SeoDelegationTask into a portfolio Initiative (with WSJF
    scores preserved), registers them in a PortfolioManager, and lays them
    onto a three-horizon roadmap using capacity-based allocation.

    This directly implements the "turn SEO backlog into roadmap" workflow
    from Search Engine Land's methodology.
    """
    company = await get_company_access(company_id, user)
    report = get_report(audit_id)
    if report is None or report.company_id != company.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit {audit_id} not found for this company",
        )

    # Filter delegation plan by priority
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    filtered_tasks = [
        pkg for pkg in report.delegation_plan
        if priority_rank[pkg.priority] <= priority_rank[request.min_priority]
    ]

    if not filtered_tasks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No delegation tasks match the priority filter",
        )

    from agents.seo_portfolio_bridge import build_seo_roadmap

    roadmap_plan = build_seo_roadmap(
        filtered_tasks,
        audit_id=audit_id,
        website_url=report.website_url,
        capacity_per_horizon=request.capacity_per_horizon,
    )

    # Convert roadmap to serializable format
    roadmap_dict = {}
    for horizon, initiatives in roadmap_plan.roadmap.items():
        roadmap_dict[horizon] = [
            {
                "initiative_id": i.initiative_id,
                "title": i.title,
                "wsjf": round(i.wsjf, 2),
                "job_size": i.job_size,
                "business_value": i.business_value,
                "time_criticality": i.time_criticality,
                "risk_reduction": i.risk_reduction,
                "horizon": i.horizon.value,
                "status": i.status.value,
                "estimated_monthly_value": getattr(i, 'estimated_monthly_value', 0),
            }
            for i in initiatives
        ]

    return SeoRoadmapResponse(
        audit_id=audit_id,
        website_url=report.website_url,
        total_initiatives=roadmap_plan.total_initiatives,
        scheduled_initiatives=roadmap_plan.scheduled_initiatives,
        unscheduled_initiatives=roadmap_plan.unscheduled_initiatives,
        capacity_per_horizon=roadmap_plan.capacity_per_horizon,
        roadmap=roadmap_dict,
        markdown=roadmap_plan.to_markdown(),
    )


class SeoSprintRequest(BaseModel):
    """Options for planning an agile sprint from SEO findings."""
    sprint_name: str = Field(..., min_length=1, max_length=100, description="Name for the sprint")
    sprint_goal: str = Field(default="", max_length=500, description="Optional sprint goal")
    capacity: int = Field(default=20, ge=1, le=100, description="Total job-size capacity for the sprint")
    min_priority: Literal["high", "medium", "low"] = Field(
        default="low", description="Only include packages at or above this priority"
    )


class SeoSprintResponse(BaseModel):
    """Response for the SEO sprint planning endpoint."""
    audit_id: str
    website_url: str
    sprint_id: str
    sprint_name: str
    sprint_goal: str
    status: str
    capacity_total: int
    capacity_used: int
    committed_initiatives: int
    deferred_initiatives: int
    committed: List[dict]
    deferred: List[dict]
    markdown: str


@router.post(
    "/company/{company_id}/seo/audits/{audit_id}/sprint",
    response_model=SeoSprintResponse,
)
async def plan_seo_sprint(
    company_id: str = Path(..., description="Company ID"),
    audit_id: str = Path(..., description="Audit ID"),
    request: SeoSprintRequest = Body(...),
    user: dict = Depends(_get_current_user_thunk),
) -> SeoSprintResponse:
    """Plan an agile sprint from the audit's delegation plan.

    Converts delegation tasks to portfolio initiatives, allocates capacity
    by WSJF priority, creates a new AgileSprint with one UserStory per
    committed initiative, and links each initiative to the sprint.

    The sprint is left in PLANNING state for a human (or Delivery Manager)
    to start.
    """
    company = await get_company_access(company_id, user)
    report = get_report(audit_id)
    if report is None or report.company_id != company.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit {audit_id} not found for this company",
        )

    # Filter delegation plan by priority
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    filtered_tasks = [
        pkg for pkg in report.delegation_plan
        if priority_rank[pkg.priority] <= priority_rank[request.min_priority]
    ]

    if not filtered_tasks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No delegation tasks match the priority filter",
        )

    from agents.seo_portfolio_bridge import plan_seo_sprint

    sprint_plan = plan_seo_sprint(
        filtered_tasks,
        audit_id=audit_id,
        website_url=report.website_url,
        sprint_name=request.sprint_name,
        sprint_goal=request.sprint_goal,
        capacity=request.capacity,
    )

    committed = [
        {
            "initiative_id": i.initiative_id,
            "title": i.title,
            "wsjf": round(i.wsjf, 2),
            "job_size": i.job_size,
            "estimated_monthly_value": getattr(i, 'estimated_monthly_value', 0),
        }
        for i in sprint_plan.plan.committed
    ]
    deferred = [
        {
            "initiative_id": i.initiative_id,
            "title": i.title,
            "wsjf": round(i.wsjf, 2),
            "job_size": i.job_size,
            "estimated_monthly_value": getattr(i, 'estimated_monthly_value', 0),
        }
        for i in sprint_plan.plan.deferred
    ]

    return SeoSprintResponse(
        audit_id=audit_id,
        website_url=report.website_url,
        sprint_id=sprint_plan.sprint.sprint_id,
        sprint_name=sprint_plan.sprint.name,
        sprint_goal=sprint_plan.sprint.goal,
        status=sprint_plan.sprint.status.value,
        capacity_total=sprint_plan.capacity_total,
        capacity_used=sprint_plan.capacity_used,
        committed_initiatives=len(committed),
        deferred_initiatives=len(deferred),
        committed=committed,
        deferred=deferred,
        markdown=sprint_plan.to_markdown(),
    )


class SeoPipelineRequest(BaseModel):
    """Options for the full SEO → Agile pipeline."""
    capacity_per_horizon: int = Field(
        default=20, ge=1, le=100,
        description="Job-size capacity for each roadmap horizon"
    )
    sprint_capacity: int = Field(
        default=20, ge=1, le=100,
        description="Job-size capacity for the sprint"
    )
    sprint_name: Optional[str] = Field(
        default=None, max_length=100, description="Sprint name (auto-generated if omitted)"
    )
    sprint_goal: str = Field(default="", max_length=500, description="Optional sprint goal")
    min_priority: Literal["high", "medium", "low"] = Field(
        default="low", description="Only include packages at or above this priority"
    )
    create_sprint: bool = Field(default=True, description="Whether to create a sprint plan")


class SeoPipelineResponse(BaseModel):
    """Response for the full SEO → Agile pipeline endpoint."""
    audit_id: str
    website_url: str
    total_initiatives: int
    roadmap: dict[str, List[dict]]
    roadmap_markdown: str
    sprint: Optional[dict] = None
    sprint_markdown: Optional[str] = None
    full_markdown: str


@router.post(
    "/company/{company_id}/seo/audits/{audit_id}/pipeline",
    response_model=SeoPipelineResponse,
)
async def run_seo_pipeline(
    company_id: str = Path(..., description="Company ID"),
    audit_id: str = Path(..., description="Audit ID"),
    request: SeoPipelineRequest = Body(default=SeoPipelineRequest()),
    user: dict = Depends(_get_current_user_thunk),
) -> SeoPipelineResponse:
    """Run the full pipeline: SEO audit → Portfolio → Roadmap → Sprint.

    This is the "one call does it all" endpoint for turning an SEO audit into
    actionable agile delivery artifacts. It:
    1. Filters the audit's delegation plan by priority
    2. Converts tasks to portfolio initiatives with WSJF scores
    3. Builds a Now/Next/Later roadmap
    4. Optionally creates an agile sprint plan

    The result is a complete actionable plan that competes for capacity
    alongside product initiatives using the same WSJF prioritisation.
    """
    company = await get_company_access(company_id, user)
    report = get_report(audit_id)
    if report is None or report.company_id != company.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit {audit_id} not found for this company",
        )

    # Filter delegation plan by priority
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    filtered_tasks = [
        pkg for pkg in report.delegation_plan
        if priority_rank[pkg.priority] <= priority_rank[request.min_priority]
    ]

    if not filtered_tasks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No delegation tasks match the priority filter",
        )

    from agents.seo_portfolio_bridge import run_seo_to_agile_pipeline

    result = run_seo_to_agile_pipeline(
        filtered_tasks,
        audit_id=audit_id,
        website_url=report.website_url,
        capacity_per_horizon=request.capacity_per_horizon,
        sprint_capacity=request.sprint_capacity,
        sprint_name=request.sprint_name,
        sprint_goal=request.sprint_goal,
        create_sprint=request.create_sprint,
    )

    # Convert roadmap to serializable format
    roadmap_dict = {}
    for horizon, initiatives in result.roadmap.roadmap.items():
        roadmap_dict[horizon] = [
            {
                "initiative_id": i.initiative_id,
                "title": i.title,
                "wsjf": round(i.wsjf, 2),
                "job_size": i.job_size,
                "business_value": i.business_value,
                "time_criticality": i.time_criticality,
                "risk_reduction": i.risk_reduction,
                "horizon": i.horizon.value,
                "status": i.status.value,
                "estimated_monthly_value": getattr(i, 'estimated_monthly_value', 0),
            }
            for i in initiatives
        ]

    sprint_data = None
    sprint_md = None
    if result.sprint:
        sprint_data = {
            "sprint_id": result.sprint.sprint.sprint_id,
            "sprint_name": result.sprint.sprint.name,
            "sprint_goal": result.sprint.sprint.goal,
            "status": result.sprint.sprint.status.value,
            "capacity_total": result.sprint.capacity_total,
            "capacity_used": result.sprint.capacity_used,
            "committed": [
                {
                    "initiative_id": i.initiative_id,
                    "title": i.title,
                    "wsjf": round(i.wsjf, 2),
                    "job_size": i.job_size,
                    "estimated_monthly_value": getattr(i, 'estimated_monthly_value', 0),
                }
                for i in result.sprint.plan.committed
            ],
            "deferred": [
                {
                    "initiative_id": i.initiative_id,
                    "title": i.title,
                    "wsjf": round(i.wsjf, 2),
                    "job_size": i.job_size,
                    "estimated_monthly_value": getattr(i, 'estimated_monthly_value', 0),
                }
                for i in result.sprint.plan.deferred
            ],
        }
        sprint_md = result.sprint.to_markdown()

    return SeoPipelineResponse(
        audit_id=audit_id,
        website_url=report.website_url,
        total_initiatives=len(result.initiatives),
        roadmap=roadmap_dict,
        roadmap_markdown=result.roadmap.to_markdown(),
        sprint=sprint_data,
        sprint_markdown=sprint_md,
        full_markdown=result.to_markdown(),
    )


@router.post("/company/{company_id}/seo/fix", response_model=SeoFixResult)
async def run_seo_fixes(
    company_id: str = Path(..., description="Company ID"),
    request: SeoFixRequest = Body(...),
    user: dict = Depends(_get_current_user_thunk),
) -> SeoFixResult:
    """Run the repo-aware auto-fixer against this company's workspace checkout.

    Authorization boundary: the repo path must live inside the company's own
    workspace directory (<SEO_FIX_WORKSPACE_ROOT>/<company_id>/...), so an
    operator of one company can never read or modify another company's
    checkout, regardless of the path they submit.
    """
    company = await get_company_access(company_id, user)

    company_root = (_workspace_root() / company.id).resolve()
    target = FsPath(request.repo_path).resolve()
    try:
        target.relative_to(company_root)
    except ValueError:
        log.warning("Rejected SEO fix: repo_path %s outside company workspace %s",
                    target, company_root)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="repo_path must be inside this company's workspace directory",
        )
    if not target.is_dir():
        log.warning("Rejected SEO fix: repo_path does not exist: %s", target)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="repo_path not found in this company's workspace",
        )

    # run_fixes walks and (with apply) writes files - keep it off the event loop.
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(
        run_fixes, request.model_copy(update={"repo_path": str(target)}),
    )
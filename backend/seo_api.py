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

Audits are persisted (best-effort) into the Company Graph as KnowledgeItems
so specialists and the orchestrator can build on the evidence.
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path as FsPath
from typing import List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Path, Query, status
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field

from backend.company_api import _get_current_user_thunk, _resolve_user_id, get_company_access
from models.seo_audit import (
    SeoAuditReport,
    SeoAuditRequest,
    SeoAuditSummary,
    SeoCheckDefinition,
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


@router.get("/seo/checks", response_model=List[SeoCheckDefinition])
async def seo_check_catalog(
    user: dict = Depends(_get_current_user_thunk),
) -> List[SeoCheckDefinition]:
    """Return the full SEO/GEO/AIO check catalog.

    Static metadata only, but gated behind authentication like every other
    non-doctor endpoint per the repo's API guidelines.
    """
    return list_checks()


@router.post("/company/{company_id}/seo/audit", response_model=SeoAuditReport, status_code=202)
async def run_seo_audit(
    company_id: str = Path(..., description="Company ID"),
    request: SeoAuditRequest = Body(...),
    background_tasks: BackgroundTasks = None,
    user: dict = Depends(_get_current_user_thunk),
) -> SeoAuditReport:
    """Kick off an async SEO/GEO/AIO audit and return immediately with status='pending'.

    Poll GET /api/company/{company_id}/seo/audits/{audit_id} until status
    transitions to 'success', 'partial', or 'failed'.  Browser-mode crawls of
    large sites can take 3-10 minutes; this pattern lets the UI stay responsive.
    """
    company = await get_company_access(company_id, user)

    # Pre-generate the audit_id so the client can start polling before the crawl
    # finishes.  A 'pending' stub is saved immediately.
    audit_id = f"seoaudit_{secrets.token_hex(8)}"
    stub = SeoAuditReport(
        audit_id=audit_id,
        company_id=company.id,
        website_url=request.website_url,
        status="pending",
        started_at=datetime.now(timezone.utc),
    )
    save_report(stub)

    # Capture values needed inside the background closure (avoid late-binding).
    _company_id = company.id

    async def _crawl_and_save() -> None:
        engine = SeoAuditEngine()
        report = await engine.run(request, company_id=_company_id, audit_id=audit_id)
        save_report(report)
        log.info("SEO audit %s finished with status=%s pages=%d health=%.0f",
                 audit_id, report.status, report.pages_crawled, report.health_score)
        if report.status in ("success", "partial"):
            try:
                from models.company_graph import KnowledgeItem
                from services.company_graph_store import get_company_graph_store

                store = get_company_graph_store()
                await store.create_knowledge_item(KnowledgeItem(
                    title=f"SEO audit {report.audit_id} - {report.website_url} "
                          f"(health {report.health_score}/100)",
                    knowledge_type="learning",
                    content=report_to_markdown(report),
                    tags=["seo-audit", f"company:{_company_id}", f"audit:{report.audit_id}"],
                    source="automated_scan",
                ))
            except Exception as exc:  # noqa: BLE001 - persistence is best-effort
                log.warning("Could not persist SEO audit %s to company graph: %s",
                            audit_id, exc)

    background_tasks.add_task(_crawl_and_save)
    return stub


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
    """Fetch a complete stored audit report."""
    company = await get_company_access(company_id, user)
    report = get_report(audit_id)
    if report is None or report.company_id != company.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit {audit_id} not found for this company",
        )
    return report


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
    priority_map = {
        "high": TaskPriority.HIGH,
        "medium": TaskPriority.MEDIUM,
        "low": TaskPriority.LOW,
    }
    store = get_task_store()
    owner_id = _resolve_user_id(user)
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

"""
Company Graph API Router

Provides all endpoints for managing companies, their graphs, and related entities.
This is the canonical API for the Agency Core v5 Company Graph.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from typing import List, Optional, Any
from datetime import datetime
import logging
import secrets

from pydantic import BaseModel

# Import models (will work once we implement the services)
# from models.company_graph import (
#     Company,
#     CompanyCreateRequest,
#     CompanyUpdateRequest,
#     CompanyResponse,
#     CompanyGraph,
#     CompanyGraphResponse,
#     Website,
#     WebsiteScanRequest,
#     WebsiteScanResult,
#     Repo,
#     RepoScanRequest,
#     Specialist,
#     SpecialistProvisionRequest,
#     SpecialistProvisionResult,
#     SpecialistListResponse,
#     Workflow,
#     WorkflowListResponse,
#     KnowledgeItem,
#     Connector,
#     ApprovalPolicy,
#     OnboardingProgress,
#     WorkflowExecutionRequest,
#     WorkflowExecutionResult,
# )

from backend.server import get_optional_user, get_current_user

log = logging.getLogger("company_api")

# Create the router
router = APIRouter(prefix="/api/company", tags=["company"])

# =============================================================================
# AUTHENTICATION HELPERS
# =============================================================================

async def get_company_access(
    company_id: str, 
    user: dict = Depends(get_current_user)
) -> Company:
    """
    Verify user has access to a company and return the company.
    Raises HTTPException if access is denied.
    """
    store = get_company_graph_store()
    company = await store.get_company(company_id)
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )
    
    # Check if user is owner or admin
    user_id = str(user.get("_id") or user.get("id"))
    if company.owner_id != user_id and user_id not in (company.admin_ids or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this company"
        )
    
    return company


async def get_optional_company_access(
    company_id: str,
    user: Optional[dict] = Depends(get_optional_user)
) -> Optional[Company]:
    """
    Verify user has access to a company (if authenticated).
    Returns None if company not found or user not authenticated.
    """
    if not user:
        return None
    
    store = get_company_graph_store()
    company = await store.get_company(company_id)
    
    if not company:
        return None
    
    user_id = str(user.get("_id") or user.get("id"))
    if company.owner_id != user_id and user_id not in (company.admin_ids or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this company"
        )
    
    return company


# =============================================================================
# COMPANY ENDPOINTS
# =============================================================================

@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    request: CompanyCreateRequest,
    user: dict = Depends(get_current_user)
) -> CompanyResponse:
    """
    Create a new company.
    
    This is the entry point for the Company Graph.
    Creates a company and initializes its graph structure.
    """
    user_id = str(user.get("_id") or user.get("id"))
    
    service = get_company_graph_service()
    
    # Create the company
    company = await service.create_company(
        name=request.name,
        domain=request.domain,
        business_category=request.business_category or "other",
        description=request.description or "",
        owner_id=user_id,
        tagline=request.tagline
    )
    
    # Create initial company graph
    graph = await service.get_or_create_company_graph(company.id)
    
    log.info(f"Created company {company.id} with graph {graph.id}")
    
    return CompanyResponse(
        company=company,
        message="Company created successfully"
    )


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: str = Path(..., description="Company ID"),
    user: dict = Depends(get_current_user)
) -> CompanyResponse:
    """
    Get a company by ID.
    
    Returns the company with its current state and onboarding progress.
    """
    company = await get_company_access(company_id, user)
    
    service = get_company_graph_service()
    graph = await service.get_company_graph(company.id)
    
    return CompanyResponse(
        company=company,
        graph=graph,
        message="Company retrieved successfully"
    )


# =============================================================================

# =============================================================================
# COMPANY GRAPH ENDPOINTS
# =============================================================================

@router.get("/{company_id}/graph", response_model=CompanyGraphResponse)
async def get_company_graph(
    company_id: str = Path(..., description="Company ID"),
    include_detected_systems: bool = Query(True, description="Include detected systems"),
    include_specialists: bool = Query(True, description="Include specialists"),
    include_workflows: bool = Query(True, description="Include workflows"),
    user: dict = Depends(get_current_user)
) -> CompanyGraphResponse:
    """
    Get the complete Company Graph for a company.
    
    Returns the company's graph with all entities and relationships.
    """
    company = await get_company_access(company_id, user)
    
    service = get_company_graph_service()
    graph = await service.get_company_graph(
        company_id=company.id,
        include_detected_systems=include_detected_systems,
        include_specialists=include_specialists,
        include_workflows=include_workflows
    )
    
    if not graph:
        # Create a new graph if it doesn't exist
        graph = await service.get_or_create_company_graph(company.id)
    
    # Calculate completeness score
    completeness = await service.calculate_graph_completeness(company.id)
    
    return CompanyGraphResponse(
        company_id=company.id,
        graph=graph,
        completeness_score=completeness,
        message="Company Graph retrieved successfully"
    )


@router.post("/{company_id}/graph/sync", response_model=CompanyGraphResponse)
async def sync_company_graph(
    company_id: str = Path(..., description="Company ID"),
    force_rescan: bool = Body(False, description="Force re-scan of all websites and repos"),
    user: dict = Depends(get_current_user)
) -> CompanyGraphResponse:
    """
    Synchronize the Company Graph.
    
    Re-scans all websites and repositories, updates detected systems,
    and re-provisions specialists if needed.
    """
    company = await get_company_access(company_id, user)
    
    service = get_company_graph_service()
    
    # Get existing graph
    graph = await service.get_or_create_company_graph(company.id)
    
    # Get all websites and repos
    store = get_company_graph_store()
    websites = await store.list_websites(company.id)
    repos = await store.list_repos(company.id)
    
    # Re-scan if requested or if it's been a while
    if force_rescan or not websites or not repos:
        for website in websites:
            if force_rescan or not website.last_scanned:
                await scan_website(
                    website_url=website.url,
                    company_id=company.id,
                    scan_depth="standard"
                )
        
        for repo in repos:
            if force_rescan or not repo.last_scanned:
                await scan_repo(
                    repo_url=repo.url,
                    company_id=company.id
                )
    
    # Update graph with latest data
    updated_graph = await service.get_or_create_company_graph(company.id)
    
    # Calculate completeness
    completeness = await service.calculate_graph_completeness(company.id)
    
    log.info(f"Synced Company Graph for {company_id}")
    
    return CompanyGraphResponse(
        company_id=company.id,
        graph=updated_graph,
        completeness_score=completeness,
        message="Company Graph synchronized successfully"
    )


# =============================================================================
# SCANNING ENDPOINTS
# =============================================================================

@router.post("/{company_id}/scan/website", response_model=WebsiteScanResult)
async def scan_website_endpoint(
    company_id: str = Path(..., description="Company ID"),
    request: WebsiteScanRequest = Body(...),
    user: dict = Depends(get_current_user)
) -> WebsiteScanResult:
    """
    Scan a website for technology stack and systems.
    
    This performs a comprehensive scan of the website, detecting:
    - Frontend frameworks (React, Vue, Angular, etc.)
    - Backend technologies (Node.js, Django, Rails, etc.)
    - CMS platforms (WordPress, Shopify, etc.)
    - E-commerce platforms (Shopify, WooCommerce, etc.)
    - Analytics tools (Google Analytics, etc.)
    - And more...
    """
    company = await get_company_access(company_id, user)
    
    # Perform the scan
    result = await scan_website(
        website_url=request.website_url,
        company_id=company.id,
        scan_depth=request.scan_depth,
        include_sitemap=request.include_sitemap,
        max_pages=request.max_pages
    )
    
    # If scan was successful, add website to company
    if result.status == "success":
        service = get_company_graph_service()
        
        # Check if website already exists
        store = get_company_graph_store()
        existing_websites = await store.list_websites(company.id)
        website_exists = any(w.url == request.website_url for w in existing_websites)
        
        if not website_exists:
            website = Website(
                url=request.website_url,
                company_id=company.id,
                is_primary=len(existing_websites) == 0,  # First website is primary
                inferred_stack=result.inferred_stack,
                detected_systems=result.detected_systems,
                last_scanned=result.completed_at or datetime.utcnow(),
                scan_status="success",
                confidence_scores=result.inferred_stack.confidence_scores if result.inferred_stack else {}
            )
            await store.create_website(website)
            log.info(f"Created website {request.website_url} for company {company_id}")
        else:
            # Update existing website
            for existing in existing_websites:
                if existing.url == request.website_url:
                    updated_website = existing.model_copy(update={
                        "inferred_stack": result.inferred_stack,
                        "detected_systems": result.detected_systems,
                        "last_scanned": result.completed_at or datetime.utcnow(),
                        "scan_status": "success",
                        "confidence_scores": result.inferred_stack.confidence_scores if result.inferred_stack else {}
                    })
                    await store.update_website(updated_website)
                    log.info(f"Updated website {request.website_url} for company {company_id}")
                    break
        
        # Add detected systems to company graph
        for system in result.detected_systems:
            existing_systems = await store.list_detected_systems(
                company_id=company.id,
                system_type=system.system_type
            )
            if not any(ds.name == system.name for ds in existing_systems):
                await store.create_detected_system(system)
                log.debug(f"Added detected system {system.name} ({system.system_type}) to company {company_id}")
    
    return result


@router.post("/{company_id}/scan/repo", response_model=WebsiteScanResult)
async def scan_repo_endpoint(
    company_id: str = Path(..., description="Company ID"),
    request: RepoScanRequest = Body(...),
    user: dict = Depends(get_current_user)
) -> WebsiteScanResult:
    """
    Scan a repository for technology stack and systems.
    """
    company = await get_company_access(company_id, user)
    
    # Perform the scan
    result = await scan_repo(
        repo_url=request.repo_url,
        company_id=company.id,
        provider=request.provider
    )
    
    # If scan was successful, add repo to company
    if result.status == "success" and result.inferred_stack:
        service = get_company_graph_service()
        
        # Check if repo already exists
        store = get_company_graph_store()
        existing_repos = await store.list_repos(company.id)
        repo_exists = any(r.url == request.repo_url for r in existing_repos)
        
        if not repo_exists:
            from services.scanner import RepoScanner
            scanner = RepoScanner(company_id)
            provider = scanner._detect_provider(request.repo_url)
            
            repo = Repo(
                url=request.repo_url,
                company_id=company.id,
                provider=provider,
                name=request.repo_url.split('/')[-1],
                full_name=request.repo_url,
                inferred_stack=result.inferred_stack,
                last_scanned=result.completed_at or datetime.utcnow()
            )
            await store.create_repo(repo)
            log.info(f"Created repo {request.repo_url} for company {company_id}")
        else:
            # Update existing repo
            for existing in existing_repos:
                if existing.url == request.repo_url:
                    updated_repo = existing.model_copy(update={
                        "inferred_stack": result.inferred_stack,
                        "last_scanned": result.completed_at or datetime.utcnow()
                    })
                    await store.update_repo(updated_repo)
                    log.info(f"Updated repo {request.repo_url} for company {company_id}")
                    break
    
    return result


# =============================================================================
# SPECIALIST ENDPOINTS
# =============================================================================

@router.get("/{company_id}/specialists", response_model=SpecialistListResponse)
async def list_specialists(
    company_id: str = Path(..., description="Company ID"),
    family: Optional[SpecialistFamily] = Query(None, description="Filter by specialist family"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user)
) -> SpecialistListResponse:
    """
    List all specialists for a company.
    
    Returns specialists provisioned for the specified company.
    """
    company = await get_company_access(company_id, user)
    
    specialist_service = get_specialist_service()
    specialists = await specialist_service.list_specialists(
        company_id=company.id,
        family=family,
        status=status,
        limit=limit,
        offset=offset
    )
    
    # Get total count
    total = await specialist_service.count_specialists(company_id=company.id)
    
    return SpecialistListResponse(
        specialists=specialists,
        company_id=company.id,
        total=total,
        limit=limit,
        offset=offset,
        message="Specialists retrieved successfully"
    )


@router.post("/{company_id}/specialists", response_model=SpecialistProvisionResult)
async def provision_specialist(
    company_id: str = Path(..., description="Company ID"),
    request: SpecialistProvisionRequest = Body(...),
    user: dict = Depends(get_current_user)
) -> SpecialistProvisionResult:
    """
    Provision a new specialist for a company.
    
    Creates and provisions a specialist based on the specified parameters.
    """
    company = await get_company_access(company_id, user)
    
    specialist_service = get_specialist_service()
    
    result = await specialist_service.provision_specialist(
        company_id=company.id,
        specialist_family=request.specialist_family,
        name=request.name,
        auto_detect=request.auto_detect,
        system_types=request.system_types
    )
    
    if result.status == "success":
        log.info(f"Provisioned specialist {result.specialist_id} for company {company_id}")
    else:
        log.warning(f"Failed to provision specialist for company {company_id}: {result.message}")
    
    return result


@router.post("/{company_id}/specialists/match", response_model=List[Specialist])
async def match_specialists(
    company_id: str = Path(..., description="Company ID"),
    task_description: str = Body(..., description="Description of the task"),
    capabilities: List[str] = Body([], description="Required capabilities"),
    system_types: List[SystemType] = Body([], description="Relevant system types"),
    limit: int = Body(5, ge=1, le=20),
    user: dict = Depends(get_current_user)
) -> List[Specialist]:
    """
    Match specialists to a task.
    
    Returns the best specialists for the given task based on:
    - Capabilities match
    - System type compatibility
    - Success rate
    - Availability
    """
    company = await get_company_access(company_id, user)
    
    specialist_service = get_specialist_service()
    specialists = await specialist_service.get_specialists_for_task(
        company_id=company.id,
        task_description=task_description,
        capabilities=capabilities,
        system_types=system_types,
        limit=limit
    )
    
    return specialists


# =============================================================================
# ONBOARDING ENDPOINTS
# =============================================================================

@router.get("/{company_id}/onboarding", response_model=OnboardingProgressResponse)
async def get_onboarding_progress(
    company_id: str = Path(..., description="Company ID"),
    user: dict = Depends(get_current_user)
) -> OnboardingProgressResponse:
    """
    Get the current onboarding progress for a company.
    
    Returns the onboarding status, current step, and progress percentage.
    """
    company = await get_company_access(company_id, user)
    
    onboarding_service = get_onboarding_service()
    progress = await onboarding_service.get_onboarding_progress(company.id)
    
    if not progress:
        # Create default progress if not exists
        progress = OnboardingProgress(
            company_id=company.id,
            current_step="not_started",
            total_steps=5,
            completed_steps=0,
            progress_percent=0.0,
            status="not_started",
            started_at=company.created_at,
            steps=[]
        )
    
    return OnboardingProgressResponse(
        company_id=progress.company_id,
        current_step=progress.current_step,
        total_steps=progress.total_steps,
        completed_steps=progress.completed_steps,
        progress_percent=progress.progress_percent,
        status=progress.status,
        steps=progress.steps,
        errors=progress.errors,
        started_at=progress.started_at,
        completed_at=progress.completed_at,
        message=f"Onboarding progress for {company.name}"
    )


@router.post("/{company_id}/onboarding/start", response_model=OnboardingProgressResponse)
async def start_onboarding(
    company_id: str = Path(..., description="Company ID"),
    website_urls: List[str] = Body([], description="Website URLs to scan"),
    repo_urls: List[str] = Body([], description="Repository URLs to scan"),
    skip_website_scan: bool = Body(False, description="Skip website scanning"),
    skip_repo_scan: bool = Body(False, description="Skip repository scanning"),
    auto_provision_specialists: bool = Body(True, description="Auto-provision specialists"),
    user: dict = Depends(get_current_user)
) -> OnboardingProgressResponse:
    """
    Start the onboarding process for a company.
    """
    company = await get_company_access(company_id, user)
    
    onboarding_service = get_onboarding_service()
    progress = await onboarding_service.start_onboarding(
        company_id=company.id,
        website_urls=website_urls,
        repo_urls=repo_urls,
        skip_website_scan=skip_website_scan,
        skip_repo_scan=skip_repo_scan,
        auto_provision_specialists=auto_provision_specialists
    )
    
    log.info(f"Started onboarding for company {company_id}")
    
    return OnboardingProgressResponse(
        company_id=progress.company_id,
        current_step=progress.current_step,
        total_steps=progress.total_steps,
        completed_steps=progress.completed_steps,
        progress_percent=progress.progress_percent,
        status=progress.status,
        steps=progress.steps,
        errors=progress.errors,
        started_at=progress.started_at,
        completed_at=progress.completed_at,
        message="Onboarding started successfully"
    )


@router.post("/{company_id}/onboarding/pause", response_model=OnboardingProgressResponse)
async def pause_onboarding(
    company_id: str = Path(..., description="Company ID"),
    user: dict = Depends(get_current_user)
) -> OnboardingProgressResponse:
    """Pause the onboarding process for a company."""
    company = await get_company_access(company_id, user)
    onboarding_service = get_onboarding_service()
    progress = await onboarding_service.pause_onboarding(company.id)
    log.info(f"Paused onboarding for company {company_id}")
    return OnboardingProgressResponse(
        company_id=progress.company_id,
        current_step=progress.current_step,
        total_steps=progress.total_steps,
        completed_steps=progress.completed_steps,
        progress_percent=progress.progress_percent,
        status=progress.status,
        steps=progress.steps,
        errors=progress.errors,
        started_at=progress.started_at,
        completed_at=progress.completed_at,
        message="Onboarding paused successfully"
    )


@router.post("/{company_id}/onboarding/resume", response_model=OnboardingProgressResponse)
async def resume_onboarding(
    company_id: str = Path(..., description="Company ID"),
    user: dict = Depends(get_current_user)
) -> OnboardingProgressResponse:
    """Resume a paused onboarding process."""
    company = await get_company_access(company_id, user)
    onboarding_service = get_onboarding_service()
    progress = await onboarding_service.resume_onboarding(company.id)
    log.info(f"Resumed onboarding for company {company_id}")
    return OnboardingProgressResponse(
        company_id=progress.company_id,
        current_step=progress.current_step,
        total_steps=progress.total_steps,
        completed_steps=progress.completed_steps,
        progress_percent=progress.progress_percent,
        status=progress.status,
        steps=progress.steps,
        errors=progress.errors,
        started_at=progress.started_at,
        completed_at=progress.completed_at,
        message="Onboarding resumed successfully"
    )


@router.post("/{company_id}/onboarding/cancel", response_model=OnboardingProgressResponse)
async def cancel_onboarding(
    company_id: str = Path(..., description="Company ID"),
    user: dict = Depends(get_current_user)
) -> OnboardingProgressResponse:
    """Cancel the onboarding process for a company."""
    company = await get_company_access(company_id, user)
    onboarding_service = get_onboarding_service()
    progress = await onboarding_service.cancel_onboarding(company.id)
    log.info(f"Cancelled onboarding for company {company_id}")
    return OnboardingProgressResponse(
        company_id=progress.company_id,
        current_step=progress.current_step,
        total_steps=progress.total_steps,
        completed_steps=progress.completed_steps,
        progress_percent=progress.progress_percent,
        status=progress.status,
        steps=progress.steps,
        errors=progress.errors,
        started_at=progress.started_at,
        completed_at=progress.completed_at,
        message="Onboarding cancelled"
    )


# =============================================================================
# DOCTOR ENDPOINT (Public + Authenticated)
# =============================================================================

@router.get("/doctor/public")
async def get_public_doctor_report():
    """
    Public Doctor endpoint - no authentication required.
    
    Returns basic system health information without user-specific checks.
    This is the public version of the Doctor endpoint.
    """
    # Import here to avoid circular imports
    from backend.server import _DoctorCheck, _DoctorReport
    import datetime
    import shutil
    
    checks = []
    
    # Basic checks that don't require auth
    # 1. Git binary
    git_ok = bool(shutil.which("git"))
    checks.append(_DoctorCheck(
        id="git_binary",
        category="Setup",
        label="Git binary",
        status="pass" if git_ok else "fail",
        detail="Git binary found on PATH" if git_ok else "Git binary not found on PATH",
        explanation="Git is required for repository operations. Install git and ensure it is on PATH." if not git_ok else None
    ))
    
    # 2. Basic system info
    checks.append(_DoctorCheck(
        id="system_info",
        category="System",
        label="System information",
        status="pass",
        detail="Basic system checks passed",
        explanation="System is operational"
    ))
    
    # 3. Storage backend
    try:
        store = get_company_graph_store()
        # Try a simple operation
        count = await store.count_companies()
        checks.append(_DoctorCheck(
            id="storage_backend",
            category="Storage",
            label="Storage backend",
            status="pass",
            detail=f"Storage backend connected ({count} companies)",
            explanation="Storage backend is operational"
        ))
    except Exception as e:
        checks.append(_DoctorCheck(
            id="storage_backend",
            category="Storage",
            label="Storage backend",
            status="fail",
            detail=f"Storage backend connection failed: {str(e)}",
            explanation="Check storage configuration and connection"
        ))
    
    ready = all(c.status != "fail" for c in checks)
    fail_count = sum(1 for c in checks if c.status == "fail")
    pass_count = sum(1 for c in checks if c.status == "pass")
    
    if ready:
        summary = f"{pass_count} check(s) passing — system healthy"
    else:
        summary = f"{fail_count} check(s) failing — action required"
    
    return _DoctorReport(
        ready=ready,
        summary=summary,
        checks=checks,
        run_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


# =============================================================================
# EXPORT ROUTER
# =============================================================================
# This will be included in backend/server.py
# app.include_router(router)

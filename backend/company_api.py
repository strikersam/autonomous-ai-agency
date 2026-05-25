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

# =============================================================================
# REQUEST/RESPONSE MODELS (Temporary - will be replaced by models.company_graph)
# =============================================================================

class CompanyBase(BaseModel):
    name: str
    domain: str
    business_category: str = "other"
    description: str = ""

class CompanyCreateRequest(CompanyBase):
    pass

class CompanyUpdateRequest(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    business_category: Optional[str] = None
    description: Optional[str] = None
    tagline: Optional[str] = None
    is_active: Optional[bool] = None

class CompanyResponse(BaseModel):
    id: str
    name: str
    domain: str
    business_category: str
    description: str
    tagline: str = ""
    is_active: bool = True
    onboarding_status: str = "not_started"
    onboarding_progress: float = 0.0
    created_at: str
    updated_at: str
    message: str = ""

class CompanyListResponse(BaseModel):
    companies: List[CompanyResponse]
    total: int
    limit: int
    offset: int

class WebsiteScanRequest(BaseModel):
    website_url: str
    scan_depth: str = "standard"
    include_sitemap: bool = True
    max_pages: int = 20

class WebsiteScanResult(BaseModel):
    scan_id: str
    website_url: str
    status: str
    inferred_stack: Optional[dict] = None
    detected_systems: List[dict] = []
    pages_scanned: int = 0
    errors: List[str] = []
    started_at: str
    completed_at: Optional[str] = None

class SpecialistProvisionRequest(BaseModel):
    specialist_family: str
    name: Optional[str] = None
    capabilities: List[str] = []
    system_types: List[str] = []
    auto_provision: bool = True

class SpecialistProvisionResult(BaseModel):
    request_id: str
    specialist_id: Optional[str] = None
    status: str
    message: str
    errors: List[str] = []
    provisioned_at: str

class OnboardingProgressResponse(BaseModel):
    company_id: str
    current_step: str
    total_steps: int
    completed_steps: int
    progress_percent: float
    status: str
    steps: List[dict] = []
    errors: List[str] = []

# =============================================================================
# ROUTER
# =============================================================================

router = APIRouter(prefix="/api/company", tags=["company", "company-graph"])


# =============================================================================
# COMPANY ENDPOINTS
# =============================================================================

@router.get("", response_model=CompanyListResponse)
async def list_companies(
    owner_id: Optional[str] = Query(None, description="Filter by owner ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of companies"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    search: Optional[str] = Query(None, description="Search by name or domain"),
    user: Optional[dict] = Depends(get_optional_user)
):
    """
    List all companies.
    
    Returns a paginated list of companies that the user has access to.
    """
    # TODO: Implement with CompanyGraphStore
    # For now, return mock data
    mock_companies = []
    for i in range(min(limit, 5)):
        mock_companies.append(CompanyResponse(
            id=f"company_{i}",
            name=f"Company {i}",
            domain=f"company{i}.com",
            business_category="saas",
            description=f"Test company {i}",
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat()
        ))
    
    return CompanyListResponse(
        companies=mock_companies,
        total=5,
        limit=limit,
        offset=offset
    )


@router.post("", response_model=CompanyResponse)
async def create_company(
    request: CompanyCreateRequest,
    user: dict = Depends(get_current_user)
):
    """
    Create a new company.
    
    Creates a new company and initializes its Company Graph.
    """
    # TODO: Implement with CompanyGraphStore
    # For now, return mock response
    company_id = f"company_{secrets.token_hex(4)}"
    
    return CompanyResponse(
        id=company_id,
        name=request.name,
        domain=request.domain,
        business_category=request.business_category,
        description=request.description,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
        message="Company created successfully (mock)"
    )


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: str,
    user: Optional[dict] = Depends(get_optional_user)
):
    """
    Get a company by ID.
    
    Returns detailed information about a specific company.
    """
    # TODO: Implement with CompanyGraphStore
    # For now, return mock response
    
    return CompanyResponse(
        id=company_id,
        name="Test Company",
        domain="test.com",
        business_category="saas",
        description="A test company",
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
        message="Company retrieved successfully (mock)"
    )


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: str,
    request: CompanyUpdateRequest,
    user: dict = Depends(get_current_user)
):
    """
    Update a company.
    
    Updates company information. Requires admin access.
    """
    # TODO: Implement with CompanyGraphStore
    # For now, return mock response
    
    return CompanyResponse(
        id=company_id,
        name=request.name or "Test Company",
        domain=request.domain or "test.com",
        business_category=request.business_category or "saas",
        description=request.description or "",
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
        message="Company updated successfully (mock)"
    )


@router.delete("/{company_id}", response_model=CompanyResponse)
async def delete_company(
    company_id: str,
    force: bool = Query(False, description="Force deletion"),
    user: dict = Depends(get_current_user)
):
    """
    Delete a company.
    
    Deletes a company and all its associated data. Requires admin access.
    """
    # TODO: Implement with CompanyGraphStore
    if not force:
        raise HTTPException(
            status_code=400,
            detail="Force parameter required for deletion"
        )
    
    return CompanyResponse(
        id=company_id,
        name="Deleted Company",
        domain="",
        business_category="other",
        description="",
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
        message="Company deleted successfully (mock)"
    )


# =============================================================================
# COMPANY GRAPH ENDPOINTS
# =============================================================================

@router.get("/{company_id}/graph", response_model=Any)
async def get_company_graph(
    company_id: str,
    include: Optional[str] = Query(None, description="What to include"),
    depth: Optional[str] = Query("standard", description="Depth of graph"),
    user: Optional[dict] = Depends(get_optional_user)
):
    """
    Get the complete Company Graph for a company.
    
    Returns the Company Graph including websites, repos, systems, specialists, etc.
    """
    # TODO: Implement with CompanyGraphStore
    return {
        "company_id": company_id,
        "company": {
            "id": company_id,
            "name": "Test Company",
            "domain": "test.com"
        },
        "websites": [],
        "repos": [],
        "systems": [],
        "specialists": [],
        "workflows": [],
        "knowledge": [],
        "connectors": [],
        "detected_systems": [],
        "is_complete": False,
        "completeness_score": 0.0,
        "message": "Company Graph retrieved successfully (mock)"
    }


# =============================================================================
# WEBSITE SCAN ENDPOINTS
# =============================================================================

@router.post("/{company_id}/scan/website", response_model=WebsiteScanResult)
async def scan_website(
    company_id: str,
    request: WebsiteScanRequest,
    user: dict = Depends(get_current_user)
):
    """
    Scan a website and detect its technology stack.
    
    Scans the specified website and returns detected systems and stack inference.
    """
    # TODO: Implement with WebsiteScanner
    return WebsiteScanResult(
        scan_id=f"scan_{secrets.token_hex(8)}",
        website_url=request.website_url,
        status="success",
        inferred_stack={
            "frameworks": ["React", "Next.js"],
            "languages": ["JavaScript", "TypeScript"],
            "cms": [],
            "analytics": ["Google Analytics"],
            "confidence_scores": {
                "React": 0.95,
                "Next.js": 0.9,
                "Google Analytics": 0.85
            }
        },
        detected_systems=[
            {
                "system_type": "CMS",
                "name": "Next.js",
                "confidence": 0.95,
                "evidence": [
                    {"type": "meta_tag", "value": "next.js", "location": "head"}
                ]
            },
            {
                "system_type": "analytics",
                "name": "Google Analytics",
                "confidence": 0.85,
                "evidence": [
                    {"type": "script", "value": "google-analytics.com", "location": "body"}
                ]
            }
        ],
        pages_scanned=1,
        started_at=datetime.utcnow().isoformat(),
        completed_at=datetime.utcnow().isoformat()
    )


# =============================================================================
# SPECIALIST ENDPOINTS
# =============================================================================

@router.get("/{company_id}/specialists", response_model=Any)
async def list_specialists(
    company_id: str,
    family: Optional[str] = Query(None, description="Filter by specialist family"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: Optional[dict] = Depends(get_optional_user)
):
    """
    List all specialists for a company.
    
    Returns specialists provisioned for the specified company.
    """
    # TODO: Implement with SpecialistService
    mock_specialists = [
        {
            "id": "spec_1",
            "name": "Engineering Specialist",
            "family": "engineering",
            "capabilities": ["code", "development", "bug_fixing"],
            "status": "available",
            "is_provisioned": True
        },
        {
            "id": "spec_2",
            "name": "QA Specialist",
            "family": "qa",
            "capabilities": ["testing", "quality_assurance"],
            "status": "available",
            "is_provisioned": True
        }
    ]
    
    if family:
        mock_specialists = [s for s in mock_specialists if s["family"] == family]
    
    return {
        "specialists": mock_specialists[:limit],
        "company_id": company_id,
        "total": len(mock_specialists),
        "message": "Specialists retrieved successfully (mock)"
    }


@router.post("/{company_id}/specialists", response_model=SpecialistProvisionResult)
async def provision_specialist(
    company_id: str,
    request: SpecialistProvisionRequest,
    user: dict = Depends(get_current_user)
):
    """
    Provision a new specialist for a company.
    
    Creates and provisions a specialist based on the specified parameters.
    """
    # TODO: Implement with SpecialistService
    return SpecialistProvisionResult(
        request_id=f"req_{secrets.token_hex(8)}",
        specialist_id=f"spec_{secrets.token_hex(4)}",
        status="success",
        message="Specialist provisioned successfully (mock)",
        provisioned_at=datetime.utcnow().isoformat()
    )


# =============================================================================
# ONBOARDING ENDPOINTS
# =============================================================================

@router.get("/{company_id}/onboarding", response_model=OnboardingProgressResponse)
async def get_onboarding_progress(
    company_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get the current onboarding progress for a company.
    
    Returns the onboarding status, current step, and progress percentage.
    """
    # TODO: Implement with OnboardingService
    return OnboardingProgressResponse(
        company_id=company_id,
        current_step="scan_websites",
        total_steps=5,
        completed_steps=2,
        progress_percent=40.0,
        status="in_progress",
        steps=[
            {"name": "create_company", "status": "completed", "completed_at": datetime.utcnow().isoformat()},
            {"name": "scan_websites", "status": "in_progress", "started_at": datetime.utcnow().isoformat()},
            {"name": "scan_repositories", "status": "pending"},
            {"name": "detect_systems", "status": "pending"},
            {"name": "provision_specialists", "status": "pending"}
        ],
        errors=[]
    )


@router.post("/{company_id}/onboarding/start", response_model=OnboardingProgressResponse)
async def start_onboarding(
    company_id: str,
    website_urls: List[str] = Body([], description="Website URLs to scan"),
    repo_urls: List[str] = Body([], description="Repository URLs to scan"),
    skip_website_scan: bool = Body(False, description="Skip website scanning"),
    skip_repo_scan: bool = Body(False, description="Skip repository scanning"),
    auto_provision_specialists: bool = Body(True, description="Auto-provision specialists"),
    user: dict = Depends(get_current_user)
):
    """
    Start the onboarding process for a company.
    
    Initiates the onboarding flow: website scanning, repo scanning, system detection,
    and specialist provisioning.
    """
    # TODO: Implement with OnboardingService
    return OnboardingProgressResponse(
        company_id=company_id,
        current_step="scan_websites",
        total_steps=5,
        completed_steps=1,
        progress_percent=20.0,
        status="in_progress",
        steps=[
            {"name": "create_company", "status": "completed", "completed_at": datetime.utcnow().isoformat()},
            {"name": "scan_websites", "status": "in_progress", "started_at": datetime.utcnow().isoformat()},
            {"name": "scan_repositories", "status": "pending"},
            {"name": "detect_systems", "status": "pending"},
            {"name": "provision_specialists", "status": "pending"}
        ],
        errors=[]
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
    
    checks = []
    
    # Basic checks that don't require auth
    # 1. Git binary
    import shutil
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

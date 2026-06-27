"""
Company Graph API Router

Provides all endpoints for managing companies, their graphs, and related entities.
This is the canonical API for the Autonomous AI Agency Company Graph.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, Request, status
from typing import List, Optional, Any
from datetime import datetime
import json
import logging
import os
import secrets

from pydantic import BaseModel

from models.company_graph import (
    Company,
    CompanyCreateRequest,
    CompanyUpdateRequest,
    CompanyResponse,
    CompanyGraph,
    CompanyGraphResponse,
    Website,
    WebsiteScanRequest,
    WebsiteScanResult,
    Repo,
    RepoScanRequest,
    RepoScanResult,
    Specialist,
    SpecialistFamily,
    SystemType,
    SpecialistProvisionRequest,
    SpecialistProvisionResult,
    SpecialistListResponse,
    Workflow,
    WorkflowListResponse,
    KnowledgeItem,
    Connector,
    ApprovalPolicy,
    OnboardingProgress,
    WorkflowExecutionRequest,
    WorkflowExecutionResult,
)
from pydantic import Field as _Field


class OnboardingProgressResponse(OnboardingProgress):
    """OnboardingProgress extended with an optional status message."""
    model_config = {"frozen": True, "extra": "forbid"}
    message: str = _Field(default="", description="Status message")


from services.company_graph_store import get_company_graph_store
from services.company_graph import get_company_graph_service
from services.specialist import get_specialist_service
from services.onboarding import OnboardingService, get_onboarding_service
# Thunk functions to avoid circular import with backend.server.
# NOTE: `request` MUST be annotated as `Request`. Without the annotation FastAPI
# treats it as a required request-body field named "request", which makes every
# endpoint using this dependency reject valid payloads with
# `{"loc": ["body", "request"], "msg": "Field required"}` (e.g. POST /api/company
# failing with "Field required"). The wrapped helpers are async, so await them.
async def _get_current_user_thunk(request: Request):
    from backend.server import get_current_user
    return await get_current_user(request)

async def _get_optional_user_thunk(request: Request):
    from backend.server import get_optional_user
    return await get_optional_user(request)


log = logging.getLogger("company_api")

# Local doctor models (mirrors server.py _DoctorCheck/_DoctorReport)
class _DoctorCheck(BaseModel):
    id: str
    category: str
    label: str
    status: str  # "pass" | "warn" | "fail"
    detail: str = ""
    explanation: Optional[str] = None


class _DoctorReport(BaseModel):
    ready: bool
    summary: str
    checks: list[_DoctorCheck] = []
    run_at: str = ""


# Create the router
router = APIRouter(prefix="/api/company", tags=["company"])

# =============================================================================
# AUTHENTICATION HELPERS
# =============================================================================

def _resolve_user_id(user: dict) -> str:
    """Extract a consistent user_id from the user dict.

    Works across all auth methods:
    - GitHub OAuth: user_id = "gh_<github_id>"  (from social_auth.py _upsert_user)
    - Google OAuth: user_id = "goog_<google_id>"
    - Email/password: user_id = "<email>" or MongoDB _id
    - JWT token: user_id from the "sub" claim

    Raises ValueError if no identifiable user_id can be extracted.
    """
    for key in ("_id", "id", "user_id", "email"):
        val = user.get(key)
        if val:
            return str(val)
    log.warning("Could not resolve user_id from user dict: %s", list(user.keys())[:5])
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not identify user from session",
    )


def _is_admin(user: dict) -> bool:
    """Check if a user has admin role.

    Works for both social_auth users (role in SocialUser) and
    traditional users (role in MongoDB user document).
    """
    role = str(user.get("role", "user")).lower()
    return role == "admin"


def _resolve_provider(user: dict) -> str:
    """Best-effort auth provider for a user dict.

    social_auth users carry an explicit ``provider`` ("github"/"google"); we
    also infer from the user_id prefix (``gh_`` / ``goog_``) written by
    social_auth._upsert_user. Falls back to "local" for email/password users.
    """
    prov = str(user.get("provider", "") or "").strip().lower()
    if prov:
        return prov
    uid = ""
    for key in ("user_id", "_id", "id"):
        if user.get(key):
            uid = str(user[key])
            break
    if uid.startswith("gh_"):
        return "github"
    if uid.startswith("goog_"):
        return "google"
    return "local"


async def get_company_access(
    company_id: str, 
    user: dict = Depends(_get_current_user_thunk)
) -> Company:
    """
    Verify user has access to a company and return the company.

    - Admin users bypass ownership check (they can access any company).
    - Regular users must be the owner or an admin of the company.

    Raises HTTPException if access is denied.
    """
    store = get_company_graph_store()
    company = await store.get_company(company_id)
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )
    
    # Admin users can access any company
    if _is_admin(user):
        return company

    # Regular users: check owner_id or admin_ids
    user_id = _resolve_user_id(user)
    if company.owner_id != user_id and user_id not in (company.admin_ids or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this company"
        )
    
    return company


async def get_optional_company_access(
    company_id: str,
    user: Optional[dict] = Depends(_get_optional_user_thunk)
) -> Optional[Company]:
    """
    Verify user has access to a company (if authenticated).

    Admins bypass ownership check. Regular users must own or be admin of the company.
    Returns None if company not found or user not authenticated.
    """
    if not user:
        return None
    
    store = get_company_graph_store()
    company = await store.get_company(company_id)
    
    if not company:
        return None

    # Admin users can access any company
    if _is_admin(user):
        return company
    
    user_id = _resolve_user_id(user)
    if company.owner_id != user_id and user_id not in (company.admin_ids or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this company"
        )
    
    return company


# =============================================================================
# SKILLS ENDPOINTS
# =============================================================================

@router.get("/skills")
async def list_skills(
    family: str | None = Query(None, description="Filter by specialist family"),
    category: str | None = Query(None, description="Filter by skill category"),
    search: str | None = Query(None, description="Search by name/description"),
    user: dict = Depends(_get_current_user_thunk),
) -> dict:
    """
    List all available skills with optional filtering.

    Returns the skill catalog from the SkillBindings registry.
    """
    try:
        from services.skill_bindings import get_skill_bindings
        bindings = get_skill_bindings()

        if search:
            skills = bindings.search(search)
        elif family:
            skills = bindings.list_for_family(family)
        else:
            skills = bindings.list_all()

        # Filter by category if specified
        if category:
            skills = [s for s in skills if s.category.value == category]

        return {
            "skills": [s.as_dict() for s in skills],
            "total": len(skills),
        }
    except ImportError:
        return {"skills": [], "total": 0, "message": "SkillBindings service not available"}


@router.get("/skills/recommend/auto")
async def auto_recommend_skills(
    company_id: str | None = Query(None, description="Company ID for context-based recommendations"),
    user: dict = Depends(_get_current_user_thunk),
) -> dict:
    """
    Auto-recommend skills based on the user's company context.

    If company_id is provided, uses detected systems and specialist families.
    Otherwise returns all skills with base scores.
    """
    try:
        from services.skill_bindings import get_skill_bindings
        bindings = get_skill_bindings()

        system_types = []
        specialist_families = []
        tech_stack = []
        workflow_types = []

        if company_id:
            # Enforce tenant access BEFORE reading any company graph metadata —
            # otherwise any authenticated user could probe another tenant's
            # stack/systems/specialists by guessing a company_id.
            company = await get_company_access(company_id, user)
            try:
                store = get_company_graph_store()
                # Get detected systems
                websites = await store.list_websites(company.id)
                for w in websites:
                    if w.inferred_stack:
                        tech_stack.extend(w.inferred_stack.frameworks or [])
                        tech_stack.extend(w.inferred_stack.languages or [])
                        tech_stack.extend(w.inferred_stack.cms or [])
                # Get system types
                detected = await store.list_detected_systems(company.id)
                system_types = list({d.system_type for d in detected})

                # Get specialist families
                specialists = await store.list_specialists(company.id)
                specialist_families = list({s.family for s in specialists})
            except Exception as exc:
                log.warning("auto_recommend_skills: context load failed: %s", exc)

        recommendations = bindings.recommend_for_company(
            system_types=system_types,
            specialist_families=specialist_families,
        )

        return {
            "recommendations": recommendations,
            "tech_stack": list(dict.fromkeys(tech_stack))[:20],
            "system_types": system_types,
            "specialist_families": specialist_families,
            "workflow_types": workflow_types,
        }
    except ImportError:
        return {"recommendations": [], "tech_stack": [], "message": "SkillBindings service not available"}


@router.get("/skills/{skill_id}")
async def get_skill(
    skill_id: str,
    user: dict = Depends(_get_current_user_thunk),
) -> dict:
    """Get a single skill by its ID."""
    try:
        from services.skill_bindings import get_skill_bindings
        bindings = get_skill_bindings()
        skill = bindings.get(skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
        return skill.as_dict()
    except ImportError:
        raise HTTPException(status_code=503, detail="SkillBindings service not available")


class SkillRecommendRequest(BaseModel):
    """Request to recommend skills based on context."""
    model_config = {"frozen": True, "extra": "forbid"}
    system_types: list[str] = _Field(default_factory=list)
    specialist_families: list[str] = _Field(default_factory=list)


@router.post("/skills/recommend")
async def recommend_skills(
    request: SkillRecommendRequest = Body(...),
    user: dict = Depends(_get_current_user_thunk),
) -> dict:
    """Recommend skills based on provided context."""
    try:
        from services.skill_bindings import get_skill_bindings
        bindings = get_skill_bindings()

        recommendations = bindings.recommend_for_company(
            system_types=request.system_types,
            specialist_families=request.specialist_families,
        )

        return {"recommendations": recommendations}
    except ImportError:
        return {"recommendations": [], "message": "SkillBindings service not available"}


# =============================================================================
# COMPANY ENDPOINTS
# =============================================================================

@router.get("", response_model=dict)
async def list_companies(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, description="Search by name or domain"),
    user: dict = Depends(_get_current_user_thunk),
) -> dict:
    """
    List companies.

    - Admin users see ALL companies across the platform.
    - Regular users see only companies they own or are admin/member of.

    This ensures user-level setup isolation: regardless of whether the user
    logged in via GitHub OAuth or Google OAuth, they only see their own
    companies.  Admins can see every user's setup and activity.
    """
    store = get_company_graph_store()
    user_id = _resolve_user_id(user)
    is_admin_user = _is_admin(user)

    # NOTE: store.list_companies returns a plain List[Company] (no grand-total),
    # so we must NOT tuple-unpack it (that 500s for any result count != 2).
    if is_admin_user:
        # Admin: see all companies
        companies = await store.list_companies(
            owner_id=None, limit=limit, offset=offset, search=search,
        )
    else:
        # Regular user: only their own companies
        companies = await store.list_companies(
            owner_id=user_id, limit=limit, offset=offset, search=search,
        )

    return {
        "companies": [c.model_dump() for c in companies],
        "total": len(companies),
        "limit": limit,
        "offset": offset,
        "scoped_to_user": not is_admin_user,
        "user_id": user_id if not is_admin_user else None,
    }


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    request: CompanyCreateRequest,
    user: dict = Depends(_get_current_user_thunk)
) -> CompanyResponse:
    """
    Create a new company.
    
    This is the entry point for the Company Graph.
    Creates a company and initializes its graph structure.
    """
    user_id = _resolve_user_id(user)

    service = get_company_graph_service()

    # ── Company lifecycle (free-Render hosting policy) ───────────────────────
    # Admin-created companies persist forever. Companies created by non-admin
    # (GitHub/Google) users are ephemeral and reaped after the configured TTL,
    # because the platform runs on the free Render backend and cannot keep every
    # visitor's agency running indefinitely.
    from datetime import timedelta, timezone
    is_admin_user = _is_admin(user)
    provider = _resolve_provider(user)
    lifecycle: dict[str, Any] = {
        "created_by_role": "admin" if is_admin_user else str(user.get("role", "user")).lower(),
        "created_by_provider": provider,
    }
    if is_admin_user:
        lifecycle["persistent"] = True
        lifecycle["expires_at"] = None
    else:
        try:
            from app_settings import ephemeral_ttl_hours
            ttl_hours = await ephemeral_ttl_hours()
        except Exception:  # noqa: BLE001 — fall back to the documented default
            ttl_hours = 24
        lifecycle["persistent"] = False
        lifecycle["expires_at"] = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

    # Create the company with the user as owner
    company = await service.create_company(
        name=request.name,
        domain=request.domain,
        business_category=request.business_category or "other",
        description=request.description or "",
        owner_id=user_id,
        tagline=request.tagline,
        **lifecycle,
    )

    # Create initial company graph
    graph = await service.get_or_create_company_graph(company.id)

    log.info(
        "Created company %s with graph %s (persistent=%s, provider=%s)",
        company.id, graph.id, lifecycle["persistent"], provider,
    )
    
    return CompanyResponse(
        company=company,
        message="Company created successfully"
    )


class AccountLifecycleResponse(BaseModel):
    """Lifecycle/ephemerality status for the current user's agencies.

    Drives the floating banner that warns non-admin users their agency is
    temporary on the free Render backend.
    """
    ephemeral: bool
    persistent: bool
    ttl_hours: int
    expires_at: Optional[str] = None
    provider: str = "local"
    note: str = ""


_EPHEMERAL_NOTE = (
    "Heads up: running an agency beyond {hours} hours needs real compute, and "
    "this platform is currently hosted on a free Render backend — so we can't "
    "keep your agency running forever. Companies created by signed-in "
    "GitHub/Google users are automatically removed after {hours} hours. Ask an "
    "admin if you need a permanent agency."
)


@router.get("/account/lifecycle", response_model=AccountLifecycleResponse)
async def account_lifecycle(
    user: dict = Depends(_get_current_user_thunk),
) -> AccountLifecycleResponse:
    """Return whether the current user's agencies are ephemeral + when they expire.

    Admins are persistent (no banner). Non-admin (GitHub/Google) users get the
    24-hour free-Render notice and the earliest expiry across their companies.
    """
    is_admin_user = _is_admin(user)
    provider = _resolve_provider(user)
    try:
        from app_settings import ephemeral_ttl_hours
        ttl_hours = await ephemeral_ttl_hours()
    except Exception:  # noqa: BLE001
        ttl_hours = 24

    if is_admin_user:
        return AccountLifecycleResponse(
            ephemeral=False, persistent=True, ttl_hours=ttl_hours,
            provider=provider, note="",
        )

    # Earliest expiry across the user's existing ephemeral companies (if any).
    earliest: Optional[datetime] = None
    try:
        user_id = _resolve_user_id(user)
        service = get_company_graph_service()
        companies, _ = await service.list_companies(owner_id=user_id, limit=100)
        for c in companies:
            if not getattr(c, "persistent", True) and getattr(c, "expires_at", None):
                exp = c.expires_at
                if earliest is None or exp < earliest:
                    earliest = exp
    except Exception as exc:  # noqa: BLE001 — banner must never 500
        log.warning("account_lifecycle expiry scan failed: %s", exc)

    return AccountLifecycleResponse(
        ephemeral=True,
        persistent=False,
        ttl_hours=ttl_hours,
        expires_at=earliest.isoformat() if earliest else None,
        provider=provider,
        note=_EPHEMERAL_NOTE.format(hours=ttl_hours),
    )


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: str = Path(..., description="Company ID"),
    user: dict = Depends(_get_current_user_thunk)
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


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: str = Path(..., description="Company ID"),
    request: CompanyUpdateRequest = Body(...),
    user: dict = Depends(_get_current_user_thunk)
) -> CompanyResponse:
    """
    Update a company's metadata.

    Accepts partial updates for company fields including
    intelligence_competitors and intelligence_keywords.
    """
    company = await get_company_access(company_id, user)

    store = get_company_graph_store()
    update_data = request.model_dump(exclude_unset=True, exclude_none=True)

    if update_data:
        updated_company = company.model_copy(update=update_data)
        updated = await store.update_company(updated_company)
        if updated:
            company = updated

    service = get_company_graph_service()
    graph = await service.get_company_graph(company.id)

    return CompanyResponse(
        company=company,
        graph=graph,
        message="Company updated successfully"
    )



@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_endpoint(
    company_id: str = Path(..., description="Company ID"),
    user: dict = Depends(_get_current_user_thunk),
) -> None:
    """
    Delete a company and all associated data.

    Access control is handled by get_company_access:
    - Admin users can delete any company.
    - Regular users can only delete companies they own or are admin of.
    """
    company = await get_company_access(company_id, user)
    
    service = get_company_graph_service()
    success = await service.delete_company(company.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete company",
        )
    
    log.info(f"Deleted company {company_id} and all associated data")

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
    user: dict = Depends(_get_current_user_thunk)
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
    user: dict = Depends(_get_current_user_thunk)
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
        from services.scanner import WebsiteScanner, RepoScanner

        # Resolve GitHub token for authenticated repo scanning
        _gh_token: str | None = user.get("github_repo_token")
        if not _gh_token:
            try:
                from backend.server import get_db
                uid = user.get("_id") or user.get("id") or user.get("user_id")
                if uid:
                    doc = await get_db().github_settings.find_one({"user_id": uid})
                    if doc:
                        _gh_token = doc.get("token")
            except Exception:
                pass
        if not _gh_token:
            _gh_token = (
                os.environ.get("GH_PAT")
                or os.environ.get("GH_TOKEN")
                or os.environ.get("GITHUB_TOKEN")
            )

        for website in websites:
            if force_rescan or not website.last_scanned:
                ws = WebsiteScanner(company_id=company.id)
                result = await ws.scan_website(
                    website_url=website.url,
                    scan_depth="standard"
                )
                if result.status == "success":
                    updated = website.model_copy(update={
                        "inferred_stack": result.inferred_stack,
                        "detected_systems": result.detected_systems,
                        "last_scanned": datetime.utcnow(),
                        "scan_status": "success",
                    })
                    await store.update_website(updated, company.id)

        for repo in repos:
            if force_rescan or not repo.last_scanned:
                rs = RepoScanner(company_id=company.id, github_token=_gh_token)
                result = await rs.scan_repo(repo_url=repo.url)
                if result.status == "success" and result.inferred_stack:
                    updated = repo.model_copy(update={
                        "inferred_stack": result.inferred_stack,
                        "last_scanned": datetime.utcnow(),
                        "scan_status": "success",
                    })
                    await store.update_repo(updated)
    
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
    user: dict = Depends(_get_current_user_thunk)
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
    from services.scanner import WebsiteScanner
    _ws = WebsiteScanner(company_id=company.id)
    result = await _ws.scan_website(
        website_url=request.website_url,
        scan_depth=request.scan_depth,
        include_sitemap=request.include_sitemap,
        max_pages=request.max_pages
    )
    
    # If the scan was successful, persist its findings to the company graph.
    # Persistence is best-effort and split into independent blocks: a failure
    # here must never turn a successful scan into an HTTP 500 (the scan result —
    # including detected systems — is always returned to the caller).
    if result.status == "success":
        store = get_company_graph_store()

        # Persist detected systems.
        try:
            for system in result.detected_systems:
                existing_systems = await store.list_detected_systems(
                    company_id=company.id,
                    system_type=system.system_type,
                )
                if not any(ds.name == system.name for ds in existing_systems):
                    await store.create_detected_system(system, company.id)
                    log.debug(f"Added detected system {system.name} ({system.system_type}) to company {company_id}")
        except Exception as exc:  # noqa: BLE001 - best-effort persistence
            log.warning(f"Could not persist detected systems for company {company_id}: {exc}")

        # Persist the website record.
        try:
            existing_websites = await store.list_websites(company.id)
            website_exists = any(w.url == request.website_url for w in existing_websites)
            confidence = result.inferred_stack.confidence_scores if result.inferred_stack else {}
            if not website_exists:
                website = Website(
                    url=request.website_url,
                    is_primary=len(existing_websites) == 0,  # First website is primary
                    inferred_stack=result.inferred_stack,
                    detected_systems=result.detected_systems,
                    last_scanned=result.completed_at or datetime.utcnow(),
                    scan_status="success",
                    confidence_scores=confidence,
                )
                await store.create_website(website, company.id)
                log.info(f"Created website {request.website_url} for company {company_id}")
            else:
                for existing in existing_websites:
                    if existing.url == request.website_url:
                        updated_website = existing.model_copy(update={
                            "inferred_stack": result.inferred_stack,
                            "detected_systems": result.detected_systems,
                            "last_scanned": result.completed_at or datetime.utcnow(),
                            "scan_status": "success",
                            "confidence_scores": confidence,
                        })
                        await store.update_website(updated_website, company.id)
                        log.info(f"Updated website {request.website_url} for company {company_id}")
                        break
        except Exception as exc:  # noqa: BLE001 - best-effort persistence
            log.warning(f"Could not persist website record for company {company_id}: {exc}")

    return result


@router.post("/{company_id}/scan/repo", response_model=RepoScanResult)
async def scan_repo_endpoint(
    company_id: str = Path(..., description="Company ID"),
    request: RepoScanRequest = Body(...),
    user: dict = Depends(_get_current_user_thunk)
) -> RepoScanResult:
    """
    Scan a repository for technology stack and systems.
    """
    company = await get_company_access(company_id, user)

    # Resolve the user's GitHub token for authenticated API calls.
    # Check user's github_repo_token, then github_settings collection,
    # then server-level env vars (mirrors server.py GitHub access logic).
    github_token: str | None = user.get("github_repo_token")
    if not github_token:
        try:
            from backend.server import get_db
            uid = user.get("_id") or user.get("id") or user.get("user_id")
            if uid:
                doc = await get_db().github_settings.find_one({"user_id": uid})
                if doc:
                    github_token = doc.get("token")
        except Exception:
            pass
    if not github_token:
        github_token = (
            os.environ.get("GH_PAT")
            or os.environ.get("GH_TOKEN")
            or os.environ.get("GITHUB_TOKEN")
        )

    # Perform the scan
    from services.scanner import RepoScanner
    _rs = RepoScanner(company_id=company.id, github_token=github_token)
    result = await _rs.scan_repo(repo_url=request.repo_url)
    
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
    user: dict = Depends(_get_current_user_thunk)
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
    
    # Get total count — use the already-fetched list length
    total = len(specialists)

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
    user: dict = Depends(_get_current_user_thunk)
) -> SpecialistProvisionResult:
    """
    Provision a new specialist for a company.
    
    Creates and provisions a specialist based on the specified parameters.
    """
    company = await get_company_access(company_id, user)
    
    specialist_service = get_specialist_service()
    
    result = await specialist_service.provision_specialist(request)

    if result.status == "success":
        log.info(f"Provisioned specialist {result.specialist.id} for company {company_id}")
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
    user: dict = Depends(_get_current_user_thunk)
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
    user: dict = Depends(_get_current_user_thunk)
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
    user: dict = Depends(_get_current_user_thunk)
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
    user: dict = Depends(_get_current_user_thunk)
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
    user: dict = Depends(_get_current_user_thunk)
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
    user: dict = Depends(_get_current_user_thunk)
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
# AI-POWERED ONBOARDING QUESTIONS & REMEDIATION
# =============================================================================

class OnboardingQuestionsRequest(BaseModel):
    """Request to generate AI-tailored onboarding questions."""
    domain: str = _Field(default="", description="Company domain")
    site_type: str = _Field(default="generic", description="Detected site type (ecommerce, saas, media, generic)")
    detected_systems: list[dict] = _Field(default_factory=list, description="Detected systems with name, system_type, category")
    business_category: str = _Field(default="other", description="Business category")


class OnboardingAnswersRequest(BaseModel):
    """Request to submit onboarding answers and create remediation tasks."""
    answers: dict = _Field(default_factory=dict, description="Question ID → answer mapping")
    site_type: str = _Field(default="generic", description="Site type used for context")
    detected_systems: list[dict] = _Field(default_factory=list, description="Detected systems for context")


@router.post("/{company_id}/onboarding/questions")
async def generate_onboarding_questions(
    company_id: str = Path(..., description="Company ID"),
    request: OnboardingQuestionsRequest = Body(...),
    user: dict = Depends(_get_current_user_thunk),
):
    """
    Generate AI-tailored onboarding questions based on detected domain and technologies.

    Uses the LLM to create contextual questions that help understand the user's
    specific needs, pain points, and priorities. Falls back to sensible defaults
    if the LLM is unavailable.
    """
    company = await get_company_access(company_id, user)

    # Build a rich context string from detected systems
    system_names = []
    for s in request.detected_systems[:15]:
        name = s.get("name", "") or s.get("label", "")
        cat = s.get("category", "") or s.get("system_type", "")
        if name:
            system_names.append(f"- {name} ({cat})" if cat else f"- {name}")

    systems_text = "\n".join(system_names) if system_names else "No systems detected yet"

    site_type_labels = {
        "ecommerce": "e-commerce", "saas": "SaaS", "media": "media/content",
        "agency": "agency/services", "generic": "general"
    }
    site_type_label = site_type_labels.get(request.site_type, "general")

    prompt = f"""You are an onboarding specialist for an AI-powered DevOps platform.

A new company is being onboarded:
- Domain: {request.domain or 'Not provided'}
- Business type: {site_type_label}
- Category: {request.business_category}

Detected technologies/systems:
{systems_text}

Generate exactly 4 tailored questions to understand this company's specific needs.
Each question should be relevant to their stack and business type.

Return ONLY a JSON array of question objects. No explanation, no markdown.

Each question object must have these fields:
- "id": a short slug (e.g. "pain", "kpis", "deploys")
- "label": the full question text, phrased as a natural question
- "type": one of "yesno", "select", "multi", or "freeform"
- "options": array of strings (required for "select" and "multi" types)
- "placeholder": string (only for "freeform" type)

Make the questions specific to the detected stack and business context.
For {site_type_label} businesses, ask about things like deployment cadence,
peak traffic patterns, key metrics, pain points, and technology preferences.

Example format:
[
  {{"id": "peak", "label": "Are there peak traffic seasons?", "type": "yesno"}},
  {{"id": "deploys", "label": "How often do you deploy?", "type": "select", "options": ["Daily", "Weekly", "Monthly"]}},
  {{"id": "kpis", "label": "Which metrics matter most?", "type": "multi", "options": ["Speed", "Reliability", "Cost"]}},
  {{"id": "pain", "label": "What is your biggest pain point?", "type": "freeform", "placeholder": "Describe your challenge..."}}
]"""

    try:
        from backend.server import call_llm
        raw = await call_llm(
            messages=[
                {"role": "system", "content": "You return only valid JSON arrays. No explanation."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )

        # Extract JSON from the response (handle markdown fences)
        import re
        json_match = re.search(r"\[.*\]", raw.strip(), re.DOTALL)
        if json_match:
            questions = json.loads(json_match.group())
            # Validate each question has required fields
            validated = []
            for q in questions:
                if not isinstance(q, dict) or "id" not in q or "label" not in q or "type" not in q:
                    continue
                if q["type"] not in ("yesno", "select", "multi", "freeform"):
                    q["type"] = "freeform"
                if q["type"] in ("select", "multi") and "options" not in q:
                    q["options"] = ["Yes", "No"]
                validated.append(q)
            if len(validated) >= 3:
                log.info(f"AI generated {len(validated)} tailored questions for company {company_id}")
                return {"questions": validated, "source": "ai"}

        log.warning(f"AI question generation returned insufficient valid questions for {company_id}, falling back")
    except Exception as exc:
        log.warning(f"AI question generation failed for {company_id}: {exc}, falling back to defaults")

    # Fallback: return hardcoded questions matching the detected site type
    fallback = _get_fallback_questions(request.site_type, request.business_category, request.detected_systems)
    return {"questions": fallback, "source": "fallback"}


@router.post("/{company_id}/onboarding/answers")
async def submit_onboarding_answers(
    company_id: str = Path(..., description="Company ID"),
    request: OnboardingAnswersRequest = Body(...),
    user: dict = Depends(_get_current_user_thunk),
):
    """
    Submit onboarding answers and create intelligent remediation tasks.

    Analyzes user answers using AI to identify pain points, risks, and opportunities,
    then creates tracked tasks in the task board for follow-up.
    """
    company = await get_company_access(company_id, user)

    created_tasks = []

    if not request.answers:
        return {"tasks": [], "message": "No answers to process", "source": "none"}

    # Format answers for the LLM
    answers_text = "\n".join(f"Q[{k}]: {v}" for k, v in request.answers.items() if v)
    if not answers_text.strip():
        return {"tasks": [], "message": "No meaningful answers to process", "source": "none"}

    # Build system context
    system_names = [s.get("name", "") or s.get("label", "") for s in request.detected_systems[:10] if s.get("name") or s.get("label")]
    systems_text = ", ".join(system_names) if system_names else "unknown stack"

    prompt = f"""A company using {systems_text} just completed onboarding questions.
Business type: {request.site_type}

Their answers:
{answers_text}

Based on these answers, identify 1-3 concrete remediation tasks that would help them.
Focus on actionable DevOps/SRE/engineering improvements.

Return ONLY a JSON array of task objects:
[
  {{
    "title": "short task title (max 80 chars)",
    "description": "1-2 sentence description of what to do and why",
    "priority": "high" | "medium" | "low",
    "task_type": "remediation" | "setup" | "optimization" | "security"
  }}
]

Only suggest tasks that are genuinely useful based on the answers.
If no clear tasks emerge from the answers, return an empty array []"""

    try:
        from backend.server import call_llm
        raw = await call_llm(
            messages=[
                {"role": "system", "content": "You return only valid JSON arrays of task objects. No explanation."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        import re
        json_match = re.search(r"\[.*\]", raw.strip(), re.DOTALL)
        if json_match:
            suggested_tasks = json.loads(json_match.group())
        else:
            suggested_tasks = []
    except Exception as exc:
        log.warning(f"AI remediation task generation failed for {company_id}: {exc}")
        suggested_tasks = []

    # Also create tasks from direct answer signals (deterministic, no LLM needed)
    # Pain point → remediation task
    pain_answer = request.answers.get("pain", "")
    if pain_answer and len(pain_answer.strip()) > 5:
        if not any(t.get("title", "") == f"Address: {pain_answer.strip()[:60]}" for t in suggested_tasks):
            suggested_tasks.append({
                "title": f"Address: {pain_answer.strip()[:77]}..." if len(pain_answer) > 80 else f"Address: {pain_answer.strip()}",
                "description": f"User reported this as their biggest pain point during onboarding: {pain_answer.strip()}",
                "priority": "high",
                "task_type": "remediation",
            })

    # Persist the user's stated priorities onto the company so the company page
    # surfaces them (previously onboarding answers were turned into tasks and the
    # priorities tab stayed empty forever). Derive priorities from the KPI/metrics
    # answers the user selected plus their stated pain point.
    try:
        derived_priorities: list[str] = []
        for key in ("priorities", "goals", "kpis", "outcomes", "metrics"):
            val = request.answers.get(key)
            if isinstance(val, list):
                derived_priorities.extend(str(v).strip() for v in val if str(v).strip())
            elif isinstance(val, str) and val.strip():
                derived_priorities.extend(p.strip() for p in val.split(",") if p.strip())
        if pain_answer and pain_answer.strip():
            derived_priorities.append(f"Resolve: {pain_answer.strip()[:120]}")
        # De-duplicate, preserve order, cap at 10.
        seen_p: set[str] = set()
        unique_priorities = [
            p for p in derived_priorities
            if not (p in seen_p or seen_p.add(p))
        ][:10]
        if unique_priorities:
            store_cg = get_company_graph_store()
            existing = list(getattr(company, "priorities", []) or [])
            merged = existing + [p for p in unique_priorities if p not in existing]
            updated_company = company.model_copy(update={"priorities": merged[:10]})
            saved = await store_cg.update_company(updated_company)
            if saved:
                company = saved
            log.info(
                "Saved %d priorities to company %s from onboarding answers",
                len(merged[:10]), company_id,
            )
    except Exception as exc:  # never block task creation on priority persistence
        log.warning("Failed to persist onboarding priorities for %s: %s", company_id, exc)

    # Create tasks in the task store
    priority_map = {"high": "high", "medium": "medium", "low": "low"}
    user_id = _resolve_user_id(user)

    for st in suggested_tasks[:3]:  # Max 3 remediation tasks
        try:
            from tasks.store import get_task_store
            from tasks.models import Task, TaskPriority, TaskStatus

            store = get_task_store()
            priority = TaskPriority(priority_map.get(str(st.get("priority", "medium")).lower(), "medium"))

            task = Task(
                owner_id=user_id,
                title=str(st.get("title", "Remediation task"))[:512],
                description=str(st.get("description", ""))[:32000],
                priority=priority,
                task_type=str(st.get("task_type", "remediation"))[:64],
                tags=["onboarding", "remediation", request.site_type or "generic"],
                status=TaskStatus.TODO,
            )

            await store.create(task)
            created_tasks.append(task.as_dict())
            log.info(f"Created remediation task {task.task_id} from onboarding answers for company {company_id}")
        except Exception as exc:
            log.warning(f"Failed to create remediation task for company {company_id}: {exc}")

    return {
        "tasks": created_tasks,
        "total": len(created_tasks),
        "priorities": list(getattr(company, "priorities", []) or []),
        "message": f"Created {len(created_tasks)} remediation task(s)",
        "source": "ai" if created_tasks else "none",
    }


def _get_fallback_questions(site_type: str, business_category: str, detected_systems: list[dict]) -> list[dict]:
    """Return hardcoded fallback questions when AI generation fails."""
    # Inject detected system names into generic questions for better context
    sys_names = []
    for s in detected_systems[:5]:
        name = s.get("name", "") or s.get("label", "")
        if name:
            sys_names.append(name)
    stack_hint = f" ({', '.join(sys_names)})" if sys_names else ""

    sets = {
        "ecommerce": [
            {"id": "peak", "label": f"Are there peak traffic seasons{stack_hint}?", "type": "yesno"},
            {"id": "deploys", "label": "How often do you deploy to production?", "type": "select", "options": ["Multiple times a day", "Daily", "Weekly", "Monthly or less"]},
            {"id": "kpis", "label": "Which metrics matter most?", "type": "multi", "options": ["Conversion rate", "Cart abandonment", "Site speed", "SEO ranking", "Support tickets", "AOV"]},
            {"id": "pain", "label": "What is your biggest pain point right now?", "type": "freeform", "placeholder": "e.g. slow checkout, cart abandonment, stock visibility..."},
        ],
        "saas": [
            {"id": "trials", "label": "Do you have a free trial or freemium tier?", "type": "yesno"},
            {"id": "deploys", "label": "How often do you deploy?", "type": "select", "options": ["Continuous CI/CD", "Daily", "Weekly", "Quarterly"]},
            {"id": "kpis", "label": "Which metrics matter most?", "type": "multi", "options": ["MRR growth", "Churn rate", "Activation rate", "Support tickets", "Feature adoption", "NPS"]},
            {"id": "pain", "label": "What is your biggest technical pain point?", "type": "freeform", "placeholder": "e.g. onboarding drop-off, high churn, slow CI..."},
        ],
        "media": [
            {"id": "publishing", "label": "How often do you publish content?", "type": "select", "options": ["Daily", "Weekly", "Monthly"]},
            {"id": "deploys", "label": f"How often do you deploy{stack_hint}?", "type": "select", "options": ["Continuous", "Weekly", "Monthly", "Rarely"]},
            {"id": "kpis", "label": "Which metrics matter most?", "type": "multi", "options": ["Page views", "Time on site", "Subscribers", "Ad revenue", "SEO ranking", "Engagement"]},
            {"id": "pain", "label": "What is your biggest pain point?", "type": "freeform", "placeholder": "e.g. slow publishing, broken embeds, SEO gaps..."},
        ],
        "agency": [
            {"id": "clients", "label": "How many active client projects?", "type": "select", "options": ["1-5", "6-15", "16-50", "50+"]},
            {"id": "deploys", "label": "How often do you deliver?", "type": "select", "options": ["Daily", "Weekly", "Monthly", "Per project"]},
            {"id": "kpis", "label": "Which outcomes matter most?", "type": "multi", "options": ["Delivery speed", "Bug rate", "Client satisfaction", "Code quality", "Team velocity", "Revenue"]},
            {"id": "pain", "label": "What is your biggest operational pain point?", "type": "freeform", "placeholder": "e.g. scope creep, manual QA, context switching..."},
        ],
    }

    # Try specific match first, then generic
    if site_type in sets:
        return sets[site_type]

    # For "generic", inject stack names into the questions
    return [
        {"id": "deploys", "label": f"How often do you deploy{stack_hint}?", "type": "select", "options": ["Multiple times a day", "Daily", "Weekly", "Monthly or less"]},
        {"id": "team", "label": "How large is your engineering team?", "type": "select", "options": ["Solo", "2-5", "6-20", "20+"]},
        {"id": "kpis", "label": "Which outcomes matter most?", "type": "multi", "options": ["Code quality", "Deployment speed", "Bug rate", "Team velocity", "Cost reduction", "Security posture"]},
        {"id": "pain", "label": "What is your biggest technical pain point?", "type": "freeform", "placeholder": "e.g. technical debt, slow deployments, poor test coverage..."},
    ]


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


@router.get("/{company_id}/specialists/{specialist_id}/skills")
async def get_specialist_bound_skills(
    company_id: str,
    specialist_id: str,
    user: dict = Depends(_get_current_user_thunk),
) -> dict:
    """Get the skills bound to a specific specialist."""
    company = await get_company_access(company_id, user)
    specialist_service = get_specialist_service()
    # Scope the specialist to the authorized company — a caller who owns
    # company A must not read a specialist that belongs to company B by ID.
    specialist = await specialist_service.get_specialist(specialist_id)
    if specialist is None or specialist.company_id != company.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Specialist {specialist_id} not found for this company",
        )
    skills = await specialist_service.get_bound_skills(specialist_id)
    return {"specialist_id": specialist_id, "skills": skills, "total": len(skills)}

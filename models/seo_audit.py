"""
models/seo_audit.py - SEO / GEO / AIO Audit Contracts

Typed Pydantic models for the world-class SEO audit engine (issue #533).

The vocabulary intentionally mirrors Screaming Frog SEO Spider exports so the
generated reports are drop-in compatible with existing SEO workflows:

    Issue Name, Issue Type, Issue Priority, URLs, % of Total,
    Description, How To Fix, Help URL

Beyond classic technical SEO, checks are grouped into *pillars*:

- ``technical``  classic crawl/indexing/markup health (Screaming Frog parity)
- ``content``    word count, readability, headings quality
- ``security``   header & link hygiene that affects trust and rankings
- ``social``     Open Graph / Twitter card sharing readiness
- ``geo``        Generative Engine Optimization - visibility to AI crawlers
                 (llms.txt, robots access for GPTBot/ClaudeBot/PerplexityBot,
                 sitemaps, feeds, semantic structure)
- ``aio``        AI Overviews / answer-engine readiness (structured data,
                 FAQ/HowTo schema, chunkable content, E-E-A-T signals)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# VOCABULARY
# =============================================================================

# Screaming Frog-compatible issue taxonomy.
SeoIssueType = Literal["issue", "warning", "opportunity"]
SeoIssuePriority = Literal["high", "medium", "low"]
SeoPillar = Literal["technical", "content", "security", "social", "geo", "aio"]
SeoCheckScope = Literal["page", "site"]

SeoAuditStatus = Literal["pending", "running", "success", "partial", "failed"]
SeoFixActionType = Literal["modified", "created", "suggested"]


# =============================================================================
# CHECK CATALOG
# =============================================================================

class SeoCheckDefinition(BaseModel):
    """Static definition of a single audit check (catalog entry)."""
    model_config = {"frozen": True, "extra": "forbid"}

    code: str = Field(..., description="Stable machine code, e.g. 'title_missing'")
    name: str = Field(..., description="Display name, e.g. 'Page Titles: Missing'")
    category: str = Field(..., description="Group, e.g. 'Page Titles', 'Security'")
    issue_type: SeoIssueType = Field(..., description="issue | warning | opportunity")
    priority: SeoIssuePriority = Field(..., description="high | medium | low")
    pillar: SeoPillar = Field(default="technical", description="Audit pillar")
    scope: SeoCheckScope = Field(default="page", description="page or site level")
    description: str = Field(..., description="What this check detects and why it matters")
    how_to_fix: str = Field(..., description="Actionable remediation guidance")
    help_url: str = Field(default="", description="Reference documentation URL")
    auto_fixable: bool = Field(
        default=False,
        description="True if the repo-aware fixer can remediate this automatically"
    )


# =============================================================================
# AUDIT INPUT
# =============================================================================

class SeoAuditRequest(BaseModel):
    """Request to run an SEO/GEO/AIO audit against a website."""
    model_config = {"frozen": True, "extra": "forbid"}

    website_url: str = Field(..., description="Root URL to audit (http/https)")
    max_pages: int = Field(default=50, ge=1, le=500, description="Crawl page budget")
    max_depth: int = Field(default=3, ge=0, le=10, description="Max link depth from the root")
    include_sitemap: bool = Field(default=True, description="Seed crawl from sitemap.xml")
    respect_robots: bool = Field(default=True, description="Honor robots.txt disallow rules")
    check_image_sizes: bool = Field(
        default=True,
        description="Issue bounded HEAD requests to measure image weights"
    )
    check_external_links: bool = Field(
        default=False,
        description="Issue bounded HEAD requests to validate external links"
    )
    timeout_seconds: float = Field(default=15.0, gt=0, le=60, description="Per-request timeout")
    monthly_organic_revenue: float = Field(
        default=0.0, ge=0,
        description="Estimated monthly revenue attributable to organic/AI search. "
                    "When set, every finding is quantified as potential monthly "
                    "revenue loss and the delegation plan is WSJF-scored against it."
    )

    @field_validator("website_url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        from urllib.parse import urlparse

        v = v.strip()
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("website_url must be an absolute http(s) URL with a host")
        return v


# =============================================================================
# AUDIT FINDINGS
# =============================================================================

class SeoIssueInstance(BaseModel):
    """A single occurrence of a check firing on a specific URL."""
    model_config = {"frozen": True, "extra": "forbid"}

    check_code: str = Field(..., description="SeoCheckDefinition.code that fired")
    url: str = Field(..., description="Affected URL")
    detail: str = Field(default="", description="Human-readable specifics for this URL")
    evidence: Dict[str, Any] = Field(
        default_factory=dict,
        description="Machine-readable supporting data (lengths, values, selectors)"
    )


class SeoPageAudit(BaseModel):
    """Snapshot of one crawled page with the on-page facts the checks used."""
    model_config = {"frozen": True, "extra": "forbid"}

    url: str = Field(..., description="Requested URL")
    final_url: str = Field(default="", description="URL after redirects (if different)")
    status_code: int = Field(default=0, description="HTTP status code")
    redirected: bool = Field(default=False)
    content_type: str = Field(default="")
    html_bytes: int = Field(default=0, description="Uncompressed HTML document size")
    fetch_ms: int = Field(default=0, description="Fetch time in milliseconds")
    depth: int = Field(default=0, description="Link depth from the crawl root")

    title: str = Field(default="")
    meta_description: str = Field(default="")
    canonical: str = Field(default="")
    lang: str = Field(default="")
    robots_directives: List[str] = Field(default_factory=list)
    h1s: List[str] = Field(default_factory=list)
    h2s: List[str] = Field(default_factory=list)
    word_count: int = Field(default=0)
    flesch_reading_ease: Optional[float] = Field(default=None)

    internal_links: int = Field(default=0)
    external_links: int = Field(default=0)
    images_total: int = Field(default=0)
    structured_data_types: List[str] = Field(default_factory=list)
    has_open_graph: bool = Field(default=False)
    has_twitter_card: bool = Field(default=False)
    has_viewport: bool = Field(default=False)

    issue_codes: List[str] = Field(
        default_factory=list,
        description="Codes of all checks that fired on this page"
    )


class SeoIssueReportRow(BaseModel):
    """Aggregated report row - Screaming Frog CSV compatible."""
    model_config = {"frozen": True, "extra": "forbid"}

    check_code: str = Field(..., description="Stable check code")
    issue_name: str = Field(..., description="'Issue Name' column")
    issue_type: SeoIssueType = Field(..., description="'Issue Type' column")
    issue_priority: SeoIssuePriority = Field(..., description="'Issue Priority' column")
    urls_affected: int = Field(..., ge=0, description="'URLs' column")
    percent_of_total: float = Field(..., ge=0, description="'% of Total' column")
    description: str = Field(..., description="'Description' column")
    how_to_fix: str = Field(..., description="'How To Fix' column")
    help_url: str = Field(default="", description="'Help URL' column")
    pillar: SeoPillar = Field(default="technical")
    auto_fixable: bool = Field(default=False)
    estimated_monthly_revenue_loss: float = Field(
        default=0.0, ge=0,
        description="Heuristic monthly revenue at risk from this finding "
                    "(0 when no revenue baseline was provided)"
    )
    sample_urls: List[str] = Field(
        default_factory=list,
        description="Up to 5 example URLs for quick triage"
    )


class SeoSiteFindings(BaseModel):
    """Site-level facts discovered during the crawl."""
    model_config = {"frozen": True, "extra": "forbid"}

    https: bool = Field(default=False, description="Root URL served over HTTPS")
    robots_txt_present: bool = Field(default=False)
    robots_txt_url: str = Field(default="")
    sitemap_present: bool = Field(default=False)
    sitemap_urls: List[str] = Field(default_factory=list)
    sitemap_in_robots: bool = Field(default=False)
    llms_txt_present: bool = Field(default=False, description="GEO: llms.txt discoverability file")
    rss_feed_present: bool = Field(default=False)
    favicon_present: bool = Field(default=False)
    ai_crawlers_blocked: List[str] = Field(
        default_factory=list,
        description="GEO: AI user-agents disallowed by robots.txt (GPTBot, ClaudeBot, ...)"
    )
    security_headers: Dict[str, bool] = Field(
        default_factory=dict,
        description="Presence of key security headers on the root response"
    )


class SeoDelegationTask(BaseModel):
    """An agent-delegable remediation work package derived from the findings.

    Findings are grouped into coherent tasks (by category) with a priority,
    effort estimate and suggested specialist family, so the orchestrator (or a
    human) can assign each package to the right agent.
    """
    model_config = {"frozen": True, "extra": "forbid"}

    task_key: str = Field(..., description="Stable key, e.g. 'seo-fix-page-titles'")
    title: str = Field(..., description="Actionable task title")
    priority: SeoIssuePriority = Field(..., description="Highest priority among grouped findings")
    effort: Literal["S", "M", "L"] = Field(..., description="Effort estimate from affected URL volume")
    pillar: SeoPillar = Field(default="technical")
    category: str = Field(..., description="Finding category this task covers")
    suggested_specialist: str = Field(
        ..., description="SpecialistFamily best suited to execute this task"
    )
    check_codes: List[str] = Field(default_factory=list)
    urls_affected: int = Field(default=0)
    auto_fixable: bool = Field(
        default=False,
        description="True when every grouped finding can be fixed by the repo-aware fixer"
    )
    instructions: str = Field(..., description="Concrete remediation instructions for the agent")
    sample_urls: List[str] = Field(default_factory=list)

    # Portfolio quantification (WSJF - SAFe Weighted Shortest Job First).
    # These slot directly into agents/portfolio.py Initiative fields so SEO
    # remediation competes for capacity against the rest of the portfolio.
    estimated_monthly_value: float = Field(
        default=0.0, ge=0,
        description="Monthly revenue recoverable by completing this package"
    )
    business_value: int = Field(default=1, ge=1, description="WSJF business value (Fibonacci)")
    time_criticality: int = Field(default=1, ge=1, description="WSJF time criticality (Fibonacci)")
    risk_reduction: int = Field(default=1, ge=1, description="WSJF risk reduction (Fibonacci)")
    job_size: int = Field(default=1, ge=1, description="WSJF job size (Fibonacci)")
    wsjf_score: float = Field(
        default=0.0, ge=0,
        description="WSJF = (business_value + time_criticality + risk_reduction) / job_size"
    )


class SeoAuditReport(BaseModel):
    """Complete result of one audit run."""
    model_config = {"frozen": True, "extra": "forbid"}

    audit_id: str = Field(..., description="Unique audit identifier")
    company_id: Optional[str] = Field(default=None, description="Owning company, if any")
    website_url: str = Field(..., description="Audited root URL")
    status: SeoAuditStatus = Field(default="success")
    error: str = Field(default="", description="Failure reason when status != success")

    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = Field(default=None)

    pages_crawled: int = Field(default=0)
    pages_failed: int = Field(default=0)
    urls_discovered: int = Field(default=0)

    health_score: float = Field(
        default=100.0, ge=0, le=100,
        description="Overall 0-100 weighted health score (100 = clean)"
    )
    pillar_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="0-100 score per pillar (technical/content/security/social/geo/aio)"
    )
    total_issues: int = Field(default=0, description="Total issue instances found")
    issues_by_priority: Dict[str, int] = Field(default_factory=dict)
    issues_by_type: Dict[str, int] = Field(default_factory=dict)

    monthly_organic_revenue: float = Field(
        default=0.0, ge=0,
        description="Revenue baseline supplied in the request (0 = not modeled)"
    )
    estimated_monthly_revenue_loss: float = Field(
        default=0.0, ge=0,
        description="Total estimated monthly revenue at risk across all findings, "
                    "capped at 35% of the baseline"
    )

    rows: List[SeoIssueReportRow] = Field(
        default_factory=list,
        description="Aggregated, prioritized report rows (Screaming Frog compatible)"
    )
    issues: List[SeoIssueInstance] = Field(
        default_factory=list,
        description="Every individual issue occurrence"
    )
    pages: List[SeoPageAudit] = Field(default_factory=list)
    site: SeoSiteFindings = Field(default_factory=SeoSiteFindings)
    delegation_plan: List[SeoDelegationTask] = Field(
        default_factory=list,
        description="Agent-delegable work packages grouping the findings into tasks"
    )
    summary: str = Field(default="", description="Human-readable executive summary")


class SeoAuditSummary(BaseModel):
    """Lightweight listing entry for past audits."""
    model_config = {"frozen": True, "extra": "forbid"}

    audit_id: str
    company_id: Optional[str] = None
    website_url: str
    status: SeoAuditStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    pages_crawled: int = 0
    total_issues: int = 0
    health_score: float = 100.0


# =============================================================================
# REPO-AWARE AUTO-FIXING
# =============================================================================

class SeoFixRequest(BaseModel):
    """Request to remediate auto-fixable findings in a local code repository."""
    model_config = {"frozen": True, "extra": "forbid"}

    repo_path: str = Field(..., description="Path to the repo checkout (within the workspace root)")
    audit_id: Optional[str] = Field(
        default=None,
        description="Audit whose findings should drive the fixes; omit to run all fixers"
    )
    base_url: str = Field(
        default="",
        description="Canonical site base URL used for canonical/sitemap generation"
    )
    apply: bool = Field(
        default=False,
        description="False = dry run (diffs only); True = write changes to disk"
    )
    include_checks: List[str] = Field(
        default_factory=list,
        description="Restrict to these check codes; empty = all auto-fixable checks"
    )
    default_lang: str = Field(default="en", description="lang attribute used when adding one")
    site_name: str = Field(default="", description="Site name used in generated llms.txt / OG tags")


class SeoFixAction(BaseModel):
    """One concrete remediation performed (or proposed) by the fixer."""
    model_config = {"frozen": True, "extra": "forbid"}

    check_code: str = Field(..., description="Check this action remediates")
    file_path: str = Field(..., description="Repo-relative file path")
    action: SeoFixActionType = Field(..., description="modified | created | suggested")
    description: str = Field(..., description="What was changed and why")
    diff: str = Field(default="", description="Unified diff (or full content for created files)")
    applied: bool = Field(default=False, description="True when written to disk")


class SeoFixResult(BaseModel):
    """Result of a fixer run."""
    model_config = {"frozen": True, "extra": "forbid"}

    repo_path: str
    audit_id: Optional[str] = None
    dry_run: bool = True
    files_scanned: int = 0
    files_modified: int = 0
    files_created: int = 0
    suggestions: int = 0
    actions: List[SeoFixAction] = Field(default_factory=list)
    summary: str = Field(default="")

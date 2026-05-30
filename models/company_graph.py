"""
Company Graph - Canonical Core Model for Agency Core v5

This module defines the typed, serializable models for the Company Graph,
which serves as the single source of truth for company context, systems,
and specialist provisioning in the autonomous agency platform.

Design Principles:
- All models are immutable (frozen=True) after construction
- All models forbid extra fields (extra="forbid") to prevent drift
- All string fields are stripped and validated
- All timestamps use UTC
- All IDs are generated using ObjectId for MongoDB compatibility
"""

from __future__ import annotations
from typing import Any, Literal, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from bson import ObjectId
import re
import secrets

# =============================================================================
# ENUMS AND LITERALS
# =============================================================================

# Business categories for company classification
BusinessCategory = Literal[
    "retail", "ecommerce", "saas", "finance", "banking", "insurance",
    "healthcare", "education", "media", "entertainment", "gaming",
    "social", "marketplace", "logistics", "manufacturing", "energy",
    "real_estate", "legal", "government", "nonprofit", "consulting",
    "technology", "telecom", "travel", "hospitality", "food", "other"
]

# System types for detected business systems
SystemType = Literal[
    "CMS", "CRM", "OMS", "PIM", "DAM", "ERP", "HRM", "LMS",
    "analytics", "payment_gateway", "shipping", "tax", "inventory",
    "marketing_automation", "email_service", "search", "database",
    "cache", "cdc", "message_queue", "api_gateway", "auth", "billing",
    "support", "chat", "video", "voice", "iot", "ai_ml", "custom"
]

# Specialist families for dynamic provisioning
SpecialistFamily = Literal[
    "engineering", "qa", "docs", "analytics", "ecommerce",
    "operations", "agile", "portfolio", "security", "devops",
    "data", "ml", "frontend", "backend", "fullstack", "mobile",
    "cloud", "infra", "architecture", "product", "design", "ux"
]

# Workflow phases (aligned with CRISPY workflow)
WorkflowPhaseType = Literal[
    "classify", "context", "research", "investigate", "structure",
    "plan", "awaiting_approval", "executing", "reviewing", "verifying",
    "report", "summarize", "monitor"
]

# Workflow statuses
WorkflowStatus = Literal[
    "pending", "running", "succeeded", "failed", "cancelled", "paused"
]

# Approval gate statuses
ApprovalStatus = Literal["pending", "approved", "rejected", "skipped"]

# Connector types for system integrations
ConnectorType = Literal[
    "api_key", "oauth2", "webhook", "service_account", "jwt",
    "ssh", "database", "sftp", "mqtt", "grpc", "custom"
]

# Knowledge item types
KnowledgeType = Literal[
    "documentation", "decision", "learning", "best_practice",
    "lesson_learned", "architecture", "api_spec", "data_schema",
    "process", "policy", "template", "example", "reference"
]


# =============================================================================
# SUPPORTING MODELS
# =============================================================================

class StackInference(BaseModel):
    """Inferred technology stack from website/repo analysis."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    frameworks: List[str] = Field(
        default_factory=list,
        description="Detected web frameworks (e.g., React, Vue, Angular, Next.js)"
    )
    languages: List[str] = Field(
        default_factory=list,
        description="Detected programming languages"
    )
    libraries: List[str] = Field(
        default_factory=list,
        description="Detected libraries and packages"
    )
    cms: List[str] = Field(
        default_factory=list,
        description="Detected CMS platforms (e.g., WordPress, Shopify, Drupal)"
    )
    databases: List[str] = Field(
        default_factory=list,
        description="Detected database technologies"
    )
    analytics: List[str] = Field(
        default_factory=list,
        description="Detected analytics platforms (e.g., Google Analytics, Mixpanel)"
    )
    payment_processors: List[str] = Field(
        default_factory=list,
        description="Detected payment processors (e.g., Stripe, PayPal)"
    )
    hosting: List[str] = Field(
        default_factory=list,
        description="Detected hosting providers (e.g., AWS, Vercel, Netlify)"
    )
    ci_cd: List[str] = Field(
        default_factory=list,
        description="Detected CI/CD tools (e.g., GitHub Actions, Jenkins)"
    )
    infrastructure: List[str] = Field(
        default_factory=list,
        description="Detected infrastructure components"
    )
    confidence_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Confidence scores for each detection (0.0-1.0)"
    )
    detected_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the stack inference was performed"
    )
    source: str = Field(
        default="website_scan",
        description="Source of the stack inference (website_scan, repo_analysis, manual)"
    )
    
    @field_validator("*", mode="before")
    @classmethod
    def _strip_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip() or None
        return v


class Evidence(BaseModel):
    """Evidence supporting a system detection."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    type: str = Field(..., description="Type of evidence (meta_tag, script, header, etc.)")
    value: str = Field(..., description="The actual evidence value")
    location: str = Field(
        default="",
        description="Where the evidence was found (e.g., HTML head, specific file)"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        default=0.8,
        description="Confidence score for this evidence (0.0-1.0)"
    )
    
    @field_validator("type", "value", "location", mode="before")
    @classmethod
    def _strip_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v


class Connector(BaseModel):
    """Connection configuration for a business system."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    id: str = Field(
        default_factory=lambda: str(ObjectId()),
        description="Unique connector identifier"
    )
    name: str = Field(..., description="Human-readable connector name")
    connector_type: ConnectorType = Field(
        ...,
        description="Type of authentication/connection"
    )
    system_type: SystemType = Field(
        ...,
        description="Type of system this connector is for"
    )
    system_name: str = Field(..., description="Name of the system (e.g., 'Shopify', 'Stripe')")
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Connection configuration (excluding secrets)"
    )
    is_configured: bool = Field(
        default=False,
        description="Whether this connector has valid credentials"
    )
    last_validated: datetime | None = Field(
        default=None,
        description="When the connector was last validated"
    )
    validation_error: str | None = Field(
        default=None,
        description="Error message if validation failed"
    )
    scopes: List[str] = Field(
        default_factory=list,
        description="OAuth scopes or permissions granted"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the connector was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the connector was last updated"
    )
    
    @field_validator("name", "system_name", mode="before")
    @classmethod
    def _strip_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("name and system_name must not be blank")
            return stripped
        return v


class KnowledgeItem(BaseModel):
    """Structured knowledge about the company, systems, or processes."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    id: str = Field(
        default_factory=lambda: str(ObjectId()),
        description="Unique knowledge item identifier"
    )
    title: str = Field(..., description="Title of the knowledge item")
    knowledge_type: KnowledgeType = Field(
        ...,
        description="Category of knowledge"
    )
    content: str = Field(..., description="The actual knowledge content (markdown supported)")
    content_hash: str = Field(
        default="",
        description="SHA-256 hash of the content for change detection"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorization and search"
    )
    related_systems: List[str] = Field(
        default_factory=list,
        description="System IDs this knowledge relates to"
    )
    related_specialists: List[str] = Field(
        default_factory=list,
        description="Specialist IDs who should be aware of this knowledge"
    )
    source: str = Field(
        default="manual",
        description="Source of the knowledge (manual, automated_scan, documentation_import)"
    )
    author: str | None = Field(
        default=None,
        description="Who created this knowledge item"
    )
    is_active: bool = Field(
        default=True,
        description="Whether this knowledge is currently relevant"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the knowledge was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the knowledge was last updated"
    )
    last_accessed: datetime | None = Field(
        default=None,
        description="When this knowledge was last accessed/used"
    )
    
    @field_validator("title", "content", mode="before")
    @classmethod
    def _strip_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("title and content must not be blank")
            return stripped
        return v


class ApprovalPolicy(BaseModel):
    """Approval policies for HITL (Human-in-the-Loop) gates."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    id: str = Field(
        default_factory=lambda: str(ObjectId()),
        description="Unique policy identifier"
    )
    name: str = Field(..., description="Human-readable policy name")
    description: str = Field(
        default="",
        description="Description of when this policy applies"
    )
    # Conditions for when this policy applies
    applies_to_workflow_phases: List[WorkflowPhaseType] = Field(
        default_factory=list,
        description="Which workflow phases require approval under this policy"
    )
    applies_to_specialists: List[str] = Field(
        default_factory=list,
        description="Which specialist families/IDs require approval"
    )
    applies_to_systems: List[str] = Field(
        default_factory=list,
        description="Which system types require approval"
    )
    risk_threshold: float = Field(
        ge=0.0, le=1.0,
        default=0.5,
        description="Risk score threshold (0.0-1.0) above which approval is required"
    )
    # Approval configuration
    require_human_approval: bool = Field(
        default=True,
        description="Whether human approval is required"
    )
    auto_approve_if: dict[str, Any] = Field(
        default_factory=dict,
        description="Conditions under which auto-approval is allowed"
    )
    approvers: List[str] = Field(
        default_factory=list,
        description="List of user IDs or roles who can approve"
    )
    notification_channels: List[str] = Field(
        default_factory=list,
        description="Where to send approval requests (email, slack, etc.)"
    )
    timeout_minutes: int = Field(
        ge=1, le=1440,
        default=60,
        description="How long to wait for approval before timing out"
    )
    escalation_path: List[str] = Field(
        default_factory=list,
        description="Who to escalate to if not approved in time"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the policy was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the policy was last updated"
    )
    
    @field_validator("name", mode="before")
    @classmethod
    def _strip_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("name must not be blank")
            return stripped
        return v


# =============================================================================
# CORE ENTITIES
# =============================================================================

class DetectedSystem(BaseModel):
    """A business system detected on a company's website or in their stack."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    id: str = Field(
        default_factory=lambda: str(ObjectId()),
        description="Unique detected system identifier"
    )
    system_type: SystemType = Field(
        ...,
        description="Category of the detected system"
    )
    name: str = Field(..., description="Name of the system (e.g., 'Shopify', 'Salesforce')")
    version: str | None = Field(
        default=None,
        description="Detected version if available"
    )
    evidence: List[Evidence] = Field(
        default_factory=list,
        description="Evidence supporting this detection"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        default=0.0,
        description="Overall confidence score (0.0-1.0)"
    )
    is_active: bool = Field(
        default=True,
        description="Whether this system is currently in use"
    )
    last_detected: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this system was last detected"
    )
    connectors: List[str] = Field(
        default_factory=list,
        description="IDs of connectors configured for this system"
    )
    configuration: dict[str, Any] = Field(
        default_factory=dict,
        description="Detected configuration details"
    )
    integrations: List[str] = Field(
        default_factory=list,
        description="Other systems this system integrates with"
    )
    
    @field_validator("name", mode="before")
    @classmethod
    def _strip_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("name must not be blank")
            return stripped
        return v
    
    @property
    def primary_evidence(self) -> str:
        """Get the most confident evidence description."""
        if not self.evidence:
            return ""
        sorted_evidence = sorted(self.evidence, key=lambda e: e.confidence, reverse=True)
        return f"{sorted_evidence[0].type}: {sorted_evidence[0].value}"


class Website(BaseModel):
    """A company website with detected systems and stack inference."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    id: str = Field(
        default_factory=lambda: str(ObjectId()),
        description="Unique website identifier"
    )
    url: str = Field(..., description="The website URL")
    is_primary: bool = Field(
        default=False,
        description="Whether this is the company's primary website"
    )
    inferred_stack: StackInference | None = Field(
        default=None,
        description="Inferred technology stack from scanning this website"
    )
    detected_systems: List[DetectedSystem] = Field(
        default_factory=list,
        description="Business systems detected on this website"
    )
    confidence_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Confidence scores for various detections"
    )
    last_scanned: datetime | None = Field(
        default=None,
        description="When the website was last scanned"
    )
    scan_status: str | None = Field(
        default=None,
        description="Status of the last scan (success, failed, pending)"
    )
    scan_error: str | None = Field(
        default=None,
        description="Error message if scan failed"
    )
    sitemap_urls: List[str] = Field(
        default_factory=list,
        description="URLs from the website's sitemap"
    )
    important_pages: List[str] = Field(
        default_factory=list,
        description="Important pages identified on the website"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the website was added to the company graph"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the website was last updated"
    )
    
    @field_validator("url", mode="before")
    @classmethod
    def _validate_url(cls, v: Any) -> str:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("url must not be blank")
            # Add https:// if missing
            if not stripped.startswith(("http://", "https://")):
                stripped = "https://" + stripped
            return stripped
        return v


class Repo(BaseModel):
    """A company repository with detected technologies and metadata."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    id: str = Field(
        default_factory=lambda: str(ObjectId()),
        description="Unique repository identifier"
    )
    url: str = Field(..., description="Repository URL")
    provider: Literal["github", "gitlab", "bitbucket", "azure_devops", "other"] = Field(
        ...,
        description="Git provider"
    )
    name: str = Field(..., description="Repository name (e.g., owner/repo)")
    full_name: str = Field(..., description="Full repository name with owner")
    is_private: bool = Field(
        default=False,
        description="Whether the repository is private"
    )
    description: str | None = Field(
        default=None,
        description="Repository description"
    )
    homepage: str | None = Field(
        default=None,
        description="Repository homepage URL"
    )
    languages: List[str] = Field(
        default_factory=list,
        description="Programming languages used in the repository"
    )
    frameworks: List[str] = Field(
        default_factory=list,
        description="Frameworks detected in the repository"
    )
    topics: List[str] = Field(
        default_factory=list,
        description="Repository topics/tags"
    )
    ci_cd: str | None = Field(
        default=None,
        description="CI/CD configuration detected"
    )
    size_kb: int = Field(
        default=0,
        description="Repository size in kilobytes"
    )
    stargazers_count: int = Field(
        default=0,
        description="Number of stars"
    )
    forks_count: int = Field(
        default=0,
        description="Number of forks"
    )
    open_issues_count: int = Field(
        default=0,
        description="Number of open issues"
    )
    last_push: datetime | None = Field(
        default=None,
        description="When the repository was last pushed to"
    )
    last_scanned: datetime | None = Field(
        default=None,
        description="When the repository was last scanned for stack inference"
    )
    inferred_stack: StackInference | None = Field(
        default=None,
        description="Inferred technology stack from repository analysis"
    )
    detected_systems: List[str] = Field(
        default_factory=list,
        description="System IDs detected in this repository"
    )
    is_connected: bool = Field(
        default=False,
        description="Whether we have API access to this repository"
    )
    connection_error: str | None = Field(
        default=None,
        description="Error message if connection failed"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the repository was added to the company graph"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the repository was last updated"
    )
    
    @field_validator("url", "name", "full_name", mode="before")
    @classmethod
    def _validate_strings(cls, v: Any) -> str:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("url, name, and full_name must not be blank")
            return stripped
        return v
    
    @property
    def repo_owner(self) -> str:
        """Extract the owner from the full name."""
        return self.full_name.split("/")[0] if "/" in self.full_name else self.full_name
    
    @property
    def repo_name(self) -> str:
        """Extract the repository name from the full name."""
        return self.full_name.split("/")[-1] if "/" in self.full_name else self.full_name


class BusinessSystem(BaseModel):
    """A business system used by the company."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    id: str = Field(
        default_factory=lambda: str(ObjectId()),
        description="Unique business system identifier"
    )
    system_type: SystemType = Field(
        ...,
        description="Category of the business system"
    )
    name: str = Field(..., description="Name of the system (e.g., 'Shopify Plus', 'Salesforce CRM')")
    category: str = Field(
        default="",
        description="Business category (e.g., 'E-commerce Platform', 'Customer Relationship Management')"
    )
    description: str = Field(
        default="",
        description="Description of what this system does"
    )
    version: str | None = Field(
        default=None,
        description="Version of the system"
    )
    is_primary: bool = Field(
        default=False,
        description="Whether this is the primary system of its type"
    )
    is_custom: bool = Field(
        default=False,
        description="Whether this is a custom-built system"
    )
    connectors: List[Connector] = Field(
        default_factory=list,
        description="Connectors configured for this system"
    )
    configured_connector_ids: List[str] = Field(
        default_factory=list,
        description="IDs of connectors that are properly configured"
    )
    integrations: List[str] = Field(
        default_factory=list,
        description="IDs of other systems this system integrates with"
    )
    websites: List[str] = Field(
        default_factory=list,
        description="Website IDs where this system is detected"
    )
    repos: List[str] = Field(
        default_factory=list,
        description="Repository IDs related to this system"
    )
    status: Literal["active", "inactive", "deprecated", "planned"] = Field(
        default="active",
        description="Current status of the system"
    )
    health_status: Literal["healthy", "degraded", "unhealthy", "unknown"] = Field(
        default="unknown",
        description="Current health status"
    )
    last_health_check: datetime | None = Field(
        default=None,
        description="When the last health check was performed"
    )
    documentation_url: str | None = Field(
        default=None,
        description="URL to system documentation"
    )
    admin_url: str | None = Field(
        default=None,
        description="URL to system admin interface"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the system was added to the company graph"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the system was last updated"
    )
    
    @field_validator("name", mode="before")
    @classmethod
    def _validate_name(cls, v: Any) -> str:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("name must not be blank")
            return stripped
        return v


class Specialist(BaseModel):
    """A specialist agent that can be provisioned for company-specific tasks."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    id: str = Field(
        default_factory=lambda: str(ObjectId()),
        description="Unique specialist identifier"
    )
    name: str = Field(..., description="Human-readable specialist name")
    family: SpecialistFamily = Field(
        ...,
        description="Family/category of specialist"
    )
    description: str = Field(
        default="",
        description="Description of what this specialist does"
    )
    capabilities: List[str] = Field(
        default_factory=list,
        description="List of capabilities this specialist has"
    )
    tools: List[str] = Field(
        default_factory=list,
        description="List of tools this specialist can use"
    )
    model_preference: str | None = Field(
        default=None,
        description="Preferred model for this specialist"
    )
    runtime: Literal["internal_agent", "claude_code", "goose", "aider", "hermes", "opencode", "custom"] | None = Field(
        default=None,
        description="Preferred runtime for this specialist"
    )
    # System specializations
    specialized_systems: List[str] = Field(
        default_factory=list,
        description="System IDs this specialist is specialized for"
    )
    system_types: List[SystemType] = Field(
        default_factory=list,
        description="System types this specialist can work with"
    )
    # Company-specific configuration
    company_id: str | None = Field(
        default=None,
        description="Company ID this specialist is provisioned for"
    )
    is_provisioned: bool = Field(
        default=False,
        description="Whether this specialist is currently provisioned"
    )
    provisioned_at: datetime | None = Field(
        default=None,
        description="When the specialist was provisioned"
    )
    # Status and health
    status: Literal["available", "busy", "error", "disabled"] = Field(
        default="available",
        description="Current status of the specialist"
    )
    last_activity: datetime | None = Field(
        default=None,
        description="When the specialist was last active"
    )
    error_count: int = Field(
        default=0,
        description="Number of errors encountered"
    )
    success_count: int = Field(
        default=0,
        description="Number of successful tasks completed"
    )
    # Configuration
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Specialist-specific configuration"
    )
    # Access control
    allowed_users: List[str] = Field(
        default_factory=list,
        description="User IDs who can use this specialist"
    )
    allowed_repos: List[str] = Field(
        default_factory=list,
        description="Repository IDs this specialist can access"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the specialist was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the specialist was last updated"
    )
    
    @field_validator("name", mode="before")
    @classmethod
    def _validate_name(cls, v: Any) -> str:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("name must not be blank")
            return stripped
        return v
    
    def can_handle_task(self, task_capabilities: List[str]) -> bool:
        """Check if this specialist can handle a task with given capabilities."""
        if not self.is_provisioned or self.status != "available":
            return False
        # Check if any of the specialist's capabilities match the task requirements
        return any(cap in self.capabilities for cap in task_capabilities)


class WorkflowAssignment(BaseModel):
    """Assignment of a specialist to a workflow phase."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    id: str = Field(
        default_factory=lambda: str(ObjectId()),
        description="Unique assignment identifier"
    )
    workflow_id: str = Field(..., description="ID of the workflow")
    phase: WorkflowPhaseType = Field(
        ...,
        description="Workflow phase this specialist is assigned to"
    )
    specialist_id: str = Field(..., description="ID of the assigned specialist")
    role: str = Field(
        default="executor",
        description="Role of the specialist in this workflow (executor, reviewer, verifier, etc.)"
    )
    status: Literal["pending", "assigned", "working", "completed", "failed"] = Field(
        default="pending",
        description="Status of this assignment"
    )
    assigned_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the specialist was assigned"
    )
    started_at: datetime | None = Field(
        default=None,
        description="When the specialist started working"
    )
    completed_at: datetime | None = Field(
        default=None,
        description="When the specialist completed their work"
    )
    result: dict[str, Any] | None = Field(
        default=None,
        description="Result of the specialist's work"
    )
    error: str | None = Field(
        default=None,
        description="Error message if the assignment failed"
    )
    
    @field_validator("workflow_id", "specialist_id", mode="before")
    @classmethod
    def _validate_ids(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class Workflow(BaseModel):
    """A workflow that defines a sequence of phases for completing tasks."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    id: str = Field(
        default_factory=lambda: str(ObjectId()),
        description="Unique workflow identifier"
    )
    name: str = Field(..., description="Human-readable workflow name")
    description: str = Field(
        default="",
        description="Description of what this workflow does"
    )
    phases: List[WorkflowPhaseType] = Field(
        default_factory=list,
        description="Ordered list of phases in this workflow"
    )
    triggers: List[str] = Field(
        default_factory=list,
        description="Events that can trigger this workflow"
    )
    specialist_assignments: List[WorkflowAssignment] = Field(
        default_factory=list,
        description="Assignments of specialists to workflow phases"
    )
    # Context binding
    company_id: str | None = Field(
        default=None,
        description="Company ID this workflow is associated with"
    )
    repo_id: str | None = Field(
        default=None,
        description="Repository ID this workflow is associated with"
    )
    system_ids: List[str] = Field(
        default_factory=list,
        description="System IDs this workflow involves"
    )
    # Configuration
    is_default: bool = Field(
        default=False,
        description="Whether this is the default workflow for its context"
    )
    is_active: bool = Field(
        default=True,
        description="Whether this workflow is currently active"
    )
    requires_approval: bool = Field(
        default=False,
        description="Whether this workflow requires approval before execution"
    )
    approval_policy_id: str | None = Field(
        default=None,
        description="ID of the approval policy to use"
    )
    # Execution settings
    timeout_minutes: int = Field(
        ge=1, le=1440,
        default=60,
        description="Maximum execution time in minutes"
    )
    retry_attempts: int = Field(
        ge=0, le=5,
        default=0,
        description="Number of retry attempts on failure"
    )
    # Metadata
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorization"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the workflow was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the workflow was last updated"
    )
    last_executed: datetime | None = Field(
        default=None,
        description="When the workflow was last executed"
    )
    execution_count: int = Field(
        default=0,
        description="Number of times this workflow has been executed"
    )
    
    @field_validator("name", mode="before")
    @classmethod
    def _validate_name(cls, v: Any) -> str:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("name must not be blank")
            return stripped
        return v
    
    def get_phase_index(self, phase: WorkflowPhaseType) -> int:
        """Get the index of a phase in the workflow."""
        try:
            return self.phases.index(phase)
        except ValueError:
            return -1


class Company(BaseModel):
    """The core company entity - root of the Company Graph."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    id: str = Field(
        default_factory=lambda: str(ObjectId()),
        description="Unique company identifier"
    )
    name: str = Field(..., description="Company name")
    domain: str = Field(..., description="Primary domain (e.g., strikersam.com)")
    business_category: BusinessCategory = Field(
        default="other",
        description="Primary business category"
    )
    secondary_categories: List[BusinessCategory] = Field(
        default_factory=list,
        description="Additional business categories"
    )
    description: str = Field(
        default="",
        description="Company description"
    )
    tagline: str = Field(
        default="",
        description="Company tagline or slogan"
    )
    founded_year: int | None = Field(
        default=None,
        description="Year the company was founded"
    )
    employee_count: int | None = Field(
        default=None,
        description="Approximate number of employees"
    )
    revenue_range: str | None = Field(
        default=None,
        description="Revenue range (e.g., '1M-10M', '10M-50M')"
    )
    # Contact information
    email: str | None = Field(
        default=None,
        description="Primary contact email"
    )
    phone: str | None = Field(
        default=None,
        description="Primary contact phone"
    )
    address: dict[str, Any] | None = Field(
        default=None,
        description="Physical address"
    )
    # Branding
    logo_url: str | None = Field(
        default=None,
        description="URL to company logo"
    )
    brand_colors: dict[str, str] = Field(
        default_factory=dict,
        description="Brand colors (name: hex_code)"
    )
    # Online presence
    websites: List[str] = Field(
        default_factory=list,
        description="Website IDs belonging to this company"
    )
    repos: List[str] = Field(
        default_factory=list,
        description="Repository IDs belonging to this company"
    )
    systems: List[str] = Field(
        default_factory=list,
        description="Business system IDs used by this company"
    )
    specialists: List[str] = Field(
        default_factory=list,
        description="Specialist IDs provisioned for this company"
    )
    workflows: List[str] = Field(
        default_factory=list,
        description="Workflow IDs available to this company"
    )
    knowledge: List[str] = Field(
        default_factory=list,
        description="Knowledge item IDs belonging to this company"
    )
    connectors: List[str] = Field(
        default_factory=list,
        description="Connector IDs configured for this company"
    )
    approval_policies: List[str] = Field(
        default_factory=list,
        description="Approval policy IDs for this company"
    )
    # Status and metadata
    is_active: bool = Field(
        default=True,
        description="Whether this company is active"
    )
    onboarding_status: Literal[
        # Granular scan states
        "not_started", "scanning", "detected", "configured",
        # Lifecycle states written by OnboardingService.start_onboarding
        "in_progress", "paused", "failed", "cancelled",
        "complete",
    ] = Field(
        default="not_started",
        description="Current onboarding status"
    )
    onboarding_progress: float = Field(
        ge=0.0, le=1.0,
        default=0.0,
        description="Onboarding progress (0.0-1.0)"
    )
    # Integration settings
    integration_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Company-specific integration configuration"
    )
    # Access control
    owner_id: str | None = Field(
        default=None,
        description="User ID of the company owner"
    )
    admin_ids: List[str] = Field(
        default_factory=list,
        description="User IDs with admin access"
    )
    member_ids: List[str] = Field(
        default_factory=list,
        description="User IDs with member access"
    )
    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the company was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the company was last updated"
    )
    last_activity: datetime | None = Field(
        default=None,
        description="When the company had last activity"
    )
    
    @field_validator("name", "domain", mode="before")
    @classmethod
    def _validate_required(cls, v: Any) -> str:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("name and domain must not be blank")
            return stripped
        return v
    
    @field_validator("domain", mode="before")
    @classmethod
    def _validate_domain(cls, v: Any) -> str:
        if isinstance(v, str):
            stripped = v.strip().lower()
            if not stripped:
                raise ValueError("domain must not be blank")
            # Remove protocol and path if present
            if stripped.startswith(("http://", "https://")):
                stripped = stripped.split("//")[1].split("/")[0]
            # Basic domain validation
            if not re.match(r"^[a-z0-9\-\.]+\.[a-z]{2,}$", stripped):
                raise ValueError("domain must be a valid domain name")
            return stripped
        return v
    
    @field_validator("email", mode="before")
    @classmethod
    def _validate_email(cls, v: Any) -> str | None:
        if isinstance(v, str):
            stripped = v.strip().lower()
            if stripped and not re.match(r"^[^@]+@[^@]+\.[^@]+$", stripped):
                raise ValueError("email must be a valid email address")
            return stripped if stripped else None
        return v


# =============================================================================
# COMPANY GRAPH (ROOT MODEL)
# =============================================================================

class CompanyGraph(BaseModel):
    """
    The complete Company Graph - canonical core model for Agency Core v5.
    
    This model represents the entire knowledge graph for a company, including
    all websites, repositories, systems, specialists, workflows, and knowledge.
    It serves as the single source of truth for company context in the
    autonomous agency platform.
    """
    model_config = {"frozen": True, "extra": "forbid"}
    
    # Metadata
    id: str = Field(
        default_factory=lambda: str(ObjectId()),
        description="Unique graph identifier"
    )
    company_id: str = Field(
        ...,
        description="ID of the company this graph belongs to"
    )
    version: str = Field(
        default="1.0",
        description="Graph schema version"
    )
    snapshot_id: str | None = Field(
        default=None,
        description="ID of the snapshot this graph was built from"
    )
    
    # Core entities
    company: Company = Field(
        ...,
        description="The company entity"
    )
    websites: List[Website] = Field(
        default_factory=list,
        description="All websites belonging to the company"
    )
    repos: List[Repo] = Field(
        default_factory=list,
        description="All repositories belonging to the company"
    )
    systems: List[BusinessSystem] = Field(
        default_factory=list,
        description="All business systems used by the company"
    )
    specialists: List[Specialist] = Field(
        default_factory=list,
        description="All specialists provisioned for the company"
    )
    workflows: List[Workflow] = Field(
        default_factory=list,
        description="All workflows available to the company"
    )
    knowledge: List[KnowledgeItem] = Field(
        default_factory=list,
        description="All knowledge items for the company"
    )
    
    # Supporting entities
    connectors: List[Connector] = Field(
        default_factory=list,
        description="All connectors configured for the company"
    )
    approval_policies: List[ApprovalPolicy] = Field(
        default_factory=list,
        description="All approval policies for the company"
    )
    
    # Graph metadata
    detected_systems: List[DetectedSystem] = Field(
        default_factory=list,
        description="All detected systems across websites and repos"
    )
    
    # Computed properties
    inference_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of stack inference results"
    )
    
    # Status
    is_complete: bool = Field(
        default=False,
        description="Whether the graph has been fully populated"
    )
    completeness_score: float = Field(
        ge=0.0, le=1.0,
        default=0.0,
        description="How complete the graph is (0.0-1.0)"
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the graph was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the graph was last updated"
    )
    last_synced: datetime | None = Field(
        default=None,
        description="When the graph was last synced with external sources"
    )
    
    # Methods for working with the graph
    def get_website_by_url(self, url: str) -> Website | None:
        """Find a website by its URL."""
        for website in self.websites:
            if website.url.lower() == url.lower():
                return website
        return None
    
    def get_repo_by_url(self, url: str) -> Repo | None:
        """Find a repository by its URL."""
        for repo in self.repos:
            if repo.url.lower() == url.lower():
                return repo
        return None
    
    def get_system_by_type(self, system_type: SystemType) -> List[BusinessSystem]:
        """Find all systems of a specific type."""
        return [s for s in self.systems if s.system_type == system_type]
    
    def get_specialists_by_family(self, family: SpecialistFamily) -> List[Specialist]:
        """Find all specialists of a specific family."""
        return [s for s in self.specialists if s.family == family]
    
    def get_specialists_for_task(self, capabilities: List[str]) -> List[Specialist]:
        """Find specialists that can handle a task with given capabilities."""
        return [s for s in self.specialists if s.can_handle_task(capabilities)]
    
    def get_workflow_by_name(self, name: str) -> Workflow | None:
        """Find a workflow by its name."""
        for workflow in self.workflows:
            if workflow.name.lower() == name.lower():
                return workflow
        return None
    
    def get_knowledge_by_tags(self, tags: List[str]) -> List[KnowledgeItem]:
        """Find knowledge items matching any of the given tags."""
        tag_set = set(tags)
        return [k for k in self.knowledge if tag_set.intersection(set(k.tags))]
    
    def get_connector_for_system(self, system_id: str) -> List[Connector]:
        """Find connectors configured for a specific system."""
        return [
            c for c in self.connectors
            if c.system_type in [s.system_type for s in self.systems if s.id == system_id]
        ]


# =============================================================================
# GRAPH SNAPSHOT (FOR HISTORY AND ROLLBACK)
# =============================================================================

class CompanyGraphSnapshot(BaseModel):
    """A point-in-time snapshot of a Company Graph for history and rollback."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    id: str = Field(
        default_factory=lambda: str(ObjectId()),
        description="Unique snapshot identifier"
    )
    company_id: str = Field(
        ...,
        description="ID of the company"
    )
    graph_id: str = Field(
        ...,
        description="ID of the graph this snapshot was taken from"
    )
    snapshot_data: dict[str, Any] = Field(
        ...,
        description="The complete graph data at the time of snapshot"
    )
    change_description: str = Field(
        default="",
        description="Description of what changed since last snapshot"
    )
    created_by: str | None = Field(
        default=None,
        description="User ID who created this snapshot"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the snapshot was created"
    )
    
    @field_validator("company_id", "graph_id", mode="before")
    @classmethod
    def _validate_ids(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


# =============================================================================
# ONBOARDING AND SCAN MODELS
# =============================================================================

class WebsiteScanRequest(BaseModel):
    """Request to scan a website and infer its stack."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    website_url: str = Field(
        ...,
        description="URL of the website to scan"
    )
    company_id: str | None = Field(
        default=None,
        description="Company ID to associate with this scan"
    )
    scan_depth: Literal["shallow", "standard", "deep"] = Field(
        default="standard",
        description="How thorough the scan should be"
    )
    include_sitemap: bool = Field(
        default=True,
        description="Whether to scan sitemap URLs"
    )
    max_pages: int = Field(
        ge=1, le=100,
        default=20,
        description="Maximum number of pages to scan"
    )
    
    @field_validator("website_url", mode="before")
    @classmethod
    def _validate_url(cls, v: Any) -> str:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("website_url must not be blank")
            if not stripped.startswith(("http://", "https://")):
                stripped = "https://" + stripped
            return stripped
        return v


class WebsiteScanResult(BaseModel):
    """Result of a website scan with detected systems and stack inference."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    scan_id: str = Field(
        ...,
        description="Unique scan identifier"
    )
    website_url: str = Field(
        ...,
        description="URL that was scanned"
    )
    company_id: str | None = Field(
        default=None,
        description="Company ID this scan belongs to"
    )
    status: Literal["success", "failed", "partial"] = Field(
        default="success",
        description="Overall scan status"
    )
    started_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the scan started"
    )
    completed_at: datetime | None = Field(
        default=None,
        description="When the scan completed"
    )
    duration_seconds: float = Field(
        default=0.0,
        description="Total scan duration in seconds"
    )
    pages_scanned: int = Field(
        default=0,
        description="Number of pages scanned"
    )
    pages_failed: int = Field(
        default=0,
        description="Number of pages that failed to scan"
    )
    inferred_stack: StackInference | None = Field(
        default=None,
        description="Inferred technology stack"
    )
    detected_systems: List[DetectedSystem] = Field(
        default_factory=list,
        description="Detected business systems"
    )
    sitemap_urls: List[str] = Field(
        default_factory=list,
        description="URLs found in sitemap"
    )
    important_pages: List[str] = Field(
        default_factory=list,
        description="Important pages identified"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Errors encountered during scan"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings during scan"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional scan metadata"
    )


class RepoScanRequest(BaseModel):
    """Request to scan a repository and infer its stack."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    repo_url: str = Field(
        ...,
        description="URL of the repository to scan"
    )
    company_id: str | None = Field(
        default=None,
        description="Company ID to associate with this scan"
    )
    provider: Literal["github", "gitlab", "bitbucket", "azure_devops"] | None = Field(
        default=None,
        description="Git provider (auto-detected if not specified)"
    )
    scan_depth: Literal["shallow", "standard", "deep"] = Field(
        default="standard",
        description="How thorough the scan should be"
    )
    include_code_analysis: bool = Field(
        default=True,
        description="Whether to analyze code for stack inference"
    )
    include_dependencies: bool = Field(
        default=True,
        description="Whether to analyze dependency files"
    )
    
    @field_validator("repo_url", mode="before")
    @classmethod
    def _validate_url(cls, v: Any) -> str:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("repo_url must not be blank")
            if not stripped.startswith(("http://", "https://", "git@")):
                stripped = "https://" + stripped
            return stripped
        return v


class OnboardingProgress(BaseModel):
    """Tracks the onboarding progress for a company."""
    model_config = {"frozen": False, "extra": "forbid"}
    
    company_id: str = Field(
        ...,
        description="ID of the company"
    )
    current_step: str = Field(
        ...,
        description="Current onboarding step"
    )
    total_steps: int = Field(
        ge=1,
        default=5,
        description="Total number of onboarding steps"
    )
    completed_steps: int = Field(
        ge=0,
        default=0,
        description="Number of completed steps"
    )
    progress_percent: float = Field(
        ge=0.0, le=100.0,
        default=0.0,
        description="Progress percentage"
    )
    status: Literal["not_started", "in_progress", "paused", "completed", "failed"] = Field(
        default="not_started",
        description="Overall onboarding status"
    )
    steps: List[dict[str, Any]] = Field(
        default_factory=list,
        description="Details of each onboarding step"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Errors encountered during onboarding"
    )
    started_at: datetime | None = Field(
        default=None,
        description="When onboarding started"
    )
    completed_at: datetime | None = Field(
        default=None,
        description="When onboarding completed"
    )
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        description="When onboarding progress was last updated"
    )


# =============================================================================
# SPECIALIST PROVISIONING MODELS
# =============================================================================

class SpecialistProvisionRequest(BaseModel):
    """Request to provision a specialist for a company."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    company_id: str = Field(
        ...,
        description="ID of the company"
    )
    specialist_family: SpecialistFamily = Field(
        ...,
        description="Family of specialist to provision"
    )
    name: str | None = Field(
        default=None,
        description="Custom name for the specialist (auto-generated if not provided)"
    )
    capabilities: List[str] = Field(
        default_factory=list,
        description="Specific capabilities to configure"
    )
    tools: List[str] = Field(
        default_factory=list,
        description="Specific tools to configure (auto-derived from family if empty)"
    )
    system_types: List[SystemType] = Field(
        default_factory=list,
        description="System types this specialist should handle"
    )
    model_preference: str | None = Field(
        default=None,
        description="Preferred model for this specialist"
    )
    runtime: Literal["internal_agent", "claude_code", "goose", "aider", "hermes", "opencode", "custom"] | None = Field(
        default=None,
        description="Preferred runtime for this specialist"
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Specialist-specific configuration"
    )
    auto_provision: bool = Field(
        default=True,
        description="Whether to automatically provision based on detected systems"
    )
    
    @field_validator("company_id", mode="before")
    @classmethod
    def _validate_company_id(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class SpecialistProvisionResult(BaseModel):
    """Result of provisioning a specialist."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    request_id: str = Field(
        ...,
        description="ID of the provision request"
    )
    specialist: Specialist = Field(
        ...,
        description="The provisioned specialist"
    )
    status: Literal["success", "failed", "skipped"] = Field(
        default="success",
        description="Provision status"
    )
    message: str = Field(
        default="",
        description="Status message"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Errors encountered during provisioning"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings during provisioning"
    )
    provisioned_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the specialist was provisioned"
    )


# =============================================================================
# WORKFLOW EXECUTION MODELS
# =============================================================================


class RepoScanResult(BaseModel):
    """Result of a repository scan with detected stack and systems."""
    model_config = {"extra": "allow"}

    scan_id: str = Field(default_factory=lambda: secrets.token_hex(8), description="Unique scan identifier")
    repo_url: str = Field(..., description="Repository URL that was scanned")
    company_id: Optional[str] = Field(default=None, description="Associated company ID")
    status: str = Field(default="pending", description="Scan status: pending/success/partial/failed")
    inferred_stack: Optional[Any] = Field(default=None, description="Inferred technology stack")
    detected_systems: List[Any] = Field(default_factory=list, description="Detected systems")
    files_scanned: int = Field(default=0, description="Number of files scanned")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")
    started_at: Optional[datetime] = Field(default=None, description="When scan started")
    completed_at: Optional[datetime] = Field(default=None, description="When scan completed")
    default_branch: Optional[str] = Field(default=None, description="Default branch name")
    is_private: bool = Field(default=False, description="Whether the repo is private")
    stars: int = Field(default=0, description="Number of stars")
    forks: int = Field(default=0, description="Number of forks")
    open_issues: int = Field(default=0, description="Number of open issues")
    language: Optional[str] = Field(default=None, description="Primary language")

class WorkflowExecutionRequest(BaseModel):
    """Request to execute a workflow."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    workflow_id: str = Field(
        ...,
        description="ID of the workflow to execute"
    )
    company_id: str = Field(
        ...,
        description="ID of the company"
    )
    repo_id: str | None = Field(
        default=None,
        description="ID of the repository (if applicable)"
    )
    system_ids: List[str] = Field(
        default_factory=list,
        description="System IDs involved in this execution"
    )
    trigger: str = Field(
        default="manual",
        description="What triggered this workflow execution"
    )
    input_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Input data for the workflow"
    )
    override_specialists: List[str] = Field(
        default_factory=list,
        description="Specialist IDs to use instead of default assignments"
    )
    skip_approval: bool = Field(
        default=False,
        description="Whether to skip approval gates"
    )
    
    @field_validator("workflow_id", "company_id", mode="before")
    @classmethod
    def _validate_ids(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class WorkflowExecutionResult(BaseModel):
    """Result of a workflow execution."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    execution_id: str = Field(
        ...,
        description="Unique execution identifier"
    )
    workflow_id: str = Field(
        ...,
        description="ID of the workflow that was executed"
    )
    company_id: str = Field(
        ...,
        description="ID of the company"
    )
    status: WorkflowStatus = Field(
        default="pending",
        description="Execution status"
    )
    current_phase: WorkflowPhaseType | None = Field(
        default=None,
        description="Current phase of execution"
    )
    completed_phases: List[WorkflowPhaseType] = Field(
        default_factory=list,
        description="Phases that have been completed"
    )
    failed_phases: List[WorkflowPhaseType] = Field(
        default_factory=list,
        description="Phases that failed"
    )
    phase_results: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Results from each phase"
    )
    specialist_assignments: List[WorkflowAssignment] = Field(
        default_factory=list,
        description="Actual specialist assignments used"
    )
    output: dict[str, Any] = Field(
        default_factory=dict,
        description="Final output from the workflow"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Errors encountered during execution"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings during execution"
    )
    started_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When execution started"
    )
    completed_at: datetime | None = Field(
        default=None,
        description="When execution completed"
    )
    duration_seconds: float = Field(
        default=0.0,
        description="Total execution duration in seconds"
    )
    approval_gate_results: List[dict[str, Any]] = Field(
        default_factory=list,
        description="Results from approval gates"
    )


# =============================================================================
# API REQUEST/RESPONSE MODELS
# =============================================================================

class CompanyCreateRequest(BaseModel):
    """Request to create a new company."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    name: str = Field(
        ...,
        description="Company name"
    )
    domain: str = Field(
        ...,
        description="Primary domain"
    )
    business_category: BusinessCategory = Field(
        default="other",
        description="Primary business category"
    )
    description: str = Field(
        default="",
        description="Company description"
    )
    tagline: str = Field(
        default="",
        description="Company tagline"
    )
    owner_id: str | None = Field(
        default=None,
        description="User ID of the company owner"
    )


class CompanyUpdateRequest(BaseModel):
    """Request to update a company."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    name: str | None = Field(
        default=None,
        description="Company name"
    )
    domain: str | None = Field(
        default=None,
        description="Primary domain"
    )
    business_category: BusinessCategory | None = Field(
        default=None,
        description="Primary business category"
    )
    description: str | None = Field(
        default=None,
        description="Company description"
    )
    tagline: str | None = Field(
        default=None,
        description="Company tagline"
    )
    founded_year: int | None = Field(
        default=None,
        description="Year the company was founded"
    )
    employee_count: int | None = Field(
        default=None,
        description="Approximate number of employees"
    )
    revenue_range: str | None = Field(
        default=None,
        description="Revenue range"
    )
    email: str | None = Field(
        default=None,
        description="Primary contact email"
    )
    phone: str | None = Field(
        default=None,
        description="Primary contact phone"
    )
    address: dict[str, Any] | None = Field(
        default=None,
        description="Physical address"
    )
    logo_url: str | None = Field(
        default=None,
        description="URL to company logo"
    )
    integration_config: dict[str, Any] | None = Field(
        default=None,
        description="Company-specific integration configuration"
    )
    is_active: bool | None = Field(
        default=None,
        description="Whether this company is active"
    )


class CompanyResponse(BaseModel):
    """Response containing a company."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    company: Company = Field(
        ...,
        description="The company"
    )
    graph: Optional[Any] = Field(
        default=None,
        description="Company graph"
    )
    message: str = Field(
        default="",
        description="Status message"
    )


class CompanyGraphResponse(BaseModel):
    """Response containing a company graph."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    graph: CompanyGraph = Field(
        ...,
        description="The company graph"
    )
    company_id: str = Field(
        default="",
        description="Company ID"
    )
    completeness_score: float = Field(
        default=0.0,
        description="Graph completeness score (0.0-1.0)"
    )
    message: str = Field(
        default="",
        description="Status message"
    )


class SpecialistListResponse(BaseModel):
    """Response containing a list of specialists."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    specialists: List[Specialist] = Field(
        default_factory=list,
        description="List of specialists"
    )
    company_id: str = Field(
        ...,
        description="Company ID"
    )
    total: int = Field(
        default=0,
        description="Total number of specialists"
    )
    limit: int = Field(
        default=100,
        description="Page limit"
    )
    offset: int = Field(
        default=0,
        description="Page offset"
    )
    message: str = Field(
        default="",
        description="Status message"
    )


class WorkflowListResponse(BaseModel):
    """Response containing a list of workflows."""
    model_config = {"frozen": True, "extra": "forbid"}
    
    workflows: List[Workflow] = Field(
        default_factory=list,
        description="List of workflows"
    )
    company_id: str = Field(
        ...,
        description="Company ID"
    )
    total: int = Field(
        default=0,
        description="Total number of workflows"
    )
    message: str = Field(
        default="",
        description="Status message"
    )


# Rebuild models to resolve forward references
CompanyGraph.model_rebuild()
CompanyGraphSnapshot.model_rebuild()
WebsiteScanResult.model_rebuild()
RepoScanRequest.model_rebuild()
OnboardingProgress.model_rebuild()
SpecialistProvisionResult.model_rebuild()
WorkflowExecutionResult.model_rebuild()
CompanyResponse.model_rebuild()
CompanyGraphResponse.model_rebuild()
SpecialistListResponse.model_rebuild()
WorkflowListResponse.model_rebuild()

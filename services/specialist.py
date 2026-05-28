"""
services/specialist.py - Specialist Provisioning and Management Service

Provides functionality for provisioning, managing, and matching specialists
to tasks based on capabilities and system types.

Usage:
    from services.specialist import SpecialistService
    
    service = SpecialistService()
    
    # Provision a specialist
    result = await service.provision_specialist(
        SpecialistProvisionRequest(
            company_id="company_123",
            specialist_family="engineering"
        )
    )
    
    # Get specialists for a task
    specialists = await service.get_specialists_for_task(
        company_id="company_123",
        capabilities=["code_review", "refactoring"]
    )
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import secrets

from models.company_graph import (
    Specialist,
    SpecialistProvisionRequest,
    SpecialistProvisionResult,
    SpecialistFamily,
    SystemType
)
from services.company_graph_store import get_company_graph_store, CompanyGraphStore

log = logging.getLogger("company_graph.specialist")


class SpecialistService:
    """
    Service for managing specialists, including provisioning, matching,
    and lifecycle management.
    """

    def __init__(self, store: CompanyGraphStore | None = None):
        """
        Initialize the service.
        
        Args:
            store: Optional CompanyGraphStore instance. If None, uses singleton.
        """
        self.store = store or get_company_graph_store()

    # =========================================================================
    # SPECIALIST PROVISIONING
    # =========================================================================

    async def provision_specialist(
        self,
        request: SpecialistProvisionRequest
    ) -> SpecialistProvisionResult:
        """
        Provision a new specialist for a company.
        
        Args:
            request: SpecialistProvisionRequest with provisioning parameters
            
        Returns:
            SpecialistProvisionResult with the provisioned specialist
        """
        # Check if specialist already exists
        existing = await self.store.list_specialists(
            company_id=request.company_id,
            family=request.specialist_family
        )
        
        if existing:
            # Return first existing specialist of this family
            return SpecialistProvisionResult(
                request_id=f"req_{secrets.token_hex(8)}",
                specialist=existing[0],
                status="skipped",
                message="Specialist already provisioned",
                provisioned_at=datetime.utcnow()
            )
        
        # Create new specialist
        specialist = Specialist(
            company_id=request.company_id,
            name=request.name or self._generate_specialist_name(request.specialist_family),
            family=request.specialist_family,
            capabilities=request.capabilities or self._get_default_capabilities(request.specialist_family),
            tools=request.tools or self._get_default_tools(request.specialist_family),
            system_types=request.system_types or [],
            model_preference=request.model_preference,
            runtime=request.runtime,
            is_provisioned=True,
            provisioned_at=datetime.utcnow(),
            status="available",
            config=request.config or {}
        )
        
        created = await self.store.create_specialist(specialist)
        
        log.info(
            f"Provisioned specialist: {created.id} ({created.name}) "
            f"for company {request.company_id}"
        )
        
        return SpecialistProvisionResult(
            request_id=f"req_{secrets.token_hex(8)}",
            specialist=created,
            status="success",
            message="Specialist provisioned successfully",
            provisioned_at=datetime.utcnow()
        )

    async def provision_specialists_for_company(
        self,
        company_id: str,
        system_types: List[SystemType]
    ) -> List[SpecialistProvisionResult]:
        """
        Auto-provision specialists based on detected system types.
        
        Args:
            company_id: Company ID
            system_types: List of detected system types
            
        Returns:
            List of SpecialistProvisionResult for each provisioned specialist
        """
        # Map system types to specialist families
        system_to_family: Dict[SystemType, List[SpecialistFamily]] = {
            "CMS": ["frontend", "docs", "backend"],
            "CRM": ["operations", "analytics", "backend"],
            "ecommerce": ["ecommerce", "frontend", "backend", "operations"],
            "analytics": ["analytics", "data", "backend"],
            "payment_gateway": ["backend", "security", "operations"],
            "ERP": ["operations", "backend", "data"],
            "HRM": ["operations", "docs", "backend"],
            "LMS": ["docs", "operations", "frontend"],
            "marketing_automation": ["operations", "analytics", "backend"],
            "chat": ["operations", "frontend", "backend"],
            "hosting": ["devops", "infra", "backend"],
            "database": ["backend", "data", "infra"],
            "ci_cd": ["devops", "backend", "infra"],
            "infrastructure": ["devops", "infra", "backend"]
        }
        
        results = []
        unique_families = set()
        
        # Get already provisioned specialists for this company
        existing = await self.store.list_specialists(company_id)
        existing_families = {s.family for s in existing}
        
        for system_type in system_types:
            families = system_to_family.get(system_type, ["engineering"])
            for family in families:
                if family not in unique_families and family not in existing_families:
                    request = SpecialistProvisionRequest(
                        company_id=company_id,
                        specialist_family=family,
                        system_types=[system_type],
                        auto_provision=True
                    )
                    result = await self.provision_specialist(request)
                    results.append(result)
                    unique_families.add(family)
        
        log.info(
            f"Auto-provisioned {len(results)} specialists for company {company_id} "
            f"based on system types: {system_types}"
        )
        
        return results

    async def deprovision_specialist(
        self,
        specialist_id: str
    ) -> bool:
        """
        Deprovision (delete) a specialist.
        
        Args:
            specialist_id: Specialist ID
            
        Returns:
            True if deleted, False otherwise
        """
        # Mark as deprovisioned first
        specialist = await self.store.get_specialist(specialist_id)
        if specialist:
            specialist = specialist.model_copy(update={
                "is_provisioned": False,
                "status": "deprovisioned",
                "updated_at": datetime.utcnow()
            })
            await self.store.update_specialist(specialist)
        
        # Then delete
        deleted = await self.store.delete_specialist(specialist_id)
        
        if deleted:
            log.info(f"Deprovisioned specialist: {specialist_id}")
        
        return deleted

    async def enable_specialist(
        self,
        specialist_id: str
    ) -> Specialist | None:
        """
        Enable a specialist.
        
        Args:
            specialist_id: Specialist ID
            
        Returns:
            Updated Specialist or None if not found
        """
        specialist = await self.store.get_specialist(specialist_id)
        if not specialist:
            return None
        
        specialist = specialist.model_copy(update={
            "status": "available",
            "updated_at": datetime.utcnow()
        })
        
        await self.store.update_specialist(specialist)
        log.info(f"Enabled specialist: {specialist_id}")
        return specialist

    async def disable_specialist(
        self,
        specialist_id: str,
        reason: str = ""
    ) -> Specialist | None:
        """
        Disable a specialist.
        
        Args:
            specialist_id: Specialist ID
            reason: Reason for disabling
            
        Returns:
            Updated Specialist or None if not found
        """
        specialist = await self.store.get_specialist(specialist_id)
        if not specialist:
            return None
        
        specialist = specialist.model_copy(update={
            "status": "disabled",
            "disabled_reason": reason,
            "updated_at": datetime.utcnow()
        })
        
        await self.store.update_specialist(specialist)
        log.info(f"Disabled specialist: {specialist_id} (reason: {reason})")
        return specialist

    # =========================================================================
    # SPECIALIST MATCHING
    # =========================================================================

    async def get_specialists_for_task(
        self,
        company_id: str,
        capabilities: List[str],
        system_types: List[SystemType] | None = None,
        limit: int = 5
    ) -> List[Specialist]:
        """
        Get specialists that can handle a task with given capabilities.
        
        Args:
            company_id: Company ID
            capabilities: Required capabilities for the task
            system_types: Optional system types to filter by
            limit: Maximum number of specialists to return
            
        Returns:
            List of Specialist instances that can handle the task
        """
        specialists = await self.store.list_specialists(
            company_id=company_id,
            status="available"
        )
        
        matched = []
        
        for specialist in specialists:
            if not specialist.is_provisioned:
                continue
            if specialist.status != "available":
                continue
            if not specialist.can_handle_task(capabilities):
                continue
            if system_types:
                # Check if specialist has any of the required system types
                if not any(st in specialist.system_types for st in system_types):
                    continue
            matched.append(specialist)
        
        # Sort by best match
        matched.sort(
            key=lambda s: (
                -len(set(s.capabilities) & set(capabilities)),  # Most capabilities matched
                -len(s.system_types),  # Most system types
                -s.success_count,  # Most successful tasks
                s.name  # Alphabetical
            )
        )
        
        return matched[:limit]

    async def get_best_specialist(
        self,
        company_id: str,
        capabilities: List[str],
        system_types: List[SystemType] | None = None
    ) -> Specialist | None:
        """
        Get the best specialist for a task.
        
        Args:
            company_id: Company ID
            capabilities: Required capabilities
            system_types: Optional system types to filter by
            
        Returns:
            Best Specialist or None if no match
        """
        specialists = await self.get_specialists_for_task(
            company_id, capabilities, system_types, limit=1
        )
        return specialists[0] if specialists else None

    async def get_specialists_by_family(
        self,
        company_id: str,
        family: SpecialistFamily
    ) -> List[Specialist]:
        """
        Get all specialists of a specific family for a company.
        
        Args:
            company_id: Company ID
            family: Specialist family
            
        Returns:
            List of Specialist instances
        """
        return await self.store.list_specialists(
            company_id=company_id,
            family=family
        )

    async def list_specialists(
        self,
        company_id: str | None = None,
        family: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Specialist]:
        """
        List specialists with optional filtering.
        
        Args:
            company_id: Filter by company ID
            family: Filter by specialist family
            status: Filter by status
            limit: Maximum to return
            offset: Pagination offset
            
        Returns:
            List of Specialist instances
        """
        return await self.store.list_specialists(
            company_id=company_id,
            family=family,
            status=status,
            limit=limit,
            offset=offset
        )

    async def get_specialist(
        self,
        specialist_id: str
    ) -> Specialist | None:
        """
        Get a specialist by ID.
        
        Args:
            specialist_id: Specialist ID
            
        Returns:
            Specialist or None if not found
        """
        return await self.store.get_specialist(specialist_id)

    async def update_specialist(
        self,
        specialist_id: str,
        **kwargs
    ) -> Specialist | None:
        """
        Update a specialist.
        
        Args:
            specialist_id: Specialist ID
            **kwargs: Fields to update
            
        Returns:
            Updated Specialist or None if not found
        """
        specialist = await self.store.get_specialist(specialist_id)
        if not specialist:
            return None
        
        updated = specialist.model_copy(update=kwargs)
        await self.store.update_specialist(updated)
        return updated

    # =========================================================================
    # SPECIALIST STATISTICS AND MANAGEMENT
    # =========================================================================

    async def record_success(
        self,
        specialist_id: str
    ) -> None:
        """
        Record a successful task completion for a specialist.
        
        Args:
            specialist_id: Specialist ID
        """
        specialist = await self.store.get_specialist(specialist_id)
        if specialist:
            specialist = specialist.model_copy(update={
                "success_count": specialist.success_count + 1,
                "last_activity": datetime.utcnow()
            })
            await self.store.update_specialist(specialist)

    async def record_error(
        self,
        specialist_id: str,
        error: str
    ) -> None:
        """
        Record an error for a specialist.
        
        Args:
            specialist_id: Specialist ID
            error: Error message
        """
        specialist = await self.store.get_specialist(specialist_id)
        if specialist:
            specialist = specialist.model_copy(update={
                "error_count": specialist.error_count + 1,
                "last_error": error,
                "last_activity": datetime.utcnow()
            })
            await self.store.update_specialist(specialist)

    async def get_specialist_stats(
        self,
        company_id: str
    ) -> Dict[str, Any]:
        """
        Get statistics for specialists in a company.
        
        Args:
            company_id: Company ID
            
        Returns:
            Dictionary with specialist statistics
        """
        specialists = await self.store.list_specialists(company_id)
        
        stats = {
            "total": len(specialists),
            "provisioned": 0,
            "available": 0,
            "busy": 0,
            "disabled": 0,
            "families": {},
            "total_success": 0,
            "total_errors": 0
        }
        
        for specialist in specialists:
            if specialist.is_provisioned:
                stats["provisioned"] += 1
            
            if specialist.status == "available":
                stats["available"] += 1
            elif specialist.status == "busy":
                stats["busy"] += 1
            elif specialist.status == "disabled":
                stats["disabled"] += 1
            
            # Count by family
            family = specialist.family
            if family not in stats["families"]:
                stats["families"][family] = {"count": 0, "available": 0}
            stats["families"][family]["count"] += 1
            if specialist.status == "available":
                stats["families"][family]["available"] += 1
            
            stats["total_success"] += specialist.success_count
            stats["total_errors"] += specialist.error_count
        
        return stats

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _generate_specialist_name(self, family: SpecialistFamily) -> str:
        """Generate a name for a specialist based on family."""
        names = {
            "engineering": "Engineering Specialist",
            "qa": "Quality Assurance Specialist",
            "docs": "Documentation Specialist",
            "analytics": "Analytics Specialist",
            "ecommerce": "E-commerce Specialist",
            "operations": "Operations Specialist",
            "agile": "Agile Coach",
            "portfolio": "Portfolio Manager",
            "security": "Security Specialist",
            "devops": "DevOps Specialist",
            "data": "Data Specialist",
            "ml": "Machine Learning Specialist",
            "frontend": "Frontend Specialist",
            "backend": "Backend Specialist",
            "fullstack": "Fullstack Specialist",
            "mobile": "Mobile Specialist",
            "cloud": "Cloud Specialist",
            "infra": "Infrastructure Specialist",
            "architecture": "Architecture Specialist",
            "product": "Product Specialist",
            "design": "Design Specialist",
            "ux": "UX Specialist"
        }
        return names.get(family, f"{family.title()} Specialist")

    def _get_default_capabilities(self, family: SpecialistFamily) -> List[str]:
        """Get default capabilities for a specialist family."""
        capabilities: Dict[SpecialistFamily, List[str]] = {
            "engineering": ["code_review", "refactoring", "bug_fixing", "feature_development", "testing"],
            "qa": ["testing", "test_writing", "quality_assurance", "automated_testing", "manual_testing"],
            "docs": ["documentation", "api_docs", "tutorials", "knowledge_base", "markdown"],
            "analytics": ["data_analysis", "metrics", "reporting", "insights", "visualization"],
            "ecommerce": ["shopify", "woocommerce", "payment_integration", "product_management", "order_management"],
            "operations": ["process_optimization", "workflow_management", "tooling", "automation", "monitoring"],
            "agile": ["sprint_planning", "standups", "retrospectives", "backlog_management", "scrum"],
            "portfolio": ["roadmapping", "prioritization", "resource_allocation", "strategy", "planning"],
            "security": ["vulnerability_assessment", "code_review", "penetration_testing", "compliance", "authentication"],
            "devops": ["ci_cd", "deployment", "infrastructure", "monitoring", "scaling"],
            "data": ["data_pipelines", "etl", "data_warehousing", "sql", "nosql"],
            "ml": ["model_training", "feature_engineering", "data_preprocessing", "model_evaluation", "prediction"],
            "frontend": ["ui_development", "responsive_design", "javascript", "css", "html"],
            "backend": ["api_development", "database_design", "server_architecture", "performance", "scaling"],
            "fullstack": ["full_stack_development", "frontend", "backend", "database", "deployment"],
            "mobile": ["mobile_development", "ios", "android", "react_native", "flutter"],
            "cloud": ["cloud_architecture", "aws", "azure", "gcp", "serverless"],
            "infra": ["infrastructure", "networking", "containers", "orchestration", "monitoring"],
            "architecture": ["system_design", "microservices", "scalability", "reliability", "security"],
            "product": ["product_management", "requirements", "prioritization", "roadmapping", "user_stories"],
            "design": ["ui_design", "ux_design", "prototyping", "user_research", "visual_design"],
            "ux": ["user_experience", "usability_testing", "user_research", "wireframing", "prototyping"]
        }
        return capabilities.get(family, [])

    def _get_default_tools(self, family: SpecialistFamily) -> List[str]:
        """Get default tools for a specialist family."""
        tools: Dict[SpecialistFamily, List[str]] = {
            "engineering": ["git", "github_api", "code_analysis", "linting", "debugging"],
            "qa": ["pytest", "selenium", "cypress", "jest", "mocha"],
            "docs": ["markdown", "sphinx", "mkdocs", "swagger", "confluence"],
            "analytics": ["google_analytics", "mixpanel", "amplitude", "sql", "pandas"],
            "ecommerce": ["shopify_api", "stripe_api", "paypal_api", "woocommerce_api", "bigcommerce_api"],
            "operations": ["jira", "trello", "asana", "notion", "slack"],
            "agile": ["jira", "trello", "asana", "confluence", "miro"],
            "portfolio": ["jira", "aha", "productboard", "miro", "excel"],
            "security": ["nmap", "burp", "owasp_zap", "snyk", "nessus"],
            "devops": ["docker", "kubernetes", "terraform", "ansible", "jenkins"],
            "data": ["apache_spark", "apache_kafka", "postgresql", "mongodb", "redis"],
            "ml": ["tensorflow", "pytorch", "scikit_learn", "pandas", "numpy"],
            "frontend": ["react", "vue", "angular", "svelte", "typescript"],
            "backend": ["python", "nodejs", "java", "go", "rust"],
            "fullstack": ["git", "docker", "javascript", "python", "database"],
            "mobile": ["xcode", "android_studio", "react_native", "flutter", "expo"],
            "cloud": ["aws_cli", "azure_cli", "gcloud", "terraform", "pulumi"],
            "infra": ["docker", "kubernetes", "terraform", "ansible", "vagrant"],
            "architecture": ["lucidchart", "drawio", "miro", "visio", "excalidraw"],
            "product": ["jira", "trello", "asana", "productboard", "aha"],
            "design": ["figma", "sketch", "adobe_xd", "photoshop", "illustrator"],
            "ux": ["figma", "sketch", "adobe_xd", "optimal_workshop", "hotjar"]
        }
        return tools.get(family, [])


# =============================================================================
# SINGLETON AND FACTORY
# =============================================================================

_specialist_service: SpecialistService | None = None


def get_specialist_service() -> SpecialistService:
    """
    Get the singleton Specialist service instance.
    
    Returns:
        The singleton SpecialistService instance.
    """
    global _specialist_service
    if _specialist_service is None:
        _specialist_service = SpecialistService()
    return _specialist_service


def set_specialist_service(service: SpecialistService) -> None:
    """
    Set the singleton Specialist service instance (for testing).
    
    Args:
        service: The SpecialistService instance to use.
    """
    global _specialist_service
    _specialist_service = service

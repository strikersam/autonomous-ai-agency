"""
services/company_graph.py - Company Graph Business Logic Service

Provides high-level business logic for managing Company Graphs, including creation,
retrieval, updates, and complex operations like onboarding and scanning.

Usage:
    from services.company_graph import CompanyGraphService
    service = CompanyGraphService()
    # Get or create a company graph
    graph = await service.get_or_create_company_graph(company_id)
    # Add a website to a company
    website = await service.add_website(company_id, website_url)
"""

from __future__ import annotations

from urllib.parse import urlparse
from typing import Any, List, Optional, Dict, Tuple
from datetime import datetime
import logging
import asyncio
import secrets
import hashlib

from models.company_graph import (
    Company,
    CompanyGraph,
    CompanyGraphSnapshot,
    Website,
    Repo,
    BusinessSystem,
    DetectedSystem,
    Specialist,
    Workflow,
    KnowledgeItem,
    Connector,
    ApprovalPolicy,
    BusinessCategory,
    SystemType,
    SpecialistFamily,
    WorkflowPhaseType
)
from services.company_graph_store import get_company_graph_store, CompanyGraphStore

log = logging.getLogger("company_graph.service")


class CompanyGraphService:
    """
    High-level business logic service for Company Graph operations.
    This service provides the main interface for working with Company Graphs,
    including creation, retrieval, updates, and complex operations.
    """

    def __init__(self, store: CompanyGraphStore | None = None):
        """
        Initialize the service.
        Args:
            store: Optional CompanyGraphStore instance. If None, uses singleton.
        """
        self.store = store or get_company_graph_store()
        self._lock = asyncio.Lock()

    # =========================================================================
    # COMPANY OPERATIONS
    # =========================================================================

    async def create_company(
        self,
        name: str,
        domain: str,
        business_category: BusinessCategory = "other",
        description: str = "",
        owner_id: str | None = None,
        **kwargs
    ) -> Company:
        """
        Create a new company.
        
        Args:
            name: Company name
            domain: Primary domain
            business_category: Business category
            description: Company description
            owner_id: User ID of the owner
            **kwargs: Additional company fields
            
        Returns:
            The created Company instance
        """
        company_data = {
            "name": name,
            "domain": domain,
            "business_category": business_category,
            "description": description,
            "owner_id": owner_id,
            **kwargs
        }
        company = Company(**company_data)
        created = await self.store.create_company(company)
        log.info(f"Created company: {created.id} ({created.name})")
        # Create an initial company graph
        await self._create_initial_graph(created.id)
        return created

    async def get_company(self, company_id: str) -> Company | None:
        """
        Get a company by ID.
        
        Args:
            company_id: Company ID
            
        Returns:
            Company instance or None if not found
        """
        return await self.store.get_company(company_id)

    async def update_company(
        self, company_id: str, **kwargs
    ) -> Company | None:
        """
        Update a company.
        
        Args:
            company_id: Company ID
            **kwargs: Fields to update
            
        Returns:
            Updated Company instance or None if not found
        """
        company = await self.store.get_company(company_id)
        if not company:
            return None
        
        update_data = {}
        for key, value in kwargs.items():
            if hasattr(company, key):
                update_data[key] = value
        
        if not update_data:
            return company
            
        updated = company.model_copy(update=update_data)
        await self.store.update_company(updated)
        log.info(f"Updated company: {company_id}")
        return updated

    async def delete_company(self, company_id: str) -> bool:
        """
        Delete a company and all its associated data.
        
        Args:
            company_id: Company ID
            
        Returns:
            True if deleted, False otherwise
        """
        return await self.store.delete_company(company_id)

    async def list_companies(
        self,
        owner_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None
    ) -> Tuple[List[Company], int]:
        """
        List companies with optional filtering.
        
        Args:
            owner_id: Filter by owner ID
            limit: Maximum number to return
            offset: Pagination offset
            search: Search by name or domain
            
        Returns:
            Tuple of (companies, total_count)
        """
        companies = await self.store.list_companies(owner_id, limit, offset, search)
        # Get total count (simplified - in production, use count query)
        total = len(companies) + offset  # Approximate
        return companies, total

    # =========================================================================
    # COMPANY GRAPH OPERATIONS
    # =========================================================================

    async def get_or_create_company_graph(self, company_id: str) -> CompanyGraph:
        """
        Get the company graph for a company, or create one if it doesn't exist.
        
        Args:
            company_id: Company ID
            
        Returns:
            CompanyGraph instance
        """
        # Try to get existing graph
        graph = await self.store.get_company_graph(company_id)
        if graph:
            return graph
        
        # Get or create company
        company = await self.store.get_company(company_id)
        if not company:
            raise ValueError(f"Company {company_id} not found")
        
        # Create new graph
        graph = CompanyGraph(
            company_id=company_id,
            company=company,
            websites=[],
            repos=[],
            systems=[],
            specialists=[],
            workflows=[],
            knowledge=[],
            connectors=[],
            approval_policies=[],
            detected_systems=[]
        )
        created = await self.store.create_company_graph(graph)
        log.info(f"Created company graph: {created.id} for company {company_id}")
        return created

    async def get_company_graph(
        self,
        company_id: str,
        include_detected_systems: bool = True,
        include_specialists: bool = True,
        include_workflows: bool = True,
    ) -> CompanyGraph | None:
        """
        Get the company graph for a company.

        Args:
            company_id: Company ID
            include_detected_systems: Include detected systems (the store always
                assembles the full graph; the flag is accepted for API parity).
            include_specialists: Include specialists (see above).
            include_workflows: Include workflows (see above).

        Returns:
            CompanyGraph instance or None if not found
        """
        return await self.store.get_company_graph(company_id)

    async def calculate_graph_completeness(self, company_id: str) -> float:
        """Compute the completeness score (0.0–1.0) for a company's graph.

        Loads the graph and delegates to the in-memory scorer. Returns 0.0 when
        the company has no graph yet (rather than raising), so the graph
        endpoint never 500s on a freshly-created company.
        """
        graph = await self.store.get_company_graph(company_id)
        if not graph:
            return 0.0
        return self._calculate_completeness_score(graph)

    async def update_company_graph(self, graph: CompanyGraph) -> CompanyGraph:
        """
        Update a company graph.
        
        Args:
            graph: CompanyGraph instance to update
            
        Returns:
            Updated CompanyGraph instance
        """
        # Update timestamps
        graph.updated_at = datetime.utcnow()
        # Calculate completeness score
        graph.completeness_score = self._calculate_completeness_score(graph)
        graph.is_complete = graph.completeness_score >= 0.8
        
        updated = await self.store.update_company_graph(graph)
        log.info(f"Updated company graph: {updated.id}")
        return updated

    def _calculate_completeness_score(self, graph: CompanyGraph) -> float:
        """
        Calculate the completeness score for a company graph.
        
        Args:
            graph: CompanyGraph instance
            
        Returns:
            Completeness score (0.0 to 1.0)
        """
        score = 0.0
        total_weight = 0.0
        
        # Company information (20%)
        company = graph.company
        company_fields = [
            (company.name, 0.05),
            (company.domain, 0.05),
            (company.description, 0.05),
            (company.business_category != "other", 0.05)
        ]
        for field, weight in company_fields:
            if field:
                score += weight
            total_weight += weight
        
        # Websites (20%)
        if graph.websites:
            score += 0.2 * min(len(graph.websites), 3) / 3
            total_weight += 0.2
        
        # Repositories (15%)
        if graph.repos:
            score += 0.15 * min(len(graph.repos), 5) / 5
            total_weight += 0.15
        
        # Systems (15%)
        if graph.systems:
            score += 0.15 * min(len(graph.systems), 10) / 10
            total_weight += 0.15
        
        # Detected systems (10%)
        if graph.detected_systems:
            score += 0.1 * min(len(graph.detected_systems), 20) / 20
            total_weight += 0.1
        
        # Specialists (10%)
        if graph.specialists:
            score += 0.1 * min(len(graph.specialists), 5) / 5
            total_weight += 0.1
        
        # Normalize
        if total_weight > 0:
            score = score / total_weight
        
        return round(score, 2)

    async def _create_initial_graph(self, company_id: str) -> CompanyGraph:
        """
        Create an initial company graph for a new company.
        
        Args:
            company_id: Company ID
            
        Returns:
            Initial CompanyGraph instance
        """
        company = await self.store.get_company(company_id)
        if not company:
            raise ValueError(f"Company {company_id} not found")
        
        graph = CompanyGraph(
            company_id=company_id,
            company=company,
            websites=[],
            repos=[],
            systems=[],
            specialists=[],
            workflows=[],
            knowledge=[],
            connectors=[],
            approval_policies=[],
            detected_systems=[]
        )
        return await self.store.create_company_graph(graph)

    # =========================================================================
    # WEBSITE OPERATIONS
    # =========================================================================

    async def add_website(
        self,
        company_id: str,
        url: str,
        is_primary: bool = False,
        **kwargs
    ) -> Website:
        """
        Add a website to a company.
        
        Args:
            company_id: Company ID
            url: Website URL
            is_primary: Whether this is the primary website
            **kwargs: Additional website fields
            
        Returns:
            Created Website instance
        """
        # Validate URL
        if not url:
            raise ValueError("URL is required")
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        
        website = Website(
            url=url,
            is_primary=is_primary,
            **kwargs
        )
        created = await self.store.create_website(website)
        
        # Update company
        company = await self.store.get_company(company_id)
        if company:
            websites = list(company.websites)
            if created.id not in websites:
                websites.append(created.id)
            company = company.model_copy(update={"websites": websites})
            await self.store.update_company(company)
        
        log.info(f"Added website: {created.id} ({created.url}) to company {company_id}")
        return created

    async def add_workflow(
        self,
        company_id: str,
        name: str,
        phases: List[str],
        description: str = "",
        triggers: List[str] = [],
        **kwargs
    ) -> Workflow:
        """
        Add a workflow to a company's graph.
        
        Args:
            company_id: Company ID
            name: Name of the workflow
            phases: List of workflow phases
            description: Description of the workflow
            triggers: List of workflow triggers
            **kwargs: Additional fields
            
        Returns:
            Created Workflow instance
        """
        workflow = Workflow(
            company_id=company_id,
            name=name,
            description=description,
            phases=phases,
            triggers=triggers,
            **kwargs
        )
        
        # If MongoDB is active, persist within the company_graphs collection
        if self.store.backend == "mongodb":
            graph = await self.store.get_company_graph(company_id)
            if graph:
                workflows = list(graph.workflows)
                workflows.append(workflow)
                graph = graph.model_copy(update={"workflows": workflows})
                await self.store.update_company_graph(graph)
                
        log.info(f"Added workflow: {workflow.name} to company {company_id}")
        return workflow

    async def get_website(self, website_id: str) -> Website | None:
        """Get a website by ID."""
        return await self.store.get_website(website_id)

    async def list_websites(
        self,
        company_id: str | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Website]:
        """List websites."""
        return await self.store.list_websites(company_id, limit, offset)

    async def update_website(
        self,
        website_id: str,
        **kwargs
    ) -> Website | None:
        """Update a website."""
        website = await self.store.get_website(website_id)
        if not website:
            return None
        updated = website.model_copy(update=kwargs)
        return await self.store.update_website(updated)

    async def delete_website(self, website_id: str) -> bool:
        """Delete a website."""
        return await self.store.delete_website(website_id)

    # =========================================================================
    # REPOSITORY OPERATIONS
    # =========================================================================

    async def add_repo(
        self,
        company_id: str,
        url: str,
        provider: str = "github",
        **kwargs
    ) -> Repo:
        """
        Add a repository to a company.
        
        Args:
            company_id: Company ID
            url: Repository URL
            provider: Git provider (github, gitlab, bitbucket)
            **kwargs: Additional repo fields
            
        Returns:
            Created Repo instance
        """
        if not url:
            raise ValueError("URL is required")
        if not url.startswith(("http://", "https://", "git@")):
            url = f"https://{url}"
        
        # Extract name and full_name from URL
        name = url.split('/')[-1]
        if name.endswith('.git'):
            name = name[:-4]
        full_name = url
        
        parsed_url = urlparse(url)
        if parsed_url.hostname == 'github.com':
            path = parsed_url.path.strip('/').replace('.git', '')
            parts = path.split('/')
            if len(parts) >= 2:
                full_name = f"{parts[0]}/{parts[1]}"
                name = parts[1]
        
        repo = Repo(
            url=url,
            company_id=company_id,
            provider=provider,
            name=name,
            full_name=full_name,
            **kwargs
        )
        created = await self.store.create_repo(repo)
        
        # Update company
        company = await self.store.get_company(company_id)
        if company:
            repos = list(company.repos)
            if created.id not in repos:
                repos.append(created.id)
            company = company.model_copy(update={"repos": repos})
            await self.store.update_company(company)
        
        log.info(f"Added repo: {created.id} ({created.full_name}) to company {company_id}")
        return created

    async def get_repo(self, repo_id: str) -> Repo | None:
        """Get a repository by ID."""
        return await self.store.get_repo(repo_id)

    async def list_repos(
        self,
        company_id: str | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Repo]:
        """List repositories."""
        return await self.store.list_repos(company_id, limit, offset)

    async def update_repo(
        self,
        repo_id: str,
        **kwargs
    ) -> Repo | None:
        """Update a repository."""
        repo = await self.store.get_repo(repo_id)
        if not repo:
            return None
        updated = repo.model_copy(update=kwargs)
        return await self.store.update_repo(updated)

    async def delete_repo(self, repo_id: str) -> bool:
        """Delete a repository."""
        return await self.store.delete_repo(repo_id)

    # =========================================================================
    # SPECIALIST OPERATIONS
    # =========================================================================

    async def add_specialist(
        self,
        company_id: str,
        name: str,
        family: SpecialistFamily,
        capabilities: List[str] | None = None,
        tools: List[str] | None = None,
        model_preference: str | None = None,
        runtime: str | None = None,
        system_types: List[SystemType] | None = None,
        **kwargs
    ) -> Specialist:
        """
        Add a specialist to a company.
        
        Args:
            company_id: Company ID
            name: Specialist name
            family: Specialist family (engineering, qa, docs, etc.)
            capabilities: List of capabilities
            tools: List of tools the specialist can use
            model_preference: Preferred model
            runtime: Preferred runtime
            system_types: System types the specialist is specialized for
            **kwargs: Additional specialist fields
            
        Returns:
            Created Specialist instance
        """
        specialist = Specialist(
            company_id=company_id,
            name=name,
            family=family,
            capabilities=capabilities or [],
            tools=tools or [],
            model_preference=model_preference,
            runtime=runtime,
            system_types=system_types or [],
            is_provisioned=True,
            provisioned_at=datetime.utcnow(),
            status="available",
            **kwargs
        )
        created = await self.store.create_specialist(specialist)
        
        # Update company
        company = await self.store.get_company(company_id)
        if company:
            specialists = list(company.specialists)
            if created.id not in specialists:
                specialists.append(created.id)
            company = company.model_copy(update={"specialists": specialists})
            await self.store.update_company(company)
        
        log.info(f"Added specialist: {created.id} ({created.name}) to company {company_id}")
        return created

    async def get_specialist(self, specialist_id: str) -> Specialist | None:
        """Get a specialist by ID."""
        return await self.store.get_specialist(specialist_id)

    async def list_specialists(
        self,
        company_id: str | None = None,
        family: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Specialist]:
        """List specialists."""
        return await self.store.list_specialists(company_id, family, status, limit, offset)

    async def get_specialists_by_family(
        self,
        company_id: str,
        family: SpecialistFamily
    ) -> List[Specialist]:
        """
        Get all specialists of a specific family for a company.
        
        Args:
            company_id: Company ID
            family: Specialist family to filter by
            
        Returns:
            List of Specialist instances
        """
        return await self.store.list_specialists(company_id, family)

    async def get_specialists_for_task(
        self,
        company_id: str,
        capabilities: List[str],
        system_types: List[SystemType] | None = None
    ) -> List[Specialist]:
        """
        Get specialists that can handle a task with given capabilities.
        
        Args:
            company_id: Company ID
            capabilities: Required capabilities for the task
            system_types: Optional system types to filter by
            
        Returns:
            List of Specialist instances that can handle the task
        """
        specialists = await self.store.list_specialists(company_id)
        matched = []
        
        for specialist in specialists:
            if specialist.can_handle_task(capabilities):
                if system_types:
                    # Check if specialist has any of the required system types
                    if any(st in specialist.system_types for st in system_types):
                        matched.append(specialist)
                else:
                    matched.append(specialist)
        
        # Sort by best match (most capabilities matched, then most system types)
        matched.sort(
            key=lambda s: (
                -len(set(s.capabilities) & set(capabilities)),
                -len(s.system_types),
                s.name
            )
        )
        return matched

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
        capabilities = {
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
        tools = {
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

    # =========================================================================
    # KNOWLEDGE OPERATIONS
    # =========================================================================

    async def add_knowledge_item(
        self,
        company_id: str,
        title: str,
        knowledge_type: str,
        content: str,
        tags: List[str] | None = None,
        related_systems: List[str] | None = None,
        related_specialists: List[str] | None = None,
        **kwargs
    ) -> KnowledgeItem:
        """
        Add a knowledge item to a company.
        
        Args:
            company_id: Company ID
            title: Knowledge item title
            knowledge_type: Type of knowledge
            content: Knowledge content
            tags: List of tags
            related_systems: Related system IDs
            related_specialists: Related specialist IDs
            **kwargs: Additional knowledge fields
            
        Returns:
            Created KnowledgeItem instance
        """
        # Calculate content hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        item = KnowledgeItem(
            company_id=company_id,
            title=title,
            knowledge_type=knowledge_type,
            content=content,
            content_hash=content_hash,
            tags=tags or [],
            related_systems=related_systems or [],
            related_specialists=related_specialists or [],
            **kwargs
        )
        created = await self.store.create_knowledge_item(item)
        
        # Update company
        company = await self.store.get_company(company_id)
        if company:
            knowledge = list(company.knowledge)
            if created.id not in knowledge:
                knowledge.append(created.id)
            company = company.model_copy(update={"knowledge": knowledge})
            await self.store.update_company(company)
        
        log.info(f"Added knowledge item: {created.id} ({created.title}) to company {company_id}")
        return created

    async def get_knowledge_item(self, item_id: str) -> KnowledgeItem | None:
        """Get a knowledge item by ID."""
        return await self.store.get_knowledge_item(item_id)

    async def search_knowledge(
        self,
        query: str | None = None,
        company_id: str | None = None,
        tags: List[str] | None = None,
        knowledge_type: str | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[KnowledgeItem]:
        """Search knowledge items."""
        return await self.store.search_knowledge(query, company_id, tags, knowledge_type, limit, offset)

    async def get_knowledge_by_tags(
        self,
        company_id: str,
        tags: List[str]
    ) -> List[KnowledgeItem]:
        """
        Get knowledge items by tags for a company.
        
        Args:
            company_id: Company ID
            tags: List of tags to match
            
        Returns:
            List of KnowledgeItem instances
        """
        return await self.store.search_knowledge(
            company_id=company_id,
            tags=tags
        )


# =============================================================================
# SINGLETON AND FACTORY
# =============================================================================

_graph_service: CompanyGraphService | None = None


def get_company_graph_service() -> CompanyGraphService:
    """
    Get the singleton Company Graph service instance.
    
    Returns:
        The singleton CompanyGraphService instance.
    """
    global _graph_service
    if _graph_service is None:
        _graph_service = CompanyGraphService()
    return _graph_service


def set_company_graph_service(service: CompanyGraphService) -> None:
    """
    Set the singleton Company Graph service instance (for testing).
    
    Args:
        service: The CompanyGraphService instance to use.
    """
    global _graph_service
    _graph_service = service

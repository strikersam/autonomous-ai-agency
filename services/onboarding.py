"""
services/onboarding.py - Company Onboarding Service

Provides the complete onboarding flow for new companies, including:
- Website scanning and stack detection
- Repository scanning and analysis
- System detection and classification
- Specialist auto-provisioning
- Progress tracking

Usage:
    from services.onboarding import OnboardingService
    
    service = OnboardingService()
    
    # Start onboarding
    progress = await service.start_onboarding(
        company_id="company_123",
        website_urls=["https://example.com"],
        repo_urls=["https://github.com/user/repo"]
    )
    
    # Get progress
    progress = await service.get_onboarding_progress(company_id)
"""

from __future__ import annotations

from urllib.parse import urlparse
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import logging
import secrets
import asyncio

from models.company_graph import (
    Company,
    CompanyGraph,
    Website,
    Repo,
    DetectedSystem,
    Specialist,
    OnboardingProgress,
    Workflow,
    BusinessSystem,
    SystemType
)
from services.company_graph_store import get_company_graph_store, CompanyGraphStore
from services.company_graph import get_company_graph_service, CompanyGraphService
from services.scanner import WebsiteScanner, RepoScanner
from services.specialist import get_specialist_service, SpecialistService

log = logging.getLogger("company_graph.onboarding")


class OnboardingService:
    """
    Service for managing the company onboarding process.
    
    The onboarding flow:
    1. Create company (if not exists)
    2. Scan websites
    3. Scan repositories
    4. Detect systems
    5. Auto-provision specialists
    6. Create initial workflows
    """

    # Onboarding steps
    ONBOARDING_STEPS = [
        {"name": "create_company", "label": "Create Company", "description": "Creating company record"},
        {"name": "scan_websites", "label": "Scan Websites", "description": "Scanning company websites"},
        {"name": "scan_repositories", "label": "Scan Repositories", "description": "Scanning code repositories"},
        {"name": "detect_systems", "label": "Detect Systems", "description": "Detecting business systems"},
        {"name": "provision_specialists", "label": "Provision Specialists", "description": "Provisioning specialists"},
        {"name": "create_workflows", "label": "Create Workflows", "description": "Creating initial workflows"},
        {"name": "complete", "label": "Complete", "description": "Onboarding complete"}
    ]

    def __init__(
        self,
        store: CompanyGraphStore | None = None,
        graph_service: CompanyGraphService | None = None,
        specialist_service: SpecialistService | None = None
    ):
        """
        Initialize the onboarding service.
        
        Args:
            store: Optional CompanyGraphStore instance
            graph_service: Optional CompanyGraphService instance
            specialist_service: Optional SpecialistService instance
        """
        self.store = store or get_company_graph_store()
        self.graph_service = graph_service or get_company_graph_service()
        self.specialist_service = specialist_service or get_specialist_service()
        self._lock = asyncio.Lock()

    # =========================================================================
    # ONBOARDING MAIN FLOW
    # =========================================================================

    async def start_onboarding(
        self,
        company_id: str,
        website_urls: List[str],
        repo_urls: List[str] = [],
        skip_website_scan: bool = False,
        skip_repo_scan: bool = False,
        auto_provision_specialists: bool = True,
        create_workflows: bool = True,
        owner_id: str | None = None
    ) -> OnboardingProgress:
        """
        Start the onboarding process for a company.
        
        Args:
            company_id: Company ID
            website_urls: List of website URLs to scan
            repo_urls: List of repository URLs to scan
            skip_website_scan: Skip website scanning
            skip_repo_scan: Skip repository scanning
            auto_provision_specialists: Auto-provision specialists based on detected systems
            create_workflows: Create initial workflows
            owner_id: Optional owner ID for the company
            
        Returns:
            OnboardingProgress with current state
        """
        async with self._lock:
            # Get or create company
            company = await self.store.get_company(company_id)
            if not company:
                # Create company with first website domain
                domain = website_urls[0] if website_urls else ""
                company = await self.graph_service.create_company(
                    name=self._extract_company_name(website_urls[0]) if website_urls else "New Company",
                    domain=self._extract_domain(website_urls[0]) if website_urls else "",
                    owner_id=owner_id
                )
                company_id = company.id
            
            # Initialize progress
            progress = OnboardingProgress(
                company_id=company_id,
                current_step="create_company",
                total_steps=len(self.ONBOARDING_STEPS),
                completed_steps=1,
                progress_percent=100 / len(self.ONBOARDING_STEPS),
                status="in_progress",
                started_at=datetime.utcnow(),
                steps=[],
                errors=[]
            )
            
            # Update company onboarding status
            company = company.model_copy(update={
                "onboarding_status": "in_progress",
                "onboarding_progress": progress.progress_percent / 100
            })
            await self.store.update_company(company)
            
            # Step 1: Create company (already done)
            progress.steps.append({
                "name": "create_company",
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
                "message": f"Company {company.name} created"
            })
            
            try:
                # Step 2: Scan websites
                if not skip_website_scan and website_urls:
                    progress.current_step = "scan_websites"
                    progress.completed_steps = 2
                    progress.progress_percent = (2 / len(self.ONBOARDING_STEPS)) * 100
                    await self._update_progress(progress)
                    
                    scanned_websites = []
                    for url in website_urls:
                        try:
                            website = await self._scan_website(company_id, url)
                            scanned_websites.append(website)
                        except Exception as e:
                            progress.errors.append(f"Failed to scan website {url}: {str(e)}")
                            log.error(f"Website scan failed for {url}: {e}")
                    
                    progress.steps.append({
                        "name": "scan_websites",
                        "status": "completed",
                        "completed_at": datetime.utcnow().isoformat(),
                        "message": f"Scanned {len(scanned_websites)} websites",
                        "details": {"websites": [w.url for w in scanned_websites]}
                    })
                
                # Step 3: Scan repositories
                if not skip_repo_scan and repo_urls:
                    progress.current_step = "scan_repositories"
                    progress.completed_steps = 3
                    progress.progress_percent = (3 / len(self.ONBOARDING_STEPS)) * 100
                    await self._update_progress(progress)
                    
                    scanned_repos = []
                    for url in repo_urls:
                        try:
                            repo = await self._scan_repo(company_id, url)
                            scanned_repos.append(repo)
                        except Exception as e:
                            progress.errors.append(f"Failed to scan repository {url}: {str(e)}")
                            log.error(f"Repository scan failed for {url}: {e}")
                    
                    progress.steps.append({
                        "name": "scan_repositories",
                        "status": "completed",
                        "completed_at": datetime.utcnow().isoformat(),
                        "message": f"Scanned {len(scanned_repos)} repositories",
                        "details": {"repositories": [r.url for r in scanned_repos]}
                    })
                
                # Step 4: Detect systems
                progress.current_step = "detect_systems"
                progress.completed_steps = 4
                progress.progress_percent = (4 / len(self.ONBOARDING_STEPS)) * 100
                await self._update_progress(progress)
                
                # Get all websites and repos for the company
                websites = await self.store.list_websites(company_id)
                repos = await self.store.list_repos(company_id)
                
                detected_system_types: set[SystemType] = set()
                
                # Detect from websites
                for website in websites:
                    if website.detected_systems:
                        for system in website.detected_systems:
                            detected_system_types.add(system.system_type)
                    if website.inferred_stack:
                        stack = website.inferred_stack
                        if stack.cms:
                            detected_system_types.add("CMS")
                        if stack.analytics:
                            detected_system_types.add("analytics")
                        if stack.frameworks:
                            for fw in stack.frameworks:
                                if fw.lower() in ["react", "vue", "angular", "svelte"]:
                                    detected_system_types.add("frontend")
                                elif fw.lower() in ["django", "flask", "rails", "laravel", "express"]:
                                    detected_system_types.add("backend")
                
                # Detect from repos
                for repo in repos:
                    if repo.inferred_stack:
                        stack = repo.inferred_stack
                        if stack.frameworks:
                            for fw in stack.frameworks:
                                if fw.lower() in ["django", "flask", "rails", "laravel", "express"]:
                                    detected_system_types.add("backend")
                                elif fw.lower() in ["react", "vue", "angular", "svelte"]:
                                    detected_system_types.add("frontend")
                        if stack.databases:
                            detected_system_types.add("database")
                
                progress.steps.append({
                    "name": "detect_systems",
                    "status": "completed",
                    "completed_at": datetime.utcnow().isoformat(),
                    "message": f"Detected {len(detected_system_types)} system types",
                    "details": {"system_types": list(detected_system_types)}
                })
                
                # Step 5: Provision specialists
                if auto_provision_specialists:
                    progress.current_step = "provision_specialists"
                    progress.completed_steps = 5
                    progress.progress_percent = (5 / len(self.ONBOARDING_STEPS)) * 100
                    await self._update_progress(progress)
                    
                    provision_results = await self.specialist_service.provision_specialists_for_company(
                        company_id=company_id,
                        system_types=list(detected_system_types)
                    )
                    
                    progress.steps.append({
                        "name": "provision_specialists",
                        "status": "completed",
                        "completed_at": datetime.utcnow().isoformat(),
                        "message": f"Provisioned {len(provision_results)} specialists",
                        "details": {"specialists": [r.specialist.name if r.specialist else "Unknown" for r in provision_results]}
                    })
                
                # Step 6: Create workflows
                if create_workflows:
                    progress.current_step = "create_workflows"
                    progress.completed_steps = 6
                    progress.progress_percent = (6 / len(self.ONBOARDING_STEPS)) * 100
                    await self._update_progress(progress)
                    
                    workflows = await self._create_initial_workflows(company_id)
                    
                    progress.steps.append({
                        "name": "create_workflows",
                        "status": "completed",
                        "completed_at": datetime.utcnow().isoformat(),
                        "message": f"Created {len(workflows)} initial workflows",
                        "details": {"workflows": [w.name for w in workflows]}
                    })
                
                # Step 7: Complete
                progress.current_step = "complete"
                progress.completed_steps = len(self.ONBOARDING_STEPS)
                progress.progress_percent = 100.0
                progress.status = "completed"
                progress.completed_at = datetime.utcnow()
                
                # Update company onboarding status
                company = company.model_copy(update={
                    "onboarding_status": "complete",
                    "onboarding_progress": 1.0
                })
                await self.store.update_company(company)
                
                progress.steps.append({
                    "name": "complete",
                    "status": "completed",
                    "completed_at": datetime.utcnow().isoformat(),
                    "message": "Onboarding completed successfully"
                })
                
                log.info(f"Completed onboarding for company {company_id}")
                
            except Exception as e:
                progress.status = "failed"
                progress.errors.append(str(e))
                progress.completed_at = datetime.utcnow()
                
                # Update company onboarding status
                company = company.model_copy(update={
                    "onboarding_status": "failed",
                    "onboarding_progress": progress.progress_percent / 100
                })
                await self.store.update_company(company)
                
                log.error(f"Onboarding failed for company {company_id}: {e}")
            
            return progress

    async def get_onboarding_progress(
        self,
        company_id: str
    ) -> OnboardingProgress:
        """
        Get the current onboarding progress for a company.
        
        Args:
            company_id: Company ID
            
        Returns:
            OnboardingProgress with current state
        """
        company = await self.store.get_company(company_id)
        if not company:
            return OnboardingProgress(
                company_id=company_id,
                current_step="not_started",
                total_steps=len(self.ONBOARDING_STEPS),
                completed_steps=0,
                progress_percent=0.0,
                status="not_started"
            )
        
        # Check if onboarding is in progress
        if company.onboarding_status == "not_started":
            return OnboardingProgress(
                company_id=company_id,
                current_step="not_started",
                total_steps=len(self.ONBOARDING_STEPS),
                completed_steps=0,
                progress_percent=0.0,
                status="not_started"
            )
        
        # Check if onboarding is complete
        if company.onboarding_status == "complete":
            return OnboardingProgress(
                company_id=company_id,
                current_step="complete",
                total_steps=len(self.ONBOARDING_STEPS),
                completed_steps=len(self.ONBOARDING_STEPS),
                progress_percent=100.0,
                status="completed",
                completed_at=datetime.utcnow()
            )
        
        # For in_progress or failed, try to get actual progress
        # In a real implementation, this would be stored in the database
        # For now, we'll return a basic progress based on company status
        
        if company.onboarding_status == "in_progress":
            # Estimate progress based on what we have
            websites = await self.store.list_websites(company_id)
            repos = await self.store.list_repos(company_id)
            specialists = await self.store.list_specialists(company_id)
            
            completed_steps = 1  # create_company
            if websites:
                completed_steps += 1
            if repos:
                completed_steps += 1
            if websites or repos:
                completed_steps += 1  # detect_systems
            if specialists:
                completed_steps += 1
            
            progress_percent = (completed_steps / len(self.ONBOARDING_STEPS)) * 100
            
            return OnboardingProgress(
                company_id=company_id,
                current_step=self.ONBOARDING_STEPS[min(completed_steps, len(self.ONBOARDING_STEPS) - 1)]["name"],
                total_steps=len(self.ONBOARDING_STEPS),
                completed_steps=completed_steps,
                progress_percent=progress_percent,
                status="in_progress",
                started_at=datetime.utcnow()
            )
        
        # Failed status
        return OnboardingProgress(
            company_id=company_id,
            current_step="detect_systems",
            total_steps=len(self.ONBOARDING_STEPS),
            completed_steps=4,
            progress_percent=57.0,  # ~4/7
            status="failed"
        )

    async def resume_onboarding(
        self,
        company_id: str
    ) -> OnboardingProgress:
        """
        Resume onboarding from where it left off.
        
        Args:
            company_id: Company ID
            
        Returns:
            OnboardingProgress with updated state
        """
        # Get current progress
        progress = await self.get_onboarding_progress(company_id)
        
        if progress.status == "completed":
            return progress
        
        if progress.status == "not_started":
            # Can't resume, start fresh
            return await self.start_onboarding(
                company_id=company_id,
                website_urls=[],
                repo_urls=[]
            )
        
        # Get company
        company = await self.store.get_company(company_id)
        if not company:
            raise ValueError(f"Company {company_id} not found")
        
        # Determine next step
        next_step_index = progress.completed_steps
        if next_step_index >= len(self.ONBOARDING_STEPS):
            progress.status = "completed"
            progress.completed_at = datetime.utcnow()
            return progress
        
        next_step = self.ONBOARDING_STEPS[next_step_index]["name"]
        
        # Resume based on next step
        if next_step == "scan_websites":
            # Find websites that haven't been scanned
            websites = await self.store.list_websites(company_id)
            unscreened = [w for w in websites if not w.scan_status or w.scan_status == "pending"]
            if unscreened:
                return await self.start_onboarding(
                    company_id=company_id,
                    website_urls=[w.url for w in unscreened],
                    skip_website_scan=False,
                    skip_repo_scan=True,
                    auto_provision_specialists=False,
                    create_workflows=False
                )
        
        elif next_step == "scan_repositories":
            # Find repos that haven't been scanned
            repos = await self.store.list_repos(company_id)
            unscreened = [r for r in repos if not r.last_scanned]
            if unscreened:
                return await self.start_onboarding(
                    company_id=company_id,
                    website_urls=[],
                    repo_urls=[r.url for r in unscreened],
                    skip_website_scan=True,
                    skip_repo_scan=False,
                    auto_provision_specialists=False,
                    create_workflows=False
                )
        
        elif next_step == "detect_systems":
            # Systems should be detected during scanning, so just move to next
            return await self.start_onboarding(
                company_id=company_id,
                website_urls=[],
                repo_urls=[],
                skip_website_scan=True,
                skip_repo_scan=True,
                auto_provision_specialists=True,
                create_workflows=False
            )
        
        elif next_step == "provision_specialists":
            return await self.start_onboarding(
                company_id=company_id,
                website_urls=[],
                repo_urls=[],
                skip_website_scan=True,
                skip_repo_scan=True,
                auto_provision_specialists=True,
                create_workflows=False
            )
        
        elif next_step == "create_workflows":
            return await self.start_onboarding(
                company_id=company_id,
                website_urls=[],
                repo_urls=[],
                skip_website_scan=True,
                skip_repo_scan=True,
                auto_provision_specialists=False,
                create_workflows=True
            )
        
        # Default: just mark as complete
        progress.completed_steps = len(self.ONBOARDING_STEPS)
        progress.progress_percent = 100.0
        progress.status = "completed"
        progress.completed_at = datetime.utcnow()
        progress.current_step = "complete"
        
        company = company.model_copy(update={
            "onboarding_status": "complete",
            "onboarding_progress": 1.0
        })
        await self.store.update_company(company)
        
        return progress

    async def pause_onboarding(
        self,
        company_id: str
    ) -> OnboardingProgress:
        """
        Pause onboarding for a company (sets status to paused).

        Args:
            company_id: Company ID

        Returns:
            OnboardingProgress with paused state
        """
        progress = await self.get_onboarding_progress(company_id)

        if progress.status in ("completed", "not_started"):
            return progress

        company = await self.store.get_company(company_id)
        if company:
            company = company.model_copy(update={
                "onboarding_status": "in_progress",  # keep in_progress; status tracked in progress obj
            })
            await self.store.update_company(company)

        return OnboardingProgress(
            company_id=company_id,
            current_step=progress.current_step,
            total_steps=progress.total_steps,
            completed_steps=progress.completed_steps,
            progress_percent=progress.progress_percent,
            status="paused",
            steps=progress.steps,
            errors=progress.errors,
            started_at=progress.started_at,
            completed_at=None,
        )

    async def cancel_onboarding(
        self,
        company_id: str
    ) -> OnboardingProgress:
        """
        Cancel onboarding for a company.
        
        Args:
            company_id: Company ID
            
        Returns:
            OnboardingProgress with cancelled state
        """
        company = await self.store.get_company(company_id)
        if not company:
            raise ValueError(f"Company {company_id} not found")
        
        # Update company onboarding status
        company = company.model_copy(update={
            "onboarding_status": "cancelled",
            "onboarding_progress": 0.0
        })
        await self.store.update_company(company)
        
        return OnboardingProgress(
            company_id=company_id,
            current_step="cancelled",
            total_steps=len(self.ONBOARDING_STEPS),
            completed_steps=0,
            progress_percent=0.0,
            status="cancelled",
            completed_at=datetime.utcnow()
        )

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    async def _scan_website(
        self,
        company_id: str,
        url: str
    ) -> Website:
        """
        Scan a website and save the results.
        
        Args:
            company_id: Company ID
            url: Website URL
            
        Returns:
            Created Website instance
        """
        scanner = WebsiteScanner(company_id)
        scan_result = await scanner.scan_website(url)
        
        if scan_result.status != "success":
            raise Exception(f"Website scan failed: {scan_result.errors}")
        
        # Create website
        website = Website(
            url=url,
            company_id=company_id,
            is_primary=True,  # First website is primary
            scan_status="success",
            inferred_stack=scan_result.inferred_stack,
            detected_systems=scan_result.detected_systems,
            last_scanned=datetime.utcnow()
        )
        
        created = await self.graph_service.add_website(
            company_id=company_id,
            url=url
        )
        
        # Update with scan results
        created = created.model_copy(update={
            "scan_status": "success",
            "inferred_stack": scan_result.inferred_stack,
            "detected_systems": scan_result.detected_systems,
            "last_scanned": datetime.utcnow()
        })
        
        await self.store.update_website(created)
        
        return created

    async def _scan_repo(
        self,
        company_id: str,
        url: str
    ) -> Repo:
        """
        Scan a repository and save the results.
        
        Args:
            company_id: Company ID
            url: Repository URL
            
        Returns:
            Created Repo instance
        """
        scanner = RepoScanner(company_id)
        scan_result = await scanner.scan_repo(url)
        
        if scan_result.status != "success":
            raise Exception(f"Repository scan failed: {scan_result.errors}")
        
        # Extract provider from URL
        provider = self._detect_provider(url)
        
        # Create repo
        repo = Repo(
            url=url,
            company_id=company_id,
            provider=provider,
            name=url.split('/')[-1],
            full_name=url,
            inferred_stack=scan_result.inferred_stack,
            last_scanned=datetime.utcnow()
        )
        
        created = await self.graph_service.add_repo(
            company_id=company_id,
            url=url,
            provider=provider
        )
        
        # Update with scan results
        created = created.model_copy(update={
            "inferred_stack": scan_result.inferred_stack,
            "last_scanned": datetime.utcnow()
        })
        
        await self.store.update_repo(created)
        
        return created

    async def _create_initial_workflows(
        self,
        company_id: str
    ) -> List[Workflow]:
        """
        Create initial workflows for a company.
        
        Args:
            company_id: Company ID
            
        Returns:
            List of created Workflow instances
        """
        workflows = []
        
        # Basic development workflow
        dev_workflow = Workflow(
            company_id=company_id,
            name="Development",
            description="Standard development workflow",
            phases=["plan", "develop", "review", "test", "deploy"],
            triggers=["code_push", "pr_created", "issue_created"],
            is_active=True,
            is_default=True
        )
        created = await self.graph_service.add_workflow(
            company_id=company_id,
            name="Development",
            phases=["plan", "develop", "review", "test", "deploy"],
            description="Standard development workflow",
            triggers=["code_push", "pr_created", "issue_created"]
        )
        workflows.append(created)
        
        # QA workflow
        qa_workflow = Workflow(
            company_id=company_id,
            name="Quality Assurance",
            description="QA and testing workflow",
            phases=["test_plan", "test_execution", "bug_reporting", "verification"],
            triggers=["pr_merged", "release_created"],
            is_active=True
        )
        created = await self.graph_service.add_workflow(
            company_id=company_id,
            name="Quality Assurance",
            phases=["test_plan", "test_execution", "bug_reporting", "verification"],
            description="QA and testing workflow",
            triggers=["pr_merged", "release_created"]
        )
        workflows.append(created)
        
        return workflows

    async def _update_progress(
        self,
        progress: OnboardingProgress
    ) -> None:
        """
        Update onboarding progress in storage.
        
        Args:
            progress: OnboardingProgress to update
        """
        # In a real implementation, this would save to the database
        # For now, we just log it
        log.debug(f"Onboarding progress for {progress.company_id}: {progress.progress_percent}%")

    def _extract_company_name(self, url: str) -> str:
        """
        Extract company name from a URL.
        
        Args:
            url: Website URL
            
        Returns:
            Extracted company name
        """
        if not url:
            return "New Company"
        
        # Remove protocol and path
        domain = self._extract_domain(url)
        
        # Remove common TLDs
        if '.' in domain:
            parts = domain.split('.')
            # Take the first part (usually the company name)
            name = parts[0]
            # Capitalize
            return name.title()
        
        return domain.title()

    def _extract_domain(self, url: str) -> str:
        """
        Extract domain from a URL.
        
        Args:
            url: URL
            
        Returns:
            Domain name
        """
        if not url:
            return ""
        
        # Remove protocol
        if url.startswith(("http://", "https://")):
            url = url[url.index("://") + 3:]
        
        # Remove path and query
        if '/' in url:
            url = url[:url.index('/')]
        if '?' in url:
            url = url[:url.index('?')]
        if '#' in url:
            url = url[:url.index('#')]
        
        return url

    def _detect_provider(self, repo_url: str) -> str:
        """
        Detect the Git provider from a repository URL.
        
        Args:
            repo_url: Repository URL
            
        Returns:
            Provider name
        """
        parsed = urlparse(repo_url)
        hostname = (parsed.hostname or repo_url).lower()

        def _host_match(*domains):
            return any(hostname == d or hostname.endswith('.' + d) for d in domains)

        if _host_match('github.com'):
            return 'github'
        elif _host_match('gitlab.com'):
            return 'gitlab'
        elif _host_match('bitbucket.org'):
            return 'bitbucket'
        elif _host_match('azure.com', 'dev.azure.com'):
            return 'azure'
        elif repo_url.startswith('git@'):
            # SSH URLs: git@github.com:user/repo
            ssh_host = repo_url.split('@')[1].split(':')[0] if '@' in repo_url else ''
            if ssh_host == 'github.com':
                return 'github'
            elif ssh_host == 'gitlab.com':
                return 'gitlab'
            elif ssh_host == 'bitbucket.org':
                return 'bitbucket'
            else:
                return 'unknown'
        else:
            return 'unknown'


# =============================================================================
# SINGLETON AND FACTORY
# =============================================================================

_onboarding_service: OnboardingService | None = None


def get_onboarding_service() -> OnboardingService:
    """
    Get the singleton Onboarding service instance.
    
    Returns:
        The singleton OnboardingService instance.
    """
    global _onboarding_service
    if _onboarding_service is None:
        _onboarding_service = OnboardingService()
    return _onboarding_service


def set_onboarding_service(service: OnboardingService) -> None:
    """
    Set the singleton Onboarding service instance (for testing).
    
    Args:
        service: The OnboardingService instance to use.
    """
    global _onboarding_service
    _onboarding_service = service

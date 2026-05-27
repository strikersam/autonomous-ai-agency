"""
services/scanner.py - Website and Repository Scanner Service

Provides scanning capabilities for websites and repositories to detect technology stacks,
systems, and other metadata.

Usage:
    from services.scanner import WebsiteScanner, RepoScanner
    
    # Scan a website
    scanner = WebsiteScanner(company_id="company_123")
    result = await scanner.scan_website("https://example.com")
    
    # Scan a repository
    repo_scanner = RepoScanner(company_id="company_123")
    repo_result = await repo_scanner.scan_repo("https://github.com/user/repo")
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import secrets
import httpx
from bs4 import BeautifulSoup

from models.company_graph import (
    WebsiteScanRequest,
    WebsiteScanResult,
    RepoScanRequest,
    RepoScanResult,
    StackInference,
    DetectedSystem,
    Evidence
)

log = logging.getLogger("company_graph.scanner")


import ipaddress
import socket
from urllib.parse import urlparse


def _is_safe_url(url: str) -> bool:
    """Block SSRF: reject loopback, link-local, private, and non-HTTP schemes."""
    try:
        parsed = urlparse(url)
        # Only allow http/https
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        # Block obvious internal hostnames
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False
        if hostname.endswith(".local") or hostname.endswith(".internal"):
            return False
        # Resolve and check IP ranges
        resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, _, _, _, sockaddr in resolved:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
    except (socket.gaierror, ValueError):
        return False
    return True


def _hostname_is(url: str, domain: str) -> bool:
    """Check if URL hostname exactly matches or is a subdomain of the given domain."""
    try:
        hostname = urlparse(url).hostname or ""
        hostname = hostname.lower()
        domain = domain.lower()
        return hostname == domain or hostname.endswith("." + domain)
    except Exception:
        return False


def _hostname_contains(url: str, *domains: str) -> bool:
    """Check if URL hostname matches any of the given domains."""
    return any(_hostname_is(url, d) for d in domains)

class WebsiteScanner:
    """
    Scanner for detecting technology stack and systems from websites.
    
    Capabilities:
    - Detect CMS (Shopify, WordPress, etc.)
    - Detect frameworks (React, Vue, Angular, etc.)
    - Detect analytics (Google Analytics, etc.)
    - Detect payment gateways
    - Detect other business systems
    """

    def __init__(self, company_id: Optional[str] = None):
        """
        Initialize the website scanner.
        
        Args:
            company_id: Optional company ID for context
        """
        self.company_id = company_id
        self.user_agent = "AgencyCore/1.0 (Company Graph Scanner)"
        self.timeout = 30.0
        self.max_redirects = 5

    async def scan_website(
        self,
        website_url: str,
        scan_depth: str = "standard",
        include_sitemap: bool = True,
        max_pages: int = 20
    ) -> WebsiteScanResult:
        """
        Scan a website and detect its technology stack.
        
        Args:
            website_url: URL of the website to scan
            scan_depth: Depth of scan ("shallow", "standard", "deep")
            include_sitemap: Whether to include sitemap discovery
            max_pages: Maximum number of pages to scan
            
        Returns:
            WebsiteScanResult with detected systems and stack inference
        """
        scan_id = f"scan_{secrets.token_hex(8)}"
        started_at = datetime.utcnow()
        
        try:
            # Normalize URL
            if not website_url.startswith(("http://", "https://")):
                website_url = f"https://{website_url}"
            
            # SSRF protection: block internal/private networks
            if not _is_safe_url(website_url):
                return WebsiteScanResult(
                    scan_id=scan_id,
                    website_url=website_url,
                    company_id=self.company_id,
                    status="failed",
                    errors=["Blocked: target resolves to private/internal network"],
                    started_at=started_at.isoformat(),
                    completed_at=datetime.utcnow().isoformat()
                )
            
            # Fetch the homepage
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                max_redirects=self.max_redirects,
                headers={"User-Agent": self.user_agent}
            ) as client:
                try:
                    response = await client.get(website_url)
                    response.raise_for_status()
                    html = response.text
                    status_code = response.status_code
                except httpx.HTTPStatusError as e:
                    return WebsiteScanResult(
                        scan_id=scan_id,
                        website_url=website_url,
                        company_id=self.company_id,
                        status="failed",
                        errors=[f"HTTP error: {e.response.status_code}"],
                        started_at=started_at.isoformat(),
                        completed_at=datetime.utcnow().isoformat()
                    )
                except httpx.RequestError as e:
                    return WebsiteScanResult(
                        scan_id=scan_id,
                        website_url=website_url,
                        company_id=self.company_id,
                        status="failed",
                        errors=[f"Request error: {str(e)}"],
                        started_at=started_at.isoformat(),
                        completed_at=datetime.utcnow().isoformat()
                    )
                
                # Parse HTML
                soup = BeautifulSoup(html, 'html.parser')
                
                # Detect systems
                detected_systems = await self._detect_systems(soup, website_url)
                
                # Infer stack
                stack_inference = await self._infer_stack(soup, html, website_url)
                
                # Discover sitemap if requested
                sitemap_urls = []
                if include_sitemap:
                    sitemap_urls = await self._discover_sitemap(soup, website_url, client)
                
                # Count pages scanned
                pages_scanned = 1 + len(sitemap_urls) if sitemap_urls else 1
                
                completed_at = datetime.utcnow()
                
                return WebsiteScanResult(
                    scan_id=scan_id,
                    website_url=website_url,
                    company_id=self.company_id,
                    status="success",
                    inferred_stack=stack_inference,
                    detected_systems=detected_systems,
                    pages_scanned=pages_scanned,
                    sitemap_urls=sitemap_urls,
                    started_at=started_at.isoformat(),
                    completed_at=completed_at.isoformat()
                )
                
        except Exception as e:
            log.error(f"Error scanning website {website_url}: {e}")
            return WebsiteScanResult(
                scan_id=scan_id,
                website_url=website_url,
                company_id=self.company_id,
                status="failed",
                errors=[str(e)],
                started_at=started_at.isoformat(),
                completed_at=datetime.utcnow().isoformat()
            )

    async def _detect_systems(
        self,
        soup: BeautifulSoup,
        url: str
    ) -> List[DetectedSystem]:
        """
        Detect business systems from HTML content.
        
        Args:
            soup: BeautifulSoup parsed HTML
            url: Website URL
            
        Returns:
            List of detected systems with evidence
        """
        systems = []
        
        # CMS Detection
        # Shopify
        if 'shopify' in str(soup).lower() or _hostname_is(url, 'myshopify.com'):
            systems.append(DetectedSystem(
                system_type="CMS",
                name="Shopify",
                confidence=0.95,
                evidence=[
                    Evidence(
                        type="meta_tag" if soup.find('meta', attrs={'name': 'generator', 'content': lambda x: x and 'shopify' in x.lower()}) else "html_content",
                        value="shopify",
                        location="head" if soup.find('meta', attrs={'name': 'generator'}) else "body",
                        confidence=0.95
                    )
                ]
            ))
        
        # WordPress
        if 'wp-content' in str(soup) or 'wordpress' in str(soup).lower():
            systems.append(DetectedSystem(
                system_type="CMS",
                name="WordPress",
                confidence=0.9,
                evidence=[
                    Evidence(
                        type="path",
                        value="/wp-content/",
                        location="html",
                        confidence=0.9
                    )
                ]
            ))
        
        # Wix
        if _hostname_is(url, 'wix.com') or 'wix' in str(soup).lower():
            systems.append(DetectedSystem(
                system_type="CMS",
                name="Wix",
                confidence=0.9,
                evidence=[
                    Evidence(
                        type="domain",
                        value="wix.com",
                        location="url",
                        confidence=0.9
                    )
                ]
            ))
        
        # Squarespace
        if _hostname_is(url, 'squarespace.com') or 'squarespace' in str(soup).lower():
            systems.append(DetectedSystem(
                system_type="CMS",
                name="Squarespace",
                confidence=0.85,
                evidence=[
                    Evidence(
                        type="domain",
                        value="squarespace.com",
                        location="url",
                        confidence=0.85
                    )
                ]
            ))
        
        # Analytics Detection
        scripts = soup.find_all('script')
        
        # Google Analytics
        for script in scripts:
            script_text = str(script)
            if 'googletagmanager.com' in script_text or 'google-analytics.com' in script_text:
                systems.append(DetectedSystem(
                    system_type="analytics",
                    name="Google Analytics",
                    confidence=0.85,
                    evidence=[
                        Evidence(
                            type="script",
                            value="google-analytics.com",
                            location="body",
                            confidence=0.85
                        )
                    ]
                ))
                break
        
        # Google Tag Manager
        for script in scripts:
            script_text = str(script)
            if 'googletagmanager.com/gtm.js' in script_text:
                systems.append(DetectedSystem(
                    system_type="analytics",
                    name="Google Tag Manager",
                    confidence=0.85,
                    evidence=[
                        Evidence(
                            type="script",
                            value="googletagmanager.com/gtm.js",
                            location="body",
                            confidence=0.85
                        )
                    ]
                ))
                break
        
        # Mixpanel
        for script in scripts:
            script_text = str(script)
            if 'mixpanel.com' in script_text:
                systems.append(DetectedSystem(
                    system_type="analytics",
                    name="Mixpanel",
                    confidence=0.8,
                    evidence=[
                        Evidence(
                            type="script",
                            value="mixpanel.com",
                            location="body",
                            confidence=0.8
                        )
                    ]
                ))
                break
        
        # Amplitude
        for script in scripts:
            script_text = str(script)
            if 'amplitude.com' in script_text:
                systems.append(DetectedSystem(
                    system_type="analytics",
                    name="Amplitude",
                    confidence=0.8,
                    evidence=[
                        Evidence(
                            type="script",
                            value="amplitude.com",
                            location="body",
                            confidence=0.8
                        )
                    ]
                ))
                break
        
        # Payment Gateway Detection
        # Stripe
        for script in scripts:
            script_text = str(script)
            if 'stripe.com' in script_text or 'stripe.js' in script_text:
                systems.append(DetectedSystem(
                    system_type="payment_gateway",
                    name="Stripe",
                    confidence=0.85,
                    evidence=[
                        Evidence(
                            type="script",
                            value="stripe.com",
                            location="body",
                            confidence=0.85
                        )
                    ]
                ))
                break
        
        # PayPal
        for script in scripts:
            script_text = str(script)
            if 'paypal.com' in script_text or 'paypalobjects.com' in script_text:
                systems.append(DetectedSystem(
                    system_type="payment_gateway",
                    name="PayPal",
                    confidence=0.85,
                    evidence=[
                        Evidence(
                            type="script",
                            value="paypal.com",
                            location="body",
                            confidence=0.85
                        )
                    ]
                ))
                break
        
        # CRM Detection
        # HubSpot
        for script in scripts:
            script_text = str(script)
            if 'hubspot.com' in script_text:
                systems.append(DetectedSystem(
                    system_type="CRM",
                    name="HubSpot",
                    confidence=0.8,
                    evidence=[
                        Evidence(
                            type="script",
                            value="hubspot.com",
                            location="body",
                            confidence=0.8
                        )
                    ]
                ))
                break
        
        # Salesforce
        for script in scripts:
            script_text = str(script)
            if 'salesforceliveagent.com' in script_text or 'force.com' in script_text:
                systems.append(DetectedSystem(
                    system_type="CRM",
                    name="Salesforce",
                    confidence=0.8,
                    evidence=[
                        Evidence(
                            type="script",
                            value="salesforceliveagent.com",
                            location="body",
                            confidence=0.8
                        )
                    ]
                ))
                break
        
        # E-commerce Platform Detection
        # BigCommerce
        if _hostname_is(url, 'bigcommerce.com') or 'bigcommerce' in str(soup).lower():
            systems.append(DetectedSystem(
                system_type="ecommerce",
                name="BigCommerce",
                confidence=0.85,
                evidence=[
                    Evidence(
                        type="domain",
                        value="bigcommerce.com",
                        location="url",
                        confidence=0.85
                    )
                ]
            ))
        
        # Magento
        if 'magento' in str(soup).lower():
            systems.append(DetectedSystem(
                system_type="ecommerce",
                name="Magento",
                confidence=0.8,
                evidence=[
                    Evidence(
                        type="html_content",
                        value="magento",
                        location="body",
                        confidence=0.8
                    )
                ]
            ))
        
        # WooCommerce
        if 'woocommerce' in str(soup).lower() or 'wp-content/plugins/woocommerce' in str(soup):
            systems.append(DetectedSystem(
                system_type="ecommerce",
                name="WooCommerce",
                confidence=0.85,
                evidence=[
                    Evidence(
                        type="path",
                        value="/wp-content/plugins/woocommerce",
                        location="html",
                        confidence=0.85
                    )
                ]
            ))
        
        return systems

    async def _infer_stack(
        self,
        soup: BeautifulSoup,
        html: str,
        url: str
    ) -> StackInference:
        """
        Infer technology stack from HTML content.
        
        Args:
            soup: BeautifulSoup parsed HTML
            html: Raw HTML content
            url: Website URL
            
        Returns:
            StackInference with detected frameworks, languages, etc.
        """
        frameworks = []
        languages = []
        cms = []
        analytics = []
        databases = []
        servers = []
        confidence_scores = {}
        
        html_lower = html.lower()
        
        # Framework Detection
        # React
        if 'react' in html_lower or 'react-dom' in html_lower:
            frameworks.append("React")
            confidence_scores["React"] = 0.95
        
        # Vue.js
        if 'vue.js' in html_lower or 'vuejs' in html_lower:
            frameworks.append("Vue.js")
            confidence_scores["Vue.js"] = 0.9
        
        # Angular
        if 'ng-' in html_lower or 'angular' in html_lower:
            frameworks.append("Angular")
            confidence_scores["Angular"] = 0.9
        
        # Svelte
        if 'svelte' in html_lower:
            frameworks.append("Svelte")
            confidence_scores["Svelte"] = 0.85
        
        # Next.js
        if 'next.js' in html_lower or 'nextjs' in html_lower or '__next' in html_lower:
            frameworks.append("Next.js")
            confidence_scores["Next.js"] = 0.9
        
        # Nuxt.js
        if 'nuxt.js' in html_lower or 'nuxtjs' in html_lower:
            frameworks.append("Nuxt.js")
            confidence_scores["Nuxt.js"] = 0.85
        
        # jQuery
        if 'jquery' in html_lower:
            frameworks.append("jQuery")
            confidence_scores["jQuery"] = 0.9
        
        # Language Detection
        # JavaScript
        if 'javascript' in html_lower or '<script>' in html_lower:
            languages.append("JavaScript")
            confidence_scores["JavaScript"] = 0.95
        
        # TypeScript (harder to detect from HTML)
        if 'typescript' in html_lower:
            languages.append("TypeScript")
            confidence_scores["TypeScript"] = 0.7
        
        # CSS
        if '<style>' in html_lower or '.css' in html_lower:
            languages.append("CSS")
            confidence_scores["CSS"] = 0.9
        
        # HTML
        languages.append("HTML")
        confidence_scores["HTML"] = 1.0
        
        # PHP
        if 'php' in html_lower or '<?php' in html:
            languages.append("PHP")
            confidence_scores["PHP"] = 0.85
        
        # Python (server-side, hard to detect from HTML)
        if 'django' in html_lower or 'flask' in html_lower:
            languages.append("Python")
            confidence_scores["Python"] = 0.7
        
        # CMS Detection (from stack inference perspective)
        if 'shopify' in html_lower or _hostname_is(url, 'myshopify.com'):
            cms.append("Shopify")
            confidence_scores["Shopify"] = 0.95
        
        if 'wp-content' in html_lower or 'wordpress' in html_lower:
            cms.append("WordPress")
            confidence_scores["WordPress"] = 0.9
        
        if _hostname_is(url, 'wix.com'):
            cms.append("Wix")
            confidence_scores["Wix"] = 0.85
        
        # Analytics Detection
        if 'google-analytics.com' in html_lower or 'googletagmanager.com' in html_lower:
            analytics.append("Google Analytics")
            confidence_scores["Google Analytics"] = 0.85
        
        if 'mixpanel.com' in html_lower:
            analytics.append("Mixpanel")
            confidence_scores["Mixpanel"] = 0.8
        
        if 'amplitude.com' in html_lower:
            analytics.append("Amplitude")
            confidence_scores["Amplitude"] = 0.8
        
        return StackInference(
            frameworks=list(set(frameworks)),
            languages=list(set(languages)),
            cms=list(set(cms)),
            analytics=list(set(analytics)),
            databases=list(set(databases)),
            servers=list(set(servers)),
            confidence_scores=confidence_scores
        )

    async def _discover_sitemap(
        self,
        soup: BeautifulSoup,
        base_url: str,
        client: httpx.AsyncClient
    ) -> List[str]:
        """
        Discover sitemap URLs from the website.
        
        Args:
            soup: BeautifulSoup parsed HTML
            base_url: Base URL of the website
            client: HTTP client for making requests
            
        Returns:
            List of URLs found in sitemaps
        """
        sitemap_urls = []
        
        # Check for sitemap in robots.txt
        try:
            robots_url = f"{base_url.rstrip('/')}/robots.txt"
            response = await client.get(robots_url, timeout=10)
            if response.status_code == 200:
                robots_text = response.text
                for line in robots_text.split('\n'):
                    if 'sitemap:' in line.lower():
                        sitemap_url = line.split(':', 1)[1].strip()
                        if sitemap_url:
                            sitemap_urls.append(sitemap_url)
        except Exception:
            pass
        
        # Check for common sitemap locations
        common_sitemap_paths = [
            '/sitemap.xml',
            '/sitemap_index.xml',
            '/sitemap.xml.gz',
            '/sitemap/'
        ]
        
        for path in common_sitemap_paths:
            try:
                sitemap_url = f"{base_url.rstrip('/')}{path}"
                response = await client.get(sitemap_url, timeout=10)
                if response.status_code == 200:
                    sitemap_urls.append(sitemap_url)
            except Exception:
                pass
        
        # Parse sitemap.xml if found
        for sitemap_url in sitemap_urls[:]:  # Copy to avoid modification during iteration
            try:
                response = await client.get(sitemap_url, timeout=10)
                if response.status_code == 200:
                    sitemap_soup = BeautifulSoup(response.text, 'xml')
                    urls = sitemap_soup.find_all('url')
                    for url in urls:
                        loc = url.find('loc')
                        if loc and loc.text:
                            sitemap_urls.append(loc.text)
            except Exception:
                pass
        
        return list(set(sitemap_urls))


class RepoScanner:
    """
    Scanner for detecting technology stack from Git repositories.
    
    Capabilities:
    - Detect languages from repository files
    - Detect frameworks from package files
    - Detect CI/CD configuration
    - Detect dependencies
    """

    def __init__(self, company_id: Optional[str] = None):
        """
        Initialize the repository scanner.
        
        Args:
            company_id: Optional company ID for context
        """
        self.company_id = company_id
        self.user_agent = "AgencyCore/1.0 (Company Graph Repo Scanner)"
        self.timeout = 30.0

    async def scan_repo(
        self,
        repo_url: str
    ) -> RepoScanResult:
        """
        Scan a Git repository and detect its technology stack.
        
        Args:
            repo_url: URL of the repository
            
        Returns:
            RepoScanResult with inferred stack and detected systems
        """
        scan_id = f"repo_scan_{secrets.token_hex(8)}"
        started_at = datetime.utcnow()
        
        try:
            # Normalize URL
            if not repo_url.startswith(("http://", "https://", "git@")):
                repo_url = f"https://{repo_url}"
            
            # Extract provider, owner, and repo name
            provider = self._detect_provider(repo_url)
            
            # For now, we'll use the GitHub API if it's a GitHub repo
            # In production, we'd support GitLab, Bitbucket, etc.
            if provider == "github":
                return await self._scan_github_repo(repo_url, scan_id, started_at)
            else:
                # For non-GitHub repos, do a basic scan
                return RepoScanResult(
                    scan_id=scan_id,
                    repo_url=repo_url,
                    company_id=self.company_id,
                    status="partial",
                    inferred_stack=self._infer_stack_from_url(repo_url),
                    detected_systems=[],
                    files_scanned=0,
                    errors=[f"Provider {provider} not yet fully supported"],
                    started_at=started_at.isoformat(),
                    completed_at=datetime.utcnow().isoformat()
                )
                
        except Exception as e:
            log.error(f"Error scanning repo {repo_url}: {e}")
            return RepoScanResult(
                scan_id=scan_id,
                repo_url=repo_url,
                company_id=self.company_id,
                status="failed",
                errors=[str(e)],
                started_at=started_at.isoformat(),
                completed_at=datetime.utcnow().isoformat()
            )

    def _detect_provider(self, repo_url: str) -> str:
        """
        Detect the Git provider from a repository URL.
        
        Args:
            repo_url: Repository URL
            
        Returns:
            Provider name (github, gitlab, bitbucket, etc.)
        """
        parsed = urlparse(repo_url)
        hostname = (parsed.hostname or '').lower()

        def _match(*domains):
            return any(hostname == d or hostname.endswith('.' + d) for d in domains)

        if _match('github.com'):
            return 'github'
        elif _match('gitlab.com'):
            return 'gitlab'
        elif _match('bitbucket.org'):
            return 'bitbucket'
        elif _match('azure.com', 'dev.azure.com'):
            return 'azure_devops'
        elif repo_url.startswith('git@'):
            # SSH URL: git@github.com:user/repo
            ssh_host = repo_url.split('@')[1].split(':')[0] if '@' in repo_url else ''
            if ssh_host == 'github.com':
                return 'github'
            elif ssh_host == 'gitlab.com':
                return 'gitlab'
            elif ssh_host == 'bitbucket.org':
                return 'bitbucket'
            else:
                return 'other'
        else:
            return 'other'

    async def _scan_github_repo(
        self,
        repo_url: str,
        scan_id: str,
        started_at: datetime
    ) -> RepoScanResult:
        """
        Scan a GitHub repository.
        
        Args:
            repo_url: GitHub repository URL
            scan_id: Scan ID
            started_at: Start time
            
        Returns:
            RepoScanResult
        """
        # Extract owner and repo name
        parts = repo_url.replace('https://github.com/', '').replace('.git', '').split('/')
        if len(parts) < 2:
            return RepoScanResult(
                scan_id=scan_id,
                repo_url=repo_url,
                company_id=self.company_id,
                status="failed",
                errors=["Invalid GitHub repository URL"],
                started_at=started_at.isoformat(),
                completed_at=datetime.utcnow().isoformat()
            )
        
        owner = parts[0]
        repo_name = parts[1]
        
        # Try to fetch repository information from GitHub API
        # Note: This requires a GitHub token for private repos
        github_api_url = f"https://api.github.com/repos/{owner}/{repo_name}"
        
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent}
            ) as client:
                # Get repo info
                response = await client.get(github_api_url)
                
                if response.status_code == 200:
                    repo_data = response.json()
                    
                    # Get languages
                    languages_url = f"{github_api_url}/languages"
                    lang_response = await client.get(languages_url)
                    languages = {}
                    if lang_response.status_code == 200:
                        languages = lang_response.json()
                    
                    # Infer stack from languages and repo data
                    stack_inference = self._infer_stack_from_github_data(repo_data, languages)
                    
                    # Detect systems
                    detected_systems = self._detect_systems_from_github_data(repo_data)
                    
                    completed_at = datetime.utcnow()
                    
                    return RepoScanResult(
                        scan_id=scan_id,
                        repo_url=repo_url,
                        company_id=self.company_id,
                        status="success",
                        inferred_stack=stack_inference,
                        detected_systems=detected_systems,
                        files_scanned=repo_data.get('size', 0),
                        stargazers_count=repo_data.get('stargazers_count', 0),
                        forks_count=repo_data.get('forks_count', 0),
                        open_issues_count=repo_data.get('open_issues_count', 0),
                        default_branch=repo_data.get('default_branch', 'main'),
                        is_private=repo_data.get('private', False),
                        started_at=started_at.isoformat(),
                        completed_at=completed_at.isoformat()
                    )
                elif response.status_code == 404:
                    return RepoScanResult(
                        scan_id=scan_id,
                        repo_url=repo_url,
                        company_id=self.company_id,
                        status="failed",
                        errors=["Repository not found"],
                        started_at=started_at.isoformat(),
                        completed_at=datetime.utcnow().isoformat()
                    )
                elif response.status_code == 403:
                    return RepoScanResult(
                        scan_id=scan_id,
                        repo_url=repo_url,
                        company_id=self.company_id,
                        status="failed",
                        errors=["Rate limit exceeded or private repository without auth"],
                        started_at=started_at.isoformat(),
                        completed_at=datetime.utcnow().isoformat()
                    )
                else:
                    return RepoScanResult(
                        scan_id=scan_id,
                        repo_url=repo_url,
                        company_id=self.company_id,
                        status="failed",
                        errors=[f"GitHub API error: {response.status_code}"],
                        started_at=started_at.isoformat(),
                        completed_at=datetime.utcnow().isoformat()
                    )
                    
        except Exception as e:
            log.error(f"Error scanning GitHub repo {repo_url}: {e}")
            return RepoScanResult(
                scan_id=scan_id,
                repo_url=repo_url,
                company_id=self.company_id,
                status="failed",
                errors=[str(e)],
                started_at=started_at.isoformat(),
                completed_at=datetime.utcnow().isoformat()
            )

    def _infer_stack_from_url(self, repo_url: str) -> StackInference:
        """
        Infer stack from repository URL (basic detection).
        
        Args:
            repo_url: Repository URL
            
        Returns:
            StackInference
        """
        # This is a fallback for when we can't access the repo
        # We'll just return empty results
        return StackInference(
            frameworks=[],
            languages=[],
            cms=[],
            analytics=[],
            confidence_scores={}
        )

    def _infer_stack_from_github_data(
        self,
        repo_data: Dict[str, Any],
        languages: Dict[str, int]
    ) -> StackInference:
        """
        Infer stack from GitHub repository data.
        
        Args:
            repo_data: Repository data from GitHub API
            languages: Language breakdown from GitHub
            
        Returns:
            StackInference
        """
        frameworks = []
        languages_list = []
        cms = []
        analytics = []
        confidence_scores = {}
        
        # Process languages
        if languages:
            for lang, bytes_count in languages.items():
                languages_list.append(lang)
                confidence_scores[lang] = 0.9
        
        # Detect frameworks from language usage
        if 'JavaScript' in languages or 'TypeScript' in languages:
            # Check for common frontend frameworks
            if repo_data.get('name', '').lower().endswith('.next') or \
               any(f in repo_data.get('name', '').lower() for f in ['nextjs', 'next.js']):
                frameworks.append("Next.js")
                confidence_scores["Next.js"] = 0.85
            
            if 'React' in repo_data.get('description', '') or \
               'react' in repo_data.get('name', '').lower():
                frameworks.append("React")
                confidence_scores["React"] = 0.8
        
        if 'Python' in languages:
            # Check for Python frameworks
            if 'Django' in repo_data.get('description', '') or \
               'django' in repo_data.get('name', '').lower():
                frameworks.append("Django")
                confidence_scores["Django"] = 0.8
            
            if 'Flask' in repo_data.get('description', '') or \
               'flask' in repo_data.get('name', '').lower():
                frameworks.append("Flask")
                confidence_scores["Flask"] = 0.8
            
            if 'FastAPI' in repo_data.get('description', '') or \
               'fastapi' in repo_data.get('name', '').lower():
                frameworks.append("FastAPI")
                confidence_scores["FastAPI"] = 0.8
        
        if 'PHP' in languages:
            if 'Laravel' in repo_data.get('description', '') or \
               'laravel' in repo_data.get('name', '').lower():
                frameworks.append("Laravel")
                confidence_scores["Laravel"] = 0.8
            
            if 'WordPress' in repo_data.get('description', '') or \
               'wordpress' in repo_data.get('name', '').lower():
                cms.append("WordPress")
                confidence_scores["WordPress"] = 0.85
        
        return StackInference(
            frameworks=list(set(frameworks)),
            languages=list(set(languages_list)),
            cms=list(set(cms)),
            analytics=list(set(analytics)),
            confidence_scores=confidence_scores
        )

    def _detect_systems_from_github_data(
        self,
        repo_data: Dict[str, Any]
    ) -> List[DetectedSystem]:
        """
        Detect systems from GitHub repository data.
        
        Args:
            repo_data: Repository data from GitHub API
            
        Returns:
            List of detected systems
        """
        systems = []
        
        # Check topics for system hints
        topics = repo_data.get('topics', [])
        
        # E-commerce
        ecommerce_keywords = ['ecommerce', 'shop', 'store', 'woocommerce', 'shopify', 'magento']
        if any(kw in [t.lower() for t in topics] for kw in ecommerce_keywords):
            systems.append(DetectedSystem(
                system_type="ecommerce",
                name="E-commerce Platform",
                confidence=0.7,
                evidence=[
                    Evidence(
                        type="topic",
                        value=next((t for t in topics if any(kw in t.lower() for kw in ecommerce_keywords)), ""),
                        location="repository",
                        confidence=0.7
                    )
                ]
            ))
        
        # CMS
        cms_keywords = ['cms', 'content-management', 'wordpress', 'django-cms']
        if any(kw in [t.lower() for t in topics] for kw in cms_keywords):
            systems.append(DetectedSystem(
                system_type="CMS",
                name="Content Management System",
                confidence=0.7,
                evidence=[
                    Evidence(
                        type="topic",
                        value=next((t for t in topics if any(kw in t.lower() for kw in cms_keywords)), ""),
                        location="repository",
                        confidence=0.7
                    )
                ]
            ))
        
        # Analytics
        analytics_keywords = ['analytics', 'tracking', 'metrics']
        if any(kw in [t.lower() for t in topics] for kw in analytics_keywords):
            systems.append(DetectedSystem(
                system_type="analytics",
                name="Analytics System",
                confidence=0.7,
                evidence=[
                    Evidence(
                        type="topic",
                        value=next((t for t in topics if any(kw in t.lower() for kw in analytics_keywords)), ""),
                        location="repository",
                        confidence=0.7
                    )
                ]
            ))
        
        return systems

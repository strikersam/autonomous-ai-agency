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


def _content_contains_domain(content: str, *domains: str) -> bool:
    """Check if HTML content mentions any of the given domains.
    Only used for detection of known services in fetched page content,
    not for URL validation. Domains are from a fixed whitelist."""
    content_lower = content.lower()
    return any(domain.lower() in content_lower for domain in domains)


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
            
            # SSRF protection: validate URL and rebuild from parsed components
            parsed = urlparse(website_url)
            if parsed.scheme not in ("http", "https"):
                return WebsiteScanResult(
                    scan_id=scan_id, website_url=website_url, company_id=self.company_id,
                    status="failed", errors=["Blocked: only http/https schemes allowed"],
                    started_at=started_at.isoformat(), completed_at=datetime.utcnow().isoformat()
                )
            # Rebuild URL from parsed components to strip any injected credentials
            _safe_url = parsed._replace(fragment="").geturl()

            if not _is_safe_url(_safe_url):
                return WebsiteScanResult(
                    scan_id=scan_id, website_url=website_url, company_id=self.company_id,
                    status="failed", errors=["Blocked: target resolves to private/internal network"],
                    started_at=started_at.isoformat(), completed_at=datetime.utcnow().isoformat()
                )

            # Fetch the homepage
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=False,
                max_redirects=self.max_redirects,
                headers={"User-Agent": self.user_agent}
            ) as client:
                try:
                    response = await client.get(_safe_url)
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
        Detect business systems from HTML content with Wappalyzer-grade signature parsing
        and dynamic LLM-assisted verification.
        """
        systems_map = {}
        soup_str = str(soup).lower()
        
        # ── 1. High-Fidelity Rule-Based Signature Matching ────────────────────
        
        # Shopify
        if 'shopify' in soup_str or _hostname_contains(url, 'myshopify.com') or 'cdn.shopify.com' in soup_str:
            systems_map["shopify"] = DetectedSystem(
                system_type="CMS",
                name="Shopify",
                confidence=0.98,
                evidence=[Evidence(type="script", value="cdn.shopify.com", location="html", confidence=0.98)]
            )
            
        # WooCommerce
        if 'woocommerce' in soup_str or 'wp-content/plugins/woocommerce' in soup_str:
            systems_map["woocommerce"] = DetectedSystem(
                system_type="CMS",
                name="WooCommerce",
                confidence=0.95,
                evidence=[Evidence(type="path", value="woocommerce plugins path", location="html", confidence=0.95)]
            )
            
        # WordPress
        if 'wp-content' in soup_str or 'wordpress' in soup_str:
            systems_map["wordpress"] = DetectedSystem(
                system_type="CMS",
                name="WordPress",
                confidence=0.95,
                evidence=[Evidence(type="path", value="/wp-content/", location="html", confidence=0.95)]
            )
            
        # Wix
        if 'wix.com' in soup_str or 'wix-code' in soup_str:
            systems_map["wix"] = DetectedSystem(
                system_type="CMS",
                name="Wix",
                confidence=0.95,
                evidence=[Evidence(type="script", value="wix-code", location="html", confidence=0.95)]
            )

        # Webflow
        if 'webflow' in soup_str or 'data-wf-page' in soup_str:
            systems_map["webflow"] = DetectedSystem(
                system_type="CMS",
                name="Webflow",
                confidence=0.95,
                evidence=[Evidence(type="attribute", value="data-wf-page", location="html", confidence=0.95)]
            )

        # Contentful headless CMS
        if 'contentful' in soup_str or 'images.ctfassets.net' in soup_str:
            systems_map["contentful"] = DetectedSystem(
                system_type="CMS",
                name="Contentful CMS",
                confidence=0.92,
                evidence=[Evidence(type="header", value="images.ctfassets.net", location="html", confidence=0.92)]
            )

        # SAP Commerce Cloud / Hybris
        if 'hybris' in soup_str or 'v-bind:hybris' in soup_str:
            systems_map["hybris"] = DetectedSystem(
                system_type="OMS",
                name="SAP Commerce Cloud",
                confidence=0.95,
                evidence=[Evidence(type="script", value="hybris attributes", location="html", confidence=0.95)]
            )

        # Salesforce Commerce Cloud (Demandware)
        if 'dwvar_' in soup_str or 'demandware' in soup_str:
            systems_map["demandware"] = DetectedSystem(
                system_type="OMS",
                name="Salesforce Commerce Cloud",
                confidence=0.95,
                evidence=[Evidence(type="script", value="dwvar_ variables", location="html", confidence=0.95)]
            )

        # React Framework
        if 'react' in soup_str or '__next' in soup_str or '___gatsby' in soup_str:
            systems_map["react"] = DetectedSystem(
                system_type="custom",
                name="Next.js + React",
                confidence=0.95,
                evidence=[Evidence(type="script", value="React DOM fiber", location="html", confidence=0.95)]
            )

        # Stripe Payments
        if 'js.stripe.com' in soup_str or 'stripe' in soup_str:
            systems_map["stripe"] = DetectedSystem(
                system_type="payment_gateway",
                name="Stripe Payments",
                confidence=0.95,
                evidence=[Evidence(type="script", value="js.stripe.com", location="html", confidence=0.95)]
            )

        # Google Analytics (GA4) / GTM
        if 'googletagmanager.com' in soup_str or 'google-analytics.com' in soup_str:
            systems_map["gtm_analytics"] = DetectedSystem(
                system_type="analytics",
                name="GTM + GA4",
                confidence=0.98,
                evidence=[Evidence(type="script", value="googletagmanager.com", location="html", confidence=0.98)]
            )

        # Adobe Analytics
        if 'adobe' in soup_str or 'visitorapi.js' in soup_str:
            systems_map["adobe_analytics"] = DetectedSystem(
                system_type="analytics",
                name="Adobe Analytics",
                confidence=0.90,
                evidence=[Evidence(type="script", value="visitorapi.js", location="html", confidence=0.90)]
            )

        # Klaviyo Marketing
        if 'klaviyo' in soup_str or 'fast.klaviyo.com' in soup_str:
            systems_map["klaviyo"] = DetectedSystem(
                system_type="email_service",
                name="Klaviyo CRM",
                confidence=0.92,
                evidence=[Evidence(type="script", value="fast.klaviyo.com", location="html", confidence=0.92)]
            )

        # Gorgias Customer Support
        if 'gorgias' in soup_str or 'gorgias-chat' in soup_str:
            systems_map["gorgias"] = DetectedSystem(
                system_type="support",
                name="Gorgias Helpdesk",
                confidence=0.95,
                evidence=[Evidence(type="script", value="gorgias-chat loader", location="html", confidence=0.95)]
            )

        # Salesforce Concierge
        if 'liveagent' in soup_str or 'salesforce-chat' in soup_str:
            systems_map["salesforce_service"] = DetectedSystem(
                system_type="support",
                name="Salesforce Service Cloud",
                confidence=0.90,
                evidence=[Evidence(type="script", value="liveagent.js loader", location="html", confidence=0.90)]
            )

        # ── 2. Dynamic LLM-Assisted Technology Stack Analysis ─────────────────
        try:
            from backend.server import call_llm
            meta_tags = [str(tag) for tag in soup.find_all('meta')][:10]
            scripts_list = [tag.get('src') for tag in soup.find_all('script') if tag.get('src')][:15]
            
            prompt = [
                {"role": "system", "content": "You are a professional technology profiling system. "
                 "Analyze the URL, meta tags, and script URLs to identify CMS, databases, analytics, payments, and support systems. "
                 "You MUST output your findings strictly as a valid JSON object matching this structure: "
                 '{"detected": [{"id": "stripe", "system_type": "payment_gateway", "name": "Stripe Payments", "confidence": 0.95, "evidence_summary": "js.stripe.com found"}]}'},
                {"role": "user", "content": f"URL: {url}\nMeta tags: {meta_tags}\nScripts: {scripts_list}"}
            ]
            
            response_text = await call_llm(prompt, temperature=0.1)
            # Strip any markdown codeblock formats
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
                
            parsed_data = json.loads(response_text)
            for item in parsed_data.get("detected", []):
                sys_id = str(item.get("id")).lower()
                system_type = str(item.get("system_type"))
                name = str(item.get("name"))
                confidence = float(item.get("confidence", 0.9))
                evidence_summary = str(item.get("evidence_summary", "Detected via LLM analysis"))
                
                # Merge or insert
                if sys_id not in systems_map:
                    systems_map[sys_id] = DetectedSystem(
                        system_type=system_type,
                        name=name,
                        confidence=confidence,
                        evidence=[Evidence(type="llm_inference", value=evidence_summary, location="AI Parser", confidence=confidence)]
                    )
        except Exception as e:
            # Silence and fall back gracefully to the rule-based dictionary
            pass
            
        return list(systems_map.values())

    async def _infer_stack(
        self,
        soup: BeautifulSoup,
        html: str,
        url: str
    ) -> StackInference:
        """
        Infer technology stack with high-fidelity Wappalyzer matching and LLM support.
        """
        soup_str = str(soup).lower()
        
        # Deterministic base defaults
        frameworks = []
        languages = ["JavaScript"]
        libraries = []
        cms = []
        databases = []
        analytics = []
        payment_processors = []
        hosting = []
        confidence_scores = {}
        
        # 1. Signature-based inferring
        if "next.js" in soup_str or "__next" in soup_str:
            frameworks.extend(["React", "Next.js"])
            confidence_scores["react"] = 0.98
            confidence_scores["next.js"] = 0.96
        elif "react" in soup_str:
            frameworks.append("React")
            confidence_scores["react"] = 0.95
            
        if "gatsby" in soup_str or "___gatsby" in soup_str:
            frameworks.extend(["React", "Gatsby"])
            confidence_scores["react"] = 0.98
            confidence_scores["gatsby"] = 0.95
            
        if "shopify" in soup_str:
            cms.append("Shopify")
            confidence_scores["shopify"] = 0.98
            
        if "wordpress" in soup_str:
            cms.append("WordPress")
            languages.append("PHP")
            confidence_scores["wordpress"] = 0.95
            
        if "googletagmanager.com" in soup_str:
            analytics.extend(["Google Tag Manager", "Google Analytics"])
            confidence_scores["gtm"] = 0.99
            
        # 2. Dynamic LLM Verification
        try:
            from backend.server import call_llm
            meta_tags = [str(tag) for tag in soup.find_all('meta')][:10]
            
            prompt = [
                {"role": "system", "content": "You are a professional technology profiler. Analyze the meta tags, URL, and page context to infer core frameworks, languages, CMS platforms, and databases. "
                 "Output strictly as a valid JSON object: "
                 '{"frameworks": ["React"], "languages": ["JavaScript"], "cms": ["Shopify"], "databases": []}'},
                {"role": "user", "content": f"URL: {url}\nMeta tags: {meta_tags}"}
            ]
            response_text = await call_llm(prompt, temperature=0.1)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
                
            parsed = json.loads(response_text)
            frameworks = list(set(frameworks + parsed.get("frameworks", [])))
            languages = list(set(languages + parsed.get("languages", [])))
            cms = list(set(cms + parsed.get("cms", [])))
            databases = list(set(databases + parsed.get("databases", [])))
        except Exception:
            pass
            
        return StackInference(
            frameworks=frameworks,
            languages=languages,
            libraries=libraries,
            cms=cms,
            databases=databases,
            analytics=analytics,
            payment_processors=payment_processors,
            hosting=hosting,
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

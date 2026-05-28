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
    Advanced Scanner for detecting technology stack and systems from websites.
    
    Capabilities:
    - Data-driven signature matching (like BuiltWith/Wappalyzer) via `technologies.json`.
    - BuiltWith-level DNS analysis (MX, NS, TXT) for email, hosting, marketing, and security platforms.
    - Deep HTML, Header, and Cookie analysis for CMS, frameworks, analytics, and CDNs.
    - Anti-bot evasion using curl_cffi.
    """

    def __init__(self, company_id: Optional[str] = None):
        import json
        import os
        self.company_id = company_id
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        self.timeout = 15.0
        self.max_redirects = 5
        
        # Load builtwith-style JSON database
        tech_path = os.path.join(os.path.dirname(__file__), 'technologies.json')
        if os.path.exists(tech_path):
            with open(tech_path, 'r') as f:
                self.tech_data = json.load(f)
        else:
            self.tech_data = {"categories": {}, "apps": {}}

    async def scan_website(
        self,
        website_url: str,
        scan_depth: str = "standard",
        include_sitemap: bool = True,
        max_pages: int = 20
    ) -> WebsiteScanResult:
        import dns.resolver
        scan_id = f"scan_{secrets.token_hex(8)}"
        started_at = datetime.utcnow()
        
        try:
            if not website_url.startswith(("http://", "https://")):
                website_url = f"https://{website_url}"
            
            parsed = urlparse(website_url)
            if parsed.scheme not in ("http", "https"):
                return WebsiteScanResult(
                    scan_id=scan_id, website_url=website_url, company_id=self.company_id,
                    status="failed", errors=["Blocked: only http/https schemes allowed"],
                    started_at=started_at.isoformat(), completed_at=datetime.utcnow().isoformat()
                )
            
            _safe_url = parsed._replace(fragment="").geturl()
            domain = parsed.hostname.replace('www.', '') if parsed.hostname else ""

            # 1. DNS Analysis (BuiltWith-level off-site detection)
            dns_systems = self._analyze_dns(domain)

            # 2. On-Site Analysis
            html = ""
            headers = {}
            cookies = {}
            status_code = 0
            
            try:
                import curl_cffi.requests
                async with curl_cffi.requests.AsyncSession(impersonate="chrome120", timeout=self.timeout) as client:
                    response = await client.get(_safe_url, allow_redirects=True)
                    html = response.text
                    headers = response.headers
                    cookies = response.cookies
                    status_code = response.status_code
            except Exception as curl_e:
                log.warning(f"curl_cffi failed, falling back to httpx: {curl_e}")
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=True,
                    max_redirects=self.max_redirects,
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                    }
                ) as client:
                    try:
                        response = await client.get(_safe_url)
                        html = response.text
                        headers = response.headers
                        cookies = response.cookies
                        status_code = response.status_code
                    except Exception as e:
                        log.error(f"HTTPX failed: {e}")

            soup = BeautifulSoup(html, 'html.parser') if html else BeautifulSoup("", 'html.parser')
            
            # Use dynamic BuiltWith-style identification logic
            html_systems = self._detect_systems_generic(html, headers, cookies)
            
            # Merge DNS systems and HTML systems, keeping highest confidence
            all_systems_map = {sys.name: sys for sys in html_systems}
            for dns_sys in dns_systems:
                if dns_sys.name in all_systems_map:
                    if dns_sys.confidence > all_systems_map[dns_sys.name].confidence:
                        all_systems_map[dns_sys.name] = dns_sys
                else:
                    all_systems_map[dns_sys.name] = dns_sys
                    
            detected_systems = list(all_systems_map.values())
            
            stack_inference = await self._infer_stack(soup, html, headers, website_url)
            
            # 3. Sitemap discovery
            sitemap_urls = []
            if include_sitemap and html and status_code < 400:
                sitemap_urls = await self._discover_sitemap(soup, website_url)
            
            pages_scanned = 1 + len(sitemap_urls) if sitemap_urls else 1
            completed_at = datetime.utcnow()
            
            return WebsiteScanResult(
                scan_id=scan_id, website_url=website_url, company_id=self.company_id, status="success",
                inferred_stack=stack_inference, detected_systems=detected_systems, pages_scanned=pages_scanned,
                sitemap_urls=sitemap_urls, started_at=started_at.isoformat(), completed_at=completed_at.isoformat()
            )
                
        except Exception as e:
            log.error(f"Error scanning website {website_url}: {e}")
            return WebsiteScanResult(
                scan_id=scan_id, website_url=website_url, company_id=self.company_id, status="failed",
                errors=[str(e)], started_at=started_at.isoformat(), completed_at=datetime.utcnow().isoformat()
            )

    def _analyze_dns(self, domain: str) -> List[DetectedSystem]:
        import dns.resolver
        systems = []
        
        if not domain:
            return systems
            
        def add_sys(sys_id, sys_type, name, conf, ev_type, ev_val):
            systems.append(DetectedSystem(
                system_type=sys_type, name=name, confidence=conf,
                evidence=[Evidence(type=ev_type, value=ev_val, location="DNS", confidence=conf)]
            ))

        try:
            # 1. MX Records
            try:
                for rdata in dns.resolver.resolve(domain, 'MX'):
                    mx = str(rdata.exchange).lower()
                    if 'google.com' in mx or 'googlemail.com' in mx: add_sys('gsuite', 'custom', 'Google Workspace', 0.99, 'MX', mx)
                    if 'outlook.com' in mx or 'protection.outlook.com' in mx: add_sys('office365', 'custom', 'Microsoft 365', 0.99, 'MX', mx)
                    if 'pphosted.com' in mx: add_sys('proofpoint', 'custom', 'Proofpoint Email Security', 0.99, 'MX', mx)
                    if 'mimecast.com' in mx: add_sys('mimecast', 'custom', 'Mimecast', 0.99, 'MX', mx)
                    if 'zendesk.com' in mx: add_sys('zendesk', 'support', 'Zendesk', 0.99, 'MX', mx)
            except Exception: pass
            
            # 2. NS Records
            try:
                for rdata in dns.resolver.resolve(domain, 'NS'):
                    ns = str(rdata.target).lower()
                    if 'cloudflare.com' in ns: add_sys('cloudflare', 'custom', 'Cloudflare DNS', 0.99, 'NS', ns)
                    if 'awsdns' in ns: add_sys('route53', 'custom', 'AWS Route 53', 0.99, 'NS', ns)
                    if 'akam.net' in ns or 'akamai' in ns: add_sys('akamai', 'custom', 'Akamai', 0.99, 'NS', ns)
                    if 'ultradns' in ns: add_sys('ultradns', 'custom', 'UltraDNS', 0.99, 'NS', ns)
                    if 'fastly' in ns: add_sys('fastly', 'custom', 'Fastly', 0.99, 'NS', ns)
            except Exception: pass

            # 3. TXT Records
            try:
                for rdata in dns.resolver.resolve(domain, 'TXT'):
                    txt = str(rdata).lower()
                    if 'spf.protection.outlook.com' in txt: add_sys('office365', 'custom', 'Microsoft 365', 0.99, 'TXT SPF', txt)
                    if '_spf.google.com' in txt: add_sys('gsuite', 'custom', 'Google Workspace', 0.99, 'TXT SPF', txt)
                    if 'spf.mailjet.com' in txt: add_sys('mailjet', 'email_service', 'Mailjet', 0.99, 'TXT SPF', txt)
                    if 'sendgrid.net' in txt: add_sys('sendgrid', 'email_service', 'SendGrid', 0.99, 'TXT SPF', txt)
                    if '_spf.salesforce.com' in txt: add_sys('salesforce', 'CRM', 'Salesforce', 0.99, 'TXT SPF', txt)
                    if 'mailgun.org' in txt: add_sys('mailgun', 'email_service', 'Mailgun', 0.99, 'TXT SPF', txt)
                    if 'amazonses' in txt: add_sys('aws_ses', 'email_service', 'Amazon SES', 0.99, 'TXT', txt)
                    
                    if 'google-site-verification' in txt: add_sys('google_search_console', 'analytics', 'Google Search Console', 0.99, 'TXT', txt)
                    if 'facebook-domain-verification' in txt: add_sys('facebook_business', 'marketing_automation', 'Facebook Business', 0.99, 'TXT', txt)
                    if 'apple-domain-verification' in txt: add_sys('apple_pay', 'payment_gateway', 'Apple Pay / Merchant', 0.95, 'TXT', txt)
                    if 'stripe-verification' in txt: add_sys('stripe', 'payment_gateway', 'Stripe', 0.99, 'TXT', txt)
                    if 'docusign' in txt: add_sys('docusign', 'custom', 'DocuSign', 0.99, 'TXT', txt)
                    if 'atlassian' in txt: add_sys('atlassian', 'custom', 'Atlassian', 0.99, 'TXT', txt)
                    if 'mixpanel' in txt: add_sys('mixpanel', 'analytics', 'Mixpanel', 0.99, 'TXT', txt)
                    if 'onetrust' in txt: add_sys('onetrust', 'custom', 'OneTrust', 0.99, 'TXT', txt)
                    if 'dynatrace' in txt: add_sys('dynatrace', 'analytics', 'Dynatrace', 0.99, 'TXT', txt)
                    if 'twilio' in txt: add_sys('twilio', 'custom', 'Twilio', 0.99, 'TXT', txt)
                    if 'notion_verify' in txt: add_sys('notion', 'custom', 'Notion', 0.99, 'TXT', txt)
                    if 'jamf-site' in txt: add_sys('jamf', 'custom', 'Jamf', 0.99, 'TXT', txt)
                    if 'paloaltonetworks' in txt: add_sys('paloalto', 'custom', 'Palo Alto Networks', 0.99, 'TXT', txt)
                    if 'elevenlabs' in txt: add_sys('elevenlabs', 'ai_ml', 'ElevenLabs', 0.99, 'TXT', txt)
                    if 'anthropic' in txt: add_sys('anthropic', 'ai_ml', 'Anthropic', 0.99, 'TXT', txt)
                    if 'openai' in txt: add_sys('openai', 'ai_ml', 'OpenAI', 0.99, 'TXT', txt)
                    if 'miro-verification' in txt: add_sys('miro', 'custom', 'Miro', 0.99, 'TXT', txt)
                    if 'loom-verification' in txt: add_sys('loom', 'custom', 'Loom', 0.99, 'TXT', txt)
                    if 'cursor-domain' in txt: add_sys('cursor', 'ai_ml', 'Cursor', 0.99, 'TXT', txt)
            except Exception: pass
            
        except Exception as e:
            log.warning(f"DNS analysis failed for {domain}: {e}")
            
        return systems

    def _detect_systems_generic(self, html: str, headers: Any, cookies: Any) -> List[DetectedSystem]:
        """
        Replicates builtwith.builtwith() data-driven logic natively using the
        technologies.json database to avoid hanging on large minified JS files.
        """
        import re
        
        systems_map = {}
        headers_dict = {str(k).lower(): str(v).lower() for k, v in dict(headers).items()}
        cookies_dict = {str(k).lower(): str(v).lower() for k, v in dict(cookies).items()}
        
        # Limit html size to prevent catastrophic backtracking on minified bundles
        html_safe = html[:100000].lower() if html else ""
        
        # Extract meta tags once
        metas = {}
        if html_safe:
            meta_pattern = re.compile(r'<meta[^>]*?name=[\'\"]([^>]*?)[\'\"][^>]*?content=[\'\"]([^>]*?)[\'\"][^>]*?>', re.IGNORECASE)
            metas = dict(meta_pattern.findall(html_safe))

        def add_sys(app_name, app_spec, conf, ev_type, ev_val):
            # Resolve category type
            cat_id = str(app_spec.get("cats", [1])[0])
            cat_name = self.tech_data.get("categories", {}).get(cat_id, "custom")
            
            # Map common category names to SystemType literals
            valid_types = ['CMS', 'CRM', 'OMS', 'PIM', 'DAM', 'ERP', 'HRM', 'LMS', 'analytics', 'payment_gateway', 'shipping', 'tax', 'inventory', 'marketing_automation', 'email_service', 'search', 'database', 'cache', 'cdc', 'message_queue', 'api_gateway', 'auth', 'billing', 'support', 'chat', 'video', 'voice', 'iot', 'ai_ml', 'custom']
            sys_type = cat_name if cat_name in valid_types else "custom"
            
            if app_name not in systems_map or systems_map[app_name].confidence < conf:
                systems_map[app_name] = DetectedSystem(
                    system_type=sys_type, name=app_name, confidence=conf,
                    evidence=[Evidence(type=ev_type, value=ev_val, location="HTML/HTTP", confidence=conf)]
                )

        apps = self.tech_data.get("apps", {})
        for app_name, app_spec in apps.items():
            matched = False
            
            # 1. Check Headers
            if 'headers' in app_spec:
                for h_name, h_regex in app_spec['headers'].items():
                    h_val = headers_dict.get(h_name.lower())
                    if h_val and re.search(h_regex.split(';')[0], h_val, re.IGNORECASE):
                        add_sys(app_name, app_spec, 0.95, 'header', h_val)
                        matched = True
            
            # 2. Check Cookies
            if not matched and 'cookies' in app_spec:
                for c_name, c_regex in app_spec['cookies'].items():
                    c_val = cookies_dict.get(c_name.lower())
                    if c_val and re.search(c_regex.split(';')[0], c_val, re.IGNORECASE):
                        add_sys(app_name, app_spec, 0.95, 'cookie', c_name)
                        matched = True
                        
            # 3. Check HTML (includes scripts)
            if not matched and 'html' in app_spec and html_safe:
                patterns = app_spec['html']
                if not isinstance(patterns, list):
                    patterns = [patterns]
                for pattern in patterns:
                    try:
                        if re.search(pattern.split(';')[0], html_safe, re.IGNORECASE):
                            add_sys(app_name, app_spec, 0.90, 'html', pattern)
                            matched = True
                            break
                    except re.error:
                        pass
                        
            # 4. Check Meta tags
            if not matched and 'meta' in app_spec and metas:
                for m_name, m_regex in app_spec['meta'].items():
                    m_val = metas.get(m_name)
                    if m_val and re.search(m_regex.split(';')[0], m_val, re.IGNORECASE):
                        add_sys(app_name, app_spec, 0.95, 'meta', m_name)
                        matched = True
                        break

        # Process implies logic recursively
        new_additions = {}
        for app_name, sys in systems_map.items():
            implies = apps.get(app_name, {}).get("implies", [])
            if not isinstance(implies, list):
                implies = [implies]
            for implied_app in implies:
                if implied_app not in systems_map and implied_app in apps:
                    new_additions[implied_app] = DetectedSystem(
                        system_type="custom", name=implied_app, confidence=0.85,
                        evidence=[Evidence(type="implies", value=app_name, location="Dependency", confidence=0.85)]
                    )
        
        systems_map.update(new_additions)
        return list(systems_map.values())

    async def _infer_stack(self, soup: BeautifulSoup, html: str, headers: Any, url: str) -> StackInference:
        html_lower = html.lower() if html else ""
        headers_dict = {str(k).lower(): str(v).lower() for k, v in dict(headers).items()}
        
        frameworks, languages, libraries, cms, databases, analytics, payment, hosting, ci_cd, infrastructure = [], [], [], [], [], [], [], [], [], []
        conf = {}
        
        def add_stack(category, item, score=0.9):
            if item not in category:
                category.append(item)
                conf[item.lower()] = max(conf.get(item.lower(), 0), score)

        if 'react' in html_lower or '__next' in html_lower:
            add_stack(frameworks, 'React')
            add_stack(languages, 'JavaScript')
            if '__next' in html_lower or 'x-nextjs-page' in headers_dict:
                add_stack(frameworks, 'Next.js')
        if 'vue' in html_lower or '__nuxt' in html_lower:
            add_stack(frameworks, 'Vue.js')
            add_stack(languages, 'JavaScript')
            if '__nuxt' in html_lower:
                add_stack(frameworks, 'Nuxt.js')
        if 'angular' in html_lower or 'ng-version' in html_lower:
            add_stack(frameworks, 'Angular')
            add_stack(languages, 'TypeScript')
        
        if 'wordpress' in html_lower or 'wp-content' in html_lower:
            add_stack(cms, 'WordPress')
            add_stack(languages, 'PHP')
            add_stack(databases, 'MySQL')
        if 'shopify' in html_lower:
            add_stack(cms, 'Shopify')
            add_stack(languages, 'Ruby')
        if 'demandware' in html_lower:
            add_stack(cms, 'Salesforce Commerce Cloud')
            
        if 'x-powered-by' in headers_dict:
            pb = headers_dict['x-powered-by']
            if 'php' in pb: add_stack(languages, 'PHP')
            if 'express' in pb: add_stack(frameworks, 'Express'); add_stack(languages, 'JavaScript')
            if 'next.js' in pb: add_stack(frameworks, 'Next.js'); add_stack(frameworks, 'React')
            if 'asp.net' in pb: add_stack(languages, 'C#')
        
        if 'vercel' in headers_dict.get('server', '') or 'x-vercel-id' in headers_dict: add_stack(hosting, 'Vercel')
        if 'netlify' in headers_dict.get('server', '') or 'x-nf-request-id' in headers_dict: add_stack(hosting, 'Netlify')
        if 'fly.io' in headers_dict.get('server', ''): add_stack(hosting, 'Fly.io')
        if 'x-amz-cf-id' in headers_dict: add_stack(hosting, 'AWS'); add_stack(infrastructure, 'AWS CloudFront')
        if 'cloudflare' in headers_dict.get('server', ''): add_stack(infrastructure, 'Cloudflare')
        if 'akamai' in headers_dict.get('server', '') or 'x-cache' in headers_dict: add_stack(infrastructure, 'Akamai')
            
        return StackInference(
            frameworks=frameworks, languages=languages, libraries=libraries,
            cms=cms, databases=databases, analytics=analytics, payment_processors=payment,
            hosting=hosting, ci_cd=ci_cd, infrastructure=infrastructure, confidence_scores=conf
        )

    async def _discover_sitemap(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        # Using a fast httpx fallback just for quick sitemaps
        sitemap_urls = []
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                robots_url = f"{base_url.rstrip('/')}/robots.txt"
                response = await client.get(robots_url)
                if response.status_code == 200:
                    for line in response.text.split('\n'):
                        if 'sitemap:' in line.lower():
                            u = line.split(':', 1)[1].strip()
                            if u: sitemap_urls.append(u)
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

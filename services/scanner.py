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
import asyncio
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


# Maps BuiltWith/Wappalyzer category slugs to this codebase's SystemType literal.
# Anything not listed falls back to "custom" (a valid SystemType).
_BUILTWITH_CATEGORY_MAP: Dict[str, str] = {
    "cms": "CMS",
    "ecommerce": "CMS",
    "blogs": "CMS",
    "wikis": "CMS",
    "message-boards": "CMS",
    "analytics": "analytics",
    "payment-processors": "payment_gateway",
    "databases": "database",
    "cache-tools": "cache",
    "search-engines": "search",
    "marketing-automation": "marketing_automation",
    "video-players": "video",
}


class WebsiteScanner:
    """
    Advanced Scanner for detecting technology stack and systems from websites.
    
    Capabilities:
    - BuiltWith-level DNS analysis (MX, NS, TXT) for email, hosting, marketing, and security platforms.
    - Deep HTML, Header, and Cookie analysis for CMS, frameworks, analytics, and CDNs.
    - Anti-bot evasion using modern headers.
    """

    def __init__(self, company_id: Optional[str] = None):
        self.company_id = company_id
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        self.timeout = 15.0
        self.max_redirects = 5

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

            # SSRF guard: block loopback/link-local/private/reserved targets (and any
            # host that resolves to one) before performing any DNS or HTTP work.
            if not _is_safe_url(_safe_url):
                return WebsiteScanResult(
                    scan_id=scan_id, website_url=website_url, company_id=self.company_id,
                    status="failed",
                    errors=["Blocked: URL resolves to a private, loopback, or disallowed address"],
                    started_at=started_at.isoformat(), completed_at=datetime.utcnow().isoformat()
                )

            domain = parsed.hostname.replace('www.', '') if parsed.hostname else ""

            # 1. DNS Analysis (BuiltWith-level off-site detection)
            dns_systems = self._analyze_dns(domain)

            # 2. On-Site Analysis
            html = ""
            headers = {}
            cookies = {}
            status_code = 0
            fetch_error: Optional[str] = None

            # Redirects are disabled so a public URL cannot bounce the request to an
            # internal/link-local address that bypasses the SSRF check above.
            try:
                import curl_cffi.requests
                async with curl_cffi.requests.AsyncSession(impersonate="chrome120", timeout=self.timeout) as client:
                    response = await client.get(_safe_url, allow_redirects=False)
                    html = response.text
                    headers = response.headers
                    cookies = response.cookies
                    status_code = response.status_code
            except Exception as curl_e:
                log.warning(f"curl_cffi failed, falling back to httpx: {curl_e}")
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=False,
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
                        fetch_error = str(e)
                        log.error(f"HTTPX failed: {e}")

            # If both the primary (curl_cffi) and fallback (httpx) clients failed to
            # reach the host, surface the failure instead of returning a spurious
            # "success" with empty evidence — callers only reject non-success scans.
            if fetch_error is not None and not html:
                return WebsiteScanResult(
                    scan_id=scan_id, website_url=website_url, company_id=self.company_id,
                    status="failed",
                    errors=[f"Failed to fetch website: {fetch_error}"],
                    started_at=started_at.isoformat(), completed_at=datetime.utcnow().isoformat()
                )

            # Even if we get a 403, we still analyze headers and DNS!
            soup = BeautifulSoup(html, 'html.parser') if html else BeautifulSoup("", 'html.parser')
            
            # Combine detected systems from HTML/header heuristics, DNS records, and
            # the bundled BuiltWith/Wappalyzer signature database. For a given system
            # name the highest-confidence detection wins; ties keep the earlier source
            # (HTML > DNS > BuiltWith).
            html_systems = await self._detect_systems(soup, html, headers, cookies, website_url)
            builtwith_systems = await self._detect_with_builtwith(html, headers, _safe_url)

            all_systems_map: Dict[str, DetectedSystem] = {}
            for sys in [*html_systems, *dns_systems, *builtwith_systems]:
                existing = all_systems_map.get(sys.name)
                if existing is None or sys.confidence > existing.confidence:
                    all_systems_map[sys.name] = sys

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

    async def _detect_systems(self, soup: BeautifulSoup, html: str, headers: Any, cookies: Any, url: str) -> List[DetectedSystem]:
        import json
        systems_map = {}
        html_lower = html.lower()
        headers_dict = {str(k).lower(): str(v).lower() for k, v in dict(headers).items()}
        cookies_dict = {str(k).lower(): str(v).lower() for k, v in dict(cookies).items()}
        
        def add_system(sys_id, sys_type, name, conf, ev_type, ev_val, ev_loc):
            if sys_id not in systems_map or systems_map[sys_id].confidence < conf:
                systems_map[sys_id] = DetectedSystem(
                    system_type=sys_type, name=name, confidence=conf,
                    evidence=[Evidence(type=ev_type, value=ev_val, location=ev_loc, confidence=conf)]
                )

        # SERVERS & INFRASTRUCTURE
        server_header = headers_dict.get('server', '')
        if 'nginx' in server_header: add_system('nginx', 'custom', 'Nginx', 0.99, 'header', server_header, 'Server')
        if 'apache' in server_header: add_system('apache', 'custom', 'Apache HTTP Server', 0.99, 'header', server_header, 'Server')
        if 'cloudflare' in server_header or '__cf_bm' in cookies_dict or 'cf-ray' in headers_dict:
            add_system('cloudflare', 'custom', 'Cloudflare', 0.99, 'header/cookie', 'cloudflare evidence', 'HTTP')
        if 'akamai' in headers_dict.get('x-cache', '') or 'akamai' in server_header or 'akamai' in headers_dict:
            add_system('akamai', 'custom', 'Akamai CDN', 0.95, 'header', 'akamai evidence', 'HTTP')
        if 'varnish' in headers_dict.get('x-varnish', '') or 'varnish' in headers_dict.get('via', ''):
            add_system('varnish', 'custom', 'Varnish Cache', 0.95, 'header', 'varnish evidence', 'HTTP')
        if 'x-amz-cf-id' in headers_dict: add_system('aws_cloudfront', 'custom', 'AWS CloudFront', 0.95, 'header', 'x-amz-*', 'HTTP')
        if 'fly.io' in server_header: add_system('flyio', 'custom', 'Fly.io', 0.99, 'header', server_header, 'Server')
        if 'vercel' in server_header or 'x-vercel-id' in headers_dict: add_system('vercel', 'custom', 'Vercel', 0.99, 'header', 'vercel headers', 'HTTP')
        if 'netlify' in server_header or 'x-nf-request-id' in headers_dict: add_system('netlify', 'custom', 'Netlify', 0.99, 'header', 'netlify headers', 'HTTP')

        # CMS & ECOMMERCE
        if 'shopify' in html_lower or 'cdn.shopify.com' in html_lower or '_shopify_s' in cookies_dict or 'x-shopify-stage' in headers_dict:
            add_system('shopify', 'CMS', 'Shopify', 0.99, 'multiple', 'shopify traces', 'HTML/HTTP')
        if 'wp-content' in html_lower or 'wordpress' in html_lower or 'wp-settings' in cookies_dict or 'x-pingback' in headers_dict:
            add_system('wordpress', 'CMS', 'WordPress', 0.99, 'multiple', 'wp traces', 'HTML/HTTP')
        if 'demandware' in html_lower or 'dwvar_' in html_lower or 'dwsid' in cookies_dict or 'x-dw-request-info' in headers_dict:
            add_system('demandware', 'OMS', 'Salesforce Commerce Cloud (Demandware)', 0.99, 'multiple', 'demandware traces', 'HTML/HTTP')
        if 'magento' in html_lower or 'mage-cache-sessid' in cookies_dict or 'x-magento-cache-control' in headers_dict:
            add_system('magento', 'CMS', 'Magento / Adobe Commerce', 0.99, 'multiple', 'magento traces', 'HTML/HTTP')
        if 'bigcommerce' in html_lower or 'cdn11.bigcommerce.com' in html_lower:
            add_system('bigcommerce', 'CMS', 'BigCommerce', 0.95, 'html', 'bigcommerce traces', 'HTML')
        if 'contentful' in html_lower or 'images.ctfassets.net' in html_lower:
            add_system('contentful', 'CMS', 'Contentful CMS', 0.95, 'html', 'contentful domain', 'HTML')

        # FRAMEWORKS & LIBRARIES
        if 'react' in html_lower or 'data-reactroot' in html_lower or '_react' in html_lower: add_system('react', 'custom', 'React', 0.95, 'html', 'react fiber/root', 'HTML')
        if '__next' in html_lower or '/_next/' in html_lower or 'x-nextjs-page' in headers_dict:
            add_system('nextjs', 'custom', 'Next.js', 0.98, 'html/header', 'next.js signatures', 'HTML/HTTP')
            add_system('react', 'custom', 'React', 0.98, 'inferred', 'via next.js', 'Inferred')
        if 'nuxt' in html_lower or '/_nuxt/' in html_lower or 'window.__nuxt__' in html_lower:
            add_system('nuxtjs', 'custom', 'Nuxt.js', 0.98, 'html', 'nuxt object', 'HTML')
            add_system('vue', 'custom', 'Vue.js', 0.98, 'inferred', 'via nuxt', 'Inferred')
        if 'data-v-' in html_lower or 'vue.js' in html_lower or 'window.__vue__' in html_lower: add_system('vue', 'custom', 'Vue.js', 0.95, 'html', 'vue attributes', 'HTML')
        if 'ng-app' in html_lower or 'ng-version' in html_lower or 'angular' in html_lower: add_system('angular', 'custom', 'Angular', 0.95, 'html', 'angular attributes', 'HTML')
        if 'tailwindcss' in html_lower or 'tailwind.config' in html_lower: add_system('tailwind', 'custom', 'Tailwind CSS', 0.95, 'html', 'tailwind strings', 'HTML')
        if 'bootstrap' in html_lower: add_system('bootstrap', 'custom', 'Bootstrap CSS', 0.90, 'html', 'bootstrap class/script', 'HTML')
        if 'jquery' in html_lower: add_system('jquery', 'custom', 'jQuery', 0.95, 'html', 'jquery script', 'HTML')
        
        # ANALYTICS & TAG MANAGERS
        if 'googletagmanager.com' in html_lower or 'gtm.js' in html_lower: add_system('gtm', 'analytics', 'Google Tag Manager', 0.99, 'html', 'gtm script', 'HTML')
        if 'google-analytics.com' in html_lower or 'gtag(' in html_lower or 'ga(' in html_lower: add_system('google_analytics', 'analytics', 'Google Analytics', 0.99, 'html', 'ga script', 'HTML')
        if 'adobe' in html_lower or 'visitorapi.js' in html_lower or 'omtrdc.net' in html_lower: add_system('adobe_analytics', 'analytics', 'Adobe Analytics', 0.95, 'html', 'adobe omniture/dtm', 'HTML')
        if 'cdn.segment.com' in html_lower or 'analytics.js' in html_lower: add_system('segment', 'analytics', 'Segment', 0.98, 'html', 'segment cdn', 'HTML')
        if 'datadoghq' in html_lower or 'datadog-rum' in html_lower: add_system('datadog', 'analytics', 'Datadog RUM', 0.98, 'html', 'datadog rum', 'HTML')
        if 'newrelic.com' in html_lower or 'nr-data.net' in html_lower: add_system('newrelic', 'analytics', 'New Relic', 0.98, 'html', 'newrelic browser agent', 'HTML')

        # PAYMENTS & CHECKOUT
        if 'js.stripe.com' in html_lower or 'stripe' in html_lower: add_system('stripe', 'payment_gateway', 'Stripe', 0.98, 'html', 'stripe js', 'HTML')
        if 'paypalobjects.com' in html_lower or 'paypal.com/sdk' in html_lower: add_system('paypal', 'payment_gateway', 'PayPal', 0.98, 'html', 'paypal js', 'HTML')
        if 'adyen.com' in html_lower: add_system('adyen', 'payment_gateway', 'Adyen', 0.98, 'html', 'adyen js', 'HTML')
        if 'js.klarna.com' in html_lower: add_system('klarna', 'billing', 'Klarna', 0.98, 'html', 'klarna js', 'HTML')
        if 'afterpay.com' in html_lower or 'clearpay.com' in html_lower: add_system('afterpay', 'billing', 'Afterpay / Clearpay', 0.98, 'html', 'afterpay js', 'HTML')
        
        # SEARCH & VIDEO & CONSENT
        if 'algolia' in html_lower or 'algoliasearch' in html_lower: add_system('algolia', 'search', 'Algolia', 0.98, 'html', 'algolia js', 'HTML')
        if 'onetrust.com' in html_lower or 'optanon.com' in html_lower: add_system('onetrust', 'custom', 'OneTrust', 0.98, 'html', 'onetrust js', 'HTML')

        return list(systems_map.values())

    async def _detect_with_builtwith(self, html: str, headers: Any, url: str) -> List[DetectedSystem]:
        """Run the bundled BuiltWith/Wappalyzer signature database over already-fetched
        content.

        Both ``html`` and ``headers`` are passed so the library never issues its own
        (unvalidated, redirect-following) network request, which would otherwise bypass
        the SSRF protections applied to the primary fetch path. The match is pure CPU
        work over a large dataset, so it runs in a worker thread.
        """
        if not html:
            return []
        try:
            import builtwith as builtwith_lib
        except Exception as e:  # pragma: no cover - import guard
            log.warning(f"builtwith library unavailable: {e}")
            return []

        headers_dict = {str(k): str(v) for k, v in dict(headers).items()} if headers else {}

        def _run() -> Dict[str, List[str]]:
            # Passing both html and headers prevents builtwith from fetching the URL.
            return builtwith_lib.parse(url, headers=headers_dict, html=html) or {}

        try:
            results = await asyncio.to_thread(_run)
        except Exception as e:
            log.warning(f"builtwith analysis failed: {e}")
            return []

        systems: List[DetectedSystem] = []
        for category, app_names in results.items():
            sys_type = _BUILTWITH_CATEGORY_MAP.get(category, "custom")
            for app_name in app_names:
                if not app_name:
                    continue
                systems.append(DetectedSystem(
                    system_type=sys_type, name=str(app_name), confidence=0.8,
                    evidence=[Evidence(
                        type="builtwith", value=f"{category}: {app_name}",
                        location="BuiltWith signature DB", confidence=0.8,
                    )],
                ))
        return systems

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
            robots_url = f"{base_url.rstrip('/')}/robots.txt"
            if not _is_safe_url(robots_url):
                return []
            async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
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

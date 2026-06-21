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
from datetime import datetime, timezone
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


def _is_blocked_host(url: str) -> bool:
    """Cheap (no-DNS) SSRF check for headless-browser subrequests.

    A rendered page's JavaScript can issue arbitrary requests; this blocks the
    obvious internal targets (loopback, link-local cloud-metadata, private
    literal IPs, *.local/*.internal) so a malicious page can't use the browser
    to reach `169.254.169.254` etc. The initial navigation URL is already
    validated with the DNS-resolving `_is_safe_url`; this complements it on the
    per-request path without adding a DNS lookup to every asset fetch.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return True  # unparseable → fail closed (block)
    scheme = (parsed.scheme or "").lower()
    # Inline, non-network schemes are safe to allow (and have no host); blocking
    # them would needlessly break rendering of data:/blob: resources.
    if scheme in ("data", "blob", "about"):
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return True  # e.g. file:// or malformed → fail closed (block)
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or host.endswith((".local", ".internal")):
        return True
    try:
        ip = ipaddress.ip_address(host)  # only classifies literal-IP hosts
    except ValueError:
        return False  # a normal hostname (CDN, etc.) — allowed
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


# Markers that identify an anti-bot interstitial (Cloudflare "Just a moment",
# hCaptcha/reCAPTCHA walls, Akamai/Datadome/PerimeterX blocks) rather than real
# page content. If a fetched page matches, it is NOT results — parsing it would
# both yield garbage and falsely "detect" the challenge vendor (e.g. Cloudflare)
# as a technology of the target.
_BOT_CHALLENGE_MARKERS = (
    "just a moment",                     # Cloudflare interstitial title
    "cf-browser-verification",
    "cf_chl_opt",                        # Cloudflare challenge JS var
    "challenge-platform",                # /cdn-cgi/challenge-platform/
    "checking your browser",
    "enable javascript and cookies to continue",
    "attention required",                # Cloudflare block page
    "h-captcha",
    "g-recaptcha",
    "recaptcha/api.js",
    "px-captcha",                        # PerimeterX
    "_imperva_",                         # Imperva/Incapsula
    "datadome",
    "access denied",
    "are you a robot",
    "verify you are human",
)


def _looks_like_bot_challenge(html: str) -> bool:
    """True if the HTML is an anti-bot/CAPTCHA interstitial rather than content.

    Used to gate the BuiltWith fallback: builtwith.com is itself Cloudflare-
    fronted, so a plain fetch can return a "Just a moment" challenge. We must
    detect that and refuse to parse it as results (and escalate to a real
    browser, which can clear Cloudflare's *automatic* JS challenge). A hard
    interactive CAPTCHA still cannot be solved without a paid solver — in that
    case we honestly return nothing rather than fabricate detections.
    """
    if not html:
        return True  # empty body is not usable content
    head = html[:6000].lower()
    # Short bodies that mention a challenge marker are almost certainly the
    # interstitial itself (a real results page is large and content-rich).
    hit = any(m in head for m in _BOT_CHALLENGE_MARKERS)
    if not hit:
        return False
    # A long, content-rich page that merely *mentions* "access denied" in copy
    # is not a challenge; require the marker AND a short/sparse body.
    return len(html) < 30000


def _hostname_matches(url_or_host: str, *domains: str) -> bool:
    """Check if a URL or hostname exactly matches or is a subdomain of any domain.

    Uses urlparse for proper hostname extraction instead of substring matching.
    This satisfies CodeQL's py/incomplete-url-substring-sanitization rule.
    """
    # Try parsing as URL first, then as raw hostname
    try:
        parsed = urlparse(url_or_host)
        hostname = (parsed.hostname or parsed.path or url_or_host).lower()
    except Exception:
        hostname = url_or_host.lower()
    return any(hostname == d.lower() or hostname.endswith('.' + d.lower()) for d in domains)


def _hostname_contains(url: str, *domains: str) -> bool:
    """Check if URL hostname exactly matches or is a subdomain of any domain.

    Uses _hostname_matches for proper hostname comparison.
    """
    return _hostname_matches(url, *domains)


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
        # NOTE: do not import dns.resolver here. It is only needed by
        # _analyze_dns, which imports it inside its own guarded try/except — an
        # un-guarded import at method entry would turn a missing/broken
        # dnspython into a hard 500 for the whole scan instead of degrading to
        # an empty DNS result.
        scan_id = f"scan_{secrets.token_hex(8)}"
        started_at = datetime.now(timezone.utc)

        try:
            if not website_url.startswith(("http://", "https://")):
                website_url = f"https://{website_url}"
            
            parsed = urlparse(website_url)
            if parsed.scheme not in ("http", "https"):
                return WebsiteScanResult(
                    scan_id=scan_id, website_url=website_url, company_id=self.company_id,
                    status="failed", errors=["Blocked: only http/https schemes allowed"],
                    started_at=started_at.isoformat(), completed_at=datetime.now(timezone.utc).isoformat()
                )
            
            _safe_url = parsed._replace(fragment="").geturl()

            # SSRF guard: block internal/private targets before any network I/O
            if not _is_safe_url(_safe_url):
                return WebsiteScanResult(
                    scan_id=scan_id, website_url=website_url, company_id=self.company_id,
                    status="failed", errors=["Blocked: target URL is not a safe public address (SSRF protection)"],
                    started_at=started_at.isoformat(), completed_at=datetime.now(timezone.utc).isoformat()
                )

            domain = parsed.hostname.replace('www.', '') if parsed.hostname else ""

            # 1. DNS + TLS-certificate Analysis (BuiltWith-level off-site
            #    detection). Both are network/CPU work, so run them in worker
            #    threads to keep the event loop responsive.
            dns_systems = await asyncio.to_thread(self._analyze_dns, domain)
            ssl_systems = await asyncio.to_thread(self._analyze_ssl_cert, domain)

            # 2. On-Site Analysis
            html = ""
            headers = {}
            cookies = {}
            status_code = 0
            fetch_error: Optional[str] = None

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
                        log.warning(f"HTTPX fallback failed for {_safe_url}: {e}")
                        fetch_error = str(e)

            # If both fetch clients failed, surface the error rather than returning empty success
            if fetch_error is not None and not html:
                return WebsiteScanResult(
                    scan_id=scan_id, website_url=website_url, company_id=self.company_id,
                    status="failed", errors=[f"All fetch clients failed: {fetch_error}"],
                    started_at=started_at.isoformat(), completed_at=datetime.now(timezone.utc).isoformat()
                )

            soup = BeautifulSoup(html, 'html.parser') if html else BeautifulSoup("", 'html.parser')
            
            # Use dynamic BuiltWith-style identification logic. The ~1,270-signature
            # regex pass is CPU-bound; run it in a worker thread so a large/minified
            # page can't block the event loop and stall concurrent requests.
            html_systems = await asyncio.to_thread(self._detect_systems_generic, html, headers, cookies)
            
            # Explicit high-signal response-header detection (CDN/infra/security
            # headers BuiltWith reports) on top of the regex DB pass.
            header_systems = self._analyze_response_headers(headers)

            # Merge all evidence sources, keeping the highest-confidence record
            # per system: HTML signatures, DNS, TLS cert, response headers.
            all_systems_map = {sys.name: sys for sys in html_systems}
            for extra_sys in (*dns_systems, *ssl_systems, *header_systems):
                existing = all_systems_map.get(extra_sys.name)
                if existing is None or extra_sys.confidence > existing.confidence:
                    all_systems_map[extra_sys.name] = extra_sys

            detected_systems = list(all_systems_map.values())

            # Headless fallback. JS-rendered and bot-protected sites (e.g. luxury
            # commerce behind Akamai) expose little or nothing in the static HTML
            # a plain fetch returns. When static detection found nothing — or the
            # fetch looks blocked/empty — render the page with a real browser
            # (Playwright/Chromium) and re-run the same signature detection on the
            # fully-rendered DOM. No-ops gracefully when the browser isn't present.
            # Escalate when detection is *thin*, not only when it found literally
            # nothing: bot-protected storefronts (gucci.com behind Akamai) leak a
            # couple of signals from the challenge page, so a `not detected_systems`
            # gate never fired and PIM/CRM/etc. behind the JS wall stayed invisible.
            import os as _os
            try:
                _render_min = int(_os.environ.get("SCANNER_RENDER_MIN_SYSTEMS", "5"))
            except ValueError:
                _render_min = 5
            _blocked_or_thin = (
                len(detected_systems) < _render_min
                or status_code == 0
                or status_code >= 400
                or _looks_like_bot_challenge(html or "")
            )
            if _blocked_or_thin:
                rendered = await self._render_html(_safe_url)
                if rendered:
                    r_html, r_headers, r_cookies = rendered
                    merged_headers = {**(dict(headers) if headers else {}), **(r_headers or {})}
                    merged_cookies = {**(dict(cookies) if cookies else {}), **(r_cookies or {})}
                    rendered_systems = await asyncio.to_thread(
                        self._detect_systems_generic, r_html, merged_headers, merged_cookies
                    )
                    for s in rendered_systems:
                        existing = all_systems_map.get(s.name)
                        if existing is None or s.confidence > existing.confidence:
                            all_systems_map[s.name] = s
                    detected_systems = list(all_systems_map.values())
                    # Prefer the rendered DOM for downstream stack inference and
                    # sitemap discovery when the static body was thin/blocked.
                    if r_html and (not html or len(html) < len(r_html)):
                        html = r_html
                        soup = BeautifulSoup(r_html, 'html.parser')
                        if status_code == 0 or status_code >= 400:
                            status_code = 200

            # Final fallback: if we *still* found nothing (live detection fully
            # blocked — e.g. Akamai-fronted JS storefronts with no Chromium
            # available), ask builtwith.com what it already knows about the
            # domain from its own crawl. Free, no API key, off-page — so it works
            # even when the target site refuses us. Merged at lower confidence.
            try:
                _bw_min = int(_os.environ.get("SCANNER_BUILTWITH_MIN_SYSTEMS", "5"))
            except ValueError:
                _bw_min = 5
            if len(detected_systems) < _bw_min:
                bw_systems = await self._query_builtwith(domain)
                for s in bw_systems:
                    if s.name not in all_systems_map:
                        all_systems_map[s.name] = s
                detected_systems = list(all_systems_map.values())

            stack_inference = await self._infer_stack(soup, html, headers, website_url)
            
            # 3. Sitemap discovery
            sitemap_urls = []
            if include_sitemap and html and status_code < 400:
                sitemap_urls = await self._discover_sitemap(soup, website_url)
            
            pages_scanned = 1 + len(sitemap_urls) if sitemap_urls else 1
            completed_at = datetime.now(timezone.utc)
            
            return WebsiteScanResult(
                scan_id=scan_id, website_url=website_url, company_id=self.company_id, status="success",
                inferred_stack=stack_inference, detected_systems=detected_systems, pages_scanned=pages_scanned,
                sitemap_urls=sitemap_urls, started_at=started_at.isoformat(), completed_at=completed_at.isoformat()
            )
                
        except Exception as e:
            log.error(f"Error scanning website {website_url}: {e}")
            return WebsiteScanResult(
                scan_id=scan_id, website_url=website_url, company_id=self.company_id, status="failed",
                errors=[str(e)], started_at=started_at.isoformat(), completed_at=datetime.now(timezone.utc).isoformat()
            )

    async def _render_html(self, url: str) -> Optional[tuple[str, dict, dict]]:
        """Render a page with a real headless browser (Playwright/Chromium) and
        return ``(html, headers, cookies)`` from the fully-executed DOM.

        This is the strongest self-hosted detection path: a real browser runs
        the site's JavaScript (exposing tech markers injected at runtime) and
        presents a genuine browser fingerprint (defeating most bot protection
        that a plain HTTP client trips). Returns ``None`` — gracefully — when:
          * rendering is disabled via ``SCANNER_HEADLESS_RENDER=off``;
          * Playwright isn't installed (e.g. local/CI without the browser); or
          * the browser fails to launch or the navigation errors out.
        Production (the Render image) installs Chromium so this is active there;
        environments without it simply fall back to the static-HTML result.
        """
        import os as _os
        mode = _os.environ.get("SCANNER_HEADLESS_RENDER", "auto").lower()
        if mode in ("0", "off", "false", "no", "disabled"):
            return None
        try:
            from playwright.async_api import async_playwright
        except Exception:
            log.info("Headless render unavailable: playwright not installed — using static HTML only")
            return None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                    ],
                )
                try:
                    context = await browser.new_context(
                        user_agent=self.user_agent,
                        locale="en-US",
                        viewport={"width": 1366, "height": 900},
                    )
                    # SSRF guard for JS-initiated subrequests: abort anything
                    # pointed at an internal/metadata address.
                    async def _guard(route):
                        try:
                            if _is_blocked_host(route.request.url):
                                await route.abort()
                            else:
                                await route.continue_()
                        except Exception as guard_e:
                            log.debug(f"Subrequest guard error for {route.request.url}: {guard_e}")
                            try:
                                await route.continue_()
                            except Exception as cont_e:
                                log.debug(f"Subrequest continue failed: {cont_e}")
                    await context.route("**/*", _guard)

                    page = await context.new_page()
                    timeout_ms = int(self.timeout * 1000)
                    resp = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                    # Give late/async JS a chance to inject markup, but never hang:
                    # wait for network idle with a short cap, then a small settle.
                    try:
                        await page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass
                    try:
                        await page.wait_for_timeout(1000)
                    except Exception:
                        pass
                    html = await page.content()
                    headers = dict(resp.headers) if resp is not None else {}
                    try:
                        cookies = {c.get("name"): c.get("value") for c in await context.cookies()}
                    except Exception:
                        cookies = {}
                    log.info(f"Headless render succeeded for {url} ({len(html)} bytes)")
                    return html, headers, cookies
                finally:
                    await browser.close()
        except Exception as e:
            log.warning(f"Headless render failed for {url}: {e}")
            return None

    def _classify_system_type(self, name: str) -> str:
        """Map a technology name to a SystemType literal using the catalog's
        category metadata, falling back to keyword heuristics. Shared by the
        signature engine and the BuiltWith fallback parser."""
        valid_types = {
            'CMS', 'CRM', 'OMS', 'PIM', 'DAM', 'ERP', 'HRM', 'LMS', 'analytics',
            'payment_gateway', 'shipping', 'tax', 'inventory', 'marketing_automation',
            'email_service', 'search', 'database', 'cache', 'cdc', 'message_queue',
            'api_gateway', 'auth', 'billing', 'support', 'chat', 'video', 'voice',
            'iot', 'ai_ml', 'custom',
        }
        apps = self.tech_data.get("apps", {})
        spec = apps.get(name)
        if spec:
            explicit = spec.get("type")
            if explicit in valid_types:
                return explicit
            cat_id = str(spec.get("cats", [1])[0])
            cat_name = self.tech_data.get("categories", {}).get(cat_id, "custom")
            if cat_name in valid_types:
                return cat_name
        # Keyword fallback for names BuiltWith returns that aren't in the catalog.
        low = name.lower()
        keyword_map = [
            (("shopify", "magento", "woocommerce", "wordpress", "drupal", "wix",
              "squarespace", "bigcommerce", "demandware", "commerce cloud"), "CMS"),
            (("salesforce", "hubspot crm", "dynamics", "zoho"), "CRM"),
            (("stripe", "paypal", "braintree", "adyen", "klarna", "afterpay",
              "apple pay", "google pay", "checkout"), "payment_gateway"),
            (("google analytics", "mixpanel", "amplitude", "segment", "hotjar",
              "matomo", "plausible", "heap"), "analytics"),
            (("mailchimp", "marketo", "hubspot", "pardot", "klaviyo"), "marketing_automation"),
            (("sendgrid", "mailgun", "mandrill", "postmark", "sparkpost"), "email_service"),
            (("zendesk", "intercom", "freshdesk", "drift", "livechat"), "support"),
            (("algolia", "elasticsearch", "solr", "coveo"), "search"),
        ]
        for needles, stype in keyword_map:
            if any(n in low for n in needles):
                return stype
        return "custom"

    async def _fetch_builtwith_page(self, bw_url: str) -> str:
        """Fetch a builtwith.com page, defeating its bot protection as far as is
        possible *for free*. Two tiers, escalating only when needed:

          1. ``curl_cffi`` with a real Chrome TLS/JA3 fingerprint. This is what
             the old `ecrmnn`/`noname01` scrapers lacked — a plain
             ``urllib``/``requests`` GET is fingerprint-blocked by Cloudflare
             instantly. Impersonation clears Cloudflare's *fingerprint-only* mode.
          2. If tier 1 returns a Cloudflare/CAPTCHA interstitial, escalate to the
             **headless browser** (``_render_html``), which executes the
             challenge JS and can clear Cloudflare's *automatic* "Just a moment"
             page that no HTTP client can.

        Returns the HTML of a *real* page, or ``""`` if every tier still hits a
        challenge (e.g. a hard interactive CAPTCHA — unsolvable without a paid
        solver, so we honestly give up rather than fabricate detections).
        """
        # Tier 1: curl_cffi Chrome impersonation.
        html = ""
        try:
            import curl_cffi.requests
            async with curl_cffi.requests.AsyncSession(
                impersonate="chrome120", timeout=self.timeout
            ) as client:
                resp = await client.get(bw_url, allow_redirects=True)
                if resp.status_code == 200:
                    html = resp.text or ""
        except Exception as e:
            log.info(f"BuiltWith tier-1 (curl_cffi) fetch failed: {e}")
            html = ""

        if html and not _looks_like_bot_challenge(html):
            return html

        # Tier 2: real browser to clear an automatic JS challenge. _render_html
        # already honours SCANNER_HEADLESS_RENDER and no-ops without Chromium.
        log.info("BuiltWith tier-1 hit a bot challenge — escalating to headless browser")
        rendered = await self._render_html(bw_url)
        if rendered:
            r_html, _r_headers, _r_cookies = rendered
            if r_html and not _looks_like_bot_challenge(r_html):
                return r_html

        log.info("BuiltWith fetch blocked by an unsolvable challenge — returning no data")
        return ""

    async def _query_builtwith(self, domain: str) -> List[DetectedSystem]:
        """Last-resort fallback for sites we can't fingerprint live (JS-rendered
        + aggressive bot protection, e.g. Akamai-fronted luxury commerce).

        Rather than fight the target's bot wall, we ask **builtwith.com** what it
        already knows about the domain from its own historical crawl and parse
        that page. This is the technique behind the `ecrmnn/builtwith`,
        `ecrmnn/builtwith-cli`, and `noname01/builtwith-api` projects — but
        hardened in two ways those (now-stale, ~2015-era) scrapers are not:

          * **Bot protection:** they use a plain ``got()``/``urllib`` GET, which
            today's Cloudflare-fronted builtwith.com answers with a "Just a
            moment" CAPTCHA. We fetch via ``curl_cffi`` Chrome impersonation and
            escalate to a headless browser, and — critically — *refuse to parse a
            challenge page* (see ``_fetch_builtwith_page`` /
            ``_looks_like_bot_challenge``) so a CAPTCHA is never mistaken for
            results (which would also falsely "detect" Cloudflare as the target's
            tech).
          * **Markup drift:** they scrape fixed CSS classes
            (``.techItem``/``.titleBox``) BuiltWith has long since redesigned, so
            they silently return nothing. We instead cross-reference the page
            against our own ~1,270-app catalog, with the legacy selectors as a
            secondary pass.

        Free (no API key — scrapes the public page). Gated by
        ``SCANNER_BUILTWITH_FALLBACK`` (default ``auto``; set ``off`` to disable).
        Always degrades to ``[]`` — never raises into the scan.
        """
        import os as _os
        if _os.environ.get("SCANNER_BUILTWITH_FALLBACK", "auto").lower() in (
            "0", "off", "false", "no", "disabled",
        ):
            return []
        if not domain:
            return []

        bw_url = f"https://builtwith.com/{domain}"
        html = await self._fetch_builtwith_page(bw_url)
        # Empty or still-a-challenge → no usable data. Never parse a CAPTCHA page.
        if not html or _looks_like_bot_challenge(html):
            return []

        systems_map: Dict[str, DetectedSystem] = {}

        def add(name: str, evidence_val: str) -> None:
            name = (name or "").strip()
            # Guard against scraping noise (nav labels, blank cells, huge blobs).
            if not name or len(name) > 60:
                return
            if name in systems_map:
                return
            systems_map[name] = DetectedSystem(
                system_type=self._classify_system_type(name),
                name=name,
                confidence=0.80,  # historical/3rd-party signal — below live detection
                evidence=[Evidence(
                    type="builtwith", value=evidence_val[:200],
                    location="builtwith.com", confidence=0.80,
                )],
            )

        # Pass 1 (markup-independent): match our known app catalog against the
        # page. Whole-word match so "Wix" doesn't fire inside "Wixardry".
        import re as _re
        haystack = html.lower()
        for app_name in self.tech_data.get("apps", {}):
            if len(app_name) < 3:
                continue  # skip ultra-short names that false-positive
            if _re.search(r"(?<![a-z0-9])" + _re.escape(app_name.lower()) + r"(?![a-z0-9])", haystack):
                add(app_name, f"listed on {bw_url}")

        # Pass 2 (legacy selectors, best-effort): the classic BuiltWith result
        # markup. Kept as a secondary source in case the catalog misses a name
        # BuiltWith labels differently.
        try:
            soup = BeautifulSoup(html, "html.parser")
            for item in soup.select(".techItem h3, .techItem h3 a, li.card__tech-name, .tech-name"):
                txt = item.get_text(strip=True)
                if txt:
                    add(txt, "builtwith techItem")
        except Exception as e:
            log.debug(f"BuiltWith legacy-selector parse skipped for {domain}: {e}")

        if systems_map:
            log.info(f"BuiltWith fallback recovered {len(systems_map)} systems for {domain}")
        return list(systems_map.values())

    def _analyze_dns(self, domain: str) -> List[DetectedSystem]:
        systems: List[DetectedSystem] = []

        if not domain:
            return systems

        # Soft import: if dnspython is unavailable, degrade to an empty DNS
        # result rather than crashing the whole scan (the static/headless tiers
        # still run). dnspython is a production dependency (backend/requirements
        # .txt); this guard just keeps a dependency drift from 500-ing scans.
        try:
            import dns.resolver
        except ImportError:
            log.warning("dnspython not installed — skipping DNS analysis (no MX/NS/TXT/CNAME detection)")
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
                    if _hostname_matches(mx, 'google.com', 'googlemail.com'): add_sys('gsuite', 'custom', 'Google Workspace', 0.99, 'MX', mx)
                    if _hostname_matches(mx, 'outlook.com', 'protection.outlook.com'): add_sys('office365', 'custom', 'Microsoft 365', 0.99, 'MX', mx)
                    if _hostname_matches(mx, 'pphosted.com'): add_sys('proofpoint', 'custom', 'Proofpoint Email Security', 0.99, 'MX', mx)
                    if _hostname_matches(mx, 'mimecast.com'): add_sys('mimecast', 'custom', 'Mimecast', 0.99, 'MX', mx)
                    if _hostname_matches(mx, 'zendesk.com'): add_sys('zendesk', 'support', 'Zendesk', 0.99, 'MX', mx)
            except Exception: pass
            
            # 2. NS Records (DNS nameserver pattern matching against fixed known domains)
            try:
                for rdata in dns.resolver.resolve(domain, 'NS'):
                    ns = str(rdata.target).lower()
                    if _hostname_matches(ns, 'cloudflare.com'): add_sys('cloudflare', 'custom', 'Cloudflare DNS', 0.99, 'NS', ns)
                    if _hostname_matches(ns, 'akam.net', 'akamai.com', 'akamaiedge.net'): add_sys('akamai', 'custom', 'Akamai', 0.99, 'NS', ns)
                    if _hostname_matches(ns, 'ultradns.com', 'ultradns.net'): add_sys('ultradns', 'custom', 'UltraDNS', 0.99, 'NS', ns)
                    if _hostname_matches(ns, 'fastly.com', 'fastly.net'): add_sys('fastly', 'custom', 'Fastly', 0.99, 'NS', ns)
                    if '.awsdns-' in ns: add_sys('route53', 'custom', 'AWS Route 53', 0.99, 'NS', ns)  # nosec B105 — subnet matching for awsdns-XX.net Route53 domains
            except Exception: pass

            # 3. TXT Records (content-based detection — TXT values are not URLs,
            # but the pattern is a substring check on fixed known strings, not
            # user input). Using _content_contains_domain which is explicitly
            # tagged for known-string matching only (not URL validation).
            try:
                for rdata in dns.resolver.resolve(domain, 'TXT'):
                    txt = str(rdata).lower()
                    # SPF includes are hostname patterns — use _hostname_matches
                    if _content_contains_domain(txt, 'spf.protection.outlook.com'): add_sys('office365', 'custom', 'Microsoft 365', 0.99, 'TXT SPF', txt)
                    if _content_contains_domain(txt, '_spf.google.com'): add_sys('gsuite', 'custom', 'Google Workspace', 0.99, 'TXT SPF', txt)
                    if _content_contains_domain(txt, 'spf.mailjet.com'): add_sys('mailjet', 'email_service', 'Mailjet', 0.99, 'TXT SPF', txt)
                    if _content_contains_domain(txt, 'sendgrid.net'): add_sys('sendgrid', 'email_service', 'SendGrid', 0.99, 'TXT SPF', txt)
                    if _content_contains_domain(txt, '_spf.salesforce.com'): add_sys('salesforce', 'CRM', 'Salesforce', 0.99, 'TXT SPF', txt)
                    if _content_contains_domain(txt, 'mailgun.org'): add_sys('mailgun', 'email_service', 'Mailgun', 0.99, 'TXT SPF', txt)
                    if _content_contains_domain(txt, 'amazonses'): add_sys('aws_ses', 'email_service', 'Amazon SES', 0.99, 'TXT', txt)
                    
                    if _content_contains_domain(txt, 'google-site-verification'): add_sys('google_search_console', 'analytics', 'Google Search Console', 0.99, 'TXT', txt)
                    if _content_contains_domain(txt, 'facebook-domain-verification'): add_sys('facebook_business', 'marketing_automation', 'Facebook Business', 0.99, 'TXT', txt)
                    if _content_contains_domain(txt, 'apple-domain-verification'): add_sys('apple_pay', 'payment_gateway', 'Apple Pay / Merchant', 0.95, 'TXT', txt)
                    if _content_contains_domain(txt, 'stripe-verification'): add_sys('stripe', 'payment_gateway', 'Stripe', 0.99, 'TXT', txt)
                    if _content_contains_domain(txt, 'docusign'): add_sys('docusign', 'custom', 'DocuSign', 0.99, 'TXT', txt)
                    if _content_contains_domain(txt, 'atlassian'): add_sys('atlassian', 'custom', 'Atlassian', 0.99, 'TXT', txt)
                    if _content_contains_domain(txt, 'mixpanel'): add_sys('mixpanel', 'analytics', 'Mixpanel', 0.99, 'TXT', txt)
                    if _content_contains_domain(txt, 'onetrust'): add_sys('onetrust', 'custom', 'OneTrust', 0.99, 'TXT', txt)
                    if _content_contains_domain(txt, 'dynatrace'): add_sys('dynatrace', 'analytics', 'Dynatrace', 0.99, 'TXT', txt)
                    if _content_contains_domain(txt, 'twilio'): add_sys('twilio', 'custom', 'Twilio', 0.99, 'TXT', txt)
                    if _content_contains_domain(txt, 'notion_verify'): add_sys('notion', 'custom', 'Notion', 0.99, 'TXT', txt)
                    if _content_contains_domain(txt, 'jamf-site'): add_sys('jamf', 'custom', 'Jamf', 0.99, 'TXT', txt)
                    if _content_contains_domain(txt, 'paloaltonetworks'): add_sys('paloalto', 'custom', 'Palo Alto Networks', 0.99, 'TXT', txt)
                    if _content_contains_domain(txt, 'elevenlabs'): add_sys('elevenlabs', 'ai_ml', 'ElevenLabs', 0.99, 'TXT', txt)
                    if _content_contains_domain(txt, 'anthropic'): add_sys('anthropic', 'ai_ml', 'Anthropic', 0.99, 'TXT', txt)
                    if _content_contains_domain(txt, 'openai'): add_sys('openai', 'ai_ml', 'OpenAI', 0.99, 'TXT', txt)
                    if _content_contains_domain(txt, 'miro-verification'): add_sys('miro', 'custom', 'Miro', 0.99, 'TXT', txt)
                    if _content_contains_domain(txt, 'loom-verification'): add_sys('loom', 'custom', 'Loom', 0.99, 'TXT', txt)
                    if _content_contains_domain(txt, 'cursor-domain'): add_sys('cursor', 'ai_ml', 'Cursor', 0.99, 'TXT', txt)
            except Exception: pass

            # 4. CNAME chains → CDN / hosting / SaaS platform (BuiltWith-style).
            #    DNS isn't behind the site's bot wall, so this still identifies
            #    the platform even when the HTML fetch is blocked (e.g. Akamai).
            #    Map of CNAME-target substring → (id, system_type, display name).
            cname_map = [
                ('cloudfront.net',      ('cloudfront', 'custom', 'AWS CloudFront (CDN)')),
                ('elb.amazonaws.com',   ('aws_elb',    'custom', 'AWS Elastic Load Balancing')),
                ('edgekey.net',         ('akamai',     'custom', 'Akamai (CDN)')),
                ('edgesuite.net',       ('akamai',     'custom', 'Akamai (CDN)')),
                ('akamaiedge.net',      ('akamai',     'custom', 'Akamai (CDN)')),
                ('akamaized.net',       ('akamai',     'custom', 'Akamai (CDN)')),
                ('fastly.net',          ('fastly',     'custom', 'Fastly (CDN)')),
                ('fastlylb.net',        ('fastly',     'custom', 'Fastly (CDN)')),
                ('cloudflare.net',      ('cloudflare', 'custom', 'Cloudflare (CDN)')),
                ('cdn.cloudflare.net',  ('cloudflare', 'custom', 'Cloudflare (CDN)')),
                ('azureedge.net',       ('azure_cdn',  'custom', 'Azure CDN')),
                ('azurefd.net',         ('azure_fd',   'custom', 'Azure Front Door')),
                ('trafficmanager.net',  ('azure_tm',   'custom', 'Azure Traffic Manager')),
                ('cloudapp.azure.com',  ('azure',      'custom', 'Microsoft Azure')),
                ('googlehosted.com',    ('gcp',        'custom', 'Google Cloud')),
                ('ghs.googlehosted.com',('gcp',        'custom', 'Google Cloud')),
                ('herokudns.com',       ('heroku',     'custom', 'Heroku')),
                ('herokuapp.com',       ('heroku',     'custom', 'Heroku')),
                ('netlify.app',         ('netlify',    'custom', 'Netlify')),
                ('netlifyglobalcdn.com',('netlify',    'custom', 'Netlify')),
                ('vercel-dns.com',      ('vercel',     'custom', 'Vercel')),
                ('vercel.app',          ('vercel',     'custom', 'Vercel')),
                ('github.io',           ('github_pages','custom', 'GitHub Pages')),
                ('pages.dev',           ('cf_pages',   'custom', 'Cloudflare Pages')),
                ('myshopify.com',       ('shopify',    'CMS',    'Shopify')),
                ('shopifycdn.com',      ('shopify',    'CMS',    'Shopify')),
                ('myshopify.io',        ('shopify',    'CMS',    'Shopify')),
                ('wpengine.com',        ('wpengine',   'custom', 'WP Engine')),
                ('wpenginepowered.com', ('wpengine',   'custom', 'WP Engine')),
                ('wixdns.net',          ('wix',        'CMS',    'Wix')),
                ('squarespace.com',     ('squarespace','CMS',    'Squarespace')),
                ('hubspot.net',         ('hubspot',    'marketing_automation', 'HubSpot')),
                ('hubspotusercontent.net',('hubspot',  'marketing_automation', 'HubSpot')),
                ('zendesk.com',         ('zendesk',    'support', 'Zendesk')),
                ('incapdns.net',        ('imperva',    'custom', 'Imperva (Incapsula)')),
                ('edgecastcdn.net',     ('edgecast',   'custom', 'Edgecast (CDN)')),
                ('b-cdn.net',           ('bunny',      'custom', 'Bunny CDN')),
                ('stackpathdns.com',    ('stackpath',  'custom', 'StackPath (CDN)')),
            ]

            def _match_cname(target: str, source: str):
                target = target.lower().rstrip('.')
                for needle, (sid, stype, name) in cname_map:
                    if _hostname_matches(target, needle):
                        add_sys(sid, stype, name, 0.95, f'CNAME ({source})', target)
                        return

            try:
                # Apex is often CNAME-flattened, so also check the common www host.
                for host, label in ((domain, 'apex'), (f'www.{domain}', 'www')):
                    try:
                        for rdata in dns.resolver.resolve(host, 'CNAME'):
                            _match_cname(str(rdata.target), label)
                    except Exception:
                        pass
            except Exception:
                pass

        except Exception as e:
            log.warning(f"DNS analysis failed for {domain}: {e}")

        return systems

    def _analyze_ssl_cert(self, domain: str) -> List[DetectedSystem]:
        """Inspect the TLS certificate (issuer + Subject Alternative Names) to
        infer hosting/CDN/cert platforms — BuiltWith-style off-HTML evidence.

        Many platforms terminate TLS with their own certs whose issuer or SANs
        reveal the provider even when the HTML is bot-walled (e.g. Cloudflare,
        Let's Encrypt via a PaaS, Google Trust Services on GCP, Amazon on
        CloudFront/ELB). Degrades to an empty list on any error so it can never
        500 or hang the scan.
        """
        systems: List[DetectedSystem] = []
        if not domain:
            return systems

        import ssl as _ssl
        import socket as _socket

        def add_sys(sys_id, sys_type, name, conf, ev_type, ev_val):
            systems.append(DetectedSystem(
                system_type=sys_type, name=name, confidence=conf,
                evidence=[Evidence(type=ev_type, value=str(ev_val)[:200], location="SSL", confidence=conf)]
            ))

        try:
            ctx = _ssl.create_default_context()
            # We only read cert metadata; tolerate hostname/expiry mismatches so
            # detection still works on misconfigured or wildcard certs.
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
            with _socket.create_connection((domain, 443), timeout=min(self.timeout, 10)) as sock:
                with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
            if not cert:
                return systems

            # Issuer organisation / common name.
            issuer_parts = []
            for rdn in cert.get('issuer', ()):  # tuple of tuples
                for k, v in rdn:
                    if k in ('organizationName', 'commonName'):
                        issuer_parts.append(str(v))
            issuer = " ".join(issuer_parts).lower()

            issuer_map = [
                ("let's encrypt", ('letsencrypt', 'custom', "Let's Encrypt")),
                ('cloudflare',    ('cloudflare',  'custom', 'Cloudflare')),
                ('amazon',        ('aws',         'custom', 'Amazon Web Services')),
                ('google trust',  ('gcp',         'custom', 'Google Cloud')),
                ('digicert',      ('digicert',    'custom', 'DigiCert')),
                ('sectigo',       ('sectigo',     'custom', 'Sectigo')),
                ('globalsign',    ('globalsign',  'custom', 'GlobalSign')),
                ('microsoft',     ('azure',       'custom', 'Microsoft Azure')),
                ('gts ',          ('gcp',         'custom', 'Google Cloud')),
                ('entrust',       ('entrust',     'custom', 'Entrust')),
            ]
            for needle, (sid, stype, name) in issuer_map:
                if needle in issuer:
                    add_sys(sid, stype, name, 0.85, 'SSL issuer', issuer)
                    break

            # Subject Alternative Names — wildcard/secondary SANs frequently leak
            # the underlying SaaS/CDN host the cert was minted for.
            san_map = [
                ('cloudflaressl.com', ('cloudflare', 'custom', 'Cloudflare')),
                ('sni.cloudflaressl', ('cloudflare', 'custom', 'Cloudflare')),
                ('myshopify.com',     ('shopify',    'CMS',    'Shopify')),
                ('shopify',           ('shopify',    'CMS',    'Shopify')),
                ('herokuapp.com',     ('heroku',     'custom', 'Heroku')),
                ('netlify',           ('netlify',    'custom', 'Netlify')),
                ('vercel',            ('vercel',     'custom', 'Vercel')),
                ('wpengine',          ('wpengine',   'custom', 'WP Engine')),
                ('squarespace',       ('squarespace','CMS',    'Squarespace')),
                ('wixsite',           ('wix',        'CMS',    'Wix')),
                ('fastly',            ('fastly',     'custom', 'Fastly')),
                ('akamai',            ('akamai',     'custom', 'Akamai')),
                ('amazonaws.com',     ('aws',        'custom', 'Amazon Web Services')),
                ('cloudfront.net',    ('cloudfront', 'custom', 'AWS CloudFront')),
                ('azure',             ('azure',      'custom', 'Microsoft Azure')),
                ('hubspot',           ('hubspot',    'marketing_automation', 'HubSpot')),
                ('zendesk',           ('zendesk',    'support', 'Zendesk')),
            ]
            for typ, san in cert.get('subjectAltName', ()):
                if typ != 'DNS':
                    continue
                san_l = str(san).lower()
                for needle, (sid, stype, name) in san_map:
                    if needle in san_l:
                        add_sys(sid, stype, name, 0.8, 'SSL SAN', san_l)
        except Exception as e:
            log.debug("SSL cert analysis skipped for %s: %s", domain, e)

        return systems

    def _analyze_response_headers(self, headers: Any) -> List[DetectedSystem]:
        """Explicit high-signal response-header detection beyond the
        technologies.json header specs — covers CDN/infra/security headers
        BuiltWith reports (Server, Via, X-Powered-By, X-Served-By, CF-Ray,
        X-Cache, X-Amz-*, etc.). Complements the regex DB pass; never throws.
        """
        systems: List[DetectedSystem] = []
        try:
            hdr = {str(k).lower(): str(v).lower() for k, v in dict(headers or {}).items()}
        except Exception:
            return systems

        def add_sys(sys_id, sys_type, name, conf, hname, hval):
            systems.append(DetectedSystem(
                system_type=sys_type, name=name, confidence=conf,
                evidence=[Evidence(type='header', value=f'{hname}: {str(hval)[:120]}',
                                   location='headers', confidence=conf)]
            ))

        # (header name, substring-or-empty, system tuple). Empty substring =
        # presence-only signal (the header existing is itself the evidence).
        rules = [
            ('cf-ray',          '',            ('cloudflare', 'custom', 'Cloudflare')),
            ('cf-cache-status', '',            ('cloudflare', 'custom', 'Cloudflare')),
            ('x-served-by',     'cache',       ('fastly',     'custom', 'Fastly')),
            ('x-fastly-request-id', '',        ('fastly',     'custom', 'Fastly')),
            ('x-cache',         'cloudfront',  ('cloudfront', 'custom', 'AWS CloudFront')),
            ('via',             'cloudfront',  ('cloudfront', 'custom', 'AWS CloudFront')),
            ('x-amz-cf-id',     '',            ('cloudfront', 'custom', 'AWS CloudFront')),
            ('x-amz-request-id','',            ('aws_s3',     'custom', 'Amazon S3')),
            ('x-azure-ref',     '',            ('azure',      'custom', 'Microsoft Azure')),
            ('x-akamai-transformed', '',       ('akamai',     'custom', 'Akamai')),
            ('x-iinfo',         '',            ('imperva',    'custom', 'Imperva')),
            ('x-sucuri-id',     '',            ('sucuri',     'custom', 'Sucuri')),
            ('x-vercel-id',     '',            ('vercel',     'custom', 'Vercel')),
            ('x-nf-request-id', '',            ('netlify',    'custom', 'Netlify')),
            ('x-shopify-stage', '',            ('shopify',    'CMS',    'Shopify')),
            ('x-shopid',        '',            ('shopify',    'CMS',    'Shopify')),
            ('x-drupal-cache',  '',            ('drupal',     'CMS',    'Drupal')),
            ('x-generator',     'drupal',      ('drupal',     'CMS',    'Drupal')),
            ('x-powered-by',    'php',         ('php',        'custom', 'PHP')),
            ('x-powered-by',    'asp.net',     ('aspnet',     'custom', 'ASP.NET')),
            ('x-powered-by',    'express',     ('express',    'custom', 'Express.js')),
            ('x-powered-by',    'next.js',     ('nextjs',     'frontend', 'Next.js')),
            ('x-powered-by',    'wp engine',   ('wpengine',   'custom', 'WP Engine')),
            ('x-aspnet-version','',            ('aspnet',     'custom', 'ASP.NET')),
            ('server',          'cloudflare',  ('cloudflare', 'custom', 'Cloudflare')),
            ('server',          'nginx',       ('nginx',      'custom', 'Nginx')),
            ('server',          'apache',      ('apache',     'custom', 'Apache')),
            ('server',          'microsoft-iis',('iis',       'custom', 'Microsoft IIS')),
            ('server',          'litespeed',   ('litespeed',  'custom', 'LiteSpeed')),
            ('server',          'gws',         ('gcp',        'custom', 'Google Cloud')),
            ('server',          'awselb',      ('aws_elb',    'custom', 'AWS Elastic Load Balancing')),
            ('server',          'cowboy',      ('heroku',     'custom', 'Heroku')),
        ]
        for hname, needle, (sid, stype, name) in rules:
            val = hdr.get(hname)
            if val is None:
                continue
            if needle == '' or needle in val:
                add_sys(sid, stype, name, 0.9 if needle == '' else 0.85, hname, val)
        return systems

    def _detect_systems_generic(self, html: str, headers: Any, cookies: Any) -> List[DetectedSystem]:
        """
        Replicates builtwith.builtwith() data-driven logic natively using the
        technologies.json database to avoid hanging on large minified JS files.
        """
        import re

        def _match(pattern: Any, value: str) -> bool:
            # Wappalyzer appends "\;tag:..." metadata to patterns; strip it, and
            # tolerate invalid regexes in the dataset rather than failing the scan.
            if not value:
                return False
            bare = str(pattern).split("\\;")[0]
            if not bare:
                return True  # presence-only signal (e.g. header simply exists)
            try:
                return re.search(bare, value, re.IGNORECASE) is not None
            except re.error:
                return False

        def _match_snippet(pattern, value):
            """Like _match but returns the matched text so evidence shown in the
            UI ("detected via html") is human-readable, never raw regex source."""
            if not value:
                return None
            bare = str(pattern).split("\\;")[0]
            if not bare:
                return value[:80]
            try:
                m = re.search(bare, value, re.IGNORECASE)
            except re.error:
                return None
            if not m:
                return None
            snippet = m.group(0).strip()
            if not snippet:
                return str(bare)[:80]
            return (snippet[:117] + "...") if len(snippet) > 120 else snippet

        systems_map = {}
        headers_dict = {str(k).lower(): str(v).lower() for k, v in dict(headers).items()}
        cookies_dict = {str(k).lower(): str(v).lower() for k, v in dict(cookies).items()}
        
        # Limit html size to prevent catastrophic backtracking on minified bundles
        # 100KB silently dropped signatures deep in heavy storefront pages
        # (e.g. gucci.com); 500KB keeps regexes safe but sees the whole document.
        html_safe = html[:500000].lower() if html else ""
        
        # Extract meta tags once
        metas = {}
        script_srcs: List[str] = []
        if html_safe:
            meta_pattern = re.compile(r'<meta[^>]*?name=[\'\"]([^>]*?)[\'\"][^>]*?content=[\'\"]([^>]*?)[\'\"][^>]*?>', re.IGNORECASE)
            metas = dict(meta_pattern.findall(html_safe))
            # Extract <script src> URLs for Wappalyzer scriptSrc (URL-anchored) signatures.
            script_srcs = re.findall(r'<script[^>]+\bsrc=[\'\"]([^\'\"]+)[\'\"]', html_safe)

        def add_sys(app_name, app_spec, conf, ev_type, ev_val):
            # Map common category names to SystemType literals
            valid_types = ['CMS', 'CRM', 'OMS', 'PIM', 'DAM', 'ERP', 'HRM', 'LMS', 'analytics', 'payment_gateway', 'shipping', 'tax', 'inventory', 'marketing_automation', 'email_service', 'search', 'database', 'cache', 'cdc', 'message_queue', 'api_gateway', 'auth', 'billing', 'support', 'chat', 'video', 'voice', 'iot', 'ai_ml', 'custom']
            # Curated overlay entries may declare an explicit SystemType; otherwise
            # derive it from the technology's category.
            explicit = app_spec.get("type")
            if explicit in valid_types:
                sys_type = explicit
            else:
                cat_id = str(app_spec.get("cats", [1])[0])
                cat_name = self.tech_data.get("categories", {}).get(cat_id, "custom")
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
                    if _match(h_regex, h_val):
                        add_sys(app_name, app_spec, 0.95, 'header', h_val or h_name)
                        matched = True
            
            # 2. Check Cookies
            if not matched and 'cookies' in app_spec:
                for c_name, c_regex in app_spec['cookies'].items():
                    c_val = cookies_dict.get(c_name.lower())
                    if c_name.lower() in cookies_dict and _match(c_regex or ".*", c_val or c_name):
                        add_sys(app_name, app_spec, 0.95, 'cookie', c_name)
                        matched = True
                        
            # 3. Check HTML (includes scripts)
            if not matched and 'html' in app_spec and html_safe:
                patterns = app_spec['html']
                if not isinstance(patterns, list):
                    patterns = [patterns]
                for pattern in patterns:
                    snippet = _match_snippet(pattern, html_safe)
                    if snippet is not None:
                        add_sys(app_name, app_spec, 0.90, 'html', snippet)
                        matched = True
                        break

            # 3b. Check <script src> URLs (Wappalyzer scriptSrc — often URL-anchored)
            if not matched and 'scriptSrc' in app_spec and script_srcs:
                patterns = app_spec['scriptSrc']
                if not isinstance(patterns, list):
                    patterns = [patterns]
                for pattern in patterns:
                    hit = next((src for src in script_srcs if _match(pattern, src)), None)
                    if hit:
                        add_sys(app_name, app_spec, 0.90, 'script', hit)
                        matched = True
                        break

            # 4. Check Meta tags
            if not matched and 'meta' in app_spec and metas:
                for m_name, m_regex in app_spec['meta'].items():
                    m_val = metas.get(m_name)
                    if _match(m_regex, m_val):
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
            # Header value matching for technology detection (not URL validation).
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
        # Render.com detection (common PaaS for Python/Node backends)
        if 'onrender.com' in headers_dict.get('x-render-origin-server', '') \
                or 'render' in headers_dict.get('server', '').lower() \
                or 'x-render-id' in headers_dict:
            add_stack(hosting, 'Render')
        # FastAPI / Python backend signals
        if 'fastapi' in headers_dict.get('x-powered-by', '').lower() \
                or headers_dict.get('server', '').lower().startswith('uvicorn') \
                or 'uvicorn' in headers_dict.get('via', '').lower():
            add_stack(frameworks, 'FastAPI')
            add_stack(languages, 'Python')
        # Generic Python ASGI/WSGI
        if 'gunicorn' in headers_dict.get('server', '').lower() \
                or 'waitress' in headers_dict.get('server', '').lower() \
                or 'hypercorn' in headers_dict.get('server', '').lower():
            add_stack(languages, 'Python')
        # React — broader pattern: CRA bundles use static/js/main.*.js
        if 'react' in html_lower \
                or 'static/js/main.' in html_lower \
                or '__webpack_require__' in html_lower \
                or 'data-reactroot' in html_lower \
                or '_reactfiber' in html_lower:
            add_stack(frameworks, 'React')
            add_stack(languages, 'JavaScript')
        # Vite / modern bundlers
        if 'vite' in html_lower or '/@vite/' in html_lower or '/assets/index.' in html_lower:
            add_stack(frameworks, 'Vite')
            add_stack(languages, 'JavaScript')
        # Tailwind CSS
        if 'tailwind' in html_lower or 'tw-' in html_lower:
            add_stack(frameworks, 'Tailwind CSS')
        # MongoDB / document DB hints in error messages or meta
        if 'mongodb' in html_lower or 'mongoose' in html_lower:
            add_stack(databases, 'MongoDB')
        # SQLite hint (often in dev/small backends)
        if 'sqlite' in html_lower:
            add_stack(databases, 'SQLite')
        # OpenAI-compatible API signals
        if '/v1/chat/completions' in html_lower or 'openai-compatible' in html_lower \
                or 'ollama' in html_lower:
            add_stack(frameworks, 'OpenAI-compatible API')
        # GitHub Pages / Actions signals
        if 'github.io' in headers_dict.get('x-github-request-id', '') \
                or 'github' in headers_dict.get('server', '').lower():
            add_stack(hosting, 'GitHub Pages')
            
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

    def __init__(self, company_id: Optional[str] = None, github_token: Optional[str] = None):
        """
        Initialize the repository scanner.
        
        Args:
            company_id: Optional company ID for context
            github_token: Optional GitHub personal access token for authenticated API calls
        """
        self.company_id = company_id
        self.github_token = github_token
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
        started_at = datetime.now(timezone.utc)
        
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
                    completed_at=datetime.now(timezone.utc).isoformat()
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
                completed_at=datetime.now(timezone.utc).isoformat()
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

        if _hostname_matches(hostname, 'github.com'):
            return 'github'
        elif _hostname_matches(hostname, 'gitlab.com'):
            return 'gitlab'
        elif _hostname_matches(hostname, 'bitbucket.org'):
            return 'bitbucket'
        elif _hostname_matches(hostname, 'azure.com', 'dev.azure.com'):
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
                completed_at=datetime.now(timezone.utc).isoformat()
            )
        
        owner = parts[0]
        repo_name = parts[1]
        
        # Try to fetch repository information from GitHub API
        # Note: This requires a GitHub token for private repos
        github_api_url = f"https://api.github.com/repos/{owner}/{repo_name}"
        
        # Build headers with optional GitHub token for authenticated API calls.
        # Without a token, GitHub's unauthenticated rate limit is 60 requests/hour
        # (which is easily exhausted), causing 403/rate-limit errors.
        _req_headers = {"User-Agent": self.user_agent}
        if self.github_token:
            _req_headers["Authorization"] = f"Bearer {self.github_token}"
        
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers=_req_headers
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
                    
                    completed_at = datetime.now(timezone.utc)
                    
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
                        completed_at=datetime.now(timezone.utc).isoformat()
                    )
                elif response.status_code == 403:
                    return RepoScanResult(
                        scan_id=scan_id,
                        repo_url=repo_url,
                        company_id=self.company_id,
                        status="failed",
                        errors=["Rate limit exceeded or private repository without auth"],
                        started_at=started_at.isoformat(),
                        completed_at=datetime.now(timezone.utc).isoformat()
                    )
                else:
                    return RepoScanResult(
                        scan_id=scan_id,
                        repo_url=repo_url,
                        company_id=self.company_id,
                        status="failed",
                        errors=[f"GitHub API error: {response.status_code}"],
                        started_at=started_at.isoformat(),
                        completed_at=datetime.now(timezone.utc).isoformat()
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
                completed_at=datetime.now(timezone.utc).isoformat()
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

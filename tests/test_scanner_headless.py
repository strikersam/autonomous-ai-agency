"""Tests for the scanner's headless-render fallback (JS-rendered / bot-protected sites)
and the CNAME/CDN DNS detection (BuiltWith-style off-site identification).

These validate the *logic* without a real browser or live network (the CI/sandbox
can't download Chromium or reach external hosts): detection works on a rendered
DOM, `_render_html` degrades gracefully when rendering is disabled or the browser
binary is unavailable, the full `scan_website` flow invokes the render fallback,
and CNAME chains are mapped to the hosting/CDN platform.
"""
from __future__ import annotations

import asyncio
import sys
import types

import pytest


def _scanner():
    try:
        from services.scanner import WebsiteScanner
    except (ImportError, ModuleNotFoundError):
        pytest.skip("scanner not importable")
    return WebsiteScanner(company_id="test_co")


class TestRenderedDomDetection:
    """The whole point of the headless pass: tech markers that only appear in
    the JS-rendered DOM (e.g. a Salesforce Commerce Cloud `demandware.static`
    script URL) must be detectable once we feed the rendered HTML through the
    existing signature engine."""

    def test_detects_sfcc_from_rendered_script_src(self) -> None:
        scanner = _scanner()
        # Representative of what a real browser would expose for a Demandware/
        # SFCC storefront (Gucci's platform) after JS runs — the static fetch
        # of such sites often returns a bot wall with none of this.
        rendered_html = (
            "<html><head>"
            '<script src="https://www.example.com/on/demandware.static/Sites-x/foo.js"></script>'
            "</head><body>hello</body></html>"
        )
        systems = scanner._detect_systems_generic(rendered_html, {}, {})
        names = {s.name for s in systems}
        assert "Salesforce Commerce Cloud" in names, names

    def test_detects_from_server_header(self) -> None:
        scanner = _scanner()
        systems = scanner._detect_systems_generic(
            "<html></html>", {"Server": "Demandware eCommerce Server"}, {}
        )
        assert "Salesforce Commerce Cloud" in {s.name for s in systems}


class TestSubrequestSsrfGuard:
    def test_blocks_internal_and_metadata_hosts(self) -> None:
        try:
            from services.scanner import _is_blocked_host
        except (ImportError, ModuleNotFoundError):
            pytest.skip("scanner not importable")
        # Blocked: loopback, cloud metadata, private + link-local literals, *.internal
        for bad in (
            "http://127.0.0.1/", "http://localhost/admin",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.5/", "http://192.168.1.1/", "http://[::1]/",
            "http://db.internal/", "http://foo.local/",
        ):
            assert _is_blocked_host(bad) is True, bad
        # Allowed: ordinary public hostnames (resolved per-asset would be public)
        for ok_url in ("https://www.gucci.com/", "https://cdn.example.com/a.js"):
            assert _is_blocked_host(ok_url) is False, ok_url

    def test_empty_and_unparseable_hosts_fail_closed(self) -> None:
        """A URL with no hostname (file://, malformed) must be blocked, and
        data:/blob:/about: schemes (browser-internal, no network) allowed."""
        try:
            from services.scanner import _is_blocked_host
        except (ImportError, ModuleNotFoundError):
            pytest.skip("scanner not importable")
        for blocked in ("file:///etc/passwd", "http://", "://nohost"):
            assert _is_blocked_host(blocked) is True, blocked
        for allowed in ("data:text/html,<b>x</b>", "about:blank", "blob:https://x/y"):
            assert _is_blocked_host(allowed) is False, allowed


class TestRenderGating:
    def test_render_disabled_returns_none(self, monkeypatch) -> None:
        scanner = _scanner()
        monkeypatch.setenv("SCANNER_HEADLESS_RENDER", "off")
        result = asyncio.run(scanner._render_html("https://example.com"))
        assert result is None

    def test_render_graceful_without_browser(self, monkeypatch) -> None:
        """With rendering enabled but the browser launch failing (CI/sandbox has
        no Chromium binary), `_render_html` must return None rather than raise so
        scans still succeed. We make this deterministic by injecting a fake
        `playwright.async_api` whose `async_playwright()` raises on launch."""
        scanner = _scanner()
        monkeypatch.setenv("SCANNER_HEADLESS_RENDER", "auto")

        fake_api = types.ModuleType("playwright.async_api")

        class _FailingCM:
            async def __aenter__(self):
                raise RuntimeError("no chromium binary")

            async def __aexit__(self, *a):
                return False

        fake_api.async_playwright = lambda: _FailingCM()
        fake_pkg = types.ModuleType("playwright")
        fake_pkg.async_api = fake_api
        monkeypatch.setitem(sys.modules, "playwright", fake_pkg)
        monkeypatch.setitem(sys.modules, "playwright.async_api", fake_api)

        result = asyncio.run(scanner._render_html("https://example.com"))
        assert result is None


class TestRenderFallbackMerge:
    """The scan flow must invoke the render fallback when static detection is
    empty and merge whatever the rendered DOM reveals — exercised through the
    real `scan_website` entry point (not a hand-rolled re-implementation)."""

    def test_fallback_merges_rendered_systems(self, monkeypatch) -> None:
        scanner = _scanner()
        import services.scanner as scanner_mod

        # Public target passes the SSRF guard; DNS finds nothing off-site.
        monkeypatch.setattr(scanner_mod, "_is_safe_url", lambda url: True)
        monkeypatch.setattr(scanner, "_analyze_dns", lambda domain: [])

        # Fake the HTTP fetch: a bot wall — HTTP 200 but no tech markers — so
        # static detection comes back empty and the headless fallback fires.
        class _FakeResp:
            text = "<html><body>Access denied</body></html>"
            headers: dict = {}
            cookies: dict = {}
            status_code = 200

        class _FakeSession:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, *a, **k):
                return _FakeResp()

        fake_curl = types.ModuleType("curl_cffi")
        fake_curl_requests = types.ModuleType("curl_cffi.requests")
        fake_curl_requests.AsyncSession = _FakeSession
        fake_curl.requests = fake_curl_requests
        monkeypatch.setitem(sys.modules, "curl_cffi", fake_curl)
        monkeypatch.setitem(sys.modules, "curl_cffi.requests", fake_curl_requests)

        # The rendered DOM exposes the SFCC marker the static body hid.
        async def fake_render(url):
            return (
                '<script src="https://x/on/demandware.static/Sites-x/a.js"></script>',
                {},
                {},
            )

        monkeypatch.setattr(scanner, "_render_html", fake_render)

        result = asyncio.run(scanner.scan_website("https://example.com"))
        assert result.status == "success", result.errors
        assert "Salesforce Commerce Cloud" in {s.name for s in result.detected_systems}


class TestDnsCdnDetection:
    """BuiltWith-style off-site identification: a CNAME chain that points at a
    known CDN/hosting/SaaS platform is mapped to that platform even when the
    site's HTML is behind a bot wall (DNS isn't)."""

    def _patch_cname(self, monkeypatch, target: str):
        dns_resolver = pytest.importorskip("dns.resolver")

        class _Rdata:
            def __init__(self, t: str):
                self._t = t

            @property
            def target(self):
                return self._t

            def __str__(self):
                return self._t

        def fake_resolve(host, rdtype):
            if rdtype == "CNAME":
                return [_Rdata(target)]
            raise Exception("no record")

        monkeypatch.setattr(dns_resolver, "resolve", fake_resolve)

    def test_cloudfront_cname_detected(self, monkeypatch) -> None:
        scanner = _scanner()
        self._patch_cname(monkeypatch, "d111abcdef8.cloudfront.net.")
        systems = scanner._analyze_dns("example.com")
        names = {s.name for s in systems}
        assert "AWS CloudFront (CDN)" in names, names

    def test_shopify_cname_detected(self, monkeypatch) -> None:
        scanner = _scanner()
        self._patch_cname(monkeypatch, "shops.myshopify.com.")
        systems = scanner._analyze_dns("example.com")
        names = {s.name for s in systems}
        assert "Shopify" in names, names

    def test_unknown_cname_yields_no_false_positive(self, monkeypatch) -> None:
        scanner = _scanner()
        self._patch_cname(monkeypatch, "internal-lb.example-corp.com.")
        systems = scanner._analyze_dns("example.com")
        # No CDN/hosting platform should be inferred from an unrecognised target.
        names = {s.name for s in systems}
        assert "AWS CloudFront (CDN)" not in names
        assert "Shopify" not in names


class TestBuiltWithFallback:
    """Last-resort fallback that asks builtwith.com what it already knows about a
    domain (no API key — scrapes the public page), for sites we can't fingerprint
    live (Akamai-fronted JS storefronts). Hardened vs. the ecrmnn/noname01 repos:
    instead of depending on BuiltWith's (long-since-redesigned) `.techItem` CSS,
    it cross-references the page against our own app catalog, so it survives
    markup changes. The live fetch is stubbed here."""

    def _stub_fetch(self, monkeypatch, *, status=200, body=""):
        """Replace curl_cffi's AsyncSession.get with a canned response."""
        import sys as _sys
        import types as _types

        class _Resp:
            status_code = status
            text = body

        class _Session:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, *a, **k):
                return _Resp()

        fake = _types.ModuleType("curl_cffi")
        fake_req = _types.ModuleType("curl_cffi.requests")
        fake_req.AsyncSession = _Session
        fake.requests = fake_req
        monkeypatch.setitem(_sys.modules, "curl_cffi", fake)
        monkeypatch.setitem(_sys.modules, "curl_cffi.requests", fake_req)

    def test_catalog_cross_reference_detects_known_tech(self, monkeypatch) -> None:
        scanner = _scanner()
        monkeypatch.setenv("SCANNER_BUILTWITH_FALLBACK", "auto")
        # A BuiltWith-style profile page mentioning known platforms by name,
        # without any of the legacy `.techItem` markup — the catalog pass must
        # still recover them.
        page = (
            "<html><body><h2>Technology Profile</h2>"
            "<div>This site uses Shopify for ecommerce and Cloudflare for CDN, "
            "with Google Analytics for tracking.</div></body></html>"
        )
        self._stub_fetch(monkeypatch, body=page)
        systems = asyncio.run(scanner._query_builtwith("example.com"))
        names = {s.name for s in systems}
        assert "Shopify" in names, names
        # Confidence is below live detection (it's a 3rd-party historical signal).
        assert all(s.confidence <= 0.85 for s in systems)
        # Evidence is attributed to builtwith.com, not the target site.
        assert any(ev.location == "builtwith.com" for s in systems for ev in s.evidence)

    def test_disabled_via_env_returns_empty(self, monkeypatch) -> None:
        scanner = _scanner()
        monkeypatch.setenv("SCANNER_BUILTWITH_FALLBACK", "off")
        # Even with a fetch available, the kill-switch must short-circuit.
        self._stub_fetch(monkeypatch, body="<html>Shopify</html>")
        assert asyncio.run(scanner._query_builtwith("example.com")) == []

    def test_graceful_on_fetch_failure(self, monkeypatch) -> None:
        scanner = _scanner()
        monkeypatch.setenv("SCANNER_BUILTWITH_FALLBACK", "auto")
        # Non-200 (e.g. BuiltWith's own bot wall) → empty, never raises.
        self._stub_fetch(monkeypatch, status=403, body="blocked")
        # Also stub headless render so the fallback cannot recover via Playwright.
        async def _no_render(url):
            return None
        monkeypatch.setattr(scanner, "_render_html", _no_render)
        assert asyncio.run(scanner._query_builtwith("example.com")) == []

    def test_empty_domain_returns_empty(self, monkeypatch) -> None:
        scanner = _scanner()
        monkeypatch.setenv("SCANNER_BUILTWITH_FALLBACK", "auto")
        assert asyncio.run(scanner._query_builtwith("")) == []


# A representative Cloudflare "Just a moment" interstitial — what a plain fetch
# of a bot-protected site (including builtwith.com itself today) returns.
CLOUDFLARE_CHALLENGE = (
    "<!DOCTYPE html><html><head><title>Just a moment...</title>"
    '<meta http-equiv="refresh" content="0">'
    '<script src="/cdn-cgi/challenge-platform/h/g/orchestrate/chl_page/v1"></script>'
    "</head><body><div class='cf-browser-verification'>"
    "Checking your browser before accessing. Enable JavaScript and cookies to continue."
    "</div></body></html>"
)

# A real BuiltWith results page (no challenge markers, content-rich).
BUILTWITH_RESULTS = (
    "<html><body><h1>gucci.com Technology Profile</h1>"
    "<div class='content'>Detected: Salesforce Commerce Cloud, Akamai, "
    "Google Analytics, and more across this storefront.</div>"
    + ("<p>filler content to make this a realistically large page. </p>" * 50)
    + "</body></html>"
)


class TestBotChallengeDetection:
    """`_looks_like_bot_challenge` is the gate that stops us parsing a CAPTCHA /
    Cloudflare interstitial as if it were results — which would both yield
    garbage and falsely 'detect' the challenge vendor as the target's tech."""

    def _fn(self):
        try:
            from services.scanner import _looks_like_bot_challenge
        except (ImportError, ModuleNotFoundError):
            pytest.skip("scanner not importable")
        return _looks_like_bot_challenge

    def test_cloudflare_interstitial_flagged(self) -> None:
        assert self._fn()(CLOUDFLARE_CHALLENGE) is True

    def test_empty_body_flagged(self) -> None:
        assert self._fn()("") is True

    def test_recaptcha_wall_flagged(self) -> None:
        html = ("<html><head><script src='https://www.google.com/recaptcha/api.js'>"
                "</script></head><body>verify you are human</body></html>")
        assert self._fn()(html) is True

    def test_real_results_page_not_flagged(self) -> None:
        assert self._fn()(BUILTWITH_RESULTS) is False

    def test_long_content_page_mentioning_access_denied_not_flagged(self) -> None:
        # A large content page that merely contains the words "access denied"
        # in copy must not be misclassified as a challenge.
        html = "<html><body>" + ("normal content. " * 3000) + "access denied" + "</body></html>"
        assert self._fn()(html) is False


class TestBotProtectionResilience:
    """End-to-end resilience for bot-protected sites — the regression guard the
    user asked for. Builtwith.com is itself Cloudflare-fronted, so the fallback
    must (a) recognise a challenge page and NOT parse it, (b) escalate from
    curl_cffi to the headless browser, and (c) never fabricate a 'Cloudflare'
    detection from a 'Just a moment' wall. All network/browser is stubbed."""

    def _stub_curl(self, monkeypatch, *, status=200, body=""):
        import sys as _sys
        import types as _types

        class _Resp:
            status_code = status
            text = body

        class _Session:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, *a, **k):
                return _Resp()

        fake = _types.ModuleType("curl_cffi")
        fake_req = _types.ModuleType("curl_cffi.requests")
        fake_req.AsyncSession = _Session
        fake.requests = fake_req
        monkeypatch.setitem(_sys.modules, "curl_cffi", fake)
        monkeypatch.setitem(_sys.modules, "curl_cffi.requests", fake_req)

    def test_challenge_page_is_not_parsed_as_results(self, monkeypatch) -> None:
        """The critical guard: when both tiers hit a Cloudflare wall, the
        fallback returns NOTHING — it must not parse the interstitial (which
        would falsely detect Cloudflare/reCAPTCHA as the target's stack)."""
        scanner = _scanner()
        monkeypatch.setenv("SCANNER_BUILTWITH_FALLBACK", "auto")
        # Tier 1 (curl_cffi) returns the challenge…
        self._stub_curl(monkeypatch, body=CLOUDFLARE_CHALLENGE)
        # …and Tier 2 (headless) also can't clear it (hard CAPTCHA).
        async def fake_render(url):
            return (CLOUDFLARE_CHALLENGE, {}, {})
        monkeypatch.setattr(scanner, "_render_html", fake_render)

        systems = asyncio.run(scanner._query_builtwith("gucci.com"))
        assert systems == [], [s.name for s in systems]

    def test_headless_escalation_recovers_after_curl_challenge(self, monkeypatch) -> None:
        """Tier 1 hits the Cloudflare wall; the headless browser clears the
        automatic JS challenge and returns the real results page, which we then
        parse via the catalog cross-reference."""
        scanner = _scanner()
        monkeypatch.setenv("SCANNER_BUILTWITH_FALLBACK", "auto")
        self._stub_curl(monkeypatch, body=CLOUDFLARE_CHALLENGE)  # tier 1 blocked

        async def fake_render(url):
            return (BUILTWITH_RESULTS, {}, {})  # tier 2 clears it
        monkeypatch.setattr(scanner, "_render_html", fake_render)

        systems = asyncio.run(scanner._query_builtwith("gucci.com"))
        names = {s.name for s in systems}
        assert "Salesforce Commerce Cloud" in names, names

    def test_thin_static_detection_still_escalates_to_render(self, monkeypatch) -> None:
        """gucci.com / workers.dev regression: a bot-walled or JS-rendered site
        leaks a *couple* of signals statically, so `detected_systems` was non-empty
        and the old `not detected_systems` gate skipped the headless + BuiltWith
        fallbacks — the PIM/CRM behind the JS wall (e.g. Akeneo) stayed invisible.
        Detection below SCANNER_RENDER_MIN_SYSTEMS must still escalate and merge."""
        scanner = _scanner()
        import services.scanner as scanner_mod
        from models.company_graph import DetectedSystem, Evidence
        monkeypatch.setattr(scanner_mod, "_is_safe_url", lambda url: True)
        monkeypatch.setattr(scanner, "_analyze_dns", lambda domain: [])
        monkeypatch.setenv("SCANNER_RENDER_MIN_SYSTEMS", "5")

        def _sys(name: str) -> DetectedSystem:
            return DetectedSystem(
                system_type="custom", name=name, confidence=0.9,
                evidence=[Evidence(type="html", value=name, location="page", confidence=0.9)],
            )

        def fake_detect(html, headers, cookies):
            # The rendered DOM exposes a third system the thin static body hid.
            if "RENDERED_DOM" in (html or ""):
                return [_sys("Cloudflare"), _sys("Google Analytics"), _sys("Akeneo")]
            return [_sys("Cloudflare"), _sys("Google Analytics")]  # only 2 statically

        monkeypatch.setattr(scanner, "_detect_systems_generic", fake_detect)

        class _Resp:
            def __init__(self) -> None:
                self.text = "<html><body>thin storefront</body></html>"
                self.headers: dict = {}
                self.cookies: dict = {}
                self.status_code = 200

        class _Session:
            def __init__(self, *a, **k):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, *a, **k):
                return _Resp()

        fake = types.ModuleType("curl_cffi")
        fake_req = types.ModuleType("curl_cffi.requests")
        fake_req.AsyncSession = _Session
        fake.requests = fake_req
        monkeypatch.setitem(sys.modules, "curl_cffi", fake)
        monkeypatch.setitem(sys.modules, "curl_cffi.requests", fake_req)

        async def fake_render(url):
            return ("<html>RENDERED_DOM</html>", {}, {})
        monkeypatch.setattr(scanner, "_render_html", fake_render)

        result = asyncio.run(scanner.scan_website("https://gucci.com"))
        assert result.status == "success", result.errors
        names = {s.name for s in result.detected_systems}
        assert "Akeneo" in names, names  # only reachable via the rendered DOM

    def test_scan_website_falls_through_to_builtwith_when_live_blocked(self, monkeypatch) -> None:
        """Full flow for an Akamai-walled site: live fetch returns a bot wall,
        headless render of the *target* yields nothing, DNS is empty — so the
        scan falls through to the BuiltWith fallback, which recovers the stack.
        This is the gucci.com scenario, end to end."""
        scanner = _scanner()
        import services.scanner as scanner_mod
        monkeypatch.setenv("SCANNER_BUILTWITH_FALLBACK", "auto")
        monkeypatch.setattr(scanner_mod, "_is_safe_url", lambda url: True)
        monkeypatch.setattr(scanner, "_analyze_dns", lambda domain: [])

        # Live fetch of the target: an Akamai bot wall (200 but no markers).
        class _Resp:
            text = "<html><body>Access Denied - Reference #18.abc</body></html>"
            headers: dict = {}
            cookies: dict = {}
            status_code = 200

        class _Session:
            def __init__(self, *a, **k):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, *a, **k):
                return _Resp()

        fake = types.ModuleType("curl_cffi")
        fake_req = types.ModuleType("curl_cffi.requests")
        fake_req.AsyncSession = _Session
        fake.requests = fake_req
        monkeypatch.setitem(sys.modules, "curl_cffi", fake)
        monkeypatch.setitem(sys.modules, "curl_cffi.requests", fake_req)

        # Headless render of the *target* also yields nothing usable…
        async def fake_render_target(url):
            return None
        monkeypatch.setattr(scanner, "_render_html", fake_render_target)
        # …but the BuiltWith fallback returns a real profile.
        async def fake_builtwith(domain):
            from models.company_graph import DetectedSystem, Evidence
            return [DetectedSystem(
                system_type="CMS", name="Salesforce Commerce Cloud", confidence=0.80,
                evidence=[Evidence(type="builtwith", value="builtwith.com",
                                   location="builtwith.com", confidence=0.80)],
            )]
        monkeypatch.setattr(scanner, "_query_builtwith", fake_builtwith)

        result = asyncio.run(scanner.scan_website("https://gucci.com"))
        assert result.status == "success", result.errors
        assert "Salesforce Commerce Cloud" in {s.name for s in result.detected_systems}

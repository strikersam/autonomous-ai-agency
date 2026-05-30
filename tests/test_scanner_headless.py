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

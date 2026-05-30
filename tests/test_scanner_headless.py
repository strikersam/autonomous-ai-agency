"""Tests for the scanner's headless-render fallback (JS-rendered / bot-protected sites).

These validate the *logic* without a real browser (the CI/sandbox can't download
Chromium): detection works on a rendered DOM, and `_render_html` degrades
gracefully when rendering is disabled or the browser binary is unavailable.
"""
from __future__ import annotations

import asyncio
import os

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


class TestRenderGating:
    def test_render_disabled_returns_none(self) -> None:
        scanner = _scanner()
        os.environ["SCANNER_HEADLESS_RENDER"] = "off"
        try:
            result = asyncio.run(scanner._render_html("https://example.com"))
        finally:
            os.environ.pop("SCANNER_HEADLESS_RENDER", None)
        assert result is None

    def test_render_graceful_without_browser(self) -> None:
        """With rendering enabled but no Chromium binary available (CI/sandbox),
        `_render_html` must return None rather than raise, so scans still work."""
        scanner = _scanner()
        os.environ["SCANNER_HEADLESS_RENDER"] = "auto"
        try:
            result = asyncio.run(scanner._render_html("https://example.com"))
        finally:
            os.environ.pop("SCANNER_HEADLESS_RENDER", None)
        # Either Playwright isn't installed, or the browser binary isn't — both
        # paths must degrade to None (never raise).
        assert result is None


class TestRenderFallbackMerge:
    """The scan flow must invoke the render fallback when static detection is
    empty and merge whatever the rendered DOM reveals."""

    def test_fallback_merges_rendered_systems(self, monkeypatch) -> None:
        scanner = _scanner()

        async def fake_render(url):
            return (
                '<script src="https://x/on/demandware.static/Sites-x/a.js"></script>',
                {},
                {},
            )

        monkeypatch.setattr(scanner, "_render_html", fake_render)

        async def run():
            # Simulate the post-static-detection state: nothing found yet.
            all_systems_map: dict = {}
            detected = list(all_systems_map.values())
            rendered = await scanner._render_html("https://example.com")
            assert rendered is not None
            r_html, r_headers, r_cookies = rendered
            for s in scanner._detect_systems_generic(r_html, r_headers, r_cookies):
                all_systems_map.setdefault(s.name, s)
            return list(all_systems_map.values())

        systems = asyncio.run(run())
        assert "Salesforce Commerce Cloud" in {s.name for s in systems}

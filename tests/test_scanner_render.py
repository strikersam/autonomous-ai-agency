"""Offline tests for the optional headless-render scan path.

The live browser cannot run in CI (no Chromium / restricted egress), so these cover
the pure logic: JS-path collection, SSRF request filtering, js-rule matching, and the
graceful-fallback behaviour of render() when no browser is available.
"""
import pytest

from services import scanner as scanner_mod
from services.scanner import WebsiteScanner
from services.scanner_render import collect_js_paths, request_allowed, render


def test_collect_js_paths_covers_known_globals():
    scanner = WebsiteScanner()
    paths = set(collect_js_paths(scanner.tech_data))
    # Representative SPA/runtime globals from the Wappalyzer js rules.
    for expected in ["Shopify", "__NEXT_DATA__", "jQuery.fn.jquery", "Vue.version"]:
        assert expected in paths


def test_request_allowed_blocks_internal_and_bad_schemes():
    is_safe = scanner_mod._is_safe_url
    cache = {}
    # http(s) to internal/link-local is blocked
    assert request_allowed("http://127.0.0.1/x", is_safe, cache) is False
    assert request_allowed("http://169.254.169.254/latest/meta-data/", is_safe, cache) is False
    assert request_allowed("http://10.0.0.5/", is_safe, cache) is False
    # public IP allowed (numeric, no DNS needed)
    assert request_allowed("https://8.8.8.8/", is_safe, cache) is True
    # inline (non-network) schemes allowed; other schemes blocked
    assert request_allowed("data:text/html,hi", is_safe, cache) is True
    assert request_allowed("blob:https://x/y", is_safe, cache) is True
    assert request_allowed("ftp://example.com/", is_safe, cache) is False


def test_request_allowed_caches_per_host():
    calls = {"n": 0}

    def counting_is_safe(url):
        calls["n"] += 1
        return True

    cache = {}
    request_allowed("https://example.com/a", counting_is_safe, cache)
    request_allowed("https://example.com/b", counting_is_safe, cache)
    assert calls["n"] == 1  # second request hits the per-host cache


def test_detect_from_js_matches_runtime_globals():
    scanner = WebsiteScanner()
    js_values = {
        "Shopify": "[object Object]",   # presence-only rule
        "Vue.version": "3.4.21",        # regex ^(.+)$
        "jQuery.fn.jquery": "3.6.0",    # regex ([\d.]+)
    }
    systems = scanner._detect_from_js(js_values)
    names = {s.name.lower() for s in systems}
    assert "shopify" in names
    assert "vue.js" in names
    assert "jquery" in names
    for s in systems:
        assert s.evidence and s.evidence[0].type == "js"
        assert s.confidence == 0.95


def test_detect_from_js_empty():
    scanner = WebsiteScanner()
    assert scanner._detect_from_js({}) == []


@pytest.mark.asyncio
async def test_render_returns_none_when_browser_unavailable():
    # Target an internal host so that, even if a browser binary is present, the main
    # navigation is aborted by the SSRF filter -> render() returns None. With no
    # browser binary it also returns None. Either way: graceful fallback, no network.
    result = await render(
        "http://127.0.0.1:9/",
        is_safe_url=scanner_mod._is_safe_url,
        js_paths=[],
        timeout_ms=2000,
    )
    assert result is None

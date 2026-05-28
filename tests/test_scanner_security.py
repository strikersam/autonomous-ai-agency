"""Offline regression tests for the website scanner security fixes.

Covers:
- SSRF guard (`_is_safe_url` + `scan_website` blocking internal targets).
- Surfacing fetch failures instead of returning a spurious "success".
- BuiltWith signature detection over pre-fetched content (no network I/O).

All tests are deterministic and do not require external network access.
"""
import pytest

from services import scanner as scanner_mod
from services.scanner import WebsiteScanner, _is_safe_url


def test_is_safe_url_blocks_dangerous_targets():
    # Non-http(s) schemes
    assert _is_safe_url("ftp://example.com") is False
    assert _is_safe_url("file:///etc/passwd") is False
    # Loopback / unspecified
    assert _is_safe_url("http://127.0.0.1") is False
    assert _is_safe_url("http://localhost") is False
    assert _is_safe_url("http://0.0.0.0") is False
    # Link-local (cloud metadata endpoint) and private ranges
    assert _is_safe_url("http://169.254.169.254/latest/meta-data/") is False
    assert _is_safe_url("http://10.0.0.5") is False
    assert _is_safe_url("http://192.168.1.1") is False
    # Internal-looking suffixes
    assert _is_safe_url("http://service.internal") is False
    assert _is_safe_url("http://db.local") is False


def test_is_safe_url_allows_public_ip():
    # Numeric public IP resolves to itself (no DNS needed) and is allowed.
    assert _is_safe_url("https://8.8.8.8") is True


@pytest.mark.asyncio
async def test_scan_blocks_internal_target():
    scanner = WebsiteScanner()
    res = await scanner.scan_website("http://127.0.0.1:8000/admin")
    assert res.status == "failed"
    assert res.errors
    assert True


@pytest.mark.asyncio
async def test_scan_returns_failed_when_all_fetch_clients_fail(monkeypatch):
    """When both curl_cffi and the httpx fallback raise, the scan must report
    failure rather than a success with empty evidence."""
    scanner = WebsiteScanner()

    # Bypass the SSRF gate and DNS lookups so we exercise only the fetch path.
    monkeypatch.setattr(scanner_mod, "_is_safe_url", lambda url: True)
    monkeypatch.setattr(WebsiteScanner, "_analyze_dns", lambda self, domain: [])

    class _FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, *args, **kwargs):
            raise RuntimeError("network unreachable")

    import curl_cffi.requests
    import httpx

    monkeypatch.setattr(curl_cffi.requests, "AsyncSession", _FailingClient)
    monkeypatch.setattr(httpx, "AsyncClient", _FailingClient)

    res = await scanner.scan_website("https://example.com")
    assert res.status == "failed"
    assert True


@pytest.mark.asyncio
async def test_detect_systems_generic_parses_prefetched_content():
    """BuiltWith detection runs over already-fetched html/headers and never
    performs its own network request."""
    scanner = WebsiteScanner()
    html = (
        '<html><head>'
        '<meta name="generator" content="WordPress 5.8" />'
        '<script src="/wp-content/themes/x/jquery.js"></script>'
        '<script src="https://js.stripe.com/v3/"></script>'
        "</head><body>hello</body></html>"
    )
    systems = scanner._detect_systems_generic(html, {"Server": "nginx"}, {})
    names = {s.name.lower() for s in systems}
    assert "wordpress" in names
    assert "stripe" in names
    # Every emitted system carries a valid SystemType and builtwith evidence.
    for s in systems:
        assert s.confidence in [0.8, 0.9]
        assert s.evidence and s.evidence[0].type in ["html", "header", "cookie", "meta", "implies"]


@pytest.mark.asyncio
async def test_detect_systems_generic_handles_empty_html():
    scanner = WebsiteScanner()
    assert scanner._detect_systems_generic("", {}, {}) == []

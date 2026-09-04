"""Tests for agent/web_reach.py — zero-key internet access for agents."""
from __future__ import annotations

import types

import httpx
import pytest

from agent.capability_registry import ToolRegistry, _register_web_reach_tools
from agent.web_reach import UNTRUSTED_EXTERNAL, WebReach, unsafe_target_reason


# ---------------------------------------------------------------------------
# SSRF guard
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        "http://127.0.0.1:8001/admin",
        "http://localhost/",
        "http://0.0.0.0/",
    ],
)
def test_unsafe_target_reason_blocks_internal_addresses(url: str) -> None:
    assert unsafe_target_reason(url) is not None


def test_unsafe_target_reason_allows_public_https() -> None:
    assert unsafe_target_reason("https://example.com/page") is None


def test_unsafe_target_reason_rejects_bad_scheme() -> None:
    reason = unsafe_target_reason("ftp://example.com/x")
    assert reason is not None and "scheme" in reason


def test_fetch_page_refuses_internal_target_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    reach = WebReach()

    def _boom(*a, **k):
        raise AssertionError("must not attempt network I/O for a refused target")

    monkeypatch.setattr(httpx, "get", _boom)
    result = reach.fetch_page("http://127.0.0.1:9000/secret")
    assert result["ok"] is False
    assert "refused" in result["error"]


def test_safe_get_rejects_redirect_to_internal_address(monkeypatch: pytest.MonkeyPatch) -> None:
    reach = WebReach()

    class _FakeResponse:
        is_redirect = True
        next_request = types.SimpleNamespace(url="http://127.0.0.1/internal")
        headers: dict = {}

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            return _FakeResponse()

    monkeypatch.setattr(httpx, "Client", _FakeClient)
    with pytest.raises(ValueError, match="redirect target"):
        reach._safe_get("https://example.com/redirector")


# ---------------------------------------------------------------------------
# fetch_page — multi-strategy delegation to .github/scripts/fetch_url.py
# ---------------------------------------------------------------------------

def _fake_fetch_module(*, direct_meaningful: bool, jina_meaningful: bool = False) -> types.ModuleType:
    mod = types.ModuleType("fake_fetch_url")

    def fetch(url, timeout=30):
        if "r.jina.ai" in url:
            return ("<html>jina body long enough " + "x" * 600 + "</html>", url, 200)
        return ("<html>direct body</html>", url, 200)

    def strip_html(html):
        return html.replace("<html>", "").replace("</html>", "")

    def meaningful(text):
        if "jina body" in text:
            return jina_meaningful
        return direct_meaningful

    def extract_real_url(html):
        return None

    mod.fetch = fetch
    mod.strip_html = strip_html
    mod.meaningful = meaningful
    mod.extract_real_url = extract_real_url
    return mod


def _fake_video_module(*, is_video: bool = False, transcript: str = "") -> types.ModuleType:
    mod = types.ModuleType("fake_video_transcript")
    mod.is_video_url = lambda url: is_video
    mod.fetch_transcript = lambda url, timeout=30: transcript
    return mod


def test_fetch_page_succeeds_on_direct_strategy(monkeypatch: pytest.MonkeyPatch) -> None:
    reach = WebReach()
    monkeypatch.setattr(reach, "_video", lambda: _fake_video_module(is_video=False))
    monkeypatch.setattr(reach, "_fetch_mod", lambda: _fake_fetch_module(direct_meaningful=True))

    result = reach.fetch_page("https://example.com/article")
    assert result["ok"] is True
    assert result["source"] == "direct"
    assert "direct body" in result["text"]


def test_fetch_page_falls_back_to_jina_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    reach = WebReach()
    monkeypatch.setattr(reach, "_video", lambda: _fake_video_module(is_video=False))
    monkeypatch.setattr(
        reach, "_fetch_mod", lambda: _fake_fetch_module(direct_meaningful=False, jina_meaningful=True)
    )

    result = reach.fetch_page("https://example.com/spa-page")
    assert result["ok"] is True
    assert result["source"] == "jina_reader"


def test_fetch_page_reports_failure_when_all_strategies_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    reach = WebReach()
    monkeypatch.setattr(reach, "_video", lambda: _fake_video_module(is_video=False))
    monkeypatch.setattr(
        reach, "_fetch_mod", lambda: _fake_fetch_module(direct_meaningful=False, jina_meaningful=False)
    )

    result = reach.fetch_page("https://example.com/unreachable")
    assert result["ok"] is False
    assert "error" in result


def test_fetch_page_prefers_youtube_transcript(monkeypatch: pytest.MonkeyPatch) -> None:
    reach = WebReach()
    monkeypatch.setattr(
        reach, "_video", lambda: _fake_video_module(is_video=True, transcript="Title\n\nspoken words here")
    )

    def _boom(*a, **k):
        raise AssertionError("should not fall through to page-fetch strategies")

    monkeypatch.setattr(reach, "_fetch_mod", _boom)

    result = reach.fetch_page("https://www.youtube.com/watch?v=abc123")
    assert result["ok"] is True
    assert result["source"] == "youtube_transcript"
    assert "spoken words" in result["text"]


# ---------------------------------------------------------------------------
# youtube_transcript
# ---------------------------------------------------------------------------

def test_youtube_transcript_rejects_non_youtube_url() -> None:
    reach = WebReach()
    result = reach.youtube_transcript("https://example.com/not-a-video")
    assert result["ok"] is False


def test_youtube_transcript_returns_text(monkeypatch: pytest.MonkeyPatch) -> None:
    reach = WebReach()
    monkeypatch.setattr(
        reach, "_video", lambda: _fake_video_module(is_video=True, transcript="Title\n\ntranscript body")
    )
    result = reach.youtube_transcript("https://youtu.be/abc123")
    assert result["ok"] is True
    assert "transcript body" in result["text"]


# ---------------------------------------------------------------------------
# web_search — DuckDuckGo HTML (mocked, no live network)
# ---------------------------------------------------------------------------

_DDG_HTML = """
<html><body>
<a class="result-link" href="https://example.com/one">Result One</a>
<a class="result-link" href="https://example.com/two">Result Two</a>
</body></html>
"""


def test_search_web_parses_results(monkeypatch: pytest.MonkeyPatch) -> None:
    reach = WebReach()

    def fake_get(url, params=None, headers=None, timeout=None, follow_redirects=None):
        return httpx.Response(200, text=_DDG_HTML, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    result = reach.search_web("autonomous ai agents")
    assert result["ok"] is True
    assert len(result["results"]) == 2
    assert result["results"][0]["url"] == "https://example.com/one"


def test_search_web_rejects_empty_query() -> None:
    reach = WebReach()
    result = reach.search_web("   ")
    assert result["ok"] is False


def test_search_web_reports_failure_on_markup_change(monkeypatch: pytest.MonkeyPatch) -> None:
    reach = WebReach()

    def fake_get(url, params=None, headers=None, timeout=None, follow_redirects=None):
        return httpx.Response(200, text="<html><body>no matching markup</body></html>", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    result = reach.search_web("query with no parseable results")
    assert result["ok"] is False


# ---------------------------------------------------------------------------
# fetch_rss — stdlib XML, RSS 2.0 and Atom
# ---------------------------------------------------------------------------

_RSS2 = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>Post A</title><link>https://example.com/a</link></item>
<item><title>Post B</title><link>https://example.com/b</link></item>
</channel></rss>
"""

_ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Entry A</title><link href="https://example.com/entry-a"/></entry>
</feed>
"""


def test_fetch_rss_parses_rss2(monkeypatch: pytest.MonkeyPatch) -> None:
    reach = WebReach()
    monkeypatch.setattr(
        reach, "_safe_get", lambda url: httpx.Response(200, content=_RSS2.encode(), request=httpx.Request("GET", url))
    )
    result = reach.fetch_rss("https://example.com/feed.xml")
    assert result["ok"] is True
    assert len(result["entries"]) == 2
    assert result["entries"][0]["title"] == "Post A"


def test_fetch_rss_parses_atom(monkeypatch: pytest.MonkeyPatch) -> None:
    reach = WebReach()
    monkeypatch.setattr(
        reach, "_safe_get", lambda url: httpx.Response(200, content=_ATOM.encode(), request=httpx.Request("GET", url))
    )
    result = reach.fetch_rss("https://example.com/atom.xml")
    assert result["ok"] is True
    assert result["entries"][0]["url"] == "https://example.com/entry-a"


# ---------------------------------------------------------------------------
# Source-level untrusted-content tagging (defence-in-depth for the #1409 spike)
# ---------------------------------------------------------------------------

def test_every_content_result_is_tagged_untrusted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every content-bearing web-reach success carries trust=untrusted-external at the
    source, so a consumer other than the Executor prompt fence can still tell the
    payload is attacker-influenceable external text."""
    assert UNTRUSTED_EXTERNAL == "untrusted-external"
    reach = WebReach()

    # fetch_page (direct strategy)
    monkeypatch.setattr(reach, "_video", lambda: _fake_video_module(is_video=False))
    monkeypatch.setattr(reach, "_fetch_mod", lambda: _fake_fetch_module(direct_meaningful=True))
    page = reach.fetch_page("https://example.com/article")
    assert page["ok"] is True and page["trust"] == UNTRUSTED_EXTERNAL

    # youtube_transcript
    monkeypatch.setattr(
        reach, "_video", lambda: _fake_video_module(is_video=True, transcript="Title\n\nwords")
    )
    yt = reach.youtube_transcript("https://youtu.be/abc123")
    assert yt["ok"] is True and yt["trust"] == UNTRUSTED_EXTERNAL

    # search_web
    monkeypatch.setattr(
        httpx, "get",
        lambda url, params=None, headers=None, timeout=None, follow_redirects=None:
        httpx.Response(200, text=_DDG_HTML, request=httpx.Request("GET", url)),
    )
    search = reach.search_web("autonomous ai agents")
    assert search["ok"] is True and search["trust"] == UNTRUSTED_EXTERNAL

    # fetch_rss
    monkeypatch.setattr(
        reach, "_safe_get",
        lambda url: httpx.Response(200, content=_RSS2.encode(), request=httpx.Request("GET", url)),
    )
    rss = reach.fetch_rss("https://example.com/feed.xml")
    assert rss["ok"] is True and rss["trust"] == UNTRUSTED_EXTERNAL


def test_error_results_are_not_tagged(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tag marks external content; a refusal/error carries no payload, so no tag —
    consumers must not treat an error dict as trusted-or-untrusted content."""
    reach = WebReach()
    refused = reach.fetch_page("http://127.0.0.1:9000/secret")
    assert refused["ok"] is False
    assert "trust" not in refused


def test_fetch_rss_rejects_malformed_xml(monkeypatch: pytest.MonkeyPatch) -> None:
    reach = WebReach()
    monkeypatch.setattr(
        reach, "_safe_get", lambda url: httpx.Response(200, content=b"not xml at all <<<", request=httpx.Request("GET", url))
    )
    result = reach.fetch_rss("https://example.com/broken.xml")
    assert result["ok"] is False


# ---------------------------------------------------------------------------
# doctor()
# ---------------------------------------------------------------------------

def test_doctor_reports_per_backend_health(monkeypatch: pytest.MonkeyPatch) -> None:
    reach = WebReach()

    def fake_get(url, headers=None, timeout=None, follow_redirects=None, params=None):
        return httpx.Response(200, text="ok", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    report = reach.doctor()
    assert "backends" in report
    assert report["backends"]["direct_fetch"]["ok"] is True
    assert "fetch_url_script" in report["backends"]
    assert "video_transcript_script" in report["backends"]


def test_doctor_never_raises_on_backend_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    reach = WebReach()

    def fake_get(*a, **k):
        raise httpx.ConnectError("simulated network failure")

    monkeypatch.setattr(httpx, "get", fake_get)
    report = reach.doctor()
    assert report["ok"] is False
    pinged = ("direct_fetch", "jina_reader", "duckduckgo_search", "youtube")
    assert all(report["backends"][name]["ok"] is False for name in pinged)
    assert all("error" in report["backends"][name] for name in pinged)


# ---------------------------------------------------------------------------
# Capability-registry wiring — every agent gets these tools automatically
# ---------------------------------------------------------------------------

def test_capability_registry_exposes_web_reach_tools() -> None:
    registry = ToolRegistry()
    _register_web_reach_tools(registry)

    names = {t.name for t in registry.list_all()}
    assert {"fetch_url", "youtube_transcript", "web_search", "fetch_rss"} <= names

    fetch_tool = registry.get("fetch_url")
    assert fetch_tool is not None
    assert "web" in fetch_tool.capabilities
    assert "research" in fetch_tool.capabilities

    web_tools = registry.find_by_capability("web")
    assert {t.name for t in web_tools} >= {"fetch_url", "youtube_transcript", "web_search", "fetch_rss"}


def test_capability_registry_exposes_browse_page_tool() -> None:
    """The interactive-browser capability must be discoverable, or agents can
    never reach a real browser even when one is configured (rule 19)."""
    from agent.capability_registry import _register_browser_tools

    registry = ToolRegistry()
    _register_browser_tools(registry)

    tool = registry.get("browse_page")
    assert tool is not None
    assert "browser" in tool.capabilities
    assert {t.name for t in registry.find_by_capability("browser")} == {"browse_page"}


def test_build_tool_prompt_advertises_browse_page() -> None:
    """Registration is silent — the Executor only calls tools listed in the
    prompt, so browse_page must appear there too (rule 19)."""
    from agent.prompts import build_tool_prompt

    messages = build_tool_prompt(
        goal="inspect", step={"description": "look"}, observations=[], remaining_calls=5
    )
    text = " ".join(m["content"] for m in messages)
    assert "browse_page" in text


def test_capability_registry_fetch_url_tool_is_callable(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = ToolRegistry()
    _register_web_reach_tools(registry)

    tool = registry.get("fetch_url")
    assert tool is not None
    result = tool.handler(url="http://127.0.0.1/blocked")
    assert result["ok"] is False
    assert "refused" in result["error"]

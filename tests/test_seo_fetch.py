"""tests/test_seo_fetch.py - pluggable fetch backends for the SEO audit engine.

Covers the bot-block detection heuristic, the httpx backend's normalisation to
FetchResult, the auto-escalation wrapper (httpx -> browser on bot-block), and
the make_fetcher selection logic. A fake browser backend stands in for a real
Chromium so the escalation path is tested without installing browsers.
"""
from __future__ import annotations

import asyncio
from typing import Dict, List, Tuple

import httpx
import pytest

from services.seo_fetch import (
    BOT_BLOCK_MARKERS,
    FetchResult,
    HttpxFetcher,
    ResilientFetcher,
    looks_blocked,
    make_fetcher,
)

UA = "TestBot/1.0"


def _result(status: int, text: str = "", content_type: str = "text/html") -> FetchResult:
    return FetchResult(
        requested_url="https://x.test/", final_url="https://x.test/",
        status_code=status, first_status=status,
        headers={"content-type": content_type}, text=text,
    )


class TestLooksBlocked:
    def test_403_is_blocked(self) -> None:
        assert looks_blocked(_result(403, "<html>denied</html>"))

    def test_429_and_503_are_blocked(self) -> None:
        assert looks_blocked(_result(429))
        assert looks_blocked(_result(503))

    def test_large_real_html_is_not_blocked(self) -> None:
        big = "<html><body>" + "real content " * 500 + "</body></html>"
        assert not looks_blocked(_result(200, big))

    def test_tiny_200_with_marker_is_blocked(self) -> None:
        # 200 but a tiny challenge stub mentioning a known marker.
        assert "akamai" in BOT_BLOCK_MARKERS
        assert looks_blocked(_result(200, "<html>Akamai reference #12.ab</html>"))

    def test_tiny_200_without_marker_is_not_blocked(self) -> None:
        assert not looks_blocked(_result(200, "<html>ok</html>"))


class TestHttpxFetcher:
    def test_get_normalises_to_fetch_result(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html><title>Hi</title></html>",
                                  headers={"content-type": "text/html"})

        async def run() -> FetchResult:
            f = HttpxFetcher(timeout=5, user_agent=UA, transport=httpx.MockTransport(handler))
            try:
                return await f.get("https://x.test/")
            finally:
                await f.aclose()

        r = asyncio.run(run())
        assert r.status_code == 200
        assert "<title>Hi</title>" in r.text
        assert r.headers["content-type"].startswith("text/html")
        assert r.via == "http"

    def test_non_html_body_is_blanked(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="binary", headers={"content-type": "image/png"})

        async def run() -> FetchResult:
            f = HttpxFetcher(timeout=5, user_agent=UA, transport=httpx.MockTransport(handler))
            try:
                return await f.get("https://x.test/logo.png")
            finally:
                await f.aclose()

        assert asyncio.run(run()).text == ""

    def test_head_returns_headers_and_status(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"Content-Length": "2048"})

        async def run() -> Tuple[Dict[str, str], int]:
            f = HttpxFetcher(timeout=5, user_agent=UA, transport=httpx.MockTransport(handler))
            try:
                return await f.head("https://x.test/img.jpg")
            finally:
                await f.aclose()

        headers, status = asyncio.run(run())
        assert status == 200
        assert headers["content-length"] == "2048"


class _FakeBrowser:
    """Stand-in browser backend that records calls and returns canned HTML."""

    def __init__(self, html: str = "", status: int = 200) -> None:
        self.html = html or ("<html><body>" + "browser content " * 300 + "</body></html>")
        self.status = status
        self.calls: List[str] = []

    async def get(self, url: str) -> FetchResult:
        self.calls.append(url)
        return FetchResult(
            requested_url=url, final_url=url, status_code=self.status,
            first_status=self.status, headers={"content-type": "text/html"},
            text=self.html, via="browser",
        )

    async def get_text(self, url: str) -> Tuple[str, int]:
        return self.html, self.status

    async def head(self, url: str) -> Tuple[Dict[str, str], int]:
        return {}, self.status

    async def aclose(self) -> None:
        pass


def _block_then_nothing_transport() -> httpx.MockTransport:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Access Denied (Akamai)",
                              headers={"content-type": "text/html"})
    return httpx.MockTransport(handler)


class TestResilientFetcher:
    def test_escalates_to_browser_on_block(self) -> None:
        primary = HttpxFetcher(timeout=5, user_agent=UA, transport=_block_then_nothing_transport())
        browser = _FakeBrowser()
        fetcher = ResilientFetcher(primary, browser)

        async def run() -> FetchResult:
            try:
                return await fetcher.get("https://shop.test/")
            finally:
                await fetcher.aclose()

        r = asyncio.run(run())
        assert browser.calls == ["https://shop.test/"], "browser must be used on bot-block"
        assert r.via == "browser-fallback"
        assert "browser content" in r.text

    def test_does_not_escalate_on_good_response(self) -> None:
        def ok(req: httpx.Request) -> httpx.Response:
            big = "<html><body>" + "fine " * 500 + "</body></html>"
            return httpx.Response(200, text=big, headers={"content-type": "text/html"})

        primary = HttpxFetcher(timeout=5, user_agent=UA, transport=httpx.MockTransport(ok))
        browser = _FakeBrowser()
        fetcher = ResilientFetcher(primary, browser)

        async def run() -> FetchResult:
            try:
                return await fetcher.get("https://shop.test/")
            finally:
                await fetcher.aclose()

        r = asyncio.run(run())
        assert browser.calls == [], "browser must NOT be used on a healthy response"
        assert r.via == "http"

    def test_no_browser_returns_primary_block(self) -> None:
        primary = HttpxFetcher(timeout=5, user_agent=UA, transport=_block_then_nothing_transport())
        fetcher = ResilientFetcher(primary, None)

        async def run() -> FetchResult:
            try:
                return await fetcher.get("https://shop.test/")
            finally:
                await fetcher.aclose()

        r = asyncio.run(run())
        assert r.status_code == 403  # no browser available -> surfaces the block honestly


class TestMakeFetcher:
    def test_transport_forces_httpx(self) -> None:
        f = make_fetcher(fetch_mode="auto", timeout=5, user_agent=UA,
                         transport=httpx.MockTransport(lambda r: httpx.Response(200)))
        assert isinstance(f, HttpxFetcher)

    def test_http_mode_is_httpx(self) -> None:
        f = make_fetcher(fetch_mode="http", timeout=5, user_agent=UA)
        assert isinstance(f, HttpxFetcher)

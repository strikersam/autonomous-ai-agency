"""services/seo_fetch.py - pluggable page-fetch backends for the SEO audit engine.

The audit engine crawls with plain ``httpx`` by default. Enterprise sites
(Gucci, most luxury retail) sit behind bot protection (Akamai, Cloudflare) that
returns ``403`` to non-browser clients, so a plain crawl yields a block page
instead of real HTML. This module adds browser-backed fetchers (local Playwright
or a Browserbase remote session for residential-proxy bypass) and a resilient
wrapper that automatically escalates to a browser when a bot-block is detected.

All backends return a normalised :class:`FetchResult` so the crawl loop is
agnostic to how a page was retrieved.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol, Tuple

import httpx

log = logging.getLogger("seo_audit")

# Status codes commonly returned by bot-protection layers instead of content.
BOT_BLOCK_STATUSES = {401, 403, 405, 406, 409, 429, 503}
# Phrases that mark a challenge / block page even when it answers HTTP 200.
BOT_BLOCK_MARKERS = (
    "access denied", "akamai", "reference #", "attention required",
    "captcha", "are you a human", "bot detection", "cf-chl", "just a moment",
    "unusual traffic", "request blocked", "pardon our interruption",
)
# Below this many bytes a 200 "HTML" response is almost certainly a stub/challenge.
_MIN_REAL_HTML_BYTES = 1500


@dataclass
class FetchResult:
    """Normalised result of fetching one URL, regardless of backend."""

    requested_url: str
    final_url: str
    status_code: int            # status of the final response
    first_status: int           # status the requested URL answered (pre-redirect)
    headers: Dict[str, str]     # response headers, keys lower-cased
    text: str                   # response body (HTML for pages)
    elapsed_ms: int = 0
    via: str = "http"           # which backend served this result

    @property
    def redirected(self) -> bool:
        return self.final_url != self.requested_url


def looks_blocked(result: FetchResult) -> bool:
    """Heuristic: does this result look like a bot-block rather than content?"""
    if result.status_code in BOT_BLOCK_STATUSES:
        return True
    body = (result.text or "")
    is_html = "html" in result.headers.get("content-type", "").lower()
    if result.status_code == 200 and is_html:
        snippet = body[:4000].lower()
        if len(body.encode("utf-8", "ignore")) < _MIN_REAL_HTML_BYTES and any(
            m in snippet for m in BOT_BLOCK_MARKERS
        ):
            return True
    return False


class PageFetcher(Protocol):
    """Backend that retrieves pages and discovery files for the crawler."""

    async def get(self, url: str) -> FetchResult: ...
    async def get_text(self, url: str) -> Tuple[str, int]: ...
    async def head(self, url: str) -> Tuple[Dict[str, str], int]: ...
    async def aclose(self) -> None: ...


class HttpxFetcher:
    """Default backend: a single ``httpx.AsyncClient`` (fast, no browser)."""

    def __init__(
        self,
        *,
        timeout: float,
        user_agent: str,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        concurrency: int = 5,
    ) -> None:
        self._client = httpx.AsyncClient(
            transport=transport,
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": user_agent},
            limits=httpx.Limits(max_connections=concurrency * 2),
        )

    @staticmethod
    def _to_result(requested_url: str, resp: httpx.Response, elapsed_ms: int) -> FetchResult:
        first = resp.history[0].status_code if resp.history else resp.status_code
        return FetchResult(
            requested_url=requested_url,
            final_url=str(resp.url),
            status_code=resp.status_code,
            first_status=first,
            headers={k.lower(): v for k, v in resp.headers.items()},
            text=resp.text if "html" in resp.headers.get("content-type", "").lower() else "",
            elapsed_ms=elapsed_ms,
            via="http",
        )

    async def get(self, url: str) -> FetchResult:
        t0 = time.monotonic()
        resp = await self._client.get(url)
        return self._to_result(url, resp, int((time.monotonic() - t0) * 1000))

    async def get_text(self, url: str) -> Tuple[str, int]:
        try:
            resp = await self._client.get(url)
            return resp.text, resp.status_code
        except Exception as exc:  # noqa: BLE001 - discovery files are optional
            log.warning("SEO fetch could not GET %s: %s", url, exc)
            return "", 0

    async def head(self, url: str) -> Tuple[Dict[str, str], int]:
        try:
            resp = await self._client.head(url)
            if resp.status_code == 405:  # some servers refuse HEAD
                resp = await self._client.get(url)
            return {k.lower(): v for k, v in resp.headers.items()}, resp.status_code
        except Exception as exc:  # noqa: BLE001 - bounded best-effort checks
            log.warning("SEO fetch could not HEAD %s: %s", url, exc)
            return {}, 0

    async def aclose(self) -> None:
        await self._client.aclose()


class BrowserFetcher:
    """Browser backend: renders pages with a real Chromium via Playwright.

    This is the "browser-use" path - a self-hosted local headless Chromium is
    the default and gets a real, JS-rendered DOM past most bot walls. A remote
    Browserbase session (residential proxies) is available only as an explicit
    opt-in for sites that defeat a local browser.

      * local (default) - bundled headless Chromium (needs the browser binaries:
                          ``playwright install chromium``).
      * browserbase      - connect to a Browserbase session over CDP; opt-in via
                          ``SEO_BROWSER_BACKEND=browserbase`` + BROWSERBASE_API_KEY.

    HEAD requests fall back to httpx - browsers don't issue HEAD and the
    discovery checks that use it (favicon, feeds, image weights) are best-effort.
    """

    def __init__(self, *, timeout: float, user_agent: str, browserbase: bool = False) -> None:
        self._timeout_ms = int(timeout * 1000)
        self._ua = user_agent
        self._browserbase = browserbase
        self._pw = None
        self._browser = None
        # httpx is used only for best-effort HEAD checks.
        self._http = httpx.AsyncClient(
            follow_redirects=True, timeout=timeout, headers={"User-Agent": user_agent}
        )

    async def _ensure_browser(self) -> None:
        if self._browser is not None:
            return
        from playwright.async_api import async_playwright  # lazy: optional dep

        self._pw = await async_playwright().start()
        if self._browserbase:
            api_key = os.environ["BROWSERBASE_API_KEY"]
            project = os.environ.get("BROWSERBASE_PROJECT_ID", "")
            ws = f"wss://connect.browserbase.com?apiKey={api_key}"
            if project:
                ws += f"&projectId={project}"
            self._browser = await self._pw.chromium.connect_over_cdp(ws)
            log.info("SEO fetch: connected to Browserbase remote browser")
        else:
            self._browser = await self._pw.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
            )
            log.info("SEO fetch: launched local headless Chromium")

    async def get(self, url: str) -> FetchResult:
        await self._ensure_browser()
        context = await self._browser.new_context(
            user_agent=self._ua, locale="en-US", viewport={"width": 1366, "height": 900}
        )
        page = await context.new_page()
        t0 = time.monotonic()
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
            # let late client-side rendering settle, bounded.
            try:
                await page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:  # noqa: BLE001 - networkidle is best-effort
                pass
            html = await page.content()
            status = resp.status if resp else 0
            final_url = page.url
            headers = {k.lower(): v for k, v in (resp.headers if resp else {}).items()}
            headers.setdefault("content-type", "text/html")
            return FetchResult(
                requested_url=url, final_url=final_url, status_code=status,
                first_status=status, headers=headers, text=html,
                elapsed_ms=int((time.monotonic() - t0) * 1000), via="browser",
            )
        finally:
            await context.close()

    async def get_text(self, url: str) -> Tuple[str, int]:
        try:
            r = await self.get(url)
            return r.text, r.status_code
        except Exception as exc:  # noqa: BLE001 - discovery files are optional
            log.warning("SEO browser fetch could not GET %s: %s", url, exc)
            return "", 0

    async def head(self, url: str) -> Tuple[Dict[str, str], int]:
        try:
            resp = await self._http.head(url)
            if resp.status_code == 405:
                resp = await self._http.get(url)
            return {k.lower(): v for k, v in resp.headers.items()}, resp.status_code
        except Exception as exc:  # noqa: BLE001 - best-effort
            log.warning("SEO browser fetch could not HEAD %s: %s", url, exc)
            return {}, 0

    async def aclose(self) -> None:
        try:
            if self._browser is not None:
                await self._browser.close()
            if self._pw is not None:
                await self._pw.stop()
        except Exception as exc:  # noqa: BLE001 - teardown best-effort
            log.warning("SEO browser fetch teardown error: %s", exc)
        await self._http.aclose()


class ResilientFetcher:
    """Tries the primary (httpx) backend; escalates to a browser on bot-block.

    This is the ``auto`` mode: fast plain crawl for normal sites, automatic
    browser retry for the page(s) a bot wall blocks - so an Akamai 403 on the
    homepage transparently becomes a real rendered fetch when a browser backend
    is available.
    """

    def __init__(self, primary: PageFetcher, browser: Optional[PageFetcher]) -> None:
        self._primary = primary
        self._browser = browser

    async def get(self, url: str) -> FetchResult:
        result = await self._primary.get(url)
        if self._browser is not None and looks_blocked(result):
            log.info(
                "SEO fetch: bot-block on %s (status %s) - escalating to browser",
                url, result.status_code,
            )
            try:
                escalated = await self._browser.get(url)
                escalated.via = "browser-fallback"
                if not looks_blocked(escalated):
                    return escalated
                log.warning("SEO fetch: browser fallback for %s still looks blocked", url)
                return escalated
            except Exception as exc:  # noqa: BLE001 - fall back to primary result
                log.warning("SEO fetch: browser fallback failed for %s: %s", url, exc)
        return result

    async def get_text(self, url: str) -> Tuple[str, int]:
        return await self._primary.get_text(url)

    async def head(self, url: str) -> Tuple[Dict[str, str], int]:
        return await self._primary.head(url)

    async def aclose(self) -> None:
        await self._primary.aclose()
        if self._browser is not None:
            await self._browser.aclose()


def browser_backend_available() -> Optional[str]:
    """Which browser backend to use.

    Defaults to 'local' (browser-use / Playwright headless Chromium) whenever
    Playwright is importable. Browserbase is used only when explicitly opted into
    with ``SEO_BROWSER_BACKEND=browserbase`` (and an API key), or as a last
    resort if no local browser is available at all.
    """
    explicit = os.environ.get("SEO_BROWSER_BACKEND", "").strip().lower()
    try:
        import importlib.util

        have_playwright = importlib.util.find_spec("playwright") is not None
    except Exception:  # noqa: BLE001 - detection must never raise
        have_playwright = False

    if explicit == "browserbase" and os.environ.get("BROWSERBASE_API_KEY"):
        return "browserbase"
    if have_playwright:
        return "local"  # browser-use / Playwright local Chromium (default)
    if os.environ.get("BROWSERBASE_API_KEY"):
        return "browserbase"  # last resort when no local browser exists
    return None


def make_fetcher(
    *,
    fetch_mode: str,
    timeout: float,
    user_agent: str,
    transport: Optional[httpx.AsyncBaseTransport] = None,
    concurrency: int = 5,
) -> PageFetcher:
    """Build the fetcher for a run.

    ``fetch_mode``:
      * ``http``    - httpx only (never a browser).
      * ``browser`` - browser only (Browserbase if configured, else local).
      * ``auto``    - httpx with automatic browser escalation on bot-block
                      (browser used only if a backend is available).

    A ``transport`` (test ``httpx.MockTransport``) forces pure-httpx so the
    crawl is deterministic and offline.
    """
    http = HttpxFetcher(
        timeout=timeout, user_agent=user_agent, transport=transport, concurrency=concurrency
    )
    if transport is not None or fetch_mode == "http":
        return http

    backend = browser_backend_available() if fetch_mode in ("auto", "browser") else None
    browser: Optional[PageFetcher] = None
    if backend is not None:
        browser = BrowserFetcher(
            timeout=timeout, user_agent=user_agent, browserbase=(backend == "browserbase")
        )

    if fetch_mode == "browser":
        if browser is None:
            log.warning("SEO fetch: browser mode requested but no backend available; using httpx")
            return http
        return browser

    # auto
    if browser is None:
        return http
    return ResilientFetcher(http, browser)

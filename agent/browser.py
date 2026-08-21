"""agent/browser.py — Browser Automation

Controls a real browser via Playwright so the agent can interact with
dynamic web pages: click buttons, fill forms, take screenshots, and read
rendered content — not just fetch raw HTML.

Two backends, chosen automatically:

  * **Browserbase (remote, low-RAM)** — when ``BROWSERBASE_API_KEY`` is set,
    the browser runs in Browserbase's cloud and this process only connects to
    it over CDP. No local Chromium is launched, so the backend never pays the
    ~400MB resident cost of a browser and does not need the browser binaries
    installed in its image. This is the default whenever a key is present.
  * **Local Chromium** — the fallback when there is no Browserbase key. Needs
    ``pip install playwright && playwright install chromium`` in the image.

Gated by ``BROWSER_AUTOMATION_ENABLED``. When disabled, or when Playwright is
not importable, the session runs in *stub mode*: every action returns a failed
result with a clear hint rather than raising.

Navigation targets are LLM-chosen (classic SSRF surface), so every URL is
screened with ``agent.web_reach.unsafe_target_reason`` before the browser is
pointed at it — rule 14.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from packages.config import settings

log = logging.getLogger("qwen-browser")

_INSTALL_HINT = (
    "Browser automation is unavailable. Set BROWSER_AUTOMATION_ENABLED=true and "
    "either provide BROWSERBASE_API_KEY (remote, low-RAM) or install a local "
    "browser (pip install playwright && playwright install chromium)."
)


@dataclass
class BrowserAction:
    action: str
    args: dict[str, Any] = field(default_factory=dict)
    result: str = ""
    success: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "args": self.args,
            "result": self.result,
            "success": self.success,
        }


@dataclass
class PageState:
    url: str
    title: str
    content_preview: str   # first 500 chars of visible text

    def as_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "content_preview": self.content_preview,
        }


class BrowserSession:
    """Async Playwright browser session.

    Usage::

        session = BrowserSession()
        await session.start()
        await session.navigate("https://example.com")
        await session.screenshot("/tmp/screen.png")
        state = await session.get_state()
        await session.stop()
    """

    def __init__(self) -> None:
        self._page: Any = None
        self._browser: Any = None
        self._pw: Any = None
        self._remote: bool = settings.browserbase_configured
        self._available = self._check_available()

    # ------------------------------------------------------------------
    # Capability check
    # ------------------------------------------------------------------

    def _check_available(self) -> bool:
        if not settings.browser_automation_enabled:
            log.info(
                "Browser automation disabled (set BROWSER_AUTOMATION_ENABLED=true to enable)"
            )
            return False
        try:
            import importlib.util

            if importlib.util.find_spec("playwright") is None:
                log.info("playwright not installed — BrowserSession running in stub mode")
                return False
        except Exception:  # noqa: BLE001 - detection must never raise
            return False
        return True

    @property
    def available(self) -> bool:
        """True if browser automation is enabled and Playwright is importable."""
        return self._available

    @property
    def backend(self) -> str:
        """Which backend a start() would use: 'browserbase', 'local', or 'stub'."""
        if not self._available:
            return "stub"
        return "browserbase" if self._remote else "local"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, *, headless: bool = True) -> None:
        if not self._available:
            log.warning(_INSTALL_HINT)
            return
        from playwright.async_api import async_playwright  # type: ignore[import]

        self._pw = await async_playwright().start()
        if self._remote:
            # Connect to the cloud browser over CDP — no local Chromium, so no
            # ~400MB resident browser in this process. The connect URL carries
            # the API key, so it is never logged.
            self._browser = await self._pw.chromium.connect_over_cdp(
                settings.browserbase_connect_url
            )
            log.info("Browser session started (Browserbase remote browser)")
        else:
            self._browser = await self._pw.chromium.launch(
                headless=headless,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            log.info("Browser session started (local Chromium, headless=%s)", headless)
        self._page = await self._browser.new_page()

    async def stop(self) -> None:
        try:
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
        except Exception as exc:  # noqa: BLE001 - teardown is best-effort
            log.warning("Browser session teardown error: %s", exc)
        self._page = self._browser = self._pw = None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def navigate(self, url: str) -> BrowserAction:
        if not self._page:
            return BrowserAction("navigate", {"url": url}, _not_started(), False)
        # Rule 14: an LLM-chosen URL is an SSRF target — screen it before the
        # browser is pointed at it, and re-check where a redirect landed.
        reason = _unsafe_reason(url)
        if reason:
            return BrowserAction("navigate", {"url": url}, f"blocked: {reason}", False)
        try:
            await self._page.goto(url)
            final = self._page.url
            landed = _unsafe_reason(final)
            if landed:
                return BrowserAction(
                    "navigate", {"url": url}, f"blocked after redirect: {landed}", False
                )
            title = await self._page.title()
            return BrowserAction("navigate", {"url": url}, f"Navigated to: {title}")
        except Exception as exc:
            return BrowserAction("navigate", {"url": url}, str(exc), False)

    async def click(self, selector: str) -> BrowserAction:
        if not self._page:
            return BrowserAction("click", {"selector": selector}, _not_started(), False)
        try:
            await self._page.click(selector)
            return BrowserAction("click", {"selector": selector}, "clicked")
        except Exception as exc:
            return BrowserAction("click", {"selector": selector}, str(exc), False)

    async def fill(self, selector: str, value: str) -> BrowserAction:
        if not self._page:
            return BrowserAction("fill", {"selector": selector, "value": value}, _not_started(), False)
        try:
            await self._page.fill(selector, value)
            return BrowserAction("fill", {"selector": selector, "value": value}, "filled")
        except Exception as exc:
            return BrowserAction("fill", {"selector": selector, "value": value}, str(exc), False)

    async def screenshot(self, path: str) -> BrowserAction:
        if not self._page:
            return BrowserAction("screenshot", {"path": path}, _not_started(), False)
        try:
            await self._page.screenshot(path=path)
            return BrowserAction("screenshot", {"path": path}, f"saved to {path}")
        except Exception as exc:
            return BrowserAction("screenshot", {"path": path}, str(exc), False)

    async def evaluate(self, expression: str) -> BrowserAction:
        """Evaluate a JavaScript expression in the page context."""
        if not self._page:
            return BrowserAction("evaluate", {"expression": expression}, _not_started(), False)
        try:
            result = await self._page.evaluate(expression)
            return BrowserAction("evaluate", {"expression": expression}, str(result))
        except Exception as exc:
            return BrowserAction("evaluate", {"expression": expression}, str(exc), False)

    async def get_state(self) -> PageState | None:
        """Return a summary of the current page state."""
        if not self._page:
            return None
        try:
            url = self._page.url
            title = await self._page.title()
            text = await self._page.evaluate("document.body?.innerText || ''")
            return PageState(url=url, title=title, content_preview=str(text)[:500])
        except Exception:
            return None


# ── stateless helper for the agent capability tool ─────────────────────────────


async def browse_page(url: str, *, text_limit: int = 4000) -> dict[str, Any]:
    """Open *url* in a real browser, return its rendered text, and close.

    Fail-soft: always returns a dict the model can read — never raises. Uses the
    Browserbase remote browser when configured (no local Chromium), else a local
    headless one. The SSRF screen in :meth:`BrowserSession.navigate` still runs.
    """
    session = BrowserSession()
    if not session.available:
        return {"ok": False, "url": url, "error": _INSTALL_HINT, "backend": "stub"}
    backend = session.backend
    try:
        await session.start()
        nav = await session.navigate(url)
        if not nav.success:
            return {"ok": False, "url": url, "error": nav.result, "backend": backend}
        state = await session.get_state()
        if state is None:
            return {"ok": False, "url": url, "error": "could not read page state", "backend": backend}
        text = state.content_preview
        try:
            full = await session._page.evaluate("document.body?.innerText || ''")  # noqa: SLF001
            text = str(full)[:text_limit]
        except Exception:  # noqa: BLE001 - preview is an acceptable fallback
            pass
        return {
            "ok": True,
            "url": state.url,
            "title": state.title,
            "text": text,
            "backend": backend,
        }
    except Exception as exc:  # noqa: BLE001 - a tool must never break the loop
        log.warning("browse_page failed for %s: %s", url, exc)
        return {"ok": False, "url": url, "error": str(exc), "backend": backend}
    finally:
        await session.stop()


def _not_started() -> str:
    return "Browser not started. Call await session.start() first."


def _unsafe_reason(url: str) -> str | None:
    """Screen a URL for SSRF. Fails closed — if the guard cannot be imported
    the URL is treated as unsafe, because a browser that skips the SSRF check
    is exactly the hole rule 14 exists to close."""
    try:
        from agent.web_reach import unsafe_target_reason
    except Exception as exc:  # noqa: BLE001 - fail closed, never open
        return f"URL safety check unavailable ({exc})"
    return unsafe_target_reason(url)

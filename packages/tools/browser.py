"""packages/tools/browser.py — Browser automation tool.

Safe browser automation available to every agent through the tool system.
Supports navigation, extraction, interaction, and session reuse.

Uses the existing browser-use/playwright infrastructure already in the repo
(scanner's headless render pass). This tool wraps it as a first-class
platform capability.
"""
from __future__ import annotations

import logging
from typing import Any

from packages.tools.base import Tool, ToolResult, ToolSchema

log = logging.getLogger("tool.browser")


class BrowserTool(Tool):
    """Browser automation tool for web research + interaction.

    Provides safe, sandboxed browser access to every agent. Supports:
    - Navigation to URLs
    - Page text extraction
    - Element interaction (click, fill)
    - Screenshot capture
    - Session reuse (keep browser open between calls)
    """

    def __init__(self) -> None:
        self._browser = None
        self._page = None

    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return "Navigate web pages, extract content, interact with elements, take screenshots"

    @property
    def capabilities(self) -> list[str]:
        return ["web", "navigation", "extraction", "research", "verification"]

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a browser action.

        Args:
            action: One of 'navigate', 'extract', 'click', 'fill', 'screenshot', 'close'
            url: URL to navigate to (for 'navigate')
            selector: CSS selector (for 'click', 'fill')
            value: Value to fill (for 'fill')
        """
        action = kwargs.get("action", "")
        try:
            if action == "navigate":
                return await self._navigate(kwargs.get("url", ""))
            elif action == "extract":
                return await self._extract()
            elif action == "click":
                return await self._click(kwargs.get("selector", ""))
            elif action == "fill":
                return await self._fill(kwargs.get("selector", ""), kwargs.get("value", ""))
            elif action == "screenshot":
                return await self._screenshot()
            elif action == "close":
                return await self._close()
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
        except Exception as exc:
            log.exception("Browser tool error: %s", exc)
            return ToolResult(success=False, error=str(exc))

    async def _ensure_browser(self) -> None:
        """Lazily start the browser if not already running."""
        if self._page is not None:
            return
        try:
            from playwright.async_api import async_playwright
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(headless=True)
            self._page = await self._browser.new_page()
            log.info("Browser tool: started headless Chromium")
        except ImportError:
            raise RuntimeError("playwright not installed — run: pip install playwright && playwright install chromium")

    async def _navigate(self, url: str) -> ToolResult:
        """Navigate to a URL."""
        if not url:
            return ToolResult(success=False, error="url is required")
        await self._ensure_browser()
        await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        title = await self._page.title()
        return ToolResult(
            success=True,
            output={"url": url, "title": title},
            metadata={"action": "navigate"},
        )

    async def _extract(self) -> ToolResult:
        """Extract text content from the current page."""
        await self._ensure_browser()
        text = await self._page.inner_text("body")
        return ToolResult(
            success=True,
            output=text[:10000],  # Cap at 10k chars to avoid token explosion
            metadata={"action": "extract", "chars": len(text)},
        )

    async def _click(self, selector: str) -> ToolResult:
        """Click an element."""
        if not selector:
            return ToolResult(success=False, error="selector is required")
        await self._ensure_browser()
        await self._page.click(selector, timeout=10000)
        return ToolResult(success=True, output="clicked", metadata={"action": "click", "selector": selector})

    async def _fill(self, selector: str, value: str) -> ToolResult:
        """Fill an input field."""
        if not selector:
            return ToolResult(success=False, error="selector is required")
        await self._ensure_browser()
        await self._page.fill(selector, value, timeout=10000)
        return ToolResult(success=True, output="filled", metadata={"action": "fill", "selector": selector})

    async def _screenshot(self) -> ToolResult:
        """Take a screenshot."""
        await self._ensure_browser()
        screenshot = await self._page.screenshot()
        return ToolResult(
            success=True,
            output=f"screenshot captured ({len(screenshot)} bytes)",
            metadata={"action": "screenshot", "bytes": len(screenshot)},
        )

    async def _close(self) -> ToolResult:
        """Close the browser session."""
        if self._browser:
            await self._browser.close()
            await self._pw.stop()
            self._browser = None
            self._page = None
        return ToolResult(success=True, output="browser closed")

    async def health(self) -> bool:
        """Check if playwright is available."""
        try:
            import playwright  # noqa: F401
            return True
        except ImportError:
            return False

    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="browser",
            description="Navigate web pages, extract content, interact with elements",
            parameters={
                "action": {"type": "string", "enum": ["navigate", "extract", "click", "fill", "screenshot", "close"]},
                "url": {"type": "string", "description": "URL to navigate to (for action=navigate)"},
                "selector": {"type": "string", "description": "CSS selector (for action=click/fill)"},
                "value": {"type": "string", "description": "Value to fill (for action=fill)"},
            },
        )

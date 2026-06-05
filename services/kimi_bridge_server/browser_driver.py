"""Playwright-backed Kimi web driver.

Persistent user-data dir (PLAYWRIGHT_USER_DATA_DIR) keeps the Kimi login cookie
across restarts.  A single asyncio.Lock serialises concurrent callers so we never
open two tabs simultaneously.

One-time manual login::

    python -m services.kimi_bridge_server.browser_driver --login

Headless inference (used by app.py)::

    from services.kimi_bridge_server.browser_driver import KimiBrowserDriver
    driver = KimiBrowserDriver()
    await driver.start()
    reply = await driver.ask(messages)
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page

log = logging.getLogger("qwen-proxy")

_DEFAULT_USER_DATA_DIR = str(Path.home() / ".kimi_bridge_profile")
_KIMI_URL = "https://kimi.moonshot.cn"
_CHAT_INPUT_SELECTOR = 'textarea[placeholder], div[contenteditable="true"]'
_RESPONSE_DONE_SELECTOR = "div.thinking, button[aria-label*='stop'], button[aria-label*='Stop']"


class KimiBrowserDriver:
    """Manages a single persistent Chromium context pointing at kimi.com."""

    def __init__(self) -> None:
        self._user_data_dir = os.environ.get(
            "PLAYWRIGHT_USER_DATA_DIR", _DEFAULT_USER_DATA_DIR
        )
        self._headless = os.environ.get("KIMI_BRIDGE_HEADLESS", "true").lower() in {
            "true", "1", "yes"
        }
        self._lock = asyncio.Lock()
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._playwright = None

    async def start(self) -> None:
        """Launch a persistent Chromium context (headless by default)."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        Path(self._user_data_dir).mkdir(parents=True, exist_ok=True)
        self._context = await self._playwright.chromium.launch_persistent_context(
            self._user_data_dir,
            headless=self._headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        pages = self._context.pages
        self._page = pages[0] if pages else await self._context.new_page()
        log.info("KimiBrowserDriver started (headless=%s)", self._headless)

    async def stop(self) -> None:
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()
        log.info("KimiBrowserDriver stopped")

    async def login(self) -> None:
        """Open Kimi in headed mode so the operator can log in once.

        After logging in, close the browser — the session cookie is persisted
        in PLAYWRIGHT_USER_DATA_DIR and reused by subsequent headless runs.
        """
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        Path(self._user_data_dir).mkdir(parents=True, exist_ok=True)
        ctx = await pw.chromium.launch_persistent_context(
            self._user_data_dir,
            headless=False,
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(_KIMI_URL)
        log.info("Browser open — log in to Kimi then close the window to save the session.")
        await page.wait_for_event("close", timeout=0)  # wait until operator closes
        await ctx.close()
        await pw.stop()

    async def ask(self, messages: list[dict]) -> str:
        """Submit a conversation to Kimi and return the assistant reply as plain text.

        Only the last user message is submitted; earlier turns are condensed into
        a system-style preamble if present, keeping the single-tab approach simple.
        """
        if self._page is None or self._context is None:
            raise RuntimeError("KimiBrowserDriver.start() has not been called")

        # Build a single prompt from the messages list
        prompt = _messages_to_prompt(messages)

        async with self._lock:
            return await self._submit_prompt(prompt)

    async def _submit_prompt(self, prompt: str) -> str:
        page = self._page
        if page is None:
            raise RuntimeError("KimiBrowserDriver._page is None; call start() first")

        try:
            await page.goto(_KIMI_URL, wait_until="domcontentloaded", timeout=30_000)
        except Exception as exc:
            log.warning("Navigation to Kimi failed: %s", exc)
            raise

        # Find the input box
        input_box = await page.wait_for_selector(_CHAT_INPUT_SELECTOR, timeout=15_000)
        await input_box.click()
        await input_box.fill("")
        await input_box.type(prompt, delay=10)

        # Submit
        await page.keyboard.press("Enter")

        # Wait for the response to complete — poll until we see a stable text block
        reply = await _wait_for_reply(page)
        return reply


def _messages_to_prompt(messages: list[dict]) -> str:
    """Flatten an OpenAI messages list into a single string for the web UI."""
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            # Multi-modal content blocks — extract text parts only
            content = " ".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )
        if role == "system":
            parts.append(f"[System context]: {content}")
        elif role == "assistant":
            parts.append(f"[Previous assistant reply]: {content}")
        else:
            parts.append(content)
    return "\n\n".join(p for p in parts if p)


async def _wait_for_reply(page: "Page", timeout: float = 120.0) -> str:
    """Poll the page until the streaming response is complete, then return its text."""
    deadline = time.monotonic() + timeout
    last_text = ""
    stable_count = 0

    while time.monotonic() < deadline:
        await asyncio.sleep(2.0)

        # Try to grab the last assistant message block
        text = await page.evaluate(
            """() => {
                // Kimi renders messages in div.chat-message or similar — try multiple selectors.
                const candidates = [
                    ...document.querySelectorAll('[class*="message"][class*="assistant"]'),
                    ...document.querySelectorAll('[class*="msg-content"]'),
                    ...document.querySelectorAll('[class*="reply"]'),
                ];
                if (!candidates.length) return '';
                // Return the last element's innerText
                return candidates[candidates.length - 1].innerText || '';
            }"""
        )

        text = (text or "").strip()
        if text and text == last_text:
            stable_count += 1
            if stable_count >= 2:
                return text
        else:
            stable_count = 0
            last_text = text

    # Return whatever we have even if not fully stable
    return last_text or "[kimi-bridge: no reply captured within timeout]"


if __name__ == "__main__":
    import sys

    if "--login" in sys.argv:
        driver = KimiBrowserDriver()
        asyncio.run(driver.login())
    else:
        log.error("Usage: python -m services.kimi_bridge_server.browser_driver --login")

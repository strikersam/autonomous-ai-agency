"""Tests for agent/browser.py — Browser Automation (stub-mode tests)."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent.browser import BrowserSession, PageState


def test_session_created():
    session = BrowserSession()
    assert isinstance(session.available, bool)


async def test_stub_mode_navigate() -> None:
    """When Playwright is not installed, navigate returns a failed BrowserAction."""
    session = BrowserSession()
    if session.available:
        pytest.skip("Playwright is installed; stub-mode test not applicable")
    result = await session.navigate("https://example.com")
    assert result.success is False
    assert "not started" in result.result.lower()


async def test_stub_mode_click() -> None:
    session = BrowserSession()
    if session.available:
        pytest.skip("Playwright installed")
    result = await session.click("#btn")
    assert result.success is False


async def test_stub_mode_fill() -> None:
    session = BrowserSession()
    if session.available:
        pytest.skip("Playwright installed")
    result = await session.fill("#inp", "value")
    assert result.success is False


async def test_stub_mode_screenshot(tmp_path: Path) -> None:
    session = BrowserSession()
    if session.available:
        pytest.skip("Playwright installed")
    result = await session.screenshot(str(tmp_path / "snap.png"))
    assert result.success is False


async def test_stub_mode_get_state() -> None:
    session = BrowserSession()
    if session.available:
        pytest.skip("Playwright installed")
    result = await session.get_state()
    assert result is None


def test_browser_action_as_dict():
    from agent.browser import BrowserAction
    a = BrowserAction(action="navigate", args={"url": "http://x"}, result="ok", success=True)
    d = a.as_dict()
    assert d["action"] == "navigate"
    assert d["success"] is True

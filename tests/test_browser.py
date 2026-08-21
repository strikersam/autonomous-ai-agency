"""Tests for agent/browser.py — Browser Automation (stub-mode tests)."""
import asyncio

import pytest

from agent.browser import BrowserSession, PageState


def test_session_created():
    session = BrowserSession()
    assert isinstance(session.available, bool)


def test_stub_mode_navigate():
    """When Playwright is not installed, navigate returns a failed BrowserAction."""
    session = BrowserSession()
    if session.available:
        pytest.skip("Playwright is installed; stub-mode test not applicable")
    result = asyncio.run(session.navigate("https://example.com"))
    assert result.success is False
    assert "not started" in result.result.lower()


def test_stub_mode_click():
    session = BrowserSession()
    if session.available:
        pytest.skip("Playwright installed")
    result = asyncio.run(session.click("#btn"))
    assert result.success is False


def test_stub_mode_fill():
    session = BrowserSession()
    if session.available:
        pytest.skip("Playwright installed")
    result = asyncio.run(session.fill("#inp", "value"))
    assert result.success is False


def test_stub_mode_screenshot(tmp_path):
    session = BrowserSession()
    if session.available:
        pytest.skip("Playwright installed")
    result = asyncio.run(session.screenshot(str(tmp_path / "snap.png")))
    assert result.success is False


def test_stub_mode_get_state():
    session = BrowserSession()
    if session.available:
        pytest.skip("Playwright installed")
    result = asyncio.run(session.get_state())
    assert result is None


def test_browser_action_as_dict():
    from agent.browser import BrowserAction
    a = BrowserAction(action="navigate", args={"url": "http://x"}, result="ok", success=True)
    d = a.as_dict()
    assert d["action"] == "navigate"
    assert d["success"] is True


# ── backend selection (Browserbase vs local vs stub) ──────────────────────────

class TestBackendSelection:
    """The `backend` property is what decides local-Chromium (RAM-heavy) vs
    Browserbase (remote, low-RAM) vs stub — the whole point of this feature."""

    def _session(self, *, available: bool, remote: bool):
        from agent.browser import BrowserSession
        s = BrowserSession.__new__(BrowserSession)  # bypass __init__ env reads
        s._page = s._browser = s._pw = None
        s._remote = remote
        s._available = available
        return s

    def test_browserbase_when_key_present(self):
        assert self._session(available=True, remote=True).backend == "browserbase"

    def test_local_when_no_key(self):
        assert self._session(available=True, remote=False).backend == "local"

    def test_stub_when_unavailable(self):
        assert self._session(available=False, remote=True).backend == "stub"


# ── SSRF screen on navigation (rule 14) ───────────────────────────────────────

class TestNavigationIsScreened:
    def test_private_target_is_blocked_before_navigating(self):
        """A browser that skips the SSRF check is the hole rule 14 closes."""
        from agent.browser import BrowserSession

        class _FakePage:
            url = "about:blank"
            async def goto(self, url):  # must never be reached
                raise AssertionError("goto called on a blocked URL")
            async def title(self):
                return "x"

        s = BrowserSession.__new__(BrowserSession)
        s._page = _FakePage()
        result = asyncio.run(s.navigate("http://169.254.169.254/latest/meta-data/"))
        assert result.success is False
        assert "blocked" in result.result.lower()

    def test_public_target_passes_the_screen(self):
        from agent.browser import BrowserSession

        class _FakePage:
            url = "https://example.com/"
            async def goto(self, url):
                self.url = url
            async def title(self):
                return "Example"

        s = BrowserSession.__new__(BrowserSession)
        s._page = _FakePage()
        result = asyncio.run(s.navigate("https://example.com/"))
        assert result.success is True

    def test_unsafe_reason_fails_closed_without_the_guard(self, monkeypatch):
        """If the SSRF guard can't be imported, treat the URL as unsafe."""
        import builtins
        import agent.browser as browser

        real_import = builtins.__import__

        def _boom(name, *a, **k):
            if name == "agent.web_reach":
                raise ImportError("simulated")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", _boom)
        assert browser._unsafe_reason("https://example.com/") is not None


# ── browse_page is fail-soft ──────────────────────────────────────────────────

def test_browse_page_stub_is_fail_soft(monkeypatch):
    """With automation disabled, browse_page returns a dict, never raises."""
    import agent.browser as browser
    monkeypatch.setattr(browser.settings, "browser_automation_enabled_raw", "false")
    out = asyncio.run(browser.browse_page("https://example.com"))
    assert out["ok"] is False
    assert out["backend"] == "stub"
    assert "url" in out


# ── settings: the low-RAM connect URL ─────────────────────────────────────────

class TestBrowserbaseSettings:
    def test_connect_url_carries_key_and_project(self, monkeypatch):
        from packages.config import settings as cfg
        monkeypatch.setattr(cfg, "browserbase_api_key", "sekret", raising=False)
        monkeypatch.setattr(cfg, "browserbase_project_id", "proj1", raising=False)
        url = cfg.browserbase_connect_url
        assert url.startswith("wss://connect.browserbase.com?apiKey=sekret")
        assert "projectId=proj1" in url

    def test_connect_url_empty_without_key(self, monkeypatch):
        from packages.config import settings as cfg
        monkeypatch.setattr(cfg, "browserbase_api_key", "", raising=False)
        assert cfg.browserbase_connect_url == ""
        assert cfg.browserbase_configured is False

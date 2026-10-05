"""WEB_REACH_ENABLED — the operator master switch for agent web access (#1688 item 2).

Off: every agent web tool refuses before any network call, and the tool prompt
stops advertising them (rule 19). On (the default): unchanged.
"""
from __future__ import annotations

import asyncio
import os

import pytest

from agent import prompts, web_reach
from agent.capability_registry import (
    ToolRegistry,
    _register_browser_tools,
    _register_web_reach_tools,
)
from packages.config import control_overrides
from packages.config.control_registry import get_control

WEB_TOOLS = ("fetch_url", "youtube_transcript", "web_search", "fetch_rss", "browse_page")
ARGS = {"fetch_url": {"url": "https://example.com"}, "youtube_transcript": {"url": "https://youtu.be/x"},
        "web_search": {"query": "q"}, "fetch_rss": {"url": "https://example.com/feed"},
        "browse_page": {"url": "https://example.com"}}


@pytest.fixture()
def web_off(monkeypatch):
    from packages.config import settings

    monkeypatch.setattr(settings, "web_reach_enabled_raw", "false")


def _prompt_text() -> str:
    msgs = prompts.build_tool_prompt(goal="g", step={"description": "s"}, observations=[], remaining_calls=3)
    return "\n".join(m["content"] for m in msgs)


def _registry(monkeypatch) -> ToolRegistry:
    def _no_network(*_a, **_k):
        raise AssertionError("a disabled web tool reached the network layer")

    monkeypatch.setattr(web_reach.WebReach, "fetch_page", _no_network)
    monkeypatch.setattr(web_reach.WebReach, "youtube_transcript", _no_network)
    monkeypatch.setattr(web_reach.WebReach, "search_web", _no_network)
    monkeypatch.setattr(web_reach.WebReach, "fetch_rss", _no_network)
    import agent.browser as browser

    async def _no_browser(*_a, **_k):
        raise AssertionError("a disabled browse_page opened a browser")

    monkeypatch.setattr(browser, "browse_page", _no_browser)
    reg = ToolRegistry()
    _register_browser_tools(reg)
    _register_web_reach_tools(reg)
    return reg


def test_default_is_on() -> None:
    assert web_reach.web_access_enabled()
    assert web_reach.web_access_refusal("fetch_url") is None
    assert get_control("WEB_REACH_ENABLED").default == "true"


def test_off_every_web_tool_refuses_without_network(web_off, monkeypatch) -> None:
    reg = _registry(monkeypatch)
    for name in WEB_TOOLS:
        result = reg._tools[name].handler(**ARGS[name])
        if asyncio.iscoroutine(result):
            result = asyncio.run(result)
        assert result["ok"] is False
        assert "WEB_REACH_ENABLED" in result["error"], name


def test_prompt_advertises_web_tools_only_when_on(monkeypatch) -> None:
    on = _prompt_text()
    assert "- web_search(query" in on and "- browse_page(url)" in on
    from packages.config import settings

    monkeypatch.setattr(settings, "web_reach_enabled_raw", "false")
    off = _prompt_text()
    for name in WEB_TOOLS:
        assert f"- {name}(" not in off, name
    assert '"tool": "web_search"' not in off
    assert "switched off by the operator" in off
    assert "- get_current_time()" in off


@pytest.mark.parametrize("raw,enabled", [("true", True), ("1", True), ("", True),
                                         ("false", False), ("OFF", False), ("0", False)])
def test_raw_values(monkeypatch, raw: str, enabled: bool) -> None:
    from packages.config import settings

    monkeypatch.setattr(settings, "web_reach_enabled_raw", raw)
    assert web_reach.web_access_enabled() is enabled


def test_platform_control_override_is_live() -> None:
    assert get_control("WEB_REACH_ENABLED").live is True
    before = os.environ.get("WEB_REACH_ENABLED")
    applied = dict(control_overrides._applied)
    try:
        control_overrides.apply_overrides({"WEB_REACH_ENABLED": "false"})
        assert not web_reach.web_access_enabled()
        control_overrides.apply_overrides({})
        assert web_reach.web_access_enabled()
    finally:
        if before is None:
            os.environ.pop("WEB_REACH_ENABLED", None)
        else:
            os.environ["WEB_REACH_ENABLED"] = before
        control_overrides._applied.clear()
        control_overrides._applied.update(applied)

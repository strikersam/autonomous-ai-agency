"""Blocking web and sandbox-SDK work must not run on the event loop.

Production (2026-11-14, after #1963): two stalls of 10.7 s and 12.2 s failed Render's
5 s health check. The watchdog named them: the agent's ``web_search`` tool calling a
synchronous ``httpx.get`` on the loop (each search backend can block up to 6 s, one after
another), and the first import of the Daytona SDK (hundreds of pydantic models) on the
first sandbox open of a process.
"""
from __future__ import annotations

import asyncio
import inspect
import threading
import time
from typing import Any

import pytest

from agent import web_reach
from agent.capability_registry import ToolRegistry, _register_web_reach_tools

_BLOCK_S = 0.5
_MAX_GAP_S = 0.25


async def _max_gap_while(coro: Any) -> float:
    """Longest time the loop went without running a 10 ms ticker while ``coro`` ran."""
    stamps: list[float] = [time.monotonic()]
    stop = asyncio.Event()

    async def ticker() -> None:
        while not stop.is_set():
            stamps.append(time.monotonic())
            await asyncio.sleep(0.01)

    task = asyncio.create_task(ticker())
    await asyncio.sleep(0.05)
    try:
        await coro
    finally:
        stop.set()
        await task
    stamps.append(time.monotonic())
    return max(b - a for a, b in zip(stamps, stamps[1:]))


_TOOLS = {
    "web_search": ("search_web", {"query": "anything"}),
    "fetch_url": ("fetch_page", {"url": "https://example.com/"}),
    "fetch_rss": ("fetch_rss", {"url": "https://example.com/feed"}),
    "youtube_transcript": ("youtube_transcript", {"url": "https://youtu.be/abc"}),
}


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry()
    _register_web_reach_tools(reg)
    return reg


@pytest.mark.parametrize("tool_name", sorted(_TOOLS))
async def test_a_blocking_web_tool_does_not_stall_the_loop(
    tool_name: str, registry: ToolRegistry, monkeypatch: pytest.MonkeyPatch,
) -> None:
    method, args = _TOOLS[tool_name]
    seen: list[int] = []

    def slow(*_a: Any, **_k: Any) -> dict[str, Any]:
        seen.append(threading.get_ident())
        time.sleep(_BLOCK_S)  # deliberate: stands in for a slow httpx.get
        return {"ok": True, "via": method}

    monkeypatch.setattr(web_reach.get_web_reach(), method, slow)
    tool = registry.get(tool_name)
    assert tool is not None
    holder: dict[str, Any] = {}

    async def run() -> None:
        holder["result"] = await tool.handler(**args)

    gap = await _max_gap_while(run())
    assert gap < _MAX_GAP_S, f"{tool_name} stalled the loop for {gap:.2f}s"
    assert holder["result"] == {"ok": True, "via": method}
    assert seen and seen[0] != threading.get_ident(), "the blocking call ran on the loop thread"


@pytest.mark.parametrize("tool_name", sorted(_TOOLS))
def test_web_tool_handlers_are_coroutines(tool_name: str, registry: ToolRegistry) -> None:
    """The agent loop awaits a handler that returns a coroutine; a plain def would run inline."""
    tool = registry.get(tool_name)
    assert tool is not None and inspect.iscoroutinefunction(tool.handler)


async def test_the_ssrf_guard_still_runs_for_every_url_tool(registry: ToolRegistry) -> None:
    """Moving the call to a thread must not skip the rule-14 check inside web_reach."""
    for name in ("fetch_url", "fetch_rss", "youtube_transcript"):
        tool = registry.get(name)
        assert tool is not None
        result = await tool.handler(url="http://127.0.0.1/blocked")
        assert result["ok"] is False, name
        assert "refused" in str(result.get("error", "")).lower() or "blocked" in str(result).lower(), name


# ── Sandbox SDK import ───────────────────────────────────────────────────────


async def test_sdk_import_runs_off_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    from services import sandbox_providers as sp

    threads: list[int] = []

    def slow_import(name: str) -> Any:
        threads.append(threading.get_ident())
        time.sleep(_BLOCK_S)  # deliberate: stands in for the Daytona SDK's model building
        return object()

    monkeypatch.setattr(sp.importlib, "import_module", slow_import)
    gap = await _max_gap_while(sp._warm_sdk("daytona"))
    assert gap < _MAX_GAP_S, f"the SDK import stalled the loop for {gap:.2f}s"
    assert threads and threads[0] != threading.get_ident()


async def test_a_missing_sdk_is_left_for_the_opener_to_report(monkeypatch: pytest.MonkeyPatch) -> None:
    from services import sandbox_providers as sp

    def missing(name: str) -> Any:
        raise ImportError(name)

    monkeypatch.setattr(sp.importlib, "import_module", missing)
    await sp._warm_sdk("daytona")  # must not raise


async def test_open_first_available_warms_the_sdk_before_the_opener(monkeypatch: pytest.MonkeyPatch) -> None:
    from services import sandbox_providers as sp
    from services.e2b_config import E2BConfig

    order: list[str] = []

    async def fake_warm(provider: str) -> None:
        order.append(f"warm:{provider}")

    async def opener(config: Any) -> str:
        order.append(f"open:{config.provider}")
        return "sandbox"

    monkeypatch.setattr(sp, "_warm_sdk", fake_warm)
    monkeypatch.setitem(sp._openers, "daytona", opener)
    config = E2BConfig(provider="daytona", api_key="k")
    result, used = await sp.open_first_available([config])
    assert result == "sandbox" and used is config
    assert order == ["warm:daytona", "open:daytona"]

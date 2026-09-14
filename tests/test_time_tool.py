"""tests/test_time_tool.py — agent/time_tool.py and its capability-registry wiring."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from agent.capability_registry import ToolRegistry, _register_time_tools
from agent.time_tool import get_current_time


def test_get_current_time_returns_well_formed_iso8601_utc() -> None:
    result = get_current_time()
    assert result["ok"] is True

    parsed = datetime.fromisoformat(result["utc"])
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)

    now = datetime.now(timezone.utc)
    assert abs((now - parsed).total_seconds()) < 5


def test_capability_registry_exposes_get_current_time_tool() -> None:
    registry = ToolRegistry()
    _register_time_tools(registry)

    tool = registry.get("get_current_time")
    assert tool is not None
    assert "time" in tool.capabilities
    assert {t.name for t in registry.find_by_capability("time")} == {"get_current_time"}


def test_build_tool_prompt_advertises_get_current_time() -> None:
    """Registration is silent — the Executor only calls tools listed in the
    prompt, so get_current_time must appear there too (rule 19)."""
    from agent.prompts import build_tool_prompt

    messages = build_tool_prompt(
        goal="inspect", step={"description": "look"}, observations=[], remaining_calls=5
    )
    text = " ".join(m["content"] for m in messages)
    assert "get_current_time" in text

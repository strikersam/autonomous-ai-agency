from __future__ import annotations

from datetime import datetime, timezone

from agent.capability_registry import ToolRegistry, _register_time_tools
from agent.time_tool import get_current_time


def test_get_current_time_returns_utc_iso8601() -> None:
    before = datetime.now(timezone.utc)
    result = get_current_time()
    after = datetime.now(timezone.utc)

    assert result["ok"] is True
    parsed = datetime.fromisoformat(result["utc_iso8601"])
    assert parsed.tzinfo is not None
    assert before <= parsed <= after
    assert result["unix_ts"] == int(parsed.timestamp())


def test_capability_registry_exposes_get_current_time_tool() -> None:
    registry = ToolRegistry()
    _register_time_tools(registry)

    tool = registry.get("get_current_time")
    assert tool is not None
    assert "time" in tool.capabilities
    assert {t.name for t in registry.find_by_capability("time")} == {"get_current_time"}

    result = tool.handler()
    assert result["ok"] is True
    assert "utc_iso8601" in result


def test_build_tool_prompt_advertises_get_current_time() -> None:
    """Registration is silent — the Executor only calls tools listed in the
    prompt, so get_current_time must appear there too (rule 19)."""
    from agent.prompts import build_tool_prompt

    messages = build_tool_prompt(
        goal="inspect", step={"description": "look"}, observations=[], remaining_calls=5
    )
    text = " ".join(m["content"] for m in messages)
    assert "get_current_time" in text

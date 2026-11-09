from __future__ import annotations

from agent.action_hash import action_hash, already_executed

READ_ONLY = frozenset({"read_file"})


def test_hash_ignores_key_order_and_differs_by_tool_or_args() -> None:
    assert action_hash("w", {"a": 1, "b": 2}) == action_hash("w", {"b": 2, "a": 1})
    assert action_hash("w", {"a": 1}) != action_hash("w", {"a": 2})
    assert action_hash("w", {"a": 1}) != action_hash("x", {"a": 1})


def test_identical_side_effect_is_detected() -> None:
    history = [{"tool": "write_file", "args": {"path": "a.py", "content": "x"}}]
    assert already_executed(history, "write_file", {"content": "x", "path": "a.py"}, READ_ONLY)


def test_different_args_or_read_only_or_control_not_detected() -> None:
    history = [
        {"tool": "write_file", "args": {"path": "a.py"}},
        {"tool": "read_file", "args": {"path": "b.py"}},
        {"tool": "finish", "args": {"path": "c.py"}},
    ]
    assert not already_executed(history, "write_file", {"path": "other.py"}, READ_ONLY)
    assert not already_executed(history, "read_file", {"path": "b.py"}, READ_ONLY)
    assert not already_executed(history, "finish", {"path": "c.py"}, READ_ONLY)
    assert not already_executed([], "write_file", {}, READ_ONLY)

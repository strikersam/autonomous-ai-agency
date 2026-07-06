"""Tests for agent/stuck_detector.py — OpenHands-style loop detection."""
from __future__ import annotations

import inspect

from agent.stuck_detector import StuckDetector, StuckThresholds


def _obs(tool: str, args: dict | None = None, result: str = "ok") -> dict:
    return {"tool": tool, "args": args or {}, "result": result}


def test_varied_observations_are_not_stuck() -> None:
    detector = StuckDetector()
    observations = [
        _obs("read_file", {"path": "a.py"}, "content a"),
        _obs("read_file", {"path": "b.py"}, "content b"),
        _obs("search_code", {"query": "auth"}, "3 hits"),
        _obs("read_file", {"path": "c.py"}, "content c"),
    ]
    assert detector.check(observations) is None


def test_three_identical_observations_are_stuck() -> None:
    detector = StuckDetector()
    observations = [_obs("read_file", {"path": "a.py"}, "same") for _ in range(3)]
    reason = detector.check(observations)
    assert reason is not None
    assert "read_file" in reason


def test_two_identical_observations_are_not_stuck() -> None:
    detector = StuckDetector()
    observations = [_obs("read_file", {"path": "a.py"}, "same") for _ in range(2)]
    assert detector.check(observations) is None


def test_repeated_action_with_different_errors_is_stuck() -> None:
    detector = StuckDetector()
    observations = [
        _obs("apply_diff", {"path": "a.py"}, f"Error: attempt {i} failed")
        for i in range(3)
    ]
    reason = detector.check(observations)
    assert reason is not None
    assert "failed" in reason


def test_repeated_action_with_different_success_results_is_not_stuck() -> None:
    detector = StuckDetector()
    observations = [
        _obs("search_code", {"query": "auth"}, f"result page {i}") for i in range(4)
    ]
    assert detector.check(observations) is None


def test_alternating_pattern_is_stuck() -> None:
    detector = StuckDetector()
    a = _obs("read_file", {"path": "a.py"}, "content a")
    b = _obs("search_code", {"query": "x"}, "no hits")
    observations = [a, b, a, b, a, b]
    reason = detector.check(observations)
    assert reason is not None
    assert "alternated" in reason


def test_alternating_needs_full_window() -> None:
    detector = StuckDetector()
    a = _obs("read_file", {"path": "a.py"}, "content a")
    b = _obs("search_code", {"query": "x"}, "no hits")
    assert detector.check([a, b, a, b]) is None


def test_custom_thresholds_are_respected() -> None:
    detector = StuckDetector(StuckThresholds(action_observation=5))
    observations = [_obs("read_file", {"path": "a.py"}, "same") for _ in range(4)]
    assert detector.check(observations) is None
    observations.append(_obs("read_file", {"path": "a.py"}, "same"))
    assert detector.check(observations) is not None


def test_malformed_observations_never_raise() -> None:
    detector = StuckDetector()
    assert detector.check([]) is None
    assert detector.check(None) is None  # type: ignore[arg-type]
    garbage = [None, "text", 42, {"no_tool_key": True}, {"tool": object()}]
    assert detector.check(garbage) is None  # type: ignore[arg-type]


def test_unjsonable_args_fall_back_to_str() -> None:
    detector = StuckDetector()
    weird = object()
    observations = [_obs("tool_x", {"obj": weird}, "same") for _ in range(3)]
    assert detector.check(observations) is not None


def test_agent_runner_wires_stuck_detector() -> None:
    """AgentRunner instantiates StuckDetector and checks it in the tool loop."""
    import agent.loop as loop_module

    source = inspect.getsource(loop_module)
    assert "self.stuck = StuckDetector()" in source
    step_source = inspect.getsource(loop_module.AgentRunner._execute_step)
    assert "self.stuck.check(observations)" in step_source
    assert "stuck_detector" in step_source

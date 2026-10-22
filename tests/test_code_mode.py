"""Code Mode (agent/code_mode.py): interpreter subset, limits, gating, loop seam."""
from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from agent import code_mode, prompts
from agent.code_mode import CodeModeLimits, callable_tools, run_code
from agent.models import ToolCall
from packages.config import control_overrides, settings
from packages.config.control_registry import get_control

TOOLS = {"search_code": ["query", "limit"], "head_file": ["path", "lines"], "read_file": ["path"]}


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __call__(self, name: str, args: dict[str, Any]) -> Any:
        self.calls.append((name, args))
        if name == "search_code":
            return [{"path": f"src/m{i}.py", "line": i, "snippet": "def route"} for i in range(10)]
        return f"contents of {args.get('path')}"


def _run(source: str, tools: dict[str, list[str]] | None = None, **limits: Any):
    rec = _Recorder()
    out = asyncio.run(run_code(source, rec, TOOLS if tools is None else tools, CodeModeLimits(**limits)))
    return out, rec


@pytest.fixture()
def on(monkeypatch):
    monkeypatch.setattr(settings, "agent_code_mode_enabled_raw", "true")


def _prompt_text() -> str:
    msgs = prompts.build_tool_prompt(goal="g", step={"description": "s"}, observations=[], remaining_calls=3)
    return msgs[0]["content"]


# ── interpreter ────────────────────────────────────────────────────────────


def test_batches_calls_and_returns_only_result():
    src = (
        "hits = tools.search_code(query='def route', limit=10)\n"
        "paths = [h['path'] for h in hits if h['line'] % 2 == 0][:2]\n"
        "result = {p: tools.head_file(path=p, lines=5)[:11] for p in paths}"
    )
    out, rec = _run(src)
    assert out.ok, out.error
    assert out.result == {"src/m0.py": "contents of", "src/m2.py": "contents of"}
    assert [c[0] for c in rec.calls] == ["search_code", "head_file", "head_file"]
    assert out.calls == ["search_code", "head_file", "head_file"]


def test_positional_args_map_to_advertised_params():
    out, rec = _run("result = tools.read_file('a.py')")
    assert out.ok and rec.calls == [("read_file", {"path": "a.py"})]


def test_last_expression_is_the_value_without_result():
    out, _ = _run("x = 3\nx * 2")
    assert out.ok and out.result == 6


def test_control_flow_and_builtins():
    src = (
        "total = 0\n"
        "for i, v in enumerate(range(10)):\n"
        "    if v == 7:\n"
        "        break\n"
        "    if v % 2:\n"
        "        continue\n"
        "    total += v\n"
        "words = sorted('b a c'.split(), reverse=True)\n"
        "print('total', total)\n"
        "result = [total, words, f'{total:>4}', parse_json('{\"k\": 1}')['k']]"
    )
    out, _ = _run(src)
    assert out.ok, out.error
    assert out.result == [12, ["c", "b", "a"], "  12", 1]
    assert out.printed == ["total 12"]


@pytest.mark.parametrize(
    "src",
    [
        "import os",
        "f = lambda x: x",
        "def f():\n    pass",
        "while True:\n    pass",
        "x = ().__class__",
        "x = _secret",
        "with open('x') as f:\n    pass",
        "class A:\n    pass",
        "x = 'a'.format(1)",
        "x = open('/etc/passwd')",
        "x = getattr(1, 'real')",
        "x = [1].__len__()",
        "x = tools",
        "tools = 1",
        "x = 1\nx.real",
        "x = '%s' % 'a'",
    ],
)
def test_rejects_anything_outside_the_subset(src):
    out, rec = _run(src)
    assert not out.ok and out.error
    assert rec.calls == []


def test_write_tools_are_never_callable():
    out, rec = _run("tools.write_file(path='x', content='y')")
    assert not out.ok and "not callable from run_code" in out.error
    assert rec.calls == []


@pytest.mark.parametrize(
    ("src", "limits"),
    [
        ("x = 'a' * 10000000", {}),
        ("x = 2 ** 100000", {}),
        ("x = 9 ** 60\nfor i in range(10):\n    x = x * x", {}),
        ("x = ('a' * 1000).replace('a', 'b' * 1000)", {}),
        ("x = range(100000)", {}),
        ("for i in range(9000):\n    for j in range(9000):\n        pass", {}),
        ("x = f'{1:>99999}'", {}),
        ("for i in range(5):\n    tools.read_file(path='a')", {"max_tool_calls": 3}),
    ],
)
def test_limits_stop_runaway_programs(src, limits):
    out, _ = _run(src, **limits)
    assert not out.ok and out.error


def test_timeout_is_reported_with_partial_calls():
    async def slow(name: str, args: dict[str, Any]) -> Any:
        await asyncio.sleep(1)
        return "x"

    out = asyncio.run(run_code("tools.read_file(path='a')", slow, TOOLS, CodeModeLimits(timeout_s=0.05)))
    assert not out.ok and "timed out" in out.error


def test_runtime_errors_name_the_line():
    out, _ = _run("x = {}\ny = x['missing']")
    assert not out.ok and out.error.startswith("line 2")


def test_render_truncates_large_results():
    out, _ = _run("result = 'z' * 5000")
    text, truncated = out.render(200)
    assert truncated and len(text) < 300
    text, truncated = out.render(10_000)
    assert not truncated and json.loads(text)["result"] == "z" * 5000


# ── catalogue + prompt gating (rule 19) ─────────────────────────────────────


def test_callable_tools_are_read_only_and_advertised():
    prompt = "- read_file(path)\n- write_file(workspace_id, path, content)\n- head_file(path, lines=50)\n"
    assert callable_tools(prompt) == {"read_file": ["path"], "head_file": ["path", "lines"]}


def test_disabled_web_reach_stays_uncallable_from_run_code(monkeypatch):
    monkeypatch.setattr("agent.web_reach.web_access_enabled", lambda: False)
    assert "fetch_url" not in callable_tools(_prompt_text())


def test_off_by_default_and_hidden_from_prompt():
    assert get_control("AGENT_CODE_MODE_ENABLED").default == "false"
    assert code_mode.code_mode_enabled() is False
    assert "run_code(" not in _prompt_text()


def test_on_advertises_run_code_with_example(on):
    text = _prompt_text()
    assert "- run_code(code)" in text
    assert '"tool": "run_code"' in text


def test_run_code_is_a_parseable_tool_call():
    assert ToolCall(tool="run_code", args={"code": "1"}).tool == "run_code"


def test_platform_control_override_takes_effect():
    control = get_control("AGENT_CODE_MODE_ENABLED")
    assert control is not None and control.live is True
    try:
        control_overrides.apply_overrides({"AGENT_CODE_MODE_ENABLED": "true"})
        assert code_mode.code_mode_enabled() is True
    finally:
        control_overrides.apply_overrides({})
    assert code_mode.code_mode_enabled() is False


# ── AgentRunner seam ───────────────────────────────────────────────────────


def _runner():
    from agent.loop import AgentRunner

    runner = AgentRunner.__new__(AgentRunner)
    seen: list[str] = []

    async def fake_run_tool(tool, args, user_id=None, memory_store=None):
        seen.append(tool)
        return f"{tool}:{args.get('path')}"

    runner._run_tool = fake_run_tool  # type: ignore[method-assign]
    runner._log_event = lambda *a, **k: None  # type: ignore[method-assign]
    return runner, seen


def test_runner_routes_every_inner_call_through_run_tool(on):
    runner, seen = _runner()
    prompt = "- read_file(path)\n- write_file(path, content)\n"
    text = asyncio.run(runner._run_code_mode(
        {"code": "result = [tools.read_file(path=p) for p in ['a', 'b']]"}, prompt,
    ))
    assert seen == ["read_file", "read_file"]
    assert json.loads(text)["result"] == ["read_file:a", "read_file:b"]


def test_runner_refuses_when_switched_off():
    runner, seen = _runner()
    text = asyncio.run(runner._run_code_mode({"code": "tools.read_file(path='a')"}, "- read_file(path)\n"))
    assert "switched off" in text and seen == []


# ── regressions from the independent verifier (rule 49) ────────────────────


@pytest.mark.parametrize(
    "src",
    [
        "result = ','.join(5)",
        "result = [].pop()",
        "result = {}.pop('x')",
        "result = int(1e400)",
        "result = 1e308 ** 2",
        "result = range('a')",
        "result = range(10 ** 30)",
        "result = 1 < 'a'",
        "result = -'a'",
        "result = f'{5:z}'",
        "result = f'{[1]:>5}'",
        "for x in 5:\n    pass",
        "a, b = 5",
        "d = {}\nd[[1]] = 1",
        "l = []\nl[5] = 1",
        "l = [1, 'a']\nl.sort()",
    ],
)
def test_program_runtime_errors_are_results_not_crashes(src):
    out, _ = _run(src)
    assert not out.ok and out.error


@pytest.mark.parametrize(
    "src",
    [
        "x = b'a' * (10 ** 9)",
        "x = len(b'%1000000000s' % b'a')",
        "s = 'a' * 100000\nx = s.replace('', 'b' * 100000)",
        "l = [0] * 200000\nx = [l + [] for i in range(10000)]",
        "l = [0] * 100000\ny = [l] * 1000\nx = str(y)",
        "l = 'a' * 100000\ny = [l] * 1000\nx = f'{y}'",
    ],
)
def test_memory_bombs_are_refused(src):
    out, _ = _run(src)
    assert not out.ok and out.error


def test_aliased_huge_result_is_not_serialised():
    out, _ = _run("l = 'a' * 100000\nresult = [l] * 100")
    text, _ = out.render(6000)
    body = json.loads(text)
    assert body["ok"] is False and "too large" in body["error"]


def test_timeout_interrupts_synchronous_work():
    import time

    src = "l = list(range(10000)) * 19\nfor i in range(10000):\n    l.sort()\n    l.reverse()"
    started = time.monotonic()
    out, _ = _run(src, timeout_s=0.5, max_ops=10 ** 9)
    assert not out.ok and "timed out" in out.error
    assert time.monotonic() - started < 2.0

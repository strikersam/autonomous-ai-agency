from __future__ import annotations

"""Lossless tool-output offload (agent/tool_output_store.py)."""

import pytest

from agent import prompts, tool_output_store as tos
from agent.capability_registry import ToolRegistry, _register_tool_output_tools
from agent.context_manager import ContextManager
from agent.react_loop import ReactScratchpad
from packages.config import control_overrides, settings
from packages.config.control_registry import get_control


@pytest.fixture(autouse=True)
def _fresh_store():
    tos.reset_store()
    yield
    tos.reset_store()


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _ref_in(text: str) -> str:
    return text.split("ref=")[1].split(" ")[0]


def test_offload_and_read_roundtrip():
    st = tos.ToolOutputStore()
    ref = st.offload("hello world")
    assert ref.startswith("out_") and len(ref) > 12
    out = st.read(ref)
    assert out["ok"] and out["content"] == "hello world"
    assert out["total_length"] == 11 and out["next_offset"] is None


def test_paging_next_offset():
    st = tos.ToolOutputStore()
    ref = st.offload("a" * 25)
    first = st.read(ref, offset=0, limit=10)
    assert first["content"] == "a" * 10 and first["next_offset"] == 10
    last = st.read(ref, offset=20, limit=10)
    assert last["content"] == "a" * 5 and last["next_offset"] is None


def test_limit_is_capped():
    st = tos.ToolOutputStore()
    ref = st.offload("x" * 20000)
    assert len(st.read(ref, limit=10**6)["content"]) == tos.MAX_READ_LIMIT


def test_unknown_ref_and_bad_args_never_raise():
    st = tos.ToolOutputStore()
    assert st.read("out_nope")["ok"] is False
    assert st.read(None)["ok"] is False  # type: ignore[arg-type]
    ref = st.offload("abc")
    assert st.read(ref, offset="x")["ok"] is False  # type: ignore[arg-type]


def test_lru_eviction_by_entries_and_recency():
    st = tos.ToolOutputStore(max_entries=2)
    a, b = st.offload("a"), st.offload("b")
    st.read(a)  # a is now most recent
    c = st.offload("c")
    assert st.read(b)["ok"] is False
    assert st.read(a)["ok"] and st.read(c)["ok"]


def test_eviction_by_total_chars():
    st = tos.ToolOutputStore(max_total_chars=10)
    a = st.offload("x" * 6)
    b = st.offload("y" * 6)
    assert st.read(a)["ok"] is False and st.read(b)["ok"]


def test_ttl_expiry():
    clock = Clock()
    st = tos.ToolOutputStore(ttl_seconds=60, clock=clock)
    ref = st.offload("data")
    clock.t = 61
    assert st.read(ref)["ok"] is False


def test_non_string_results_stringified_as_json():
    st = tos.ToolOutputStore()
    ref = st.offload({"k": [1, 2]})
    assert '"k"' in st.read(ref)["content"]


def _obs(n: int, big) -> list[dict]:
    return [{"tool": "t", "args": {}, "result": big if i == 0 else "ok"} for i in range(n)]


def test_masking_adds_ref_and_read_returns_original():
    big = "line\n" * 500
    masked = ContextManager().mask_observations(_obs(8, big))
    first = masked[0]["result"]
    assert "… [masked]" in first and "[full output: ref=out_" in first
    store = tos.get_tool_output_store()
    page = store.read(_ref_in(first), limit=tos.MAX_READ_LIMIT)
    assert page["content"] == big and page["total_length"] == len(big)


def test_masking_list_result_offloaded():
    masked = ContextManager().mask_observations(_obs(8, list(range(300))))
    assert "[list: 300 items — masked]" in masked[0]["result"]
    assert "ref=out_" in masked[0]["result"]


def test_masking_short_results_get_no_ref():
    masked = ContextManager().mask_observations(_obs(8, "short"))
    assert masked[0]["result"] == "short"


def test_scratchpad_offloads_over_2000_chars():
    pad = ReactScratchpad()
    pad.record_observation("z" * 5000)
    result = pad.entries[-1]["result"]
    assert result.startswith("z" * 2000) and "ref=out_" in result
    assert tos.get_tool_output_store().read(_ref_in(result))["total_length"] == 5000
    pad.record_observation("small")
    assert pad.entries[-1]["result"] == "small"


def _prompt_text() -> str:
    msgs = prompts.build_tool_prompt(goal="g", step={"description": "s"}, observations=[], remaining_calls=3)
    return "\n".join(m["content"] for m in msgs)


def test_flag_off_is_unchanged(monkeypatch):
    monkeypatch.setattr(settings, "agent_tool_output_offload_raw", "false")
    big = "line\n" * 500
    masked = ContextManager().mask_observations(_obs(8, big))
    assert masked[0]["result"] == big[:300] + " … [masked]"
    pad = ReactScratchpad()
    pad.record_observation("z" * 5000)
    assert pad.entries[-1]["result"] == "z" * 2000
    assert len(tos.get_tool_output_store()) == 0
    assert "read_tool_output" not in _prompt_text()


def test_prompt_mentions_tool_when_on():
    assert "read_tool_output(ref" in _prompt_text()


def test_registry_exposes_tool_and_reads():
    reg = ToolRegistry()
    _register_tool_output_tools(reg)
    tool = reg.get("read_tool_output")
    assert tool is not None
    ref = tos.get_tool_output_store().offload("payload")
    assert tool.handler(ref)["content"] == "payload"
    assert tool.handler("out_missing")["ok"] is False


def test_platform_control_registered_and_override_is_live():
    spec = get_control("AGENT_TOOL_OUTPUT_OFFLOAD")
    assert spec is not None and spec.live and spec.default == "true"
    applied = dict(control_overrides._applied)
    try:
        control_overrides.apply_overrides({"AGENT_TOOL_OUTPUT_OFFLOAD": "false"})
        assert tos.offload_enabled() is False
        control_overrides.apply_overrides({})
        assert tos.offload_enabled() is True
    finally:
        control_overrides._applied.clear()
        control_overrides._applied.update(applied)

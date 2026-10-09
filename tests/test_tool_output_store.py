from __future__ import annotations

"""Lossless tool-output offload (agent/tool_output_store.py)."""

import pytest

from agent import prompts, tool_output_store as tos
from agent.capability_registry import ToolDef, ToolRegistry, _register_tool_output_tools
from agent.context_manager import ContextManager
from agent.harness_enrichment import HarnessEnrichment
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


def test_scratchpad_is_unchanged():
    # Its prompt context cuts observations to 300 chars, so a ref there would
    # never reach the model: the scratchpad keeps master behaviour.
    from agent.react_loop import ReactScratchpad

    pad = ReactScratchpad()
    pad.record_observation("z" * 5000)
    assert pad.entries[-1]["result"] == "z" * 2000
    assert len(tos.get_tool_output_store()) == 0


def test_identical_masking_reuses_one_ref():
    cm = ContextManager(owner="run_a")
    obs = _obs(8, list(range(300)))
    first = cm.mask_observations(obs)[0]["result"]
    st = tos.get_tool_output_store()
    size, total = len(st), st._total
    for _ in range(10):
        assert cm.mask_observations(obs)[0]["result"] == first
    assert len(st) == size and st._total == total


def test_dedupe_is_per_owner_and_cleaned_on_eviction():
    st = tos.ToolOutputStore(max_entries=1)
    a = st.offload("same", owner="x")
    assert st.offload("same", owner="y") != a
    assert st._by_digest.keys() == {("y", tos._digest("same"))}
    assert st.offload("same", owner="y") is not None


def test_oversize_entry_gets_no_ref_and_evicts_nothing():
    st = tos.ToolOutputStore(max_total_chars=10)
    keep = st.offload("abcd")
    assert st.offload("x" * 20) is None
    assert st.read(keep)["ok"] is True
    assert tos.offload_hint("x" * 20_000_000, 10) == ""


def test_read_is_bound_to_owner():
    st = tos.ToolOutputStore()
    ref = st.offload("secret", owner="run_a")
    assert st.read(ref, owner="run_a")["content"] == "secret"
    assert st.read(ref, owner="run_b")["ok"] is False
    assert st.read(ref)["ok"] is False


def test_infinite_offset_does_not_raise():
    st = tos.ToolOutputStore()
    ref = st.offload("abc")
    assert st.read(ref, offset=float("inf"))["ok"] is False


@pytest.mark.parametrize("n", [51, 55, 61, 62])
def test_masking_boundary_lengths_keep_a_ref(n):
    text = "a" * (n - 1) + "Z"
    out = ContextManager(mask_content_limit=50).mask_observations(_obs(8, text))[0]["result"]
    assert "ref=out_" in out
    assert tos.get_tool_output_store().read(_ref_in(out))["content"] == text


def _prompt_text() -> str:
    msgs = prompts.build_tool_prompt(goal="g", step={"description": "s"}, observations=[], remaining_calls=3)
    return "\n".join(m["content"] for m in msgs)


def test_flag_off_is_unchanged(monkeypatch):
    monkeypatch.setattr(settings, "agent_tool_output_offload_raw", "false")
    big = "line\n" * 500
    masked = ContextManager().mask_observations(_obs(8, big))
    assert masked[0]["result"] == big[:300] + " … [masked]"
    assert len(tos.get_tool_output_store()) == 0
    assert "read_tool_output" not in _prompt_text()


def test_prompt_mentions_tool_when_on():
    assert "read_tool_output(ref" in _prompt_text()


def test_registry_exposes_tool_and_reads():
    reg = ToolRegistry()
    _register_tool_output_tools(reg)
    tool = reg.get("read_tool_output")
    assert tool is not None
    ref = tos.get_tool_output_store().offload("payload", owner="run_a")
    assert tool.handler(ref, owner="run_a")["content"] == "payload"
    assert tool.handler(ref, owner="run_b")["ok"] is False
    assert tool.handler(ref)["ok"] is False
    assert tool.handler("out_missing")["ok"] is False


def test_registry_tool_hidden_and_refuses_when_flag_off(monkeypatch):
    reg = ToolRegistry()
    _register_tool_output_tools(reg)
    tool = reg.get("read_tool_output")
    ref = tos.get_tool_output_store().offload("payload")
    assert tool.is_available()
    assert [t["function"]["name"] for t in reg.to_openai_tools()] == ["read_tool_output"]
    monkeypatch.setattr(settings, "agent_tool_output_offload_raw", "false")
    assert not tool.is_available()
    assert reg.to_openai_tools() == []
    assert tool.handler(ref)["ok"] is False


def _enrichment_block(reg) -> str:
    enr = HarnessEnrichment()
    enr._get_tool_registry = lambda: reg  # type: ignore[method-assign]
    enr._cache_valid = lambda: False  # type: ignore[method-assign]
    return enr.build_tool_block()


def _core_registry() -> ToolRegistry:
    reg = ToolRegistry()
    for i in range(30):
        reg.register(
            ToolDef(name=f"core_tool_{i}", description="d" * 60, parameters={}, handler=lambda: None)
        )
    return reg


def test_enrichment_block_identical_to_master_when_flag_off(monkeypatch):
    baseline = _enrichment_block(_core_registry())
    reg = _core_registry()
    _register_tool_output_tools(reg)
    monkeypatch.setattr(settings, "agent_tool_output_offload_raw", "false")
    assert _enrichment_block(reg) == baseline
    assert "read_tool_output" not in baseline


def test_enrichment_flag_on_never_displaces_core_tools():
    baseline = _enrichment_block(_core_registry())
    reg = _core_registry()
    _register_tool_output_tools(reg)
    block = _enrichment_block(reg)
    core = [ln for ln in baseline.splitlines() if ln.startswith("- ")]
    assert core, "baseline lists no tools"
    for ln in core:
        assert ln in block, ln


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


def test_runner_injects_owner_and_model_cannot_override():
    import asyncio

    from agent.loop import AgentRunner

    reg = ToolRegistry()
    _register_tool_output_tools(reg)
    runner = AgentRunner.__new__(AgentRunner)
    runner._tool_registry = reg
    runner.tools = type("T", (), {"root": "."})()
    runner.ctx = ContextManager(owner="run_mine")
    store = tos.get_tool_output_store()
    mine = store.offload("mine", owner="run_mine")
    theirs = store.offload("theirs", owner="run_other")

    got = asyncio.run(runner._dispatch_tool_unguarded("read_tool_output", {"ref": mine, "owner": "run_other"}))
    assert got["content"] == "mine"
    got = asyncio.run(runner._dispatch_tool_unguarded("read_tool_output", {"ref": theirs, "owner": "run_other"}))
    assert got["ok"] is False

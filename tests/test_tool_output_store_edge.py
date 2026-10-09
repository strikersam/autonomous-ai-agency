from __future__ import annotations

"""Adversarial edge tests for lossless tool-output offload (agent/tool_output_store.py).

Written as a QA pass over commit 0c513fe. Failing tests here are real defects,
not test mistakes; see the QA report for the root cause of each.
"""

import threading

import pytest

from agent import tool_output_store as tos
from agent.capability_registry import ToolRegistry, _register_tool_output_tools
from agent.context_manager import ContextManager
from agent.react_loop import ReactScratchpad
from packages.config import settings


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


def _obs(n: int, big) -> list[dict]:
    return [{"tool": "t", "args": {}, "result": big if i == 0 else "ok"} for i in range(n)]


def _page_all(st: tos.ToolOutputStore, ref: str, limit: int) -> str:
    parts: list[str] = []
    offset: int | None = 0
    while offset is not None:
        page = st.read(ref, offset=offset, limit=limit)
        assert page["ok"] is True
        parts.append(page["content"])
        offset = page["next_offset"]
    return "".join(parts)


# ---------------------------------------------------------------------------
# Paging: exact reassembly, boundaries, bad args
# ---------------------------------------------------------------------------

UNICODE_SAMPLES = [
    "plain ascii " * 40,
    "日本語のテキスト。" * 30,                    # 3-byte UTF-8 chars
    "emoji 🤖🚀👩‍💻 mixed 𝔘𝔫𝔦𝔠𝔬𝔡𝔢" * 10,        # 4-byte code points, ZWJ sequences
    "é" * 50,                                # combining accent split from base
    "null\x00byte and tab\tnewline\n" * 20,
    "é" * 1000,
]


@pytest.mark.parametrize("text", UNICODE_SAMPLES)
@pytest.mark.parametrize("limit", [1, 2, 3, 7, 64, 4000])
def test_paging_reassembles_exact_original(text, limit):
    st = tos.ToolOutputStore()
    ref = st.offload(text)
    assert _page_all(st, ref, limit) == text


def test_offset_at_length_and_length_minus_one():
    st = tos.ToolOutputStore()
    text = "abcdef"
    ref = st.offload(text)
    at_end = st.read(ref, offset=len(text), limit=10)
    assert at_end["ok"] and at_end["content"] == "" and at_end["next_offset"] is None
    last = st.read(ref, offset=len(text) - 1, limit=10)
    assert last["content"] == "f" and last["next_offset"] is None


def test_exact_fit_limit_has_no_next_offset():
    st = tos.ToolOutputStore()
    ref = st.offload("0123456789")
    page = st.read(ref, offset=0, limit=10)
    assert page["content"] == "0123456789" and page["next_offset"] is None


def test_offset_far_beyond_end_is_empty_not_error():
    st = tos.ToolOutputStore()
    ref = st.offload("short")
    page = st.read(ref, offset=10**6, limit=10)
    assert page["ok"] is True and page["content"] == "" and page["next_offset"] is None


def test_negative_offset_and_limit_are_clamped():
    st = tos.ToolOutputStore()
    ref = st.offload("abcdef")
    assert st.read(ref, offset=-5, limit=2)["content"] == "ab"
    assert st.read(ref, offset=0, limit=-3)["content"] == "a"
    assert st.read(ref, offset=0, limit=0)["content"] == "a"


def test_huge_limit_is_capped_not_error():
    st = tos.ToolOutputStore()
    ref = st.offload("q" * 9000)
    page = st.read(ref, offset=0, limit=10**400)
    assert page["ok"] is True and len(page["content"]) == tos.MAX_READ_LIMIT
    assert page["next_offset"] == tos.MAX_READ_LIMIT


@pytest.mark.parametrize(
    "offset,limit",
    [("abc", 10), (None, 10), ([1], 10), (0, "x"), (0, None), ({}, {}), (float("nan"), 5)],
)
def test_non_int_args_return_error_dict(offset, limit):
    st = tos.ToolOutputStore()
    ref = st.offload("hello")
    out = st.read(ref, offset=offset, limit=limit)
    assert out["ok"] is False and "integers" in out["error"]


def test_infinite_float_offset_never_raises():
    # read() documents "Never raises"; int(float('inf')) raises OverflowError,
    # which the except clause (TypeError, ValueError) does not catch.
    st = tos.ToolOutputStore()
    ref = st.offload("hello")
    out = st.read(ref, offset=float("inf"), limit=5)
    assert out["ok"] is False


def test_registry_handler_bad_args_do_not_raise():
    reg = ToolRegistry()
    _register_tool_output_tools(reg)
    tool = reg.get("read_tool_output")
    ref = tos.get_tool_output_store().offload("payload")
    assert tool.handler(ref, offset="nope")["ok"] is False
    assert tool.handler("out_missing", offset=0, limit=5)["ok"] is False


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


def test_single_entry_larger_than_total_cap_gets_no_ref():
    # Reviewer decision (replaces "still retrievable"): an entry that can never
    # fit is rejected up front, so no hint is emitted for a ref that cannot resolve.
    st = tos.ToolOutputStore(max_total_chars=10)
    assert st.offload("x" * 20) is None
    assert len(st) == 0


def test_oversize_entry_does_not_wipe_unrelated_entries_silently():
    st = tos.ToolOutputStore(max_total_chars=10)
    small = st.offload("aaaa")
    st.offload("x" * 50)
    assert st.read(small)["ok"] is True


def test_total_chars_never_exceeds_cap_after_eviction():
    st = tos.ToolOutputStore(max_total_chars=100)
    for i in range(50):
        st.offload(str(i) * 9)
    assert st._total <= 100
    assert st._total == sum(len(e[1]) for e in st._items.values())


def test_entry_cap_keeps_most_recent():
    st = tos.ToolOutputStore(max_entries=3)
    refs = [st.offload(f"v{i}") for i in range(10)]
    assert len(st) == 3
    assert st.read(refs[-1])["ok"] and st.read(refs[0])["ok"] is False


# ---------------------------------------------------------------------------
# TTL with patched clock
# ---------------------------------------------------------------------------


def test_ttl_boundary_with_patched_clock():
    clock = Clock()
    st = tos.ToolOutputStore(ttl_seconds=3600, clock=clock)
    ref = st.offload("data")
    clock.t = 3600.0
    assert st.read(ref)["ok"] is True  # exactly at TTL is still alive (strict >)
    clock.t = 3600.001
    assert st.read(ref)["ok"] is False


def test_ttl_is_from_offload_not_last_read():
    clock = Clock()
    st = tos.ToolOutputStore(ttl_seconds=60, clock=clock)
    ref = st.offload("data")
    clock.t = 50
    assert st.read(ref)["ok"] is True
    clock.t = 61
    assert st.read(ref)["ok"] is False


def test_expired_entries_are_purged_on_next_offload():
    clock = Clock()
    st = tos.ToolOutputStore(ttl_seconds=10, clock=clock)
    for _ in range(5):
        st.offload("old")
    clock.t = 100
    st.offload("new")
    assert len(st) == 1
    assert st._total == len("new")


# ---------------------------------------------------------------------------
# Ref format: unguessable and unique
# ---------------------------------------------------------------------------


def test_refs_unique_and_unguessable_across_10k_offloads():
    st = tos.ToolOutputStore(max_entries=20_000, max_total_chars=100_000_000)
    # Distinct content: identical text from one owner now dedupes to one ref.
    refs = [st.offload(f"content number {i}") for i in range(10_000)]
    assert len(set(refs)) == 10_000
    assert all(r.startswith("out_") for r in refs)
    # token_urlsafe(16) -> 22 url-safe chars (128 bits of entropy)
    assert all(len(r) == len("out_") + 22 for r in refs)
    assert all(set(r[4:]) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_") for r in refs)
    # No sequential or content-derived structure: all prefixes distinct.
    assert len({r[:12] for r in refs}) == 10_000


def test_ref_is_not_derived_from_content():
    st = tos.ToolOutputStore()
    # Same text, different owners (identical text from one owner dedupes).
    assert st.offload("abc", owner="a") != st.offload("abc", owner="b")
    assert tos.ToolOutputStore().offload("abc") != tos.ToolOutputStore().offload("abc")


def test_guessing_a_neighbour_ref_fails():
    st = tos.ToolOutputStore()
    ref = st.offload("secret")
    tampered = ref[:-1] + ("A" if ref[-1] != "A" else "B")
    assert st.read(tampered)["ok"] is False


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


def test_concurrent_offload_and_read_from_threads():
    st = tos.ToolOutputStore(max_entries=100_000, max_total_chars=500_000_000)
    errors: list[BaseException] = []
    results: dict[int, list[tuple[str, str]]] = {}

    def worker(tid: int) -> None:
        try:
            mine: list[tuple[str, str]] = []
            for i in range(300):
                text = f"thread{tid}-item{i}-" + "p" * (i % 17)
                mine.append((st.offload(text), text))
                ref, expected = mine[i // 2]
                assert st.read(ref, limit=8000)["content"] == expected
            results[tid] = mine
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not errors, errors
    assert len(results) == 8
    for mine in results.values():
        for ref, text in mine:
            assert st.read(ref, limit=8000)["content"] == text


def test_concurrent_churn_with_tiny_cap_never_raises():
    st = tos.ToolOutputStore(max_entries=5, max_total_chars=200)
    errors: list[BaseException] = []

    def hammer(tid: int) -> None:
        try:
            for i in range(500):
                ref = st.offload(f"{tid}:{i}" * (i % 9))
                st.read(ref, offset=i % 4, limit=3)
                st.read("out_missing")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=hammer, args=(t,)) for t in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not errors, errors
    assert len(st) <= 5


# ---------------------------------------------------------------------------
# Masking: boundary losslessness, repeated calls, churn
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", range(51, 62))
def test_masking_never_drops_text_without_a_ref(n):
    # mask_content_limit=50 keeps 50 chars and appends " … [masked]" (11 chars).
    # When the result is 51..61 chars the summary is longer than the full
    # text, so offload_hint() compares against the padded length, emits no
    # hint, and the last n-50 characters are silently lost.
    text = "a" * (n - 1) + "Z"
    masked = ContextManager(mask_content_limit=50).mask_observations(_obs(8, text))
    out = masked[0]["result"]
    assert "ref=out_" in out, f"{n}-char result truncated with no ref: {out!r}"
    page = tos.get_tool_output_store().read(_ref_in(out), limit=tos.MAX_READ_LIMIT)
    assert page["content"] == text


def test_masking_repeated_calls_do_not_duplicate_entries():
    # mask_observations runs on every tool iteration over the whole history.
    big = "line\n" * 500
    cm = ContextManager()
    obs = _obs(8, big)
    cm.mask_observations(obs)
    st = tos.get_tool_output_store()
    assert len(st) == 1
    for _ in range(5):
        cm.mask_observations(obs)
    assert len(st) == 1, f"same observation re-offloaded: {len(st)} entries"


def test_masking_repeated_calls_do_not_inflate_total_chars():
    big = "y" * 10_000
    cm = ContextManager()
    obs = _obs(8, big)
    for _ in range(20):
        cm.mask_observations(obs)
    assert tos.get_tool_output_store()._total == len(big)


def test_masking_churn_does_not_evict_other_runs_refs(monkeypatch):
    # The store is a process-wide singleton shared by every agent run. One run
    # re-masking its history every iteration must not push another run's live
    # ref out of a small store.
    small = tos.ToolOutputStore(max_entries=5)
    monkeypatch.setattr(tos, "_store", small)
    other_run_ref = small.offload("other run's tool output")
    cm = ContextManager()
    obs = [{"tool": "t", "args": {}, "result": "B" * 1000 + str(i)} for i in range(8)]
    for _ in range(20):
        cm.mask_observations(obs)
    assert small.read(other_run_ref)["ok"] is True


def test_masked_ref_from_iteration_k_resolves_on_iteration_k_plus_1():
    big = "z" * 1000
    cm = ContextManager()
    obs = _obs(8, big)
    first = cm.mask_observations(obs)[0]["result"]
    second = cm.mask_observations(obs)[0]["result"]
    st = tos.get_tool_output_store()
    assert st.read(_ref_in(first))["ok"] is True
    assert st.read(_ref_in(second))["ok"] is True


def test_masking_dict_and_list_results_roundtrip_json():
    payload = {"rows": [{"id": i, "name": f"név{i}"} for i in range(40)]}
    masked = ContextManager().mask_observations(_obs(8, payload))
    page = tos.get_tool_output_store().read(_ref_in(masked[0]["result"]), limit=tos.MAX_READ_LIMIT)
    assert page["ok"] is True
    assert page["content"] == tos.stringify(payload)


# ---------------------------------------------------------------------------
# Flag off: byte-identical to origin/master behaviour
# ---------------------------------------------------------------------------

# Verbatim copy of origin/master agent/context_manager.py masking logic.
def _origin_summarise(result, limit):
    if isinstance(result, str):
        if len(result) <= limit:
            return result
        return result[:limit] + " … [masked]"
    if isinstance(result, list):
        return f"[list: {len(result)} items — masked]"
    if isinstance(result, dict):
        keys = list(result.keys())[:5]
        return f"[dict keys={keys} — masked]"
    return f"[{type(result).__name__} — masked]"


def _origin_mask(observations, mask_after, limit):
    if len(observations) <= mask_after:
        return list(observations)
    masked = []
    cutoff = len(observations) - mask_after
    for i, obs in enumerate(observations):
        if i < cutoff:
            masked.append(
                {
                    "tool": obs.get("tool", "unknown"),
                    "args": obs.get("args", {}),
                    "result": _origin_summarise(obs.get("result", ""), limit),
                    "_masked": True,
                }
            )
        else:
            masked.append(dict(obs))
    return masked


_FLAG_OFF_RESULTS = [
    "short",
    "",
    "x" * 49,
    "x" * 50,
    "x" * 51,
    "y" * 55,
    "w" * 400,
    "多" * 500,
    list(range(10)),
    list(range(300)),
    {"a": 1, "b": 2},
    {f"k{i}": i for i in range(9)},
    None,
    42,
    3.5,
    ("tuple", "res"),
    b"bytes-result",
]


@pytest.mark.parametrize("limit", [0, 10, 50, 300])
@pytest.mark.parametrize("mask_after", [1, 3, 8])
def test_flag_off_masking_byte_identical_to_origin(monkeypatch, limit, mask_after):
    monkeypatch.setattr(settings, "agent_tool_output_offload_raw", "false")
    obs = [
        {"tool": f"tool{i}", "args": {"i": i}, "result": r}
        for i, r in enumerate(_FLAG_OFF_RESULTS)
    ]
    obs.append({"tool": "no_result_key"})
    cm = ContextManager(mask_after=mask_after, mask_content_limit=limit)
    got = cm.mask_observations(obs)
    expected = _origin_mask(obs, mask_after, limit)
    assert got == expected
    assert [list(o.keys()) for o in got] == [list(o.keys()) for o in expected]
    assert len(tos.get_tool_output_store()) == 0


def test_flag_off_scratchpad_byte_identical_to_origin(monkeypatch):
    monkeypatch.setattr(settings, "agent_tool_output_offload_raw", "false")
    pad = ReactScratchpad()
    for r in _FLAG_OFF_RESULTS + ["q" * 2000, "q" * 2001]:
        pad.record_observation(r)
        expected = str(r)[:2000]
        assert pad.entries[-1]["result"] == expected
    assert len(tos.get_tool_output_store()) == 0


def test_flag_off_prompt_differs_from_flag_on_only_by_tool_line(monkeypatch):
    def prompt() -> str:
        msgs = __import__("agent.prompts", fromlist=["x"]).build_tool_prompt(
            goal="g", step={"description": "s"}, observations=[], remaining_calls=3
        )
        return "\n".join(m["content"] for m in msgs)

    monkeypatch.setattr(settings, "agent_tool_output_offload_raw", "true")
    on = prompt()
    monkeypatch.setattr(settings, "agent_tool_output_offload_raw", "false")
    off = prompt()
    assert "read_tool_output" not in off
    line_start = on.index("- read_tool_output(")
    line_end = on.index("\n", on.index("  tool result shortened", line_start)) + 1
    assert on[:line_start] + on[line_end:] == off


@pytest.mark.parametrize("raw", ["0", "false", "NO", " off ", "False"])
def test_flag_off_spellings(monkeypatch, raw):
    monkeypatch.setattr(settings, "agent_tool_output_offload_raw", raw)
    assert tos.offload_enabled() is False
    assert ContextManager().mask_observations(_obs(8, "k" * 1000))[0]["result"] == "k" * 300 + " … [masked]"

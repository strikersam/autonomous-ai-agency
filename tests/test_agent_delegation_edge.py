"""Adversarial edge tests for agent/delegation.py (QA pass on feat/specialist-delegation-inbox).

Each test asserts the behaviour the feature *should* have. A failing test here is a
finding, not a broken test: see the QA report for the expected-vs-actual notes.
"""
from __future__ import annotations

import asyncio
import contextlib

import pytest

from agent import delegation, prompts
from agent.loop import AgentRunner
from packages.config import control_overrides, settings
from tasks import store as task_store_module
from tasks.models import Task
from tasks.service import TaskExecutionCoordinator, TaskWorkflowService
from tasks.store import TaskStore


@pytest.fixture()
def store(monkeypatch):
    s = TaskStore()
    monkeypatch.setattr(task_store_module, "_global_store", s)

    async def _no_agent(self, task):  # hermetic: no agent-store (Mongo) lookup
        return None

    monkeypatch.setattr(TaskWorkflowService, "_select_agent", _no_agent)
    return s


@pytest.fixture()
def on(monkeypatch):
    monkeypatch.setattr(settings, "agent_delegation_enabled_raw", "true")
    monkeypatch.setattr(settings, "agent_delegation_max_per_session", 5)


def _run(coro):
    return asyncio.run(coro)


@contextlib.contextmanager
def _ctx(owner="u1", session="sess-edge", instruction="plain parent job", depth=0, delegated=False):
    token = delegation.enter_run(owner_id=owner, session_id=session, instruction=instruction,
                                 depth=depth, meta={"delegated": delegated})
    try:
        yield
    finally:
        delegation.exit_run(token)


def _runner(tmp_path):
    return AgentRunner(ollama_base="http://localhost:11434", workspace_root=tmp_path)


def _dispatch(runner, args, user_id="u1"):
    return _run(runner._dispatch_tool_unguarded("delegate_to_specialist", args, user_id=user_id))


# ── 1. Model-supplied owner_id / parent_session_id are ignored ──

def test_model_supplied_context_is_ignored(on, store, tmp_path) -> None:
    with _ctx(session="real-sess"):
        out = _dispatch(_runner(tmp_path), {
            "instruction": "refactor the parser module",
            "owner_id": "victim", "parent_session_id": "forged-sess", "delegated": False,
        })
    assert out["ok"], out
    task = _run(store.get(out["task_id"]))
    assert task.owner_id == "u1"
    assert f"delegation-session:{delegation._session_key('real-sess')}" in task.tags


def test_no_run_owner_is_refused_not_shared_queue(on, store, tmp_path) -> None:
    # DESIGN CHANGE vs the QA draft (which expected owner "system"): the shared agency
    # queue is visible on every board, so a run with no real owner may not delegate.
    with _ctx(owner=""):
        out = _dispatch(_runner(tmp_path), {"instruction": "refactor the parser module", "owner_id": "victim"},
                        user_id=None)
    assert out["ok"] is False and "owner" in out["error"]
    assert _run(store.list_all()) == []


def test_model_cannot_bypass_cap_by_forging_session(on, store, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "agent_delegation_max_per_session", 1)
    with _ctx(session="real-sess"):
        runner = _runner(tmp_path)
        assert _dispatch(runner, {"instruction": "write the unit tests for module a"})["ok"]
        forged = _dispatch(runner, {"instruction": "write the unit tests for module b", "parent_session_id": "fresh"})
    assert forged["ok"] is False and "cap" in forged["error"]


# ── 2. Depth: flag-based, not prompt-text-based ──

def test_marker_text_in_plain_run_is_not_a_false_refusal(on, store, tmp_path) -> None:
    with _ctx(instruction=f"Document the protocol; it uses the token {delegation.DEPTH_MARKER}"):
        out = _dispatch(_runner(tmp_path), {"instruction": "refactor the parser module"})
    assert out["ok"], out


def test_delegated_task_prompt_carries_marker_into_composed_instruction(on, store) -> None:
    out = _run(delegation.delegate_to_specialist(
        "refactor the parser module", owner_id="u1", parent_session_id="sess-1"))
    task = _run(store.get(out["task_id"]))
    composed = TaskExecutionCoordinator._compose_instruction(None, task, None)  # type: ignore[arg-type]
    assert delegation.DEPTH_MARKER in composed


def test_marker_stripped_from_delegated_prompt_still_refused(on, store, tmp_path) -> None:
    out = _run(delegation.delegate_to_specialist(
        "refactor the parser module", owner_id="u1", parent_session_id="sess-1"))
    task = _run(store.get(out["task_id"]))
    task.prompt = "refactor the parser module"  # marker removed (e.g. via task update API)
    _run(store.update(task))
    composed = TaskExecutionCoordinator._compose_instruction(None, task, None)  # type: ignore[arg-type]
    # DESIGN CHANGE vs the QA draft: depth is carried by the task's own tag/source via
    # TaskWorkflowService._build_spec (context["delegation"]), not by prompt text.
    spec = TaskExecutionCoordinator(store=store, agent_store=object(), runtime_manager=object())._build_spec(task, None)
    assert spec.context["delegation"]["delegated"] is True
    with _ctx(instruction=composed, delegated=spec.context["delegation"]["delegated"]):
        out2 = _dispatch(_runner(tmp_path), {"instruction": "another separate job"})
    assert out2["ok"] is False and "depth" in out2["error"]


def test_spawn_subagent_cannot_bypass_depth_one(on, store, tmp_path, monkeypatch) -> None:
    """A delegated run spawns a sub-agent; the child delegates again. Expected: refused."""
    async def fake_impl(self, *args, **kwargs):
        return await self._dispatch_tool_unguarded(
            "delegate_to_specialist", {"instruction": "child wants a grandchild job"}, user_id="u1")

    monkeypatch.setattr(AgentRunner, "_run_impl", fake_impl)
    parent = _runner(tmp_path)
    with _ctx(instruction="parent job", delegated=True):
        child_result = _run(parent._spawn_subagent(instruction="child job"))
    assert child_result["ok"] is False and "depth" in child_result["error"], child_result


def test_spawn_subagent_of_plain_run_cannot_delegate(on, store, tmp_path, monkeypatch) -> None:
    """A sub-agent never delegates, so it cannot reset the session cap or the owner."""
    monkeypatch.setattr(settings, "agent_delegation_max_per_session", 2)

    async def fake_impl(self, *args, **kwargs):
        return await self._dispatch_tool_unguarded(
            "delegate_to_specialist", {"instruction": "child delegates a further job"}, user_id="u1")

    monkeypatch.setattr(AgentRunner, "_run_impl", fake_impl)
    parent = _runner(tmp_path)
    with _ctx(session="sess-cap"):
        assert _dispatch(parent, {"instruction": "write the unit tests for module a"})["ok"]
        assert _dispatch(parent, {"instruction": "write the unit tests for module b"})["ok"]
        child_result = _run(parent._spawn_subagent(instruction="child job"))
    # DESIGN CHANGE vs the QA draft (expected a "cap" error): the child is refused outright
    # (sub-agents are depth > 0), which is stricter than letting it hit the inherited cap.
    assert child_result["ok"] is False and "depth" in child_result["error"], child_result


# ── 3. Empty / whitespace / long instructions ──

@pytest.mark.parametrize("instruction", ["", "   ", "\n\t  ", "abc", " ab "])
def test_empty_and_short_instructions_refused(on, store, instruction) -> None:
    out = _run(delegation.delegate_to_specialist(instruction, owner_id="u1", parent_session_id="s"))
    assert out["ok"] is False
    assert _run(store.list_all()) == []


def test_four_char_instruction_accepted(on, store) -> None:
    out = _run(delegation.delegate_to_specialist("abcd", owner_id="u1", parent_session_id="s"))
    assert out["ok"] is True


def test_very_long_instruction_is_truncated_and_bounded(on, store) -> None:
    out = _run(delegation.delegate_to_specialist("q" * 50_000, owner_id="u1", parent_session_id="s"))
    assert out["ok"] is True
    task = _run(store.get(out["task_id"]))
    assert len(task.prompt) == len(delegation.DEPTH_MARKER) + 1 + 8000
    assert len(task.title) <= 120


def test_very_long_reason_is_bounded_in_description(on, store) -> None:
    out = _run(delegation.delegate_to_specialist(
        "refactor the parser", reason="r" * 50_000, owner_id="u1", parent_session_id="s"))
    assert out["ok"] is True
    task = _run(store.get(out["task_id"]))
    assert len(task.description) < 1500


def test_distinct_long_instructions_are_not_silently_merged(on, store) -> None:
    """Two different jobs that differ only after char 8000 must not dedup to one task."""
    first = _run(delegation.delegate_to_specialist("a" * 8000 + "JOB-ONE", owner_id="u1", parent_session_id="s"))
    second = _run(delegation.delegate_to_specialist("a" * 8000 + "JOB-TWO", owner_id="u1", parent_session_id="s"))
    assert first["task_id"] != second["task_id"]  # EXPECTED: distinct work, distinct task


def test_bad_specialist_path_rejected(on, store) -> None:
    out = _run(delegation.delegate_to_specialist(
        "refactor the parser", specialist="../../etc", owner_id="u1", parent_session_id="s"))
    assert out["ok"] is False


# ── 4. check_delegation scoping ──

def test_check_delegation_other_owner_is_not_found(on, store) -> None:
    out = _run(delegation.delegate_to_specialist("refactor the parser", owner_id="u1", parent_session_id="s"))
    assert _run(delegation.check_delegation(out["task_id"], owner_id="u2", parent_session_id="s"))["ok"] is False
    assert _run(delegation.check_delegation(out["task_id"], owner_id="u1", parent_session_id="s"))["ok"] is True


def test_check_delegation_non_delegation_task_is_not_found(on, store) -> None:
    manual = _run(store.create(Task(owner_id="u1", title="manual task")))
    assert _run(delegation.check_delegation(manual.task_id, owner_id="u1")) == {
        "ok": False, "error": "no delegated task with that id"}


def test_check_delegation_unknown_id_is_not_found(on, store) -> None:
    assert _run(delegation.check_delegation("does-not-exist", owner_id="u1"))["ok"] is False


def test_check_delegation_other_session_same_owner_is_not_found(on, store, tmp_path) -> None:
    out = _run(delegation.delegate_to_specialist("refactor the parser", owner_id="u1", parent_session_id="sess-A"))
    res = _run(delegation.check_delegation(out["task_id"], owner_id="u1", parent_session_id="sess-B"))
    assert res["ok"] is False  # EXPECTED: the delegating session only; check ignores parent_session_id


# ── 5. Cap boundary ──

def test_cap_boundary_fifth_allowed_sixth_refused(on, store) -> None:
    results = [
        _run(delegation.delegate_to_specialist(f"write the unit tests for module {i}",
                                               owner_id="u1", parent_session_id="cap-s"))
        for i in range(6)
    ]
    assert all(r["ok"] for r in results[:5]), results[:5]
    assert results[5]["ok"] is False and "cap" in results[5]["error"]
    assert len(_run(store.list_all())) == 5


# ── 6. Flag toggled off mid-session ──

def test_flag_toggled_off_mid_session_refuses_and_hides(on, store, tmp_path) -> None:
    runner = _runner(tmp_path)
    with _ctx():
        created = _dispatch(runner, {"instruction": "refactor the parser module"})
    assert created["ok"]
    applied = dict(control_overrides._applied)
    try:
        control_overrides.apply_overrides({"AGENT_DELEGATION_ENABLED": "false"})
        assert delegation.delegation_enabled() is False
        with _ctx():
            assert _dispatch(runner, {"instruction": "another separate job"})["ok"] is False
        assert _run(delegation.check_delegation(
            created["task_id"], owner_id="u1", parent_session_id="sess-edge"))["ok"] is False
        msgs = prompts.build_tool_prompt(goal="g", step={"description": "s"}, observations=[], remaining_calls=3)
        assert "delegate_to_specialist" not in "\n".join(m["content"] for m in msgs)
    finally:
        control_overrides.apply_overrides({})
        control_overrides._applied.clear()
        control_overrides._applied.update(applied)


def test_flag_toggled_back_on_restores_delegation(on, store, tmp_path) -> None:
    applied = dict(control_overrides._applied)
    try:
        control_overrides.apply_overrides({"AGENT_DELEGATION_ENABLED": "false"})
        assert _run(delegation.delegate_to_specialist("refactor the parser", owner_id="u1", parent_session_id="s"))["ok"] is False
        control_overrides.apply_overrides({"AGENT_DELEGATION_ENABLED": "true"})
        assert _run(delegation.delegate_to_specialist("refactor the parser", owner_id="u1", parent_session_id="s"))["ok"] is True
    finally:
        control_overrides.apply_overrides({})
        control_overrides._applied.clear()
        control_overrides._applied.update(applied)

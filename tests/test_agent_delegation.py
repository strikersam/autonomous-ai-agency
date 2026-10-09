"""Tests for agent/delegation.py — async agent-to-agent delegation via the task store."""
from __future__ import annotations

import asyncio

import pytest

from agent import delegation, prompts
from agent.capability_registry import ToolRegistry, _register_delegation_tools
from packages.config import control_overrides, settings
from packages.config.control_registry import get_control
from tasks import store as task_store_module
from tasks.models import TaskStatus
from tasks.service import TaskWorkflowService
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


def _delegate(instruction="refactor the parser module", **kw):
    kw.setdefault("owner_id", "u1")
    kw.setdefault("parent_session_id", "sess-1")
    return _run(delegation.delegate_to_specialist(instruction, **kw))


def test_creates_task_with_tags_source_and_specialist(on, store) -> None:
    out = _delegate(specialist="QA", reason="needs tests")
    assert out["ok"] and out["status"] == "queued"
    task = _run(store.get(out["task_id"]))
    assert task.source == delegation.DELEGATION_SOURCE
    assert delegation.DELEGATED_TAG in task.tags
    assert "specialist-family:qa" in task.tags
    assert task.source_id.startswith("agent-delegation:")
    assert delegation.DEPTH_MARKER in task.prompt


def test_dedup_same_session_and_instruction(on, store) -> None:
    first = _delegate()
    again = _delegate()
    assert again["task_id"] == first["task_id"] and again["deduplicated"] is True
    other_session = _delegate(parent_session_id="sess-2")
    assert other_session["task_id"] != first["task_id"]


def test_per_session_cap(on, store, monkeypatch) -> None:
    monkeypatch.setattr(settings, "agent_delegation_max_per_session", 2)
    assert _delegate("write the unit tests for module a")["ok"]
    assert _delegate("write the unit tests for module b")["ok"]
    third = _delegate("write the unit tests for module c")
    assert third["ok"] is False and "cap" in third["error"]
    assert _delegate("write the unit tests for module c", parent_session_id="sess-2")["ok"]


def test_outward_facing_text_requires_approval(on, store) -> None:
    out = _delegate("email the customer list with the new pricing")
    assert out["requires_approval"] is True and out["status"] == "awaiting_approval"
    task = _run(store.get(out["task_id"]))
    assert task.requires_approval and not task.execution_approved


def test_internal_work_is_not_gated(on, store) -> None:
    assert _delegate("refactor the parser module")["requires_approval"] is False


def test_depth_refusal_for_delegated_run(on, store) -> None:
    out = _delegate(parent_instruction=f"Task prompt:\n{delegation.DEPTH_MARKER}\ndo x")
    assert out["ok"] is False and "depth" in out["error"]
    assert _run(store.list_all()) == []


def test_bad_inputs_refused(on, store) -> None:
    assert _delegate("x")["ok"] is False
    assert _delegate(specialist="Bad Role!")["ok"] is False


def test_run_without_session_gets_per_run_key(on, store) -> None:
    a = _delegate(parent_session_id="", parent_instruction="run A")
    b = _delegate(parent_session_id="", parent_instruction="run B")
    assert a["task_id"] != b["task_id"]


@pytest.mark.parametrize("state,expected", [
    (TaskStatus.TODO, "queued"), (TaskStatus.IN_PROGRESS, "running"),
    (TaskStatus.DONE, "done"), (TaskStatus.FAILED, "failed"),
])
def test_check_delegation_states(on, store, state, expected) -> None:
    out = _delegate()
    task = _run(store.get(out["task_id"]))
    task.status, task.result, task.error_message = state, "r" * 5000, "boom"
    _run(store.update(task))
    checked = _run(delegation.check_delegation(out["task_id"], owner_id="u1"))
    assert checked["status"] == expected
    if expected == "done":
        assert len(checked["summary"]) == 2000 and "data" in checked["note"]
    if expected == "failed":
        assert checked["error"] == "boom"


def test_check_delegation_awaiting_approval(on, store) -> None:
    out = _delegate("email the customer list with the new pricing")
    assert _run(delegation.check_delegation(out["task_id"], owner_id="u1"))["status"] == "awaiting_approval"


def test_check_delegation_only_for_delegated_and_owned_tasks(on, store) -> None:
    from tasks.models import Task

    manual = _run(store.create(Task(owner_id="u1", title="manual task")))
    assert _run(delegation.check_delegation(manual.task_id, owner_id="u1"))["ok"] is False
    out = _delegate()
    assert _run(delegation.check_delegation(out["task_id"], owner_id="someone-else"))["ok"] is False
    assert _run(delegation.check_delegation("nope", owner_id="u1"))["ok"] is False


def test_flag_off_refuses_and_hides_tools(store, monkeypatch) -> None:
    assert delegation.delegation_enabled() is False
    out = _delegate()
    assert out["ok"] is False and "AGENT_DELEGATION_ENABLED" in out["error"]
    assert _run(delegation.check_delegation("t"))["ok"] is False
    assert _run(store.list_all()) == []
    text = _prompt_text()
    assert "delegate_to_specialist" not in text and "check_delegation" not in text


def _prompt_text() -> str:
    msgs = prompts.build_tool_prompt(goal="g", step={"description": "s"}, observations=[], remaining_calls=3)
    return "\n".join(m["content"] for m in msgs)


def test_flag_on_advertises_tools(on) -> None:
    text = _prompt_text()
    assert "- delegate_to_specialist(" in text and "- check_delegation(" in text


def test_registry_exposes_tools_with_injected_context_hidden_from_schema() -> None:
    reg = ToolRegistry()
    _register_delegation_tools(reg)
    for name in ("delegate_to_specialist", "check_delegation"):
        assert name in reg._tools
        props = reg._tools[name].parameters["properties"]
        assert not {"owner_id", "parent_session_id", "parent_instruction"} & set(props)


def test_governance_classifies_delegation_on_agent_surface() -> None:
    from packages.governance.enforcement import classify
    from packages.governance.policy import Surface

    assert classify("delegate_to_specialist", {"instruction": "x"}) == (Surface.AGENT, "delegate_task")


def test_runner_injects_context_into_registry_handler(on, store, tmp_path) -> None:
    from agent.loop import AgentRunner

    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=tmp_path)
    runner._current_session_id = "sess-runner"
    runner._current_instruction = "plain parent job"
    out = _run(runner._dispatch_tool_unguarded(
        "delegate_to_specialist",
        {"instruction": "refactor the parser module", "owner_id": "spoofed", "parent_session_id": "spoofed"},
        user_id="u9",
    ))
    assert out["ok"], out
    task = _run(store.get(out["task_id"]))
    assert task.owner_id == "u9" and "sess-runner" in task.description
    runner._current_instruction = f"x {delegation.DEPTH_MARKER}"
    refused = _run(runner._dispatch_tool_unguarded(
        "delegate_to_specialist", {"instruction": "another separate job"}, user_id="u9"))
    assert refused["ok"] is False and "depth" in refused["error"]


def test_platform_control_override_is_live() -> None:
    assert get_control("AGENT_DELEGATION_ENABLED").live is True
    assert get_control("AGENT_DELEGATION_ENABLED").default == "false"
    assert get_control("AGENT_DELEGATION_MAX_PER_SESSION").live is True
    assert get_control("AGENT_DELEGATION_MAX_PER_SESSION").default == "5"
    applied = dict(control_overrides._applied)
    try:
        control_overrides.apply_overrides({"AGENT_DELEGATION_ENABLED": "true",
                                           "AGENT_DELEGATION_MAX_PER_SESSION": "2"})
        assert delegation.delegation_enabled() and delegation._max_per_session() == 2
        control_overrides.apply_overrides({})
        assert not delegation.delegation_enabled() and delegation._max_per_session() == 5
    finally:
        control_overrides._applied.clear()
        control_overrides._applied.update(applied)

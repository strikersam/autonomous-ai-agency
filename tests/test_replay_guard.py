"""AGENT_REPLAY_GUARD_ENABLED: a resumed run does not repeat a tool call that committed."""
from __future__ import annotations

import pytest

from agent import replay_guard
from packages.runs import task_binding
from packages.runs.models import OperationState
from packages.runs.operations import OperationLedger
from tests._runs_task_fixtures import FakeRuntime, coordinator, queued_task, reset_process_state, sqlite_pair


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    reset_process_state(monkeypatch)
    monkeypatch.setenv("RUNS_LEDGER_ENABLED", "true")
    monkeypatch.delenv("AGENCY_KILL_SWITCH", raising=False)


class _Tool:
    def __init__(self, result="ok"):
        self.calls = 0
        self.result = result

    async def __call__(self, tool, args, **kwargs):
        self.calls += 1
        return self.result


def test_classification_matches_checkpoint_rules():
    assert replay_guard.is_side_effecting("create_pull_request") is True
    assert replay_guard.is_side_effecting("read_file") is False
    assert replay_guard.is_side_effecting("finish") is False


@pytest.mark.anyio
async def test_guard_off_is_a_plain_pass_through(monkeypatch):
    monkeypatch.delenv("AGENT_REPLAY_GUARD_ENABLED", raising=False)
    tool = _Tool()
    assert await replay_guard.run_recorded(tool, "create_pull_request", {"a": 1}) == "ok"
    assert tool.calls == 1


@pytest.mark.anyio
async def test_without_a_bound_run_the_call_just_runs(monkeypatch):
    monkeypatch.setenv("AGENT_REPLAY_GUARD_ENABLED", "true")
    tool = _Tool()
    assert await replay_guard.run_recorded(tool, "create_pull_request", {"a": 1}) == "ok"
    assert tool.calls == 1


@pytest.mark.anyio
async def test_a_read_only_call_is_never_recorded(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_REPLAY_GUARD_ENABLED", "true")
    async with sqlite_pair(tmp_path) as (store, _):
        task = await queued_task(store)
        box, tool = {}, _Tool()

        async def body(spec):
            box["run"] = task_binding.current_run.get().run_id
            await replay_guard.run_recorded(tool, "read_file", {"path": "x"})
            return await FakeRuntime().execute(spec)

        await coordinator(store, FakeRuntime(body)).execute(task.task_id)
        assert await OperationLedger(task_binding.run_store_for(store)).list(box["run"]) == []


@pytest.mark.anyio
async def test_a_committed_call_is_skipped_on_replay_and_a_failed_one_is_not(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_REPLAY_GUARD_ENABLED", "true")
    async with sqlite_pair(tmp_path) as (store, _):
        task = await queued_task(store)
        box = {}
        done, failing = _Tool("created #7"), _Tool("[tool error: boom]")

        async def body(spec):
            binding = task_binding.current_run.get()
            box["run"] = binding.run_id
            args = {"title": "x"}
            first = await replay_guard.run_recorded(done, "create_issue", args)
            binding.occurrences.clear()  # a fresh attempt counts occurrences from the start
            replay = await replay_guard.run_recorded(done, "create_issue", args)
            f1 = await replay_guard.run_recorded(failing, "post_comment", {"b": 1})
            binding.occurrences.clear()
            f2 = await replay_guard.run_recorded(failing, "post_comment", {"b": 1})
            box.update(first=first, replay=replay, f1=f1, f2=f2)
            return await FakeRuntime().execute(spec)

        await coordinator(store, FakeRuntime(body)).execute(task.task_id)
        assert box["first"] == "created #7" and done.calls == 1
        assert "already completed" in box["replay"] and "created #7" in box["replay"]
        assert box["f1"] == box["f2"] == "[tool error: boom]" and failing.calls == 2  # never skipped
        ops = await OperationLedger(task_binding.run_store_for(store)).list(box["run"])
        states = {o.tool: o.state for o in ops if o.tool == "create_issue"}
        assert states == {"create_issue": OperationState.COMMITTED}
        assert all(o.state is OperationState.FAILED for o in ops if o.tool == "post_comment")


@pytest.mark.anyio
async def test_non_json_args_are_not_guarded(monkeypatch, tmp_path):
    from pathlib import Path

    monkeypatch.setenv("AGENT_REPLAY_GUARD_ENABLED", "true")
    async with sqlite_pair(tmp_path) as (store, _):
        task = await queued_task(store)
        tool = _Tool()

        async def body(spec):
            await replay_guard.run_recorded(tool, "create_issue", {"p": Path("x")})
            return await FakeRuntime().execute(spec)

        await coordinator(store, FakeRuntime(body)).execute(task.task_id)
        assert tool.calls == 1


@pytest.mark.parametrize("result", [
    "[tool error: boom]", "[governance] blocked by policy", "[error: execute_skill x]",
    "[skill error: y]", "[save_snippet refused: z]", "[run_code is not available here]",
    "[edit_file not applied: no]", {"error": "bad"},
])
def test_failure_shapes_are_never_committed(result):
    assert replay_guard._failed(result) is True


@pytest.mark.parametrize("result", ["created #7", "ok", {"url": "u"}, "[1, 2, 3]"])
def test_success_shapes_are_committed(result):
    assert replay_guard._failed(result) is False

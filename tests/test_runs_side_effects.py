"""Phase 2 D: git push and PR creation are recorded side effects, never repeated on replay."""
from __future__ import annotations

import asyncio
import subprocess  # nosec B404 - fixed git argv in list form, local temp repos only
import time
from pathlib import Path

import pytest

from packages.runs import reconcilers, side_effects, task_binding
from packages.runs.models import OperationRecord, OperationState
from packages.runs.operations import DONE, NOT_DONE, UNKNOWN, OperationLedger
from packages.runs.recovery import RecoveryService
from tests._runs_task_fixtures import (FakeRuntime, coordinator, queued_task,
                                       reset_process_state, sqlite_pair)

LATER = 1000  # past the lease TTL and every operation deadline


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    reset_process_state(monkeypatch)
    monkeypatch.setenv("RUNS_LEDGER_ENABLED", "true")
    monkeypatch.setenv("RUNS_RECOVERY_ENABLED", "true")
    monkeypatch.setenv("RUNS_RETRY_BACKOFF_BASE_SEC", "0")
    monkeypatch.delenv("AGENCY_KILL_SWITCH", raising=False)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(  # nosec B603 B607 - fixed argv, no shell
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        cwd=cwd, check=True, capture_output=True, text=True, timeout=30).stdout.strip()


def _repo_with_remote(tmp_path: Path) -> tuple[Path, str]:
    remote, local = tmp_path / "remote.git", tmp_path / "local"
    remote.mkdir()
    _git(remote, "init", "--bare", "-q")
    local.mkdir()
    _git(local, "init", "-q", "-b", "main")
    (local / "f.txt").write_text("x")
    _git(local, "add", "f.txt")
    _git(local, "commit", "-q", "-m", "c1")
    _git(local, "remote", "add", "origin", str(remote))
    return local, _git(local, "rev-parse", "HEAD")


async def _attempt_then_die(store, task, effect, *, die_inside: bool):
    """First attempt: run *effect* (inside the ledger record), then the worker dies."""
    reached, box = asyncio.Event(), {}

    async def body(spec):
        binding = box["b"] = task_binding.current_run.get()
        box["branch"] = side_effects.task_branch_name()
        if die_inside:
            async with effect():
                await binding.heartbeat.stop()
                reached.set()
                await asyncio.Event().wait()
        async with effect():
            pass
        await binding.heartbeat.stop()
        reached.set()
        await asyncio.Event().wait()

    job = asyncio.create_task(coordinator(store, FakeRuntime(body)).execute(task.task_id))
    await reached.wait()
    return job, box


@pytest.mark.anyio
async def test_a_push_the_remote_already_holds_is_not_repeated(tmp_path):
    local, sha = _repo_with_remote(tmp_path)
    pushes: list[str] = []
    args = {"branch": "agent/task-x", "sha": sha}

    def push_effect():
        @__import__("contextlib").asynccontextmanager
        async def cm():
            async with side_effects.recorded_effect(
                    "git_push", args, {**args, "cwd": str(local)}, 60) as fx:
                if not fx.skipped:
                    pushes.append(sha)
                    _git(local, "push", "-q", "origin", "HEAD:refs/heads/agent/task-x")
                yield fx
        return cm()

    async with sqlite_pair(tmp_path) as (worker, survivor):
        task = await queued_task(worker)
        job, box = await _attempt_then_die(worker, task, push_effect, die_inside=True)
        run_id = box["b"].run_id
        report = await RecoveryService(survivor).tick(now=time.time() + LATER)
        assert report.recovered == [run_id] and report.parked == []
        ops = await OperationLedger(task_binding.run_store_for(survivor)).list(run_id)
        assert [o.state for o in ops] == [OperationState.COMMITTED]  # reconciled as done

        await _end(job)  # the stale worker's process claim goes with it
        second = {}

        async def body2(spec):
            second["branch"] = side_effects.task_branch_name()
            async with push_effect() as fx:
                second["skipped"] = fx.skipped
            return await FakeRuntime().execute(spec)

        await coordinator(survivor, FakeRuntime(body2)).execute(task.task_id)
        assert pushes == [sha] and second["skipped"] is True
        assert box["branch"] == second["branch"] == f"agent/task-{task.task_id}"


@pytest.mark.anyio
async def test_a_pull_request_is_not_opened_again_on_replay(tmp_path):
    opened: list[str] = []
    args = {"owner": "o", "repo": "r", "head": "agent/task-x", "base": "main"}
    seen = {}

    def pr_effect():
        @__import__("contextlib").asynccontextmanager
        async def cm():
            async with side_effects.recorded_effect("open_pull_request", args, args, 30) as fx:
                if not fx.skipped:
                    opened.append("pr")
                    fx.result_ref = "https://github.com/o/r/pull/1"
                yield fx
            seen["url"] = fx.result_ref
        return cm()

    async with sqlite_pair(tmp_path) as (worker, survivor):
        task = await queued_task(worker)
        job, box = await _attempt_then_die(worker, task, pr_effect, die_inside=False)
        report = await RecoveryService(survivor).tick(now=time.time() + LATER)
        assert report.recovered == [box["b"].run_id]

        await _end(job)  # the stale worker's process claim goes with it
        async def body2(spec):
            async with pr_effect() as fx:
                seen["skipped"] = fx.skipped
            return await FakeRuntime().execute(spec)

        await coordinator(survivor, FakeRuntime(body2)).execute(task.task_id)
        assert opened == ["pr"] and seen["skipped"] is True
        assert seen["url"] == "https://github.com/o/r/pull/1"


@pytest.mark.anyio
async def test_without_a_bound_run_the_effect_just_runs():
    assert task_binding.current_run.get() is None
    async with side_effects.recorded_effect("git_push", {"a": 1}, {}, 10) as fx:
        assert fx.skipped is False
    assert side_effects.task_branch_name().startswith("agent/task-")


@pytest.mark.anyio
async def test_a_failed_effect_is_marked_failed_and_reraised(tmp_path):
    async with sqlite_pair(tmp_path) as (store, _):
        task = await queued_task(store)
        box = {}

        async def body(spec):
            box["run"] = task_binding.current_run.get().run_id
            with pytest.raises(RuntimeError):
                async with side_effects.recorded_effect("git_push", {"a": 1}, {}, 10):
                    raise RuntimeError("rejected")
            return await FakeRuntime().execute(spec)

        await coordinator(store, FakeRuntime(body)).execute(task.task_id)
        ops = await OperationLedger(task_binding.run_store_for(store)).list(box["run"])
        assert [o.state for o in ops] == [OperationState.FAILED]


async def _end(job):
    job.cancel()
    with pytest.raises(BaseException):
        await job


def _op(tool: str, target: dict) -> OperationRecord:
    return OperationRecord(op_id="r:1", run_id="r", seq=1, tool=tool, action_hash="h",
                           target=target, token=1)


@pytest.mark.anyio
async def test_git_push_reconciler(tmp_path):
    local, sha = _repo_with_remote(tmp_path)
    target = {"branch": "agent/task-x", "sha": sha, "cwd": str(local)}
    assert await reconcilers.reconcile_git_push(_op("git_push", target)) == NOT_DONE
    _git(local, "push", "-q", "origin", "HEAD:refs/heads/agent/task-x")
    assert await reconcilers.reconcile_git_push(_op("git_push", target)) == DONE
    bad = {**target, "cwd": str(tmp_path / "missing")}
    assert await reconcilers.reconcile_git_push(_op("git_push", bad)) == UNKNOWN
    assert await reconcilers.reconcile_git_push(_op("git_push", {**target, "sha": "x;y"})) \
        == UNKNOWN


@pytest.mark.anyio
async def test_open_pull_request_reconciler(monkeypatch):
    target = {"owner": "o", "repo": "r", "head": "agent/task-x", "base": "main"}

    class _Client:
        def __init__(self, pulls=None, error=None):
            self.pulls, self.error = pulls or [], error

        async def list_pull_requests(self, owner, repo, state="open"):
            if self.error:
                raise self.error
            return self.pulls

    cases = [(_Client([{"head": {"ref": "agent/task-x"}}]), DONE),
             (_Client([{"head": {"ref": "other"}}]), NOT_DONE),
             (_Client(error=RuntimeError("503")), UNKNOWN)]
    for client, expected in cases:
        monkeypatch.setattr(reconcilers, "_github_client", lambda c=client: c)
        assert await reconcilers.reconcile_open_pull_request(
            _op("open_pull_request", target)) == expected


@pytest.mark.anyio
async def test_checkout_branch_reuses_a_branch_left_by_an_earlier_attempt(tmp_path):
    from agent.github_tools import LocalWorkspace

    local, _ = _repo_with_remote(tmp_path)
    ws = LocalWorkspace("o", "r")
    ws.path = local
    await side_effects.checkout_branch(ws, "agent/task-x", "main")
    _git(local, "checkout", "-q", "main")
    (local / "g.txt").write_text("y")
    _git(local, "add", "g.txt")
    _git(local, "commit", "-q", "-m", "c2")
    await side_effects.checkout_branch(ws, "agent/task-x", "main")  # exists: moved, not an error
    assert _git(local, "rev-parse", "agent/task-x") == _git(local, "rev-parse", "main")
    assert _git(local, "branch", "--show-current") == "agent/task-x"

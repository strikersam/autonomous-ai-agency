"""Preparing a task workspace must not freeze the event loop.

``InternalAgentAdapter._open_workspace`` ran ``git worktree add`` and then a
full copy of the workspace directly on the event loop. In production the app
directory is not a git repo, so every task fell through to the copy; nothing
else, including Render's 5-second health check, could run until it finished.
"""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from types import SimpleNamespace

from runtimes.adapters.internal_agent import InternalAgentAdapter


async def _ticks_while(coro) -> tuple[object, int]:
    """Run *coro* and count how many times the loop got to run meanwhile."""
    ticks = 0
    done = asyncio.Event()

    async def ticker() -> None:
        nonlocal ticks
        while not done.is_set():
            await asyncio.sleep(0.01)
            ticks += 1

    task = asyncio.create_task(ticker())
    try:
        result = await coro
    finally:
        done.set()
        await task
    return result, ticks


async def test_open_workspace_keeps_the_loop_responsive(monkeypatch, tmp_path: Path) -> None:
    def slow_create(workspace: str, task_id: str):
        time.sleep(0.4)  # stands in for git + a full workspace copy
        return workspace, None

    monkeypatch.setattr(InternalAgentAdapter, "_create_worktree", staticmethod(slow_create))
    adapter = InternalAgentAdapter.__new__(InternalAgentAdapter)
    spec = SimpleNamespace(context={}, task_id="t1")
    (path, tmp), ticks = await _ticks_while(adapter._open_workspace(spec, str(tmp_path)))
    assert path == str(tmp_path) and tmp is None
    assert ticks >= 10, f"the loop ran only {ticks} times during a 0.4s workspace build"


def test_copy_survives_a_dangling_symlink(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "real.txt").write_text("ok", encoding="utf-8")
    os.symlink(str(workspace / "missing-target.md"), str(workspace / "dangling.md"))
    path, tmp = InternalAgentAdapter._create_worktree(str(workspace), "task-x")
    try:
        assert path != str(workspace), "a dangling link must not force the live workspace"
        assert (Path(path) / "real.txt").read_text(encoding="utf-8") == "ok"
    finally:
        InternalAgentAdapter._remove_worktree(str(workspace), path, tmp)


def test_cleanup_runs_off_the_loop_in_source() -> None:
    src = Path(InternalAgentAdapter.__module__.replace(".", "/") + ".py").read_text(encoding="utf-8")
    assert "self._remove_worktree(base_workspace" not in src, "cleanup must go through to_thread"
    assert src.count("asyncio.to_thread(") >= 3

"""Bug #9: registry file tools must act on the runner's workspace, not the process root.

The capability registry is a process-wide singleton whose file tools were bound to
the process root at build time. ``_dispatch_tool_unguarded`` checks the registry
first, so an agent's ``read_file``/``edit_file`` on a worktree or tmp workspace
read and wrote the server's own checkout instead (an agent write landed in the
live repo during a test run, 2026-06-14).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from agent.loop import AgentRunner


@pytest.fixture()
def runner(tmp_path: Path) -> AgentRunner:
    root = tmp_path / "ws"
    root.mkdir()
    (root / "only_in_ws.txt").write_text("workspace copy\n")
    (root / "edit_me.txt").write_text("alpha beta\n")
    return AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)


def _dispatch(runner: AgentRunner, tool: str, args: dict) -> object:
    return asyncio.run(runner._dispatch_tool_unguarded(tool, args))


def test_read_file_reads_the_runner_workspace(runner):
    assert "workspace copy" in str(_dispatch(runner, "read_file", {"path": "only_in_ws.txt"}))


def test_list_and_search_use_the_runner_workspace(runner):
    assert "only_in_ws.txt" in str(_dispatch(runner, "list_files", {"path": "."}))
    hits = _dispatch(runner, "search_code", {"query": "workspace copy"})
    assert any("only_in_ws.txt" in str(h) for h in hits)


def test_edit_file_edits_the_runner_workspace_only(runner):
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "edit_me.txt").exists()
    _dispatch(runner, "edit_file", {"path": "edit_me.txt", "old_string": "alpha", "new_string": "gamma"})
    assert (runner.tools.root / "edit_me.txt").read_text() == "gamma beta\n"
    assert not (repo_root / "edit_me.txt").exists()


def test_model_cannot_choose_the_workspace_root(runner, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "secret.txt").write_text("nope\n")
    try:
        out = _dispatch(runner, "read_file", {"path": "secret.txt", "workspace_root": str(elsewhere)})
    except FileNotFoundError:
        out = ""  # resolved against the runner's workspace, where it does not exist
    assert "nope" not in str(out)


def test_registry_edit_file_ignores_a_model_supplied_root(runner, tmp_path):
    elsewhere = tmp_path / "elsewhere2"
    elsewhere.mkdir()
    (elsewhere / "edit_me.txt").write_text("alpha beta\n")
    _dispatch(runner, "edit_file", {"path": "edit_me.txt", "old_string": "alpha", "new_string": "zeta",
                                    "workspace_root": str(elsewhere)})
    assert (elsewhere / "edit_me.txt").read_text() == "alpha beta\n"
    assert (runner.tools.root / "edit_me.txt").read_text() == "zeta beta\n"

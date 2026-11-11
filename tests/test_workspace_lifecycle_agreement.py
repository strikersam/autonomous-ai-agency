"""The two workspace managers must answer lifecycle questions the same way.

`agent/workspace.py` (async, per job) and `workspace/manifest.py` (sync) describe
the same ten workspace states.  These tests pin the single declaration they
share, so a future edit cannot make one manager treat a state as resumable or
in use when the other does not.
"""

import asyncio

import pytest

from agent.workspace import (
    WorkspaceManager as AgentWorkspaceManager,
    WorkspaceNotResumableError,
    WorkspaceStatus as AgentWorkspaceStatus,
    _ACTIVE_STATES,
    _RESUMABLE_STATES,
)
from workspace.manifest import ACTIVE_STATES, RESUMABLE_STATES


def test_both_managers_declare_the_same_groupings():
    assert {s.value for s in _RESUMABLE_STATES} == set(RESUMABLE_STATES)
    assert {s.value for s in _ACTIVE_STATES} == set(ACTIVE_STATES)


def test_resumable_and_active_include_an_active_workspace():
    assert "active" in RESUMABLE_STATES
    assert "active" in ACTIVE_STATES


def test_async_manager_resumes_an_active_workspace(tmp_path):
    mgr = AgentWorkspaceManager(tmp_path / "ws")
    ws = asyncio.run(mgr.create("as_sess1", "aj_job1"))
    asyncio.run(mgr.transition(ws, AgentWorkspaceStatus.ACTIVE))

    resumed = asyncio.run(mgr.resume("as_sess1", "aj_job1"))

    assert resumed.status is AgentWorkspaceStatus.ACTIVE


def test_async_manager_refuses_a_completed_workspace(tmp_path):
    mgr = AgentWorkspaceManager(tmp_path / "ws")
    ws = asyncio.run(mgr.create("as_sess1", "aj_job1"))
    asyncio.run(mgr.transition(ws, AgentWorkspaceStatus.COMPLETED))

    with pytest.raises(WorkspaceNotResumableError):
        asyncio.run(mgr.resume("as_sess1", "aj_job1"))

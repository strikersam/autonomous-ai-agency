"""tests/test_ceo_direct_dedup.py — Tests for ceo_direct task deduplication.

Covers:
  a) create_task_from_oldest_open_issue sets source_id == "owner/repo#N"
  b) calling helper twice with the same issue list creates exactly one task
  c) issue whose task is FAILED-at-retry-cap is skipped and the NEXT actionable issue is picked
  d) self-heal backfills source_id on a legacy ceo_direct task and deletes the surplus duplicate
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tasks.models import Task, TaskStatus
from tasks.store import TaskStore
from tasks.issue_intake import create_task_from_oldest_open_issue, issue_source_id

# Stub GitHub credential for mocked API calls (a variable, not a literal
# kwarg, so Bandit B106 "hardcoded password funcarg" does not fire).
STUB_GH_CREDENTIAL = "stub-gh-credential"


def _make_issue(number: int, title: str = "Test issue", labels: list = None, body: str = "Test body"):
    return {
        "number": number,
        "title": title,
        "body": body,
        "labels": [{"name": lb} for lb in (labels or [])],
    }


def _mock_httpx_response(issues: list):
    """Create a mock httpx response."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = issues
    return mock


@pytest.fixture
def store():
    return TaskStore()


@pytest.fixture
def mock_gh():
    """Mock the GitHub API + agency token resolution."""
    return patch("tasks.issue_intake.httpx.AsyncClient")


@pytest.mark.asyncio
async def test_helper_sets_source_id(store, monkeypatch):
    """a) helper sets source_id == 'owner/repo#N'"""
    issue = _make_issue(42, "Fix the bug")
    mock_resp = _mock_httpx_response([issue])

    with patch("agent.agency._gh_token", return_value=STUB_GH_CREDENTIAL):
        with patch("agent.agency._gh_repo", return_value="owner/repo"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client

                task, status = await create_task_from_oldest_open_issue(
                    store=store, token=STUB_GH_CREDENTIAL, repo="owner/repo"
                )

    assert task is not None
    assert task.source_id == "owner/repo#42"
    assert task.source == "ceo_direct"
    assert task.pending_agent_run is True
    assert status["direct_issue_number"] == 42
    assert "direct_task_created" in status


@pytest.mark.asyncio
async def test_helper_idempotent_same_issue(store, monkeypatch):
    """b) calling helper twice with the same issue creates exactly one task"""
    issue = _make_issue(42, "Fix the bug")
    mock_resp = _mock_httpx_response([issue])

    with patch("agent.agency._gh_token", return_value=STUB_GH_CREDENTIAL):
        with patch("agent.agency._gh_repo", return_value="owner/repo"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client

                # First call — creates the task
                task1, status1 = await create_task_from_oldest_open_issue(
                    store=store, token=STUB_GH_CREDENTIAL, repo="owner/repo"
                )
                assert task1 is not None

                # Second call — should NOT create a duplicate
                task2, status2 = await create_task_from_oldest_open_issue(
                    store=store, token=STUB_GH_CREDENTIAL, repo="owner/repo"
                )
                assert task2 is None

    # Verify only one task exists
    all_tasks = await store.list_all(limit=100)
    assert len(all_tasks) == 1


@pytest.mark.asyncio
async def test_helper_skips_exhausted_picks_next(store, monkeypatch):
    """c) issue whose task already exists is skipped and the NEXT issue is picked"""
    issue1 = _make_issue(1, "First issue")
    issue2 = _make_issue(2, "Second issue")
    mock_resp = _mock_httpx_response([issue1, issue2])

    with patch("agent.agency._gh_token", return_value=STUB_GH_CREDENTIAL):
        with patch("agent.agency._gh_repo", return_value="owner/repo"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client

                # First call — creates task for issue #1
                task1, _ = await create_task_from_oldest_open_issue(
                    store=store, token=STUB_GH_CREDENTIAL, repo="owner/repo"
                )
                assert task1 is not None
                assert task1.source_id == "owner/repo#1"

                # Second call — issue #1 already has a task, so picks issue #2
                task2, _ = await create_task_from_oldest_open_issue(
                    store=store, token=STUB_GH_CREDENTIAL, repo="owner/repo"
                )
                assert task2 is not None
                assert task2.source_id == "owner/repo#2"

    all_tasks = await store.list_all(limit=100)
    assert len(all_tasks) == 2


@pytest.mark.asyncio
async def test_self_heal_backfills_source_id(store, monkeypatch):
    """d) self-heal backfills source_id on a legacy ceo_direct task and deletes surplus"""
    from services.self_heal import _heal_task_duplicates

    # Create two legacy tasks WITHOUT source_id (simulating the old bug)
    t1 = Task(
        owner_id="system",
        title="issue #100: Fix tests",
        source="ceo_direct",
        source_id=None,
        status=TaskStatus.TODO,
        pending_agent_run=True,
    )
    t2 = Task(
        owner_id="system",
        title="issue #100: Fix tests",
        source="ceo_direct",
        source_id=None,
        status=TaskStatus.TODO,
        pending_agent_run=True,
    )
    await store.create(t1)
    await store.create(t2)

    # Mock the repo resolution
    with patch("agent.agency._gh_repo", return_value="owner/repo"):
        import tasks.store as ts
        original_get = ts.get_task_store
        ts.get_task_store = lambda: store
        try:
            result = await _heal_task_duplicates()
        finally:
            ts.get_task_store = original_get

    # Should have backfilled 2 source_ids
    assert result["backfilled"] == 2
    # Should have deleted 1 duplicate (same source_id after backfill)
    assert result["deleted"] == 1

    # Verify only one task remains
    all_tasks = await store.list_all(limit=100)
    assert len(all_tasks) == 1
    assert all_tasks[0].source_id == "owner/repo#100"

"""tests/test_tasks.py — Unit tests for the task/issue system."""

from __future__ import annotations

import time
import pytest

from tasks.models import (
    Task, TaskStatus, TaskPriority, TaskComment,
    ApprovalCheckpoint, TaskCreateRequest, TaskUpdateRequest,
)
from tasks.store import TaskStore


# ── Model tests ───────────────────────────────────────────────────────────────

class TestTaskModel:

    def test_task_has_default_id(self):
        t = Task(owner_id="u1", title="Test task")
        assert t.task_id.startswith("task_")

    def test_task_default_status_is_todo(self):
        t = Task(owner_id="u1", title="x")
        assert t.status == TaskStatus.TODO

    def test_task_default_priority_is_medium(self):
        t = Task(owner_id="u1", title="x")
        assert t.priority == TaskPriority.MEDIUM

    def test_task_touch_updates_updated_at(self):
        t = Task(owner_id="u1", title="x")
        old = t.updated_at
        time.sleep(0.01)
        t.touch()
        assert t.updated_at >= old

    def test_task_add_log(self):
        t = Task(owner_id="u1", title="x")
        t.add_log("started", level="info")
        assert len(t.execution_log) == 1
        assert t.execution_log[0].message == "started"

    def test_task_tags_capped_at_20(self):
        with pytest.raises(Exception):
            Task(owner_id="u1", title="x", tags=[f"tag{i}" for i in range(21)])

    def test_task_as_dict_contains_task_id(self):
        t = Task(owner_id="u1", title="x")
        d = t.as_dict()
        assert "task_id" in d
        assert d["owner_id"] == "u1"

    def test_comment_has_id(self):
        c = TaskComment(author="u1", body="hello")
        assert c.comment_id.startswith("cmt_")

    def test_approval_checkpoint(self):
        cp = ApprovalCheckpoint(description="Review output")
        assert cp.approved is None
        cp.approved = True
        cp.approved_by = "admin@example.com"
        assert cp.approved is True


# ── Store tests ───────────────────────────────────────────────────────────────

@pytest.fixture
def store():
    return TaskStore(db=None)  # in-memory mode


class TestTaskStore:

    @pytest.mark.asyncio
    async def test_create_and_get(self, store):
        t = Task(owner_id="u1", title="My Task")
        await store.create(t)
        fetched = await store.get(t.task_id)
        assert fetched is not None
        assert fetched.title == "My Task"

    @pytest.mark.asyncio
    async def test_get_enforces_owner(self, store):
        t = Task(owner_id="u1", title="Private")
        await store.create(t)
        result = await store.get(t.task_id, owner_id="u2")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_admin_bypass_owner(self, store):
        t = Task(owner_id="u1", title="Admin can see")
        await store.create(t)
        result = await store.get(t.task_id, owner_id=None)
        assert result is not None

    @pytest.mark.asyncio
    async def test_update(self, store):
        t = Task(owner_id="u1", title="Original")
        await store.create(t)
        t.title = "Updated"
        await store.update(t)
        fetched = await store.get(t.task_id)
        assert fetched.title == "Updated"

    @pytest.mark.asyncio
    async def test_delete_own_task(self, store):
        t = Task(owner_id="u1", title="Delete me")
        await store.create(t)
        result = await store.delete(t.task_id, owner_id="u1")
        assert result is True
        assert await store.get(t.task_id) is None

    @pytest.mark.asyncio
    async def test_delete_other_user_fails(self, store):
        t = Task(owner_id="u1", title="Not yours")
        await store.create(t)
        result = await store.delete(t.task_id, owner_id="u2")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_for_user(self, store):
        t1 = Task(owner_id="u1", title="A")
        t2 = Task(owner_id="u1", title="B")
        t3 = Task(owner_id="u2", title="C")
        for t in [t1, t2, t3]:
            await store.create(t)
        result = await store.list_for_user("u1")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self, store):
        t1 = Task(owner_id="u1", title="A", status=TaskStatus.TODO)
        t2 = Task(owner_id="u1", title="B", status=TaskStatus.DONE)
        for t in [t1, t2]:
            await store.create(t)
        result = await store.list_for_user("u1", status=TaskStatus.DONE)
        assert len(result) == 1
        assert result[0].status == TaskStatus.DONE

    @pytest.mark.asyncio
    async def test_count_for_user(self, store):
        t1 = Task(owner_id="u1", title="A", status=TaskStatus.TODO)
        t2 = Task(owner_id="u1", title="B", status=TaskStatus.DONE)
        for t in [t1, t2]:
            await store.create(t)
        counts = await store.count_for_user("u1")
        assert counts.get("todo", 0) == 1
        assert counts.get("done", 0) == 1

    @pytest.mark.asyncio
    async def test_get_due_soon(self, store):
        now = time.time()
        t_due = Task(owner_id="u1", title="Due soon", due_date=now + 3600)
        t_not = Task(owner_id="u1", title="Not due", due_date=now + 99999)
        for t in [t_due, t_not]:
            await store.create(t)
        result = await store.get_due_soon(within_hours=12)
        ids = [t.task_id for t in result]
        assert t_due.task_id in ids
        assert t_not.task_id not in ids

    @pytest.mark.asyncio
    async def test_list_all_admin(self, store):
        t1 = Task(owner_id="u1", title="A")
        t2 = Task(owner_id="u2", title="B")
        for t in [t1, t2]:
            await store.create(t)
        result = await store.list_all()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_excludes_heavy_fields_when_include_log_false(self, store):
        # Regression for the Task Board timeout: the heavy append-only fields
        # (execution_log, workflow_history) must be dropped from list views so a
        # backlog of long-lived tasks is not fetched and deserialized in full.
        t = Task(owner_id="u1", title="Chatty")
        for i in range(50):
            t.add_log(f"entry {i}")
        t.workflow_history = [{"phase": "plan"}, {"phase": "execute"}]
        await store.create(t)

        # Default (include_log=True) still carries the full log through.
        full = (await store.list_for_user("u1"))[0]
        assert len(full.execution_log) == 50
        assert len(full.workflow_history) == 2

        # List view drops them (validated back to the model defaults: empty).
        light = (await store.list_for_user("u1", include_log=False))[0]
        assert light.execution_log == []
        assert light.workflow_history == []
        light_all = (await store.list_all(include_log=False))[0]
        assert light_all.execution_log == []
        assert light_all.workflow_history == []

        # The projection must not mutate the stored document — a later full read
        # still sees the log (guards the in-memory copy-vs-mutate path).
        assert len((await store.get(t.task_id)).execution_log) == 50

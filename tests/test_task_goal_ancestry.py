"""Goal ancestry on tasks (tasks/models.py, tasks/api.py, tasks/service.py).

Adapted from Paperclip: every task carries the chain of goals that produced it,
so the executing agent sees why the work exists, not just its title. Before
this, a CEO directive reached the runtime as a bare title and prompt, and the
directive's own description was dropped when the scheduled job became a task.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from tasks.api import task_router
from tasks.automation import TaskAutomationService
from tasks.models import Task, goal_ancestry_block, inherit_goal
from tasks.service import TaskExecutionCoordinator
from tasks.store import TaskStore, set_task_store


def _chain() -> Task:
    root = Task(owner_id="u", title="Grow signups", goal="Reach 1k weekly signups")
    mid = Task(owner_id="u", title="Fix onboarding", goal="Cut onboarding drop-off")
    inherit_goal(mid, root)
    leaf = Task(owner_id="u", title="Fix email step", goal="Verification email arrives")
    inherit_goal(leaf, mid)
    return leaf


def test_inherit_goal_carries_the_whole_chain_root_first():
    leaf = _chain()
    assert leaf.goal_chain == ["Reach 1k weekly signups", "Cut onboarding drop-off"]
    assert leaf.parent_task_id


def test_parent_without_a_goal_contributes_its_title():
    parent = Task(owner_id="u", title="Quarterly cleanup")
    child = Task(owner_id="u", title="Delete dead flags")
    inherit_goal(child, parent)
    assert child.goal_chain == ["Quarterly cleanup"]


def test_chain_depth_is_bounded():
    task = Task(owner_id="u", title="t0", goal="g0")
    for i in range(1, 12):
        child = Task(owner_id="u", title=f"t{i}", goal=f"g{i}")
        inherit_goal(child, task)
        task = child
    assert task.goal_chain == ["g6", "g7", "g8", "g9", "g10"]


def test_block_renders_nested_and_is_empty_without_goals():
    assert goal_ancestry_block(_chain()) == (
        "Why this task exists (goal ancestry, top-level goal first):\n"
        "- Reach 1k weekly signups\n"
        "  - Cut onboarding drop-off\n"
        "    - This task: Verification email arrives"
    )
    assert goal_ancestry_block(Task(owner_id="u", title="plain")) == ""


def test_runtime_instruction_includes_ancestry_only_when_present():
    coordinator = TaskExecutionCoordinator.__new__(TaskExecutionCoordinator)
    plain = Task(owner_id="u", title="plain", prompt="do it")
    assert coordinator._compose_instruction(plain, None) == "Task title: plain\n\nTask prompt:\ndo it"
    rich = coordinator._compose_instruction(_chain(), None)
    assert rich.startswith("Task title: Fix email step\n\nWhy this task exists")
    assert "Reach 1k weekly signups" in rich


@pytest.mark.anyio
async def test_scheduled_job_description_becomes_the_goal():
    captured: list[Task] = []

    class _Workflow:
        async def create_task(self, task, actor):
            captured.append(task)
            return task

    svc = TaskAutomationService(store=TaskStore(), workflow=_Workflow())
    job = SimpleNamespace(
        job_id="job_1", name="agency: Fix flaky login", cron="* * * * *",
        instruction="Fix it", description="[developer] Fix flaky login", tags=[],
    )
    await svc.handle_scheduled_job(job)
    assert captured[0].goal == "[developer] Fix flaky login"


def _client(role: str, email: str = "qa@example.com") -> TestClient:
    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        request.state.user = SimpleNamespace(email=email, role=role)
        return await call_next(request)

    app.include_router(task_router)
    return TestClient(app)


@pytest.fixture()
def store() -> TaskStore:
    s = TaskStore()
    set_task_store(s)
    return s


def test_api_creates_a_child_under_a_parent(store):
    parent = Task(owner_id="qa@example.com", title="Launch v2", goal="Ship v2 by Q4")
    asyncio.run(store.create(parent))
    resp = _client("user").post("/api/tasks/", json={
        "title": "Write migration", "goal": "Move users to v2 schema",
        "parent_task_id": parent.task_id,
    })
    assert resp.status_code == 201, resp.text
    child = resp.json()["task"]
    assert child["parent_task_id"] == parent.task_id
    assert child["goal_chain"] == ["Ship v2 by Q4"]
    assert child["goal"] == "Move users to v2 schema"


def test_api_refuses_nesting_under_someone_elses_task(store):
    other = Task(owner_id="someone-else@example.com", title="Private plan", goal="secret goal")
    asyncio.run(store.create(other))
    resp = _client("user").post("/api/tasks/", json={
        "title": "Snoop", "parent_task_id": other.task_id,
    })
    assert resp.status_code == 404
    assert "secret goal" not in resp.text

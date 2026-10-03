"""tests/test_sam_orchestrator.py — SAM runs the agency, admins only.

Covers the orchestration actions (delegate / triage / brief), their admin gate,
the operator principles in SAM's prompt, the per-user chat session namespace,
and the SAM avatar visibility endpoint + platform controls.
"""

from __future__ import annotations

import asyncio
import os

import pytest

import backend.server as server
import tasks.store as task_store_mod
from agent import sam_orchestrator
from agent.sam import SAM_SYSTEM_PROMPT, SamAgent
from packages.config import control_overrides
from packages.config.control_registry import get_control
from tasks.store import TaskStore


@pytest.fixture
def store(monkeypatch) -> TaskStore:
    fresh = TaskStore()
    monkeypatch.setattr(task_store_mod, "_global_store", fresh)

    async def _feed(limit: int = 50) -> dict:
        return {"logs": []}

    monkeypatch.setattr(server, "_get_activity_impl", _feed)
    return fresh


@pytest.mark.parametrize("text,expected", [
    ("create a task to add dark mode to the billing page", "delegate"),
    ("SAM, get the team to write docs for the router", "delegate"),
    ("create a task to fix the login error", "delegate"),
    ("triage the queue", "triage"),
    ("approve what doesn't need me", "triage"),
    ("brief me", "brief"),
    ("give me a sitrep", "brief"),
    ("status check", None),
    ("fix the alerts", None),
    ("tell me a joke", None),
])
def test_detect_orchestration_intent(text, expected):
    assert sam_orchestrator.detect_orchestration_intent(text) == expected


def test_extract_instruction():
    assert sam_orchestrator.extract_instruction(
        "Create a task to add dark mode to billing."
    ) == "add dark mode to billing"
    assert sam_orchestrator.extract_instruction(
        "tell the agents to refactor the scheduler"
    ) == "refactor the scheduler"


def test_admin_delegate_queues_one_task_and_dedupes(store):
    agent = SamAgent()
    reply = asyncio.run(agent.process_command(
        "create a task to add dark mode to billing", owner_id="admin-1", is_admin=True,
    ))
    again = asyncio.run(agent.process_command(
        "create a task to add dark mode to billing", owner_id="admin-1", is_admin=True,
    ))

    tasks = list(store._mem.values())
    assert len(tasks) == 1
    assert tasks[0]["title"] == "add dark mode to billing"
    assert tasks[0]["owner_id"] == "admin-1"
    assert "sam-delegated" in tasks[0]["tags"]
    assert reply.startswith("Queued: add dark mode to billing")
    assert "already queued" in again


def test_delegate_beats_alert_keywords(store):
    """'create a task to fix the login error' is delegation, not 'fix the alerts'."""
    asyncio.run(SamAgent().process_command(
        "create a task to fix the login error", owner_id="admin-1", is_admin=True,
    ))
    tasks = list(store._mem.values())
    assert len(tasks) == 1
    assert "alert-fix" not in tasks[0]["tags"]


def test_non_admin_cannot_orchestrate(store):
    reply = asyncio.run(SamAgent().process_command(
        "create a task to delete everything", owner_id="u1", is_admin=False,
    ))
    assert store._mem == {}
    assert "needs an admin" in reply


def test_triage_runs_the_ceo_policy(store, monkeypatch):
    from tasks import autonomy_triage

    async def _triage(store=None):
        return autonomy_triage.TriageResult(approved=2, rejected=1, left_for_human=1)

    monkeypatch.setattr(autonomy_triage, "triage_gated_tasks", _triage)
    reply = asyncio.run(SamAgent().process_command("triage the queue", is_admin=True))
    assert "approved 2, rejected 1" in reply
    assert "1 need you" in reply


def test_brief_reports_live_state_without_llm(store, monkeypatch):
    import agent.agency as agency_mod

    monkeypatch.setattr(agency_mod, "get_agency", lambda: None)

    async def _no_llm(*a, **k):  # the brief must not touch the LLM
        raise AssertionError("LLM called")

    monkeypatch.setattr(SamAgent, "_call_llm", _no_llm)
    reply = asyncio.run(SamAgent().process_command("brief me", is_admin=True))
    assert "CEO loop is off" in reply
    assert "0 tasks in the queue, 0 waiting on approval" in reply


def test_operator_principles_are_in_sams_system_prompt():
    assert "Only ask the Commander at merge time" in SAM_SYSTEM_PROMPT
    assert "never tell the" in SAM_SYSTEM_PROMPT


def test_prompt_includes_remembered_facts():
    agent = SamAgent()
    prompt = agent._build_prompt(
        "hello", {"memory": {"recent": ["prefers Groq for chat"]}}, agent._get_session("s"),
    )
    assert "prefers Groq for chat" in prompt


# ── Endpoints + controls ──────────────────────────────────────────────────────

def _as(user: dict):
    from backend.server import app, get_current_user

    app.dependency_overrides[get_current_user] = lambda: user


ADMIN = {"_id": "admin-1", "email": "a@example.com", "role": "admin"}
USER = {"_id": "u1", "email": "u@example.com", "role": "user"}


@pytest.fixture
def clean_overrides():
    """Restore env, the applied-override set and the settings singleton."""
    keys = ("SAM_AVATAR_ENABLED", "SAM_AVATAR_SCOPE")
    before = {k: os.environ.get(k) for k in keys}
    applied_before = dict(control_overrides._applied)
    yield
    for key, value in before.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    control_overrides._applied.clear()
    control_overrides._applied.update(applied_before)
    control_overrides.apply_overrides({})
    control_overrides._applied.clear()
    control_overrides._applied.update(applied_before)


def test_avatar_controls_are_live_and_on_for_admins_by_default():
    enabled, scope = get_control("SAM_AVATAR_ENABLED"), get_control("SAM_AVATAR_SCOPE")
    assert enabled.default == "true" and enabled.live
    assert scope.default == "admins" and scope.live


def test_avatar_endpoint_follows_the_toggle(client, clean_overrides):
    from backend.server import app

    try:
        os.environ.pop("SAM_AVATAR_ENABLED", None)
        os.environ.pop("SAM_AVATAR_SCOPE", None)
        control_overrides.apply_overrides({})
        _as(ADMIN)  # code default: on, admins only
        assert client.get("/agent/sam/avatar").json() == {"enabled": True, "can_orchestrate": True}
        _as(USER)
        assert client.get("/agent/sam/avatar").json()["enabled"] is False

        control_overrides.apply_overrides({"SAM_AVATAR_ENABLED": "false"})
        _as(ADMIN)
        assert client.get("/agent/sam/avatar").json()["enabled"] is False

        control_overrides.apply_overrides({"SAM_AVATAR_ENABLED": "true"})
        assert client.get("/agent/sam/avatar").json()["enabled"] is True
        _as(USER)
        assert client.get("/agent/sam/avatar").json() == {"enabled": False, "can_orchestrate": False}

        control_overrides.apply_overrides({"SAM_AVATAR_ENABLED": "true", "SAM_AVATAR_SCOPE": "all"})
        assert client.get("/agent/sam/avatar").json()["enabled"] is True
    finally:
        app.dependency_overrides.clear()


def test_avatar_endpoint_requires_auth(client):
    assert client.get("/agent/sam/avatar").status_code in (401, 403)


def test_chat_namespaces_session_and_passes_role(client, monkeypatch):
    from backend.server import app

    seen: dict = {}

    async def _fake(self, text, session_id="default", owner_id="", *, is_admin=False):
        seen.update(session_id=session_id, owner_id=owner_id, is_admin=is_admin)
        return "ok"

    monkeypatch.setattr(SamAgent, "process_command", _fake)
    try:
        _as(USER)
        resp = client.post("/agent/sam/chat", json={"text": "hi", "session_id": "sam-avatar"})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert seen == {"session_id": "u1:sam-avatar", "owner_id": "u1", "is_admin": False}


@pytest.mark.parametrize("instruction", [
    "deploy the service to production",
    "release the new version",
    "publish the package to PyPI",
    "rotate the API secrets",
    "run the database migration",
    # Codex P1 on #1647: ordinary destructive/external wording must fail closed.
    "delete inactive customer accounts",
    "restart the production service",
    "send a Slack message to the on-call channel",
    "refund the last three invoices",
    "do the thing we talked about yesterday",  # unclassifiable -> gated
    # Codex P1 on #1648: money movement behind an allowlisted verb.
    "fix the worker to transfer money to account 123",
    "update the job to wire funds to the vendor",
    "add a cron that withdraws the balance from the wallet",
])
def test_outward_facing_delegation_is_gated(store, instruction):
    """Regression (Codex P1): a delegated deploy must park for approval, not run."""
    reply = asyncio.run(SamAgent().process_command(
        f"create a task to {instruction}", owner_id="admin-1", is_admin=True,
    ))
    (task,) = store._mem.values()
    assert task["requires_approval"] is True
    assert not task.get("execution_approved")
    assert "parked for your approval" in reply


@pytest.mark.parametrize("instruction", [
    "refactor the scheduler tests",
    "add dark mode to the billing page",
    "fix the flaky login test",
    "write docs for the router",
    "investigate why the dashboard is slow",
])
def test_internal_delegation_is_not_gated(store, instruction):
    asyncio.run(SamAgent().process_command(
        f"create a task to {instruction}", owner_id="admin-1", is_admin=True,
    ))
    (task,) = store._mem.values()
    assert not task.get("requires_approval")


# ── Realtime voice (LiveKit) uses the same gates ──────────────────────────────

@pytest.mark.parametrize("metadata,expected", [
    ('{"role": "admin"}', True),
    ('{"role": "user"}', False),
    ("", False),
    (None, False),
    ("not json", False),
    ('["admin"]', False),
])
def test_voice_role_from_token_metadata(metadata, expected):
    from voice.sam_livekit_worker import role_is_admin

    assert role_is_admin(metadata) is expected


def test_voice_create_task_refuses_non_admin(store):
    """Regression: the voice create_task tool let any signed-in user queue work."""
    from voice.sam_livekit_worker import voice_create_task

    reply = asyncio.run(voice_create_task("refactor the router", "", "u1", is_admin=False))
    assert store._mem == {}
    assert "needs an admin" in reply


def test_voice_create_task_gates_outward_work_in_the_description(store):
    """Regression: voice tasks bypassed the approval gate entirely."""
    from voice.sam_livekit_worker import voice_create_task

    reply = asyncio.run(voice_create_task(
        "update the release job", "then deploy it to production", "admin-1", is_admin=True,
    ))
    (task,) = store._mem.values()
    assert task["requires_approval"] is True
    assert "parked for your approval" in reply


def test_voice_create_task_internal_work_runs(store):
    from voice.sam_livekit_worker import voice_create_task

    asyncio.run(voice_create_task("fix the flaky router test", "", "admin-1", is_admin=True))
    (task,) = store._mem.values()
    assert not task.get("requires_approval")


@pytest.mark.parametrize("user,role", [(ADMIN, "admin"), (USER, "user")])
def test_livekit_token_carries_signed_role(client, monkeypatch, user, role):
    import json as _json

    import jwt
    from backend.server import app

    monkeypatch.setenv("LIVEKIT_URL", "wss://test.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "APIkey")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "s" * 40)
    try:
        _as(user)
        resp = client.post("/agent/sam/livekit/token", json={})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200, resp.text
    claims = jwt.decode(resp.json()["token"], "s" * 40, algorithms=["HS256"], issuer="APIkey")
    assert _json.loads(claims["metadata"]) == {"role": role}

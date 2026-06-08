"""Tests for direct-chat evolution: intent routing, sticky context, humanized status."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
import proxy
import direct_chat
from agent.state import AgentSessionStore
from agent.job_manager import AgentJobManager
from direct_chat import UserInfo
from agent.schemas import DirectChatState


def _fake_user():
    return UserInfo(id="user123", email="test@example.com")


@pytest.fixture
def clean_store(tmp_path):
    return AgentSessionStore(db_path=str(tmp_path / "evolution.db"))


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Ensure dependency overrides are always cleared after each test."""
    yield
    proxy.app.dependency_overrides.clear()


def test_intent_clarification(monkeypatch, clean_store):
    proxy.app.dependency_overrides[direct_chat._get_current_user] = _fake_user
    monkeypatch.setattr(direct_chat, "_direct_chat_store", clean_store)

    client = TestClient(proxy.app)
    headers = {"Authorization": "Bearer fake-token"}
    response = client.post(
        "/api/chat/send",
        json={"content": "Fix it", "agent_mode": False},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    # Clarify reply should contain helpful prompting language
    assert any(w in data.get("response", "").lower() for w in ("detail", "provide", "clarif", "more")), \
        f"Expected clarification language in response, got: {data.get('response')}"
    assert data.get("state") == DirectChatState.NEEDS_INPUT


def test_sticky_objective_memory(monkeypatch, clean_store):
    proxy.app.dependency_overrides[direct_chat._get_current_user] = _fake_user
    monkeypatch.setattr(direct_chat, "_direct_chat_store", clean_store)
    monkeypatch.setattr(direct_chat, "_agent_jobs", AgentJobManager())

    # Mock PROVIDER_ROUTER on app.state
    class _FakeProvider:
        priority = 1
        api_key = None
        normalized_base_url = "http://localhost:11434"

        def auth_headers(self) -> dict:
            return {}

    class _FakeRouter:
        providers = [_FakeProvider()]

    proxy.app.state.PROVIDER_ROUTER = _FakeRouter()

    # Mock doctor so preflight passes instantly
    class FakeDoctor:
        def __init__(self, **kwargs):
            pass

        async def check_all(self, **kwargs):
            from agent.doctor import PreflightReport
            return PreflightReport(ready=True, summary="OK")

    monkeypatch.setattr("direct_chat.DirectChatDoctor", FakeDoctor)

    client = TestClient(proxy.app)
    headers = {"Authorization": "Bearer fake-token"}
    session_id = "sticky-eval"

    # turn 1 — execution intent should persist objective
    client.post(
        "/api/chat/send",
        json={"content": "Implement auth feature", "agent_mode": True, "session_id": session_id},
        headers=headers,
    )

    # turn 2 — should have remembered objective
    session = clean_store.get(session_id)
    assert session is not None, "Session should have been created"
    assert session.active_objective == "Implement auth feature"


def test_humanized_momentum_status(monkeypatch, clean_store):
    """GET /api/chat/agent-status returns humanized_progress for slow-running jobs."""
    proxy.app.dependency_overrides[direct_chat._get_current_user] = _fake_user
    monkeypatch.setattr(direct_chat, "_direct_chat_store", clean_store)
    mgr = AgentJobManager()
    monkeypatch.setattr(direct_chat, "_agent_jobs", mgr)

    session_id = "momentum-eval"
    job = mgr.create_job(
        session_id=session_id, owner_id="test@example.com", instruction="test"
    )
    job.status = "running"
    job.phase = "execution"
    # Simulate a job that started a long time ago so humanize returns "Still …"
    job.updated_at = "2024-01-01T00:00:00Z"
    job.progress_events.append(
        {
            "timestamp": job.updated_at,
            "phase": "execution",
            "message": "Tool: run_command",
        }
    )

    client = TestClient(proxy.app)
    response = client.get(
        f"/api/chat/agent-status?session_id={session_id}",
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "humanized_progress" in data
    # A stale-running job should produce a "Still …" message
    assert "Still" in data["humanized_progress"], \
        f"Expected 'Still …' in humanized_progress, got: {data['humanized_progress']}"


def test_agent_runner_no_stale_kwargs(monkeypatch, clean_store, tmp_path):
    """Regression: AgentRunner must not be called with removed kwargs.

    Previous versions of direct_chat.py passed ``provider_chain`` and
    ``allow_commercial_fallback`` to AgentRunner.__init__, which no longer
    accepts them.  This test verifies those kwargs are absent, ensuring the
    TypeError introduced by the stale call-site does not regress.
    """
    proxy.app.dependency_overrides[direct_chat._get_current_user] = _fake_user
    monkeypatch.setattr(direct_chat, "_direct_chat_store", clean_store)
    monkeypatch.setattr(direct_chat, "_agent_jobs", AgentJobManager())
    monkeypatch.setattr(
        direct_chat,
        "_get_github_token_for_user",
        lambda email: None,  # sync stub — avoids MongoDB timeout
    )

    class FakeDoctor:
        def __init__(self, **kwargs): pass

        async def check_all(self, **kwargs):
            from agent.doctor import PreflightReport
            return PreflightReport(ready=True, summary="OK")

    monkeypatch.setattr("direct_chat.DirectChatDoctor", FakeDoctor)

    # Capture the kwargs AgentRunner.__init__ actually receives.
    captured_init_kwargs: dict = {}

    class SpyRunner:
        def __init__(self, **kwargs):
            captured_init_kwargs.update(kwargs)

        async def plan(self, **kwargs):
            from agent.models import AgentPlan, AgentStep
            return AgentPlan(goal="test", steps=[AgentStep(id=1, description="d", type="edit")])

        async def run(self, **kwargs):
            return {"summary": "spy done"}

    monkeypatch.setattr("agent.loop.AgentRunner", SpyRunner)

    class FakeRuntimeMgr:
        def select_runtime(self, *args, **kwargs):
            return None, []

    monkeypatch.setattr("runtimes.manager.get_runtime_manager", lambda: FakeRuntimeMgr())

    class _FakeProvider:
        priority = 1
        api_key = None
        normalized_base_url = "http://localhost:11434"
        def auth_headers(self): return {}

    class _FakeRouter:
        providers = [_FakeProvider()]

    proxy.app.state.PROVIDER_ROUTER = _FakeRouter()

    async def _fake_github_token(email: str):
        return None
    monkeypatch.setattr(direct_chat, "_get_github_token_for_user", _fake_github_token)

    client = TestClient(proxy.app)
    client.post(
        "/api/chat/send",
        json={"content": "Fix the failing tests and commit", "agent_mode": True},
        headers={"Authorization": "Bearer fake"},
    )

    # The critical assertion: these two kwargs must NOT appear in the constructor call.
    assert "provider_chain" not in captured_init_kwargs, \
        "provider_chain was passed to AgentRunner — stale kwargs regression"
    assert "allow_commercial_fallback" not in captured_init_kwargs, \
        "allow_commercial_fallback was passed to AgentRunner — stale kwargs regression"
    assert "tool_callback" not in captured_init_kwargs, \
        "tool_callback was passed to AgentRunner — stale kwargs regression"

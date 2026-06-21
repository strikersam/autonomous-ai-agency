"""tests/test_workflow_orchestrator_scoping.py — Phase 8 multi-tenant isolation.

Regression coverage for per-user scoping of WorkflowOrchestrator runs:

* unit level — ``list_runs(owner_id=...)`` filters by the run's ``user_id``
  and runs are stamped with their originating ``ExecutionRequest.user_id``.
* API level — ``/api/workflow/orchestrator/runs`` and ``/runs/{id}`` only
  expose a caller's own runs (admins see all); requesting another user's
  run returns 404 (IDOR-safe), never the run body.
"""
from __future__ import annotations

import os
import socket
import pytest
from fastapi.testclient import TestClient

import backend.server as server
from backend.server import app as backend_app


# ── Unit: orchestrator-level scoping ──────────────────────────────────────────


def _ollama_reachable() -> bool:
    ollama_base = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
    host = ollama_base.replace("http://", "").replace("https://", "").split(":")[0]
    try:
        port = int(ollama_base.rsplit(":", 1)[-1].rstrip("/"))
    except ValueError:
        port = 11434
    try:
        s = socket.create_connection((host, port), timeout=2.0)
        s.close()
        return True
    except OSError:
        return False


@pytest.mark.skipif(not _ollama_reachable(), reason="LLM backend not reachable in CI")
class TestOrchestratorRunScoping:
    async def test_run_is_stamped_with_request_user_id(self):
        from services.workflow_orchestrator import (
            ExecutionRequest,
            get_workflow_orchestrator,
            reset_orchestrator,
        )

        reset_orchestrator()
        orch = get_workflow_orchestrator()
        run = await orch.execute(
            ExecutionRequest(request="scoped work", user_id="alice", auto_approve=True)
        )
        assert run.user_id == "alice"
        assert run.as_dict()["user_id"] == "alice"

    async def test_list_runs_filters_by_owner(self):
        from services.workflow_orchestrator import (
            ExecutionRequest,
            get_workflow_orchestrator,
            reset_orchestrator,
        )

        reset_orchestrator()
        orch = get_workflow_orchestrator()
        await orch.execute(
            ExecutionRequest(request="alice work", user_id="alice", auto_approve=True)
        )
        await orch.execute(
            ExecutionRequest(request="bob work", user_id="bob", auto_approve=True)
        )

        alice_runs = orch.list_runs(owner_id="alice")
        bob_runs = orch.list_runs(owner_id="bob")
        all_runs = orch.list_runs()  # admin / unscoped

        assert {r["user_id"] for r in alice_runs} == {"alice"}
        assert {r["user_id"] for r in bob_runs} == {"bob"}
        assert len(all_runs) >= 2

    async def test_resumed_run_keeps_original_owner(self):
        from services.workflow_orchestrator import (
            ExecutionRequest,
            get_workflow_orchestrator,
            reset_orchestrator,
        )

        reset_orchestrator()
        orch = get_workflow_orchestrator()
        run = await orch.execute(
            ExecutionRequest(request="needs approval", user_id="alice", auto_approve=False)
        )
        assert run.status == "awaiting_approval"
        resumed = await orch.approve_and_resume(run.run_id, approved_by="alice")
        assert resumed.user_id == "alice"


# ── API: endpoint scoping / IDOR ──────────────────────────────────────────────


def _override_user(user: dict):
    """Force backend.server.get_current_user to return ``user``."""
    backend_app.dependency_overrides[server.get_current_user] = lambda: user


@pytest.fixture
def api_client():
    client = TestClient(backend_app)
    yield client
    backend_app.dependency_overrides.pop(server.get_current_user, None)


@pytest.mark.skipif(not _ollama_reachable(), reason="LLM backend not reachable in CI")
class TestOrchestratorEndpointScoping:
    def _seed_run(self, client, user) -> str:
        _override_user(user)
        resp = client.post(
            "/api/workflow/orchestrator/execute",
            json={"request": "seed work for scoping test", "auto_approve": True},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["run"]["run_id"]

    def test_list_is_scoped_to_caller(self, api_client):
        from services.workflow_orchestrator import reset_orchestrator

        reset_orchestrator()
        alice = {"_id": "alice", "email": "alice@example.com", "role": "user"}
        bob = {"_id": "bob", "email": "bob@example.com", "role": "user"}

        alice_run = self._seed_run(api_client, alice)
        self._seed_run(api_client, bob)

        # Alice lists — sees only her run, never bob's.
        _override_user(alice)
        runs = api_client.get("/api/workflow/orchestrator/runs").json()["runs"]
        ids = {r["run_id"] for r in runs}
        assert alice_run in ids
        assert all(r["user_id"] == "alice" for r in runs)

    def test_cross_tenant_get_returns_404(self, api_client):
        from services.workflow_orchestrator import reset_orchestrator

        reset_orchestrator()
        alice = {"_id": "alice", "email": "alice@example.com", "role": "user"}
        bob = {"_id": "bob", "email": "bob@example.com", "role": "user"}

        alice_run = self._seed_run(api_client, alice)

        # Bob tries to read Alice's run by ID — 404, not the run body.
        _override_user(bob)
        resp = api_client.get(f"/api/workflow/orchestrator/runs/{alice_run}")
        assert resp.status_code == 404

    def test_cross_tenant_approve_returns_404(self, api_client):
        from services.workflow_orchestrator import reset_orchestrator

        reset_orchestrator()
        alice = {"_id": "alice", "email": "alice@example.com", "role": "user"}
        bob = {"_id": "bob", "email": "bob@example.com", "role": "user"}

        # Alice creates a run that pauses at the approval gate.
        _override_user(alice)
        resp = api_client.post(
            "/api/workflow/orchestrator/execute",
            json={"request": "needs approval", "auto_approve": False},
        )
        run_id = resp.json()["run"]["run_id"]

        # Bob cannot approve Alice's pending run.
        _override_user(bob)
        resp = api_client.post(f"/api/workflow/orchestrator/approve/{run_id}")
        assert resp.status_code == 404

    def test_non_admin_cannot_auto_approve(self, api_client):
        """A non-admin's auto_approve=true is ignored — the run still pauses at HITL."""
        from services.workflow_orchestrator import reset_orchestrator

        reset_orchestrator()
        alice = {"_id": "alice", "email": "alice@example.com", "role": "user"}
        _override_user(alice)
        resp = api_client.post(
            "/api/workflow/orchestrator/execute",
            json={"request": "do risky thing", "auto_approve": True},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["run"]["status"] == "awaiting_approval"

    def test_admin_may_auto_approve(self, api_client):
        from services.workflow_orchestrator import reset_orchestrator

        reset_orchestrator()
        admin = {"_id": "root", "email": "admin@example.com", "role": "admin"}
        _override_user(admin)
        resp = api_client.post(
            "/api/workflow/orchestrator/execute",
            json={"request": "trusted internal run", "auto_approve": True},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["run"]["status"] == "done"

    def test_approval_is_attributed_to_authenticated_user(self, api_client):
        """approved_by comes from the session, not a client-supplied string."""
        from services.workflow_orchestrator import reset_orchestrator

        reset_orchestrator()
        alice = {"_id": "alice", "email": "alice@example.com", "role": "user"}
        _override_user(alice)
        run_id = api_client.post(
            "/api/workflow/orchestrator/execute",
            json={"request": "needs approval", "auto_approve": False},
        ).json()["run"]["run_id"]

        # Even if a spoofed approved_by is sent as a query param, it's ignored.
        resp = api_client.post(
            f"/api/workflow/orchestrator/approve/{run_id}?approved_by=somebody-else"
        )
        assert resp.status_code in (200, 202), resp.text  # 202 when enqueued via approve_async
        assert resp.json()["run"]["approved_by"] == "alice"

    def test_admin_sees_all_runs(self, api_client):
        from services.workflow_orchestrator import reset_orchestrator

        reset_orchestrator()
        alice = {"_id": "alice", "email": "alice@example.com", "role": "user"}
        admin = {"_id": "root", "email": "admin@example.com", "role": "admin"}

        alice_run = self._seed_run(api_client, alice)

        _override_user(admin)
        body = api_client.get("/api/workflow/orchestrator/runs").json()
        ids = {r["run_id"] for r in body["runs"]}
        assert alice_run in ids
        assert body["scoped_to_user"] is False
        # Admin can read another user's run directly.
        resp = api_client.get(f"/api/workflow/orchestrator/runs/{alice_run}")
        assert resp.status_code == 200

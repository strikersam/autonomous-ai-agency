"""Tests for services/spec_store.py and the /api/specs review endpoints."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from services import spec_store


class FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def sort(self, key, direction=1):
        self._rows.sort(key=lambda r: r.get(key, ""), reverse=direction == -1)
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    async def to_list(self, length=None):
        return self._rows[:length] if length else self._rows


class FakeCollection:
    def __init__(self):
        self.rows: list[dict] = []

    async def insert_one(self, doc):
        self.rows.append(dict(doc))
        return SimpleNamespace(inserted_id=doc.get("spec_id"))

    async def find_one(self, query):
        for row in self.rows:
            if all(row.get(k) == v for k, v in query.items()):
                return dict(row)
        return None

    def find(self, query=None):
        query = query or {}
        return FakeCursor(
            dict(r) for r in self.rows
            if all(r.get(k) == v for k, v in query.items())
        )

    async def update_one(self, query, update):
        for row in self.rows:
            if all(row.get(k) == v for k, v in query.items()):
                row.update(update.get("$set", {}))
                return SimpleNamespace(matched_count=1, modified_count=1)
        return SimpleNamespace(matched_count=0, modified_count=0)


@pytest.fixture
def fake_db(monkeypatch):
    db = SimpleNamespace(agent_specs=FakeCollection())
    monkeypatch.setattr(spec_store, "_db", lambda: db)
    return db


def test_plan_to_markdown_renders_goal_steps_and_risks():
    md = spec_store.plan_to_markdown(
        "Add health endpoint",
        [{"id": 1, "description": "Create route", "files": ["api.py"], "type": "edit"}],
        ["Might conflict with existing route"],
    )
    assert "# Spec: Add health endpoint" in md
    assert "1. Create route" in md
    assert "Files: api.py" in md
    assert "Might conflict" in md
    assert "## Verification" in md


def test_persist_plan_spec_auto_approves_by_default(fake_db, monkeypatch):
    monkeypatch.delenv("AGENT_SPEC_APPROVAL_REQUIRED", raising=False)
    doc = asyncio.run(
        spec_store.persist_plan_spec(
            session_id="s1", goal="Goal", steps=[{"id": 1, "description": "d"}]
        )
    )
    assert doc is not None and doc["status"] == "approved"
    assert fake_db.agent_specs.rows[0]["spec_id"] == doc["spec_id"]


def test_persist_plan_spec_pending_when_approval_required(fake_db, monkeypatch):
    monkeypatch.setenv("AGENT_SPEC_APPROVAL_REQUIRED", "true")
    doc = asyncio.run(
        spec_store.persist_plan_spec(session_id="s1", goal="Goal", steps=[])
    )
    assert doc is not None and doc["status"] == "pending"


def test_persist_disabled_via_env(fake_db, monkeypatch):
    monkeypatch.setenv("AGENT_SPEC_PERSIST", "false")
    doc = asyncio.run(
        spec_store.persist_plan_spec(session_id="s1", goal="Goal", steps=[])
    )
    assert doc is None and fake_db.agent_specs.rows == []


def test_set_spec_status_rejects_invalid_status(fake_db):
    with pytest.raises(ValueError):
        asyncio.run(spec_store.set_spec_status("x", "bogus", decided_by="t"))


def test_await_spec_approval_paths(fake_db, monkeypatch):
    monkeypatch.setenv("AGENT_SPEC_APPROVAL_REQUIRED", "true")
    doc = asyncio.run(
        spec_store.persist_plan_spec(session_id="s1", goal="Goal", steps=[])
    )
    spec_id = doc["spec_id"]

    asyncio.run(spec_store.set_spec_status(spec_id, "approved", decided_by="op"))
    assert asyncio.run(spec_store.await_spec_approval(spec_id)) is True

    asyncio.run(spec_store.set_spec_status(spec_id, "rejected", decided_by="op"))
    assert asyncio.run(spec_store.await_spec_approval(spec_id)) is False

    monkeypatch.setenv("AGENT_SPEC_APPROVAL_TIMEOUT", "0")
    asyncio.run(spec_store.set_spec_status(spec_id, "pending", decided_by="op"))
    assert asyncio.run(spec_store.await_spec_approval(spec_id)) is False


def test_spec_endpoints_list_get_approve_reject(app_client, fake_db, monkeypatch):
    monkeypatch.setenv("AGENT_SPEC_APPROVAL_REQUIRED", "true")
    doc = asyncio.run(
        spec_store.persist_plan_spec(
            session_id="s1", goal="Review me", steps=[{"id": 1, "description": "d"}]
        )
    )
    spec_id = doc["spec_id"]

    resp = app_client.get("/api/specs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1 and body["specs"][0]["goal"] == "Review me"

    resp = app_client.get(f"/api/specs/{spec_id}")
    assert resp.status_code == 200
    assert "# Spec: Review me" in resp.json()["markdown"]

    resp = app_client.post(f"/api/specs/{spec_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["decided_by"] == "admin@example.com"

    resp = app_client.post(f"/api/specs/{spec_id}/reject")
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    resp = app_client.get("/api/specs/does-not-exist")
    assert resp.status_code == 404


# ── Fail-closed regression: approval-required + persistence failure ────────

def test_persist_plan_spec_reraises_when_approval_required_and_persist_fails(
    fake_db, monkeypatch
):
    """Regression: previously persist_plan_spec() swallowed insert_one()
    failures into a bare `return None`, and callers that only checked
    `spec_doc is not None` would silently proceed without approval. The
    fix moves the fail-closed decision to the caller (agent/loop.py), but
    persist_plan_spec itself must still surface the real exception rather
    than a generic None so the caller can distinguish "approval not needed"
    from "persistence broke while approval was required"."""
    monkeypatch.setenv("AGENT_SPEC_APPROVAL_REQUIRED", "true")

    async def broken_insert(doc):
        raise RuntimeError("no such table: agent_specs")

    fake_db.agent_specs.insert_one = broken_insert

    with pytest.raises(RuntimeError, match="no such table"):
        asyncio.run(
            spec_store.persist_plan_spec(session_id="s1", goal="Goal", steps=[])
        )


def test_persist_plan_spec_swallows_failure_when_approval_not_required(
    fake_db, monkeypatch
):
    """When approval isn't required, persistence stays best-effort — a
    storage hiccup shouldn't block a normal (auto-approved) run."""
    monkeypatch.delenv("AGENT_SPEC_APPROVAL_REQUIRED", raising=False)

    async def broken_insert(doc):
        raise RuntimeError("transient failure")

    fake_db.agent_specs.insert_one = broken_insert

    doc = asyncio.run(
        spec_store.persist_plan_spec(session_id="s1", goal="Goal", steps=[])
    )
    assert doc is None


def test_spec_decision_never_logs_operator_email(app_client, fake_db, monkeypatch, caplog):
    """AGENTS.md: never log sensitive values, including email addresses.
    approve/reject previously logged the operator's raw email via
    `decided_by` at INFO level."""
    import logging
    monkeypatch.setenv("AGENT_SPEC_APPROVAL_REQUIRED", "true")
    doc = asyncio.run(
        spec_store.persist_plan_spec(session_id="s1", goal="G", steps=[])
    )
    spec_id = doc["spec_id"]

    with caplog.at_level(logging.INFO):
        resp = app_client.post(f"/api/specs/{spec_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["decided_by"] == "admin@example.com"  # still recorded on the doc
    assert "admin@example.com" not in caplog.text  # but never written to the log stream

"""Tests for auto issue → task intake (Autonomy Charter G3).

Covers HMAC signature verification, the opt-in label gate, issue→Task mapping
(untrusted-text handling), and idempotency by source_id.
"""
from __future__ import annotations

import hashlib
import hmac

import pytest

from tasks.issue_intake import (
    intake_issue,
    issue_source_id,
    map_issue_to_task,
    should_intake,
    verify_signature,
)
from tasks.models import TaskPriority
from tasks.store import TaskStore
from tasks.service import TaskWorkflowService


# ── signature verification ───────────────────────────────────────────────────


def _sign(secret: str, payload: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def test_verify_signature_valid():
    secret, body = "s3cret", b'{"action":"opened"}'
    assert verify_signature(secret, body, _sign(secret, body)) is True


def test_verify_signature_rejects_tampered_and_missing():
    secret, body = "s3cret", b'{"action":"opened"}'
    assert verify_signature(secret, body, _sign(secret, body + b"x")) is False
    assert verify_signature(secret, body, None) is False
    assert verify_signature(secret, body, "garbage") is False
    assert verify_signature("", body, _sign("", body)) is False  # no secret → reject


# ── label gate ───────────────────────────────────────────────────────────────


def _issue(**over):
    base = {
        "number": 42,
        "title": "Boom",
        "body": "it broke",
        "state": "open",
        "labels": [{"name": "autonomy:intake"}],
        "user": {"login": "alice"},
        "html_url": "https://github.com/o/r/issues/42",
    }
    base.update(over)
    return base


def test_should_intake_requires_optin_label():
    assert should_intake("opened", _issue()) is True
    assert should_intake("opened", _issue(labels=[{"name": "bug"}])) is False
    # require_label=False lets any open issue through
    assert should_intake("opened", _issue(labels=[{"name": "bug"}]), require_label=False) is True


def test_should_intake_skips_prs_closed_and_irrelevant_actions():
    assert should_intake("opened", _issue(pull_request={"url": "x"})) is False
    assert should_intake("opened", _issue(state="closed")) is False
    assert should_intake("deleted", _issue()) is False
    assert should_intake("assigned", _issue()) is False


# ── mapping (untrusted text) ─────────────────────────────────────────────────


def test_map_issue_to_task_fields_and_untrusted_prompt():
    task = map_issue_to_task(_issue(labels=[{"name": "autonomy:intake"}, {"name": "bug"}]), "o/r")
    assert task.source == "github_issue"
    assert task.source_id == "o/r#42"
    assert task.task_type == "issue_intake"
    assert "github:o/r" in task.tags and "cap:bugfix" in task.tags
    assert "untrusted" in task.prompt.lower()
    assert "Boom" in task.title
    # body embedded as data
    assert "it broke" in task.description


def test_map_issue_priority_from_urgent_label():
    assert map_issue_to_task(_issue(labels=[{"name": "p0"}]), "o/r").priority == TaskPriority.HIGH
    assert map_issue_to_task(_issue(labels=[{"name": "autonomy:intake"}]), "o/r").priority == TaskPriority.MEDIUM


def test_issue_source_id():
    assert issue_source_id("octo/repo", 7) == "octo/repo#7"


# ── intake end-to-end + idempotency ──────────────────────────────────────────


@pytest.fixture
def store():
    return TaskStore(db=None)  # in-memory mode


async def test_intake_creates_task(store):
    service = TaskWorkflowService(store=store)
    payload = {"action": "opened", "repository": {"full_name": "o/r"}, "issue": _issue()}
    task = await intake_issue(payload, store=store, service=service)
    assert task is not None
    assert task.source_id == "o/r#42"
    # persisted + findable by source id
    assert (await store.find_by_source_id("o/r#42")).task_id == task.task_id


async def test_intake_is_idempotent(store):
    service = TaskWorkflowService(store=store)
    payload = {"action": "opened", "repository": {"full_name": "o/r"}, "issue": _issue()}
    first = await intake_issue(payload, store=store, service=service)
    # replay the same webhook (and a re-label event) → no duplicate
    again = await intake_issue(payload, store=store, service=service)
    relabel = await intake_issue(
        {"action": "labeled", "repository": {"full_name": "o/r"}, "issue": _issue()},
        store=store, service=service,
    )
    assert first is not None
    assert again is None
    assert relabel is None
    assert len(await store.list_all(limit=100)) == 1


async def test_intake_skips_unlabeled_issue(store):
    service = TaskWorkflowService(store=store)
    payload = {
        "action": "opened",
        "repository": {"full_name": "o/r"},
        "issue": _issue(labels=[{"name": "bug"}]),
    }
    assert await intake_issue(payload, store=store, service=service) is None
    assert len(await store.list_all(limit=100)) == 0


async def test_intake_ignores_non_issue_payloads(store):
    service = TaskWorkflowService(store=store)
    assert await intake_issue({"action": "opened"}, store=store, service=service) is None
    assert await intake_issue(
        {"action": "opened", "repository": {"full_name": "o/r"}}, store=store, service=service
    ) is None


# ── route wiring (POST /api/webhooks/github) ─────────────────────────────────


def test_webhook_route_503_without_secret(client, monkeypatch):
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
    r = client.post("/api/webhooks/github", content=b"{}",
                    headers={"X-GitHub-Event": "ping"})
    assert r.status_code == 503


def test_webhook_route_rejects_bad_signature(client, monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "whsec")
    r = client.post("/api/webhooks/github", content=b'{"zen":"hi"}',
                    headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": "sha256=bad"})
    assert r.status_code == 401


def test_webhook_route_signed_ping(client, monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "whsec")
    body = b'{"zen":"hi"}'
    r = client.post(
        "/api/webhooks/github", content=body,
        headers={
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": _sign("whsec", body),
        },
    )
    assert r.status_code == 200
    assert r.json().get("pong") is True

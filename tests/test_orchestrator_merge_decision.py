"""Tests for the G5 RepoConnection/DeliveryPolicy wiring into the orchestrator
land step (decide_merge → ApprovalGate + first-merge consent).
"""
from __future__ import annotations

from typing import Literal

import pytest

import services.company_graph_store as cgs
from models.company_graph import Company, DeliveryPolicy, RepoConnection
from services.workflow_orchestrator import WorkflowOrchestrator, WorkflowRun


class _FakeStore:
    def __init__(self, company: Company | None) -> None:
        self._company: Company | None = company
        self.saved: Company | None = None

    async def get_company(self, company_id: str) -> Company | None:
        return self._company

    async def update_company(self, company: Company) -> Company:
        self.saved = company
        self._company = company
        return company


@pytest.fixture
def orch() -> WorkflowOrchestrator:
    return WorkflowOrchestrator()


def _company(
    *,
    has_repo: bool = True,
    consent: bool = False,
    mode: Literal["pr_required", "direct_push"] = "pr_required",
) -> Company:
    conn = None
    if has_repo:
        policy = DeliveryPolicy(
            mode=mode, protected=(mode == "pr_required"), first_merge_consent=consent
        )
        conn = RepoConnection(owner="octo", repo="site", policy=policy)
    return Company(id="c1", name="Acme", domain="acme.com", repo_connection=conn)


# ── _resolve_merge_decision ──────────────────────────────────────────────────


async def test_resolve_none_without_company(orch):
    assert await orch._resolve_merge_decision(WorkflowRun()) is None


async def test_resolve_first_merge_gates(orch, monkeypatch):
    monkeypatch.setattr(cgs, "get_company_graph_store", lambda: _FakeStore(_company(consent=False)))
    d = await orch._resolve_merge_decision(WorkflowRun(company_id="c1"))
    assert d.action == "telegram_gate" and d.requires_approval is True


async def test_resolve_open_pr_after_consent(orch, monkeypatch):
    monkeypatch.setattr(
        cgs, "get_company_graph_store",
        lambda: _FakeStore(_company(consent=True, mode="pr_required")),
    )
    d = await orch._resolve_merge_decision(WorkflowRun(company_id="c1"))
    assert d.action == "open_pr" and d.requires_approval is False


async def test_resolve_direct_push_after_consent(orch, monkeypatch):
    monkeypatch.setattr(
        cgs, "get_company_graph_store",
        lambda: _FakeStore(_company(consent=True, mode="direct_push")),
    )
    d = await orch._resolve_merge_decision(WorkflowRun(company_id="c1"))
    assert d.action == "direct_push" and d.requires_approval is False


async def test_resolve_url_only_company_pauses(orch, monkeypatch):
    monkeypatch.setattr(cgs, "get_company_graph_store", lambda: _FakeStore(_company(has_repo=False)))
    d = await orch._resolve_merge_decision(WorkflowRun(company_id="c1"))
    assert d.action == "awaiting_repo_connection" and d.requires_approval is False


# ── _record_first_merge_consent ──────────────────────────────────────────────


async def test_record_consent_persists_for_first_merge(orch, monkeypatch):
    store = _FakeStore(_company(consent=False))
    monkeypatch.setattr(cgs, "get_company_graph_store", lambda: store)
    run = WorkflowRun(
        company_id="c1",
        merge_decision={"action": "telegram_gate", "requires_approval": True, "reason": "x"},
    )
    await orch._record_first_merge_consent(run)
    assert store.saved is not None
    assert store.saved.repo_connection.policy.first_merge_consent is True


async def test_record_consent_noop_for_non_gate_decision(orch, monkeypatch):
    store = _FakeStore(_company(consent=False))
    monkeypatch.setattr(cgs, "get_company_graph_store", lambda: store)
    run = WorkflowRun(
        company_id="c1",
        merge_decision={"action": "open_pr", "requires_approval": False, "reason": "x"},
    )
    await orch._record_first_merge_consent(run)
    assert store.saved is None  # nothing to consent to


async def test_record_consent_noop_without_decision(orch, monkeypatch):
    store = _FakeStore(_company(consent=False))
    monkeypatch.setattr(cgs, "get_company_graph_store", lambda: store)
    await orch._record_first_merge_consent(WorkflowRun(company_id="c1"))
    assert store.saved is None

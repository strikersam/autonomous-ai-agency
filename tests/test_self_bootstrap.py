"""Tests for the self-onboarding bootstrap.

The platform should register itself as a company on startup, idempotently, and
without ever crashing when the DB/onboarding is unavailable.
"""

from __future__ import annotations

import pytest

import services.self_bootstrap as sb


async def test_disabled_returns_disabled(monkeypatch):
    monkeypatch.setenv("SELF_BOOTSTRAP_ENABLED", "false")
    result = await sb.ensure_self_company()
    assert result["status"] == "disabled"


async def test_skips_when_already_complete(monkeypatch):
    monkeypatch.setenv("SELF_BOOTSTRAP_ENABLED", "true")

    class _Existing:
        id = "comp-self"
        domain = sb._self_domain()
        onboarding_status = "complete"

    async def _fake_find():
        return _Existing()

    async def _fake_count(company_id):
        return 3  # company already has specialists → skip

    async def _no_stale():
        return []

    monkeypatch.setattr(sb, "_find_self_company", _fake_find)
    monkeypatch.setattr(sb, "_count_specialists", _fake_count)
    monkeypatch.setattr(sb, "_find_stale_self_companies", _no_stale)
    result = await sb.ensure_self_company()
    assert result["status"] == "exists"
    assert result["company_id"] == "comp-self"


async def test_never_raises_on_failure(monkeypatch):
    monkeypatch.setenv("SELF_BOOTSTRAP_ENABLED", "true")

    async def _boom():
        raise RuntimeError("no db at boot")

    async def _stale_boom():
        raise RuntimeError("no db at boot")

    monkeypatch.setattr(sb, "_find_self_company", _boom)
    monkeypatch.setattr(sb, "_find_stale_self_companies", _stale_boom)
    # Must not raise — bootstrap is best-effort and must never crash startup.
    result = await sb.ensure_self_company()
    assert result["status"] == "deferred"
    assert "no db at boot" in result["error"]


async def test_onboards_when_missing(monkeypatch):
    monkeypatch.setenv("SELF_BOOTSTRAP_ENABLED", "true")

    async def _none():
        return None

    seeded = {}

    class _Progress:
        company_id = "comp-new"
        status = "complete"

    class _Onboarding:
        async def start_onboarding(self, **kwargs):
            seeded["kwargs"] = kwargs
            return _Progress()

    async def _seed(company_id, owner_id):
        seeded["task_company"] = company_id
        return "task-123"

    monkeypatch.setattr(sb, "_find_self_company", _none)
    monkeypatch.setattr("services.onboarding.get_onboarding_service", lambda: _Onboarding())
    monkeypatch.setattr(sb, "_seed_connect_task", _seed)

    async def _fake_count(company_id):
        return 2  # onboarding provisioned specialists

    async def _no_stale():
        return []

    monkeypatch.setattr(sb, "_count_specialists", _fake_count)
    monkeypatch.setattr(sb, "_find_stale_self_companies", _no_stale)

    result = await sb.ensure_self_company(owner_id="admin@test.local")
    assert result["status"] == "onboarded"
    assert result["company_id"] == "comp-new"
    assert result["connect_task_id"] == "task-123"
    # Website + repo were passed to onboarding.
    assert sb.SELF_WEBSITE_URL in seeded["kwargs"]["website_urls"]
    assert sb.SELF_REPO_URL in seeded["kwargs"]["repo_urls"]

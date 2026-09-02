"""Tests for services.ephemeral_reaper — destroy expired ephemeral companies.

Runs against the SQLite company-graph store (no MongoDB required).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def store(tmp_path, monkeypatch):
    try:
        from services.company_graph_store import SQLiteStore
    except (ImportError, ModuleNotFoundError):
        pytest.skip("company graph store not importable")
    s = SQLiteStore()
    s._db_path = str(tmp_path / "reaper.db")
    # Point the reaper's get_company_graph_store() at this isolated store.
    monkeypatch.setattr(
        "services.company_graph_store.get_company_graph_store", lambda: s
    )
    return s


def _company(name, domain, *, persistent, expires_at):
    from models.company_graph import Company
    return Company(
        name=name, domain=domain, persistent=persistent, expires_at=expires_at,
    )


@pytest.mark.asyncio
async def test_reaps_only_expired_ephemeral(store):
    from services.ephemeral_reaper import reap_expired_companies

    now = datetime.now(timezone.utc)
    expired = await store.create_company(
        _company("Expired", "expired.com", persistent=False, expires_at=now - timedelta(hours=1))
    )
    future = await store.create_company(
        _company("Future", "future.com", persistent=False, expires_at=now + timedelta(hours=5))
    )
    admin = await store.create_company(
        _company("AdminCo", "admin.com", persistent=True, expires_at=None)
    )

    deleted = await reap_expired_companies(now=now)
    assert deleted == 1

    assert await store.get_company(expired.id) is None       # reaped
    assert await store.get_company(future.id) is not None     # not yet due
    assert await store.get_company(admin.id) is not None       # persistent — never reaped


@pytest.mark.asyncio
async def test_persistent_company_survives_past_expiry(store):
    """A persistent company is never reaped even if it somehow carries an
    expires_at in the past (defensive — admin companies must persist forever)."""
    from services.ephemeral_reaper import reap_expired_companies

    now = datetime.now(timezone.utc)
    admin = await store.create_company(
        _company("AdminCo", "admin.com", persistent=True, expires_at=now - timedelta(days=10))
    )
    deleted = await reap_expired_companies(now=now)
    assert deleted == 0
    assert await store.get_company(admin.id) is not None


@pytest.mark.asyncio
async def test_no_expiry_is_never_reaped(store):
    from services.ephemeral_reaper import reap_expired_companies

    now = datetime.now(timezone.utc)
    c = await store.create_company(
        _company("NoExpiry", "noexp.com", persistent=False, expires_at=None)
    )
    assert await reap_expired_companies(now=now) == 0
    assert await store.get_company(c.id) is not None


def _register_specialist(agent_store, agent_id, company_id, *, auto=True):
    """Register an AgentDefinition the way CompanyAgencyService.activate_company does."""
    from agents.store import AgentDefinition
    tags = [f"company:{company_id}"]
    if auto:
        tags.append("auto-provisioned")
    return agent_store.create(AgentDefinition(
        agent_id=agent_id, owner_id=company_id, name=agent_id,
        role="backend", is_public=True, tags=tags,
    ))


class TestOrphanAgentReaper:
    """reap_orphaned_agents cleans specialist agents whose company is gone."""

    @pytest.mark.asyncio
    async def test_removes_only_agents_of_deleted_companies(self, store, monkeypatch):
        from agents import store as agent_store_module
        from agents.store import AgentStore, AgentDefinition
        from services.ephemeral_reaper import reap_orphaned_agents

        monkeypatch.setattr(agent_store_module, "_store", AgentStore())
        agent_store = agent_store_module.get_agent_store()

        # One live company with a registered specialist.
        live = await store.create_company(
            _company("Live", "live.com", persistent=True, expires_at=None)
        )
        await _register_specialist(agent_store, "specialist:live1", live.id)

        # An agent whose company was already deleted (id resolves to nothing).
        await _register_specialist(agent_store, "specialist:ghost1", "co_deleted_123")

        # A user's personal agent — no company/auto-provisioned tags — must survive.
        await agent_store.create(AgentDefinition(
            agent_id="user-agent-1", owner_id="someone@example.com",
            name="My Agent", role="backend", is_public=False, tags=[],
        ))

        removed = await reap_orphaned_agents()
        assert removed == 1

        assert await agent_store.get("specialist:live1") is not None   # company exists
        assert await agent_store.get("specialist:ghost1") is None      # orphan reaped
        assert await agent_store.get("user-agent-1") is not None       # never a candidate

    @pytest.mark.asyncio
    async def test_lookup_error_never_deletes(self, store, monkeypatch):
        """A company-lookup failure is treated as 'still exists' — no deletion."""
        from agents import store as agent_store_module
        from agents.store import AgentStore
        from services.ephemeral_reaper import reap_orphaned_agents

        monkeypatch.setattr(agent_store_module, "_store", AgentStore())
        agent_store = agent_store_module.get_agent_store()
        await _register_specialist(agent_store, "specialist:x", "co_x")

        async def boom(_cid):
            raise RuntimeError("db down")
        monkeypatch.setattr(store, "get_company", boom)

        assert await reap_orphaned_agents() == 0
        assert await agent_store.get("specialist:x") is not None

    def test_company_id_for_agent_ignores_non_specialists(self):
        from services.ephemeral_reaper import _company_id_for_agent
        from agents.store import AgentDefinition

        # Auto-provisioned specialist → returns its company id.
        spec = AgentDefinition(
            agent_id="specialist:1", owner_id="co1", name="s", role="backend",
            tags=["company:co1", "auto-provisioned"],
        )
        assert _company_id_for_agent(spec) == "co1"

        # A user agent with no tags → None (never a candidate).
        user = AgentDefinition(
            agent_id="u1", owner_id="me@example.com", name="u", role="backend", tags=[],
        )
        assert _company_id_for_agent(user) is None

        # A company-tagged agent that is NOT auto-provisioned → None (leave it).
        manual = AgentDefinition(
            agent_id="m1", owner_id="co1", name="m", role="backend",
            tags=["company:co1"],
        )
        assert _company_id_for_agent(manual) is None


@pytest.mark.asyncio
async def test_lifecycle_fields_roundtrip_sqlite(store):
    """The new lifecycle columns persist and reload correctly."""
    now = datetime.now(timezone.utc)
    from models.company_graph import Company
    created = await store.create_company(
        Company(
            name="Eph", domain="eph.com", persistent=False,
            expires_at=now + timedelta(hours=24),
            created_by_role="user", created_by_provider="github",
        )
    )
    got = await store.get_company(created.id)
    assert got is not None
    assert got.persistent is False
    assert got.created_by_provider == "github"
    assert got.created_by_role == "user"
    assert got.expires_at is not None

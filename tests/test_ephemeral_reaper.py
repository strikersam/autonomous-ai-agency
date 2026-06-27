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

"""tests/test_dashboard_cache.py — unit tests for the dashboard hot-path
helpers added to speed up /api/stats and /api/observability/metrics:

  * ``_cached``     — short-TTL, single-flight in-process cache.
  * ``_fast_count`` — count without materialising rows (estimated_document_count
                      with a count_documents fallback).
"""
from __future__ import annotations

import asyncio

import pytest

# backend.server is made importable by tests/conftest.py (it sets ADMIN_PASSWORD
# and friends); server.py itself defaults JWT_SECRET/MONGO_URL/ADMIN_EMAIL when
# unset, so no secrets are hardcoded here.
from backend.server import _cached, _fast_count, _DASHBOARD_CACHE  # noqa: E402


@pytest.fixture(autouse=True)
def _ensure_mongo_fast_count():
    """Ensure _fast_count tries estimated_document_count() for tests.

    conftest.py imports backend.server before this test file runs, so
    _storage_uses_objectids was already evaluated. Patch it directly.
    """
    import backend.server as _bs
    _bs._storage_uses_objectids = True
    yield


@pytest.fixture(autouse=True)
def _clear_cache():
    _DASHBOARD_CACHE.clear()
    yield
    _DASHBOARD_CACHE.clear()


@pytest.mark.asyncio
async def test_cached_serves_within_ttl():
    calls = {"n": 0}

    async def producer():
        calls["n"] += 1
        return calls["n"]

    first = await _cached("k", ttl_s=60.0, producer=producer)
    second = await _cached("k", ttl_s=60.0, producer=producer)
    assert first == second == 1
    assert calls["n"] == 1  # producer ran once; second call was a cache hit


@pytest.mark.asyncio
async def test_cached_recomputes_after_expiry():
    calls = {"n": 0}

    async def producer():
        calls["n"] += 1
        return calls["n"]

    await _cached("k", ttl_s=0.0, producer=producer)
    # ttl_s=0 means every call is expired → producer runs again.
    await _cached("k", ttl_s=0.0, producer=producer)
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_cached_is_single_flight():
    calls = {"n": 0}

    async def producer():
        calls["n"] += 1
        await asyncio.sleep(0.05)
        return calls["n"]

    # Many concurrent callers for a cold key → producer runs exactly once.
    results = await asyncio.gather(*[
        _cached("k", ttl_s=60.0, producer=producer) for _ in range(10)
    ])
    assert calls["n"] == 1
    assert results == [1] * 10


class _CollWithEstimate:
    async def estimated_document_count(self):
        return 42

    async def count_documents(self, query):  # pragma: no cover - must not be used
        raise AssertionError("should prefer estimated_document_count")


class _CollWithoutEstimate:
    def __init__(self):
        self.calls = []

    async def count_documents(self, query):
        self.calls.append(query)
        return 7


@pytest.mark.asyncio
async def test_fast_count_prefers_estimate():
    assert await _fast_count(_CollWithEstimate()) == 42


@pytest.mark.asyncio
async def test_fast_count_falls_back_to_count_documents():
    coll = _CollWithoutEstimate()
    assert await _fast_count(coll) == 7
    assert coll.calls == [{}]  # fell back with an unfiltered count

"""tests/test_provider_models_db_outage.py — GET /api/providers/{id}/models resilience.

Regression for a live 500: switching the Brain Card's provider to one of the
unified BrainConfig catalog providers (e.g. "moonshot") that has no row in the
legacy `providers` Mongo collection — or hitting the endpoint during a
transient Mongo outage (Render free-tier cold start) — raised an unhandled
``pymongo.errors.ServerSelectionTimeoutError`` straight out of
``provider_models()`` because, unlike its sibling ``list_providers()``, it had
no fallback around the DB lookup. Fixed by mirroring ``list_providers()``'s
resilience pattern: fall back to the predefined model catalog instead of
propagating the DB exception as a 500.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


def test_provider_models_falls_back_on_db_outage(app_client, monkeypatch):
    """A DB exception during the provider lookup must not surface as a 500."""
    import backend.server as srv

    fake_db = MagicMock()
    fake_db.providers.find_one = AsyncMock(side_effect=RuntimeError("mongo unreachable"))
    monkeypatch.setattr(srv, "get_db", lambda: fake_db)

    r = app_client.get("/api/providers/moonshot/models")
    assert r.status_code == 200
    body = r.json()
    assert body["provider_id"] == "moonshot"
    assert body["models"], "expected the predefined moonshot catalog as a fallback"


def test_provider_models_unregistered_provider_uses_predefined_catalog(app_client):
    """A catalog provider (unified BrainConfig) with no legacy `providers` row
    must return its predefined models instead of a bare 404 — it was simply
    never added via the old POST /api/providers flow."""
    r = app_client.get("/api/providers/moonshot/models")
    assert r.status_code == 200
    assert r.json()["models"]


def test_provider_models_truly_unknown_provider_still_404s(app_client):
    """A provider_id absent from both Mongo and the predefined catalog is a
    genuine 404, not swallowed into an empty 200."""
    r = app_client.get("/api/providers/totally-made-up-id-xyz/models")
    assert r.status_code == 404

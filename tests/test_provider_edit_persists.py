"""tests/test_provider_edit_persists.py — a Providers-screen edit survives restarts.

``seed_default_providers()`` runs on every boot and used to overwrite
``default_model`` and ``priority`` from env/code defaults, so an operator's edit
(e.g. moving NVIDIA NIM off the retired ``z-ai/glm-5.2``) was reverted by the
next Render restart. Edits now pin the field; the seed leaves pinned fields alone.
"""
from __future__ import annotations

import pytest

import backend.server as server
from backend.server import ProviderUpdate, _seed_sync_update


def test_seed_does_not_overwrite_an_operator_edited_model():
    existing = {
        "provider_id": "nvidia-nim",
        "default_model": "nvidia/nemotron-3-super-120b-a12b",
        "priority": 3,
        "operator_overrides": {"default_model": True, "priority": True},
    }
    seed = {"default_model": "z-ai/glm-5.2", "priority": -10, "status": "configured"}
    update = _seed_sync_update(existing, seed)
    assert "default_model" not in update
    assert "priority" not in update


def test_seed_still_syncs_fields_nobody_edited():
    existing = {"default_model": "old-model", "priority": 5, "api_key": "k1", "status": "unconfigured"}
    seed = {"default_model": "new-model", "priority": -10, "api_key": "k2", "status": "configured"}
    assert _seed_sync_update(existing, seed) == {
        "default_model": "new-model", "priority": -10, "api_key": "k2", "status": "configured",
    }


class _Result:
    matched_count = 1


class _Providers:
    def __init__(self) -> None:
        self.updates: list[dict] = []

    async def update_one(self, _query, update):
        self.updates.append(update["$set"])
        return _Result()

    async def update_many(self, *_a, **_k):
        return _Result()


class _DB:
    def __init__(self) -> None:
        self.providers = _Providers()


@pytest.mark.asyncio
async def test_edit_pins_the_changed_fields_and_refreshes_the_brain(monkeypatch):
    db = _DB()
    monkeypatch.setattr(server, "get_db", lambda: db)

    async def _no_activity(*_a, **_k):
        return None

    monkeypatch.setattr(server, "log_activity", _no_activity)
    invalidated: list[bool] = []
    import packages.ai.brain as brain
    monkeypatch.setattr(brain, "invalidate_brain_cache", lambda: invalidated.append(True))

    body = ProviderUpdate(default_model="nvidia/nemotron-3-super-120b-a12b")
    out = await server.update_provider("nvidia-nim", body, {"_id": "admin", "role": "admin"})

    assert out == {"ok": True}
    written = db.providers.updates[0]
    assert written["default_model"] == "nvidia/nemotron-3-super-120b-a12b"
    assert written["operator_overrides.default_model"] is True
    assert "operator_overrides.priority" not in written
    assert invalidated == [True]


@pytest.mark.asyncio
async def test_non_admin_cannot_edit_a_provider(monkeypatch):
    db = _DB()
    monkeypatch.setattr(server, "get_db", lambda: db)
    with pytest.raises(server.HTTPException) as exc:
        await server.update_provider(
            "nvidia-nim", ProviderUpdate(base_url="https://evil.example/v1"),
            {"_id": "u1", "role": "user"},
        )
    assert exc.value.status_code == 403
    assert db.providers.updates == []


def test_seed_never_sends_the_env_key_to_a_hand_set_base_url():
    existing = {
        "base_url": "https://elsewhere.example/v1", "api_key": "hand-set",
        "operator_overrides": {"base_url": True},
    }
    seed = {"base_url": "https://integrate.api.nvidia.com/v1", "api_key": "env-key"}
    assert "api_key" not in _seed_sync_update(existing, seed)

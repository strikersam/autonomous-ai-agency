"""tests/test_webui_provider_priority.py — Priority + reorder + brain-policy surface for the webui UI.

The CEO brain selector reads ``priority`` from each configured provider record.
Operators want to manage that priority from the /admin/app UI. These tests pin
the contract:
  - ``priority`` is persisted on create/update and exposed via ``list_admin``
  - ``reorder(provider_ids)`` assigns highest priority to the first id
  - The admin /providers/reorder route hits ``ProviderManager.reorder`` and
    returns the prioritized list
  - The admin /providers/role-tags route surfaces brain/sub/fallback/unconfigured
    roles consistent with ``brain_policy.get_provider_role_tags``
  - The admin /policy/brain route returns the active brain + ALLOW_PAID_BRAIN state
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import proxy
from webui.config_store import JsonConfigStore, JsonStorePaths
from webui.providers import ProviderCreate, ProviderManager, ProviderUpdate
from webui.workspaces import WorkspaceManager


@pytest.fixture(autouse=True)
def _reset_brain_singletons(monkeypatch):
    """Reset the brain_config + brain_policy singletons before each test.

    V2.0 Phase 2 moved brain_config_store → packages.ai.brain_config and
    brain_policy → packages.ai.brain. Tests that mutate _store or
    _cached_brain must target the REAL modules (not the shims).
    """
    import packages.ai.brain_config as _bcs
    import packages.ai.brain as _bp
    monkeypatch.setattr(_bcs, "_store", None)
    monkeypatch.setattr(_bp, "_cached_brain", None)


def _bootstrap(tmp_path: Path) -> tuple[ProviderManager, WorkspaceManager]:
    store = JsonConfigStore(
        JsonStorePaths(
            providers=tmp_path / "providers.json",
            workspaces=tmp_path / "workspaces.json",
        )
    )
    providers = ProviderManager(store)
    workspaces = WorkspaceManager(store, default_local_root=tmp_path)
    providers.ensure_defaults(local_base_url="http://localhost:11434")
    return providers, workspaces


# ── ProviderManager: priority field plumbing ──────────────────────────────────


def test_create_persists_priority(tmp_path: Path):
    providers, _ = _bootstrap(tmp_path)
    rec = providers.create(
        ProviderCreate(
            name="High prio remote",
            base_url="https://example.com",
            api_key="sk-test",
            priority=42,
        )
    )
    assert rec.priority == 42
    items = providers._items()
    saved = [it for it in items if it["provider_id"] == rec.provider_id][0]
    assert saved["priority"] == 42


def test_update_writes_priority(tmp_path: Path):
    providers, _ = _bootstrap(tmp_path)
    rec = providers.create(
        ProviderCreate(
            name="Bumpable",
            base_url="https://example.com",
            default_model="m1",
        )
    )
    assert rec.priority == 0
    bumped = providers.update(rec.provider_id, ProviderUpdate(priority=999))
    assert bumped is not None
    assert bumped.priority == 999


def test_list_includes_priority(tmp_path: Path):
    providers, _ = _bootstrap(tmp_path)
    rec = providers.create(
        ProviderCreate(
            name="Listed",
            base_url="https://example.com",
            priority=7,
        )
    )
    listed = providers.list_admin()
    me = [p for p in listed if p.provider_id == rec.provider_id][0]
    assert me.priority == 7


def test_get_secret_includes_priority(tmp_path: Path):
    providers, _ = _bootstrap(tmp_path)
    rec = providers.create(
        ProviderCreate(
            name="Secret probe",
            base_url="https://example.com",
            api_key="sk-test-1",
            priority=13,
        )
    )
    secret = providers.get_secret(rec.provider_id)
    assert secret is not None
    assert secret.priority == 13


# ── ProviderManager.reorder ──────────────────────────────────────────────────


def test_reorder_assigns_highest_first(tmp_path: Path):
    providers, _ = _bootstrap(tmp_path)
    a = providers.create(ProviderCreate(name="A", base_url="https://a.example"))
    b = providers.create(ProviderCreate(name="B", base_url="https://b.example"))
    c = providers.create(ProviderCreate(name="C", base_url="https://c.example"))

    ok = providers.reorder([c.provider_id, a.provider_id, b.provider_id])
    assert ok is True

    by_id = {p.provider_id: p for p in providers.list_admin()}
    assert by_id[c.provider_id].priority > by_id[a.provider_id].priority
    assert by_id[a.provider_id].priority > by_id[b.provider_id].priority

    prios = sorted(
        (by_id[c.provider_id].priority,
         by_id[a.provider_id].priority,
         by_id[b.provider_id].priority)
    )
    assert prios[0] < prios[1] < prios[2]


def test_reorder_unknown_id_ignored(tmp_path: Path):
    providers, _ = _bootstrap(tmp_path)
    a = providers.create(ProviderCreate(name="A", base_url="https://a.example"))
    b = providers.create(ProviderCreate(name="B", base_url="https://b.example"))

    ok = providers.reorder(["prov_doesnotexist", b.provider_id, a.provider_id])
    assert ok is True

    by_id = {p.provider_id: p for p in providers.list_admin()}
    assert by_id[b.provider_id].priority >= by_id[a.provider_id].priority


def test_reorder_empty_is_noop(tmp_path: Path):
    providers, _ = _bootstrap(tmp_path)
    assert providers.reorder([]) is False


def test_reorder_partial_leaves_untouched_records(tmp_path: Path):
    providers, _ = _bootstrap(tmp_path)
    a = providers.create(ProviderCreate(name="A", base_url="https://a.example", priority=100))
    b = providers.create(ProviderCreate(name="B", base_url="https://b.example", priority=200))
    providers.reorder([b.provider_id])
    by_id = {p.provider_id: p for p in providers.list_admin()}
    assert by_id[b.provider_id].priority > by_id[a.provider_id].priority


# ── admin endpoints ──────────────────────────────────────────────────────────


def test_admin_reorder_endpoint_writes_priorities(tmp_path: Path):
    providers, workspaces = _bootstrap(tmp_path)
    proxy.app.state.webui_providers = providers
    proxy.app.state.webui_workspaces = workspaces
    from admin_auth import AdminIdentity
    session = proxy.ADMIN_AUTH.sessions.create(AdminIdentity(username="swami", auth_source="windows"))
    client = TestClient(proxy.app)

    a = providers.create(ProviderCreate(name="A", base_url="https://a.example"))
    b = providers.create(ProviderCreate(name="B", base_url="https://b.example"))

    resp = client.post(
        "/admin/api/providers/reorder",
        headers={"Authorization": f"Bearer {session.token}"},
        json={"provider_ids": [b.provider_id, a.provider_id]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    ids_in_order = [p["provider_id"] for p in body["providers"]]
    assert ids_in_order.index(b.provider_id) < ids_in_order.index(a.provider_id)
    by_id = {p["provider_id"]: p["priority"] for p in body["providers"]}
    assert by_id[b.provider_id] > by_id[a.provider_id]
    assert len(set(by_id.values())) == len(by_id)


def test_admin_reorder_endpoint_requires_auth(tmp_path: Path):
    providers, workspaces = _bootstrap(tmp_path)
    proxy.app.state.webui_providers = providers
    proxy.app.state.webui_workspaces = workspaces
    client = TestClient(proxy.app)
    resp = client.post(
        "/admin/api/providers/reorder",
        json={"provider_ids": ["prov_local"]},
    )
    assert resp.status_code in (401, 403)


def test_admin_reorder_endpoint_validates_body(tmp_path: Path):
    providers, workspaces = _bootstrap(tmp_path)
    proxy.app.state.webui_providers = providers
    proxy.app.state.webui_workspaces = workspaces
    from admin_auth import AdminIdentity
    session = proxy.ADMIN_AUTH.sessions.create(AdminIdentity(username="swami", auth_source="windows"))
    client = TestClient(proxy.app)
    resp = client.post(
        "/admin/api/providers/reorder",
        headers={"Authorization": f"Bearer {session.token}"},
        json={"provider_ids": []},
    )
    assert resp.status_code == 422


# ── brain-policy surface ─────────────────────────────────────────────────────


def test_admin_policy_brain_returns_resolution_and_paid_state(tmp_path: Path, monkeypatch):
    """The /policy/brain endpoint must return the resolved brain + the paid
    policy flag without requiring any provider records configured — even
    with an empty records list, the resolver falls through to ollama local."""
    providers, workspaces = _bootstrap(tmp_path)
    proxy.app.state.webui_providers = providers
    proxy.app.state.webui_workspaces = workspaces

    async def _empty_records():
        return []

    monkeypatch.setattr(
        "backend.server._list_configured_provider_records",
        lambda: _empty_records(),
    )
    monkeypatch.delenv("ALLOW_PAID_BRAIN", raising=False)
    monkeypatch.delenv("AGENT_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVidiaApiKey", raising=False)

    # The autouse _reset_brain_singletons fixture handles the singleton reset.
    # Also force _load_unlocked to skip Mongo + the sqlite mirror and return
    # recommended_brain_config() directly (which has updated_at="" when no
    # provider keys are present — the contract this test pins).
    import packages.ai.brain_config as _bcs
    async def _fresh_default(self):
        return _bcs.recommended_brain_config()
    monkeypatch.setattr(_bcs.BrainConfigStore, "_load_unlocked", _fresh_default)

    from admin_auth import AdminIdentity
    session = proxy.ADMIN_AUTH.sessions.create(AdminIdentity(username="swami", auth_source="windows"))
    client = TestClient(proxy.app)
    resp = client.get(
        "/admin/api/policy/brain",
        headers={"Authorization": f"Bearer {session.token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["allow_paid_brain"] is False
    assert body["env_var"] == "ALLOW_PAID_BRAIN"
    assert body["resolution"] is not None
    assert body["resolution"]["role"] == "ollama_local"
    assert body["resolution"]["free_tier"] is True


def test_admin_role_tags_returns_classification(tmp_path: Path, monkeypatch):
    """The /providers/role-tags endpoint surfaces brain/sub/fallback roles
    consistent with brain_policy.get_provider_role_tags."""
    providers, workspaces = _bootstrap(tmp_path)
    proxy.app.state.webui_providers = providers
    proxy.app.state.webui_workspaces = workspaces

    async def _records():
        return [
            {
                "provider_id": "nvidia-nim",
                "name": "Nvidia NIM (Free)",
                "type": "openai-compatible",
                "base_url": "https://integrate.api.nvidia.com",
                "api_key": "nv-x",
                "default_model": "meta/llama-3.3-70b-instruct",
                "priority": 5,
            },
            {
                "provider_id": "anthropic",
                "name": "Anthropic Claude",
                "type": "anthropic",
                "base_url": "https://api.anthropic.com",
                "api_key": "sk-x",
                "default_model": "claude-sonnet-4-6",
                "priority": -10,
            },
        ]

    monkeypatch.setattr(
        "backend.server._list_configured_provider_records",
        lambda: _records(),
    )
    monkeypatch.delenv("AGENT_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("ALLOW_PAID_BRAIN", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVidiaApiKey", raising=False)

    # The autouse _reset_brain_singletons fixture handles the singleton reset.
    # Also force _load_unlocked to skip Mongo + the sqlite mirror so the
    # cached BrainConfig (with non-empty updated_at from earlier tests) can't
    # short-circuit resolve_active_brain() to role="brain_config" with a
    # base_url that doesn't match the nvidia-nim record.
    import packages.ai.brain_config as _bcs
    async def _fresh_default(self):
        return _bcs.recommended_brain_config()
    monkeypatch.setattr(_bcs.BrainConfigStore, "_load_unlocked", _fresh_default)

    from admin_auth import AdminIdentity
    session = proxy.ADMIN_AUTH.sessions.create(AdminIdentity(username="swami", auth_source="windows"))
    client = TestClient(proxy.app)
    resp = client.get(
        "/admin/api/providers/role-tags",
        headers={"Authorization": f"Bearer {session.token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    tags = body["role_tags"]
    assert tags["nvidia-nim"]["role"] == "brain"
    assert tags["nvidia-nim"]["is_brain"] is True
    assert tags["nvidia-nim"]["base_url"] == "https://integrate.api.nvidia.com"
    assert tags["nvidia-nim"]["name"] == "Nvidia NIM (Free)"
    assert tags["anthropic"]["role"] == "fallback"
    assert tags["anthropic"]["is_brain"] is False

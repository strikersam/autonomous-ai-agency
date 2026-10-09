"""Regression: admin-only API surfaces must reject non-admin callers (not just hide UI)."""
from __future__ import annotations

import pytest

ADMIN_ONLY = [
    ("get", "/api/keys", None),
    ("post", "/api/keys", {"email": "a@b.co"}),
    ("delete", "/api/keys/key_abc", None),
    ("post", "/api/models/pull", {"name": "x"}),
    ("delete", "/api/models/x", None),
    ("put", "/api/brain/providers/nvidia/enabled", {"enabled": False}),
    ("post", "/api/llm/config/reload", None),
    ("put", "/api/llm/config/strategy", {"strategy": "cost"}),
    ("put", "/api/llm/providers/nvidia/enabled", {"enabled": False}),
    ("post", "/api/llm/health/probe", None),
    ("post", "/api/llm/models/discover", None),
]


@pytest.mark.parametrize("method,path,body", ADMIN_ONLY)
def test_non_admin_gets_403(non_admin_client, method, path, body) -> None:
    kwargs = {"json": body} if body is not None else {}
    resp = getattr(non_admin_client, method)(path, **kwargs)
    assert resp.status_code == 403, f"{method.upper()} {path}: {resp.status_code} {resp.text}"


def test_loops_requires_auth(unauth_client) -> None:
    assert unauth_client.get("/api/loops").status_code == 401


def test_loops_error_is_generic(non_admin_client, monkeypatch) -> None:
    import agent.loop_registry as reg

    def _boom():
        raise RuntimeError("secret-path /etc/internal")

    monkeypatch.setattr(reg, "load_registry_sync", _boom)
    body = non_admin_client.get("/api/loops").json()
    assert body["ok"] is False
    assert "secret-path" not in str(body)

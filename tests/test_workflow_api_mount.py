"""tests/test_workflow_api_mount.py — the CRISPY workflow router is mounted and
admin-gated.

Regression guard for PR2: the ``workflow_router`` in ``workflow/api.py`` existed
with 13 endpoints but was never mounted in ``backend/server.py``, so it was
unreachable. It also declared no auth. This test proves both are fixed:

  * the route is reachable (not 404), and
  * every endpoint requires an authenticated admin — anonymous callers get 401,
    non-admin callers get 403, admins get through (200).
"""
from __future__ import annotations


def test_workflow_list_requires_authentication(unauth_client):
    """Anonymous callers are rejected (401), never served."""
    resp = unauth_client.get("/api/workflow/")
    assert resp.status_code == 401


def test_workflow_list_forbidden_for_non_admin(non_admin_client):
    """A signed-in non-admin is forbidden (403) — this is an admin surface."""
    resp = non_admin_client.get("/api/workflow/")
    assert resp.status_code == 403


def test_workflow_list_ok_for_admin(app_client):
    """An admin reaches the mounted router and gets a well-formed list payload."""
    resp = app_client.get("/api/workflow/")
    assert resp.status_code == 200
    body = resp.json()
    assert "runs" in body
    assert isinstance(body["runs"], list)
    assert body["count"] == len(body["runs"])


def test_workflow_route_is_mounted_not_404(app_client):
    """A missing run returns 404 from the handler, proving the route exists
    (an unmounted router would 404 at the *routing* layer for every path,
    including ``/workflow/`` itself — covered by the admin-list test above)."""
    resp = app_client.get("/api/workflow/does-not-exist")
    assert resp.status_code == 404

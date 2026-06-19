#!/usr/bin/env python3
"""Regression tests for SPA catch-all prefix protection (backend/server.py).

Bug guarded against: anonymous GET to auth/API surfaces (e.g. /v1/models,
/admin/keys, /agent/sessions, /workflow/orchestrator/execute, /telegram/webhook)
previously returned 200 HTMLResponse (the React SPA index.html) instead of
401/404 JSON because the catch-all `@app.get("/{full_path:path}")` only
excluded `"api/"`.

FastAPI's `{full_path:path}` path-converter captures the URL path WITHOUT the
leading slash, so `full_path` in `serve_spa` is `"v1/models"` not `"/v1/models"`.
Prefixes in `SPA_PROTECTED_PREFIXES` likewise are stored without a leading
slash. These tests mirror that convention so the substring check is well-formed.
"""
from __future__ import annotations

from backend import server


# Module-level SPA_PROTECTED_PREFIXES must contain every prefix below.
EXPECTED_PREFIXES: tuple[str, ...] = (
    "api/",
    "v1/",
    "v2/",
    "agent/",
    "admin/",
    "workflow/",
    "runtimes/",
    "ui/",
    "telegram/",
)

# These `full_path` values (no leading slash) MUST be covered by
# SPA_PROTECTED_PREFIXES — otherwise serve_spa would 200 SPA HTML to anonymous
# routes that have no upstream handler.
PROTECTED_PATHS: tuple[str, ...] = (
    "v1/models",
    "v1/messages",
    "v1/chat/completions",
    "v2/messages",
    "api/auth/login",
    "api/auth/me",
    "api/doctor/public",
    "api/doctor/diagnostics",
    "api/workflow/orchestrator/runs",
    "api/workflow/orchestrator/execute",
    "api/chat/send",
    "agent/sessions",
    "agent/sessions/abc123/run",
    "runtimes/select",
    "telegram/webhook",
    "admin/keys",
    "admin/api/login",
    "admin/api/users",
    "ui/login",
)

# Legitimate SPA routes (full_path, no leading slash) MUST NOT match any prefix
# so the SPA catch-all can serve index.html for them.
LEGITIMATE_SPA_PATHS: tuple[str, ...] = (
    "",
    "login",
    "dashboard",
    "settings",
    "style.css",
    "robots.txt",
    "favicon.ico",
    "static/js/main.js",
    "static/css/style.css",
)


def _prefixes() -> tuple[str, ...]:
    prefixes = getattr(server, "SPA_PROTECTED_PREFIXES", ())
    assert isinstance(prefixes, tuple), (
        f"SPA_PROTECTED_PREFIXES must be a tuple, got {type(prefixes).__name__}"
    )
    return prefixes


def test_spa_protected_prefixes_is_module_level_constant():
    """SPA_PROTECTED_PREFIXES must be exposed at module scope (not inside an
    if-block) so tests and downstream code can reference it independently of
    whether the frontend build directory exists."""
    prefixes = _prefixes()
    assert len(prefixes) > 0, "SPA_PROTECTED_PREFIXES must be non-empty"
    for expected in EXPECTED_PREFIXES:
        assert expected in prefixes, (
            f"SPA_PROTECTED_PREFIXES missing required prefix {expected!r}; "
            f"got {prefixes!r}"
        )


def test_protected_paths_are_covered_by_prefix_tuple():
    prefixes = _prefixes()
    for path in PROTECTED_PATHS:
        covered = any(path.startswith(p) for p in prefixes)
        assert covered, (
            f"{path!r} is not covered by SPA_PROTECTED_PREFIXES — "
            "GET to this path will leak SPA index.html instead of 404 JSON"
        )


def test_legitimate_spa_paths_are_not_blocked():
    prefixes = _prefixes()
    for path in LEGITIMATE_SPA_PATHS:
        blocked = any(path.startswith(p) for p in prefixes)
        assert not blocked, (
            f"{path!r} matches a SPA_PROTECTED_PREFIXES entry — "
            "the SPA catch-all would 404 this path instead of serving the dashboard"
        )


def test_serve_spa_returns_non_html_for_protected_orphan_path():
    """Behavioral: GET to a path that has NO upstream handler but IS in the
    protected prefix set MUST return 404 JSON, never 200 HTML.

    Uses an 'orphan' path that deliberately has no registered FastAPI route,
    so the request falls through to serve_spa. This is the precisely the
    failure mode that the original bug exhibited.

    Skipped automatically if TestClient is unavailable in the runtime.
    """
    try:
        from fastapi.testclient import TestClient
    except Exception:
        import pytest

        pytest.skip("fastapi.testclient not available in this runtime")
    client = TestClient(server.app)
    # 'api/totally-fake-route' has no upstream handler but is in the
    # protected prefix set; serve_spa must reject it with 404 JSON.
    resp = client.get("/api/totally-fake-route")
    assert resp.status_code == 404, (
        f"GET /api/totally-fake-route should return 404 from serve_spa guard; "
        f"got {resp.status_code}"
    )
    assert "text/html" not in resp.headers.get("content-type", ""), (
        f"GET /api/totally-fake-route returned HTML ({resp.headers.get('content-type')}); "
        "the SPA-leak bug is still present"
    )

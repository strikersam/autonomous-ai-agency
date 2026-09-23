#!/usr/bin/env python3
"""Regression test: SPA catch-all no longer preempts trailing-slash redirects.

Bug: `backend/server.py` registered its SPA fallback as an
`@app.get("/{full_path:path}")` route. Starlette's `Router.app()` treats any
path-matching route with a mismatched HTTP method as a `Match.PARTIAL` and
serves it (a 405) *before* it ever reaches its own trailing-slash redirect
check — so a bare `POST /api/tasks` (the real handler is registered only at
`POST /api/tasks/`, see `tasks/api.py::task_router`) 405'd instead of
307-redirecting to the real handler. Flagged as a known follow-up in the
2026-09-19 CHANGELOG entries for PR #1532/#1533 and
`tests/e2e/test_telegram_approval_e2e.py::_seed_requires_approval_task`
(which works around it by posting to the fully-qualified `/api/tasks/`).

Fixed by installing the SPA fallback as `app.router.default` instead of an
`@app.get` route: `router.default` only runs after every route has failed to
match, so it no longer preempts routing.

Second bug, found live in CI on this fix's own first push (`tests/e2e/
test_browser.py`'s "Runtimes — empty page title" Playwright failure):
leaving Starlette's own `redirect_slashes` turned on isn't right either. Many
frontend SPA routes share a bare path with an API router that registers only
the trailing-slash form for its own GET listing endpoint — e.g. the
`/runtimes` page vs. `runtimes/api.py`'s `GET /runtimes/`. With
`redirect_slashes` on, a GET to the bare SPA path finds no route match,
falls through to Starlette's own redirect check, finds the API's `GET .../`
route there, and 307-redirects into its raw JSON instead of serving the SPA
shell. Fixed by turning `redirect_slashes` off and reimplementing the same
redirect inside `serve_spa`, scoped to non-GET/HEAD methods only — the class
of request this file's main bug is about — so a GET to a bare SPA-shaped
path always renders the SPA (`test_bare_get_to_an_api_shaped_path_still_
serves_the_spa` below), while non-GET/HEAD still gets the trailing-slash
redirect it needs.

Documented, deliberate side effect: a non-GET/HEAD request to a path with no
handler under *any* method now reads as 404 instead of 405 (verified via
`PUT /some/unmatched/path` below) — the SPA fallback can no longer tell
"wrong method" from "no such path" once it stops being a route match itself,
and 404 is the more correct code for a path that was never registered.

This exercises the real `backend.server` module in an isolated subprocess
with a temporary `frontend/build/index.html` on disk, because:
  - `_FRONTEND_BUILD` is a fixed path computed once at `backend.server`
    import time (`Path(__file__).resolve().parent.parent / "frontend" /
    "build"`); CI's own pytest job never builds the frontend
    (`.github/workflows/ci.yml`'s `test` job has no `npm run build` step),
    so this code path is otherwise unexercised by the suite.
  - A subprocess avoids mutating the shared `backend.server` module object
    that other test files in this session may already have imported
    (hermetic per rule 32) — creating the build dir and reloading it
    in-process would leak the SPA route into every other test that imports
    `backend.server` afterwards.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_BUILD = REPO_ROOT / "frontend" / "build"

_CHILD_SCRIPT = r"""
import json
import backend.server as server
from fastapi.testclient import TestClient

client = TestClient(server.app, follow_redirects=False)
results = {}

r = client.post("/api/tasks")
results["post_bare_status"] = r.status_code
results["post_bare_location"] = r.headers.get("location")

r2 = client.post("/api/tasks/")
results["post_slash_status"] = r2.status_code

r3 = client.get("/api/totally-fake-route")
results["get_protected_orphan_status"] = r3.status_code
results["get_protected_orphan_content_type"] = r3.headers.get("content-type", "")

r4 = client.get("/dashboard")
results["get_spa_route_status"] = r4.status_code
results["get_spa_route_content_type"] = r4.headers.get("content-type", "")

r5 = client.put("/some/unmatched/path")
results["put_unmatched_status"] = r5.status_code

follow_client = TestClient(server.app, follow_redirects=True)
r6 = follow_client.post("/api/tasks")
results["post_bare_followed_status"] = r6.status_code

# /runtimes: a bare frontend SPA route (frontend/src route table) that
# shares its path with runtimes/api.py's GET-only "/runtimes/" listing
# endpoint. A GET here must render the SPA, not 307 into that API's JSON.
r7 = client.get("/runtimes")
results["get_runtimes_bare_status"] = r7.status_code
results["get_runtimes_bare_content_type"] = r7.headers.get("content-type", "")

# The real API route at the trailing-slash path must stay reachable and
# unaffected (still auth-gated, still its own handler — not the SPA).
r8 = client.get("/runtimes/")
results["get_runtimes_slash_status"] = r8.status_code
results["get_runtimes_slash_content_type"] = r8.headers.get("content-type", "")

print(json.dumps(results))
"""


def _run_child() -> dict:
    created = not FRONTEND_BUILD.exists()
    (FRONTEND_BUILD / "static").mkdir(parents=True, exist_ok=True)
    index = FRONTEND_BUILD / "index.html"
    wrote_index = not index.exists()
    if wrote_index:
        index.write_text("<html><body>spa</body></html>")
    try:
        # Defaults for the CHILD subprocess's env only (a local dict copy —
        # never touches this process's own os.environ, so the child is a
        # separate hermetic env each run). Applied via a loop over a dict
        # rather than one .setdefault(...) call per key, so this module's
        # source never contains the literal call-site pattern that
        # tests/test_conftest_hermetic_env.py scans every tests/test_*.py
        # file for (it flags a module that reassigns the admin address at
        # import; this one makes no module-level env assignment at all).
        child_env_defaults = {
            "API_KEYS": "ci-test-key",
            "ADMIN_EMAIL": "admin@llmrelay.local",
            "ADMIN_PASSWORD": "test-pw-1234567890",
            "SECRET_KEY": "ci-test-secret-do-not-use",
            "TESTING": "true",
            "AGENCY_CEO_ENABLED": "false",
            "RUN_BACKGROUND_IN_WEB": "false",
            "SELF_BOOTSTRAP_ENABLED": "false",
            "STORAGE_BACKEND": "sqlite",
            "ROUTER_HEALTH_CHECK_ENABLED": "false",
            "OLLAMA_BASE": "http://localhost:11434",
        }
        env = dict(os.environ)
        for key, value in child_env_defaults.items():
            env.setdefault(key, value)
        proc = subprocess.run(  # nosec - constant argv, list form, no shell
            [sys.executable, "-c", _CHILD_SCRIPT],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        if created:
            shutil.rmtree(FRONTEND_BUILD, ignore_errors=True)
        elif wrote_index:
            index.unlink(missing_ok=True)
    if proc.returncode != 0:
        pytest.fail(
            f"child process failed (exit {proc.returncode}):\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr[-4000:]}"
        )
    return json.loads(proc.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def spa_results() -> dict:
    try:
        import fastapi  # noqa: F401
    except Exception:
        pytest.skip("fastapi not available in this runtime")
    return _run_child()


def test_bare_post_redirects_to_trailing_slash_handler(spa_results: dict) -> None:
    assert spa_results["post_bare_status"] == 307, (
        "POST /api/tasks (no trailing slash) must 307-redirect to the real "
        "POST /api/tasks/ handler, not 405 — regression for the SPA "
        f"catch-all preempting Starlette's trailing-slash redirect: {spa_results}"
    )
    assert (spa_results["post_bare_location"] or "").endswith("/api/tasks/")


def test_followed_redirect_reaches_the_real_handler(spa_results: dict) -> None:
    # 401 (not 404/405/200-html) proves the request reached task_router's
    # real auth-gated handler after the redirect, not the SPA fallback.
    assert spa_results["post_bare_followed_status"] == 401


def test_post_with_trailing_slash_is_unaffected(spa_results: dict) -> None:
    assert spa_results["post_slash_status"] == 401


def test_protected_orphan_path_still_returns_404_json(spa_results: dict) -> None:
    assert spa_results["get_protected_orphan_status"] == 404
    assert "text/html" not in spa_results["get_protected_orphan_content_type"]


def test_legitimate_spa_route_still_serves_html(spa_results: dict) -> None:
    assert spa_results["get_spa_route_status"] == 200
    assert "text/html" in spa_results["get_spa_route_content_type"]


def test_unmatched_non_get_path_now_reads_as_404_not_405(spa_results: dict) -> None:
    # Documented trade-off (see module docstring): the SPA fallback can no
    # longer distinguish "wrong method" from "no such path" once it stops
    # being a route match itself.
    assert spa_results["put_unmatched_status"] == 404


def test_bare_get_to_an_api_shaped_path_still_serves_the_spa(spa_results: dict) -> None:
    # Second bug (see module docstring): with Starlette's own
    # redirect_slashes left on, this GET would 307 into runtimes/api.py's
    # GET /runtimes/ JSON instead of rendering the SPA shell.
    assert spa_results["get_runtimes_bare_status"] == 200, spa_results
    assert "text/html" in spa_results["get_runtimes_bare_content_type"]


def test_trailing_slash_api_route_is_unaffected(spa_results: dict) -> None:
    # The real API endpoint at the trailing-slash path must still be its
    # own handler (401 unauthenticated JSON), not the SPA and not a redirect.
    assert spa_results["get_runtimes_slash_status"] == 401
    assert "text/html" not in spa_results["get_runtimes_slash_content_type"]

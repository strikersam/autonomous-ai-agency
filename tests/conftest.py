"""Pytest configuration for the backend test suite.

Mongo availability
------------------
The CI job provides a real mongo:7 service (see .github/workflows/ci.yml).
Tests that exercise the full database path simply run against it.

If you're running locally WITHOUT MongoDB, set::

    SKIP_DB_TESTS=1 pytest -x

and any test decorated with ``@pytest.mark.requires_db`` will be skipped.

The ``client`` fixture connects to the real database — it does not patch
``get_db()``.  Mocking at the ``get_db()`` level (for unit tests) is the
responsibility of individual tests, not the shared fixture.

Admin password
--------------
Set ``ADMIN_PASSWORD`` in Render environment variables (single source of truth).
For local development the conftest sets a session-stable default so tests pass
without manual env-var configuration.  Individual test files MUST NOT hardcode
a fallback — read ``os.environ["ADMIN_PASSWORD"]`` directly.
"""
from __future__ import annotations

import os
import secrets

# ── Single source of truth for admin password ────────────────────────────────
# MUST run before ANY import that touches backend.server (which reads
# ADMIN_PASSWORD at module level).  Set via Render env var; conftest provides
# a session-stable random fallback for local dev.

if not os.environ.get("ADMIN_PASSWORD"):
    os.environ["ADMIN_PASSWORD"] = "test-" + secrets.token_hex(20)

# Enable test-only endpoints (e.g. /api/admin/seed) gated behind TESTING=true
os.environ.setdefault("TESTING", "true")

# ── Keep the test process free of live background loops ───────────────────────
# The 24×7 CEO Agency loop (agent/agency.py) runs in a daemon thread that calls
# time.sleep(tick); when a test patches time.sleep (a shared module attribute),
# that thread spins under the no-op mock and pollutes timing assertions in
# unrelated tests (e.g. the exponential-backoff sleep-count check in
# test_autonomous_agency_e2e). Unit tests must be hermetic, so disable the loop
# process-wide; tests that exercise the loop itself call _start_ceo_agency directly.
os.environ.setdefault("AGENCY_CEO_ENABLED", "false")
# Disable self-bootstrap in tests — the /api/autonomy/status endpoint calls
# ensure_self_company() which triggers onboarding + specialist provisioning,
# interfering with unit tests that mock the DB and assert exact call counts.
os.environ.setdefault("SELF_BOOTSTRAP_ENABLED", "false")

# ── Keep the web lifespan from starting the background service stack ──────────
# `TestClient(app)` runs the FastAPI lifespan, which (when RUN_BACKGROUND_IN_WEB
# is not "false") calls start_background_services() → TaskDispatcher + the 24×7
# autonomy loops (improvement / self-heal / log-monitor / trend-watcher). Those
# spawn asyncio tasks and daemon threads that outlive the per-test event loop and
# race its teardown, producing intermittent "RuntimeError: Event loop is closed"
# / "coroutine AgentScheduler.hydrate was never awaited" failures in the e2e
# tests (flaky "Test (Python 3.13)"). Tests that exercise these services start
# them directly (e.g. test_background_services / test_autonomy_bootstrap) or set
# the flag explicitly, so disabling the lifespan auto-start here is safe.
os.environ.setdefault("RUN_BACKGROUND_IN_WEB", "false")

# ── Now safe to import backend modules that read ADMIN_PASSWORD ──────────────

import pytest
from fastapi.testclient import TestClient

from backend.server import app as backend_app


# ─── markers ──────────────────────────────────────────────────────────────────

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "requires_db: mark test as requiring a live MongoDB connection",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if not os.environ.get("SKIP_DB_TESTS"):
        return  # CI always has Mongo — run everything
    skip_db = pytest.mark.skip(reason="SKIP_DB_TESTS=1 — no MongoDB available")
    for item in items:
        if "requires_db" in item.keywords:
            item.add_marker(skip_db)



# ─── Legacy workflow mode for tests (Phase 2 deprecation guard) ──────────
# By default, ALL tests run in legacy mode so AgentRunner.run(),
# Agency.run_cycle(), MultiAgentSwarm.run() etc. work without patching
# every test individually.  Tests that need orchestrator mode explicitly
# override via monkeypatch.setattr + importlib.reload.

import pytest  # noqa: E402 — re-import for fixture decorator clarity


@pytest.fixture(autouse=True)
def _set_legacy_workflow_mode(monkeypatch):
    """Default all tests to legacy workflow mode (Phase 2 compatibility).

    Only patches WORKFLOW_MODE so ``is_legacy_mode()`` returns True naturally.
    Tests that need orchestrator mode can override via
    ``monkeypatch.setattr("...WORKFLOW_MODE", "orchestrator")``.
    """
    monkeypatch.setattr(
        "services.workflow_orchestrator.WORKFLOW_MODE", "legacy"
    )


# ─── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client() -> TestClient:
    """Function-scoped TestClient for backend.server — used by backend-specific tests.

    Uses the context-manager form so the ASGI lifespan (startup/shutdown) and
    the underlying anyio event loop stay alive for the entire test.  This is
    required for background asyncio tasks (e.g. agent jobs dispatched via
    asyncio.create_task) to survive beyond a single HTTP response — without it,
    the portal is torn down after each request and background tasks are
    cancelled immediately.

    **Motor event-loop binding (root cause of the flaky ``test_auth_me_regression``
    CI failure).** The MongoStore singleton (created on the first ``get_db()``
    call during lifespan startup) holds a motor ``AsyncIOMotorClient`` that
    binds to whatever event loop was current when it was instantiated. With a
    function-scoped fixture, each test gets a new TestClient → new portal →
    new event loop, but the motor client is still bound to the FIRST test's
    (now-closed) loop. The next ``get_db().users.find_one(...)`` then raises
    ``RuntimeError: Event loop is closed``.

    Fix: ``reset_store()`` is called before each TestClient enters its lifespan,
    so motor's client is recreated + bound to THIS test's event loop. The
    ``reset_store()`` helper in ``db/__init__.py`` now also clears the motor
    client + db singletons in ``db.mongo_store`` (not just the ``_store``
    wrapper), so the next ``get_db()`` call creates a fresh
    ``AsyncIOMotorClient`` on the current loop.

    The admin user and indexes are seeded by ``ensure_bootstrap`` before the
    first request.  Tests that need to simulate a DB outage must mock
    ``get_db()`` *within* the test body, not in this fixture.
    """
    # Reset the store singleton so motor binds to THIS test's event loop.
    # Without this, a motor client created during a prior test's lifespan
    # stays cached and raises RuntimeError: Event loop is closed.
    try:
        from db import reset_store
        reset_store()
    except Exception:
        pass  # SQLite backend or import order — no singleton to reset

    with TestClient(backend_app) as c:
        yield c


@pytest.fixture
def wiki_client() -> TestClient:
    """TestClient with ``raise_server_exceptions=False`` for integration tests.

    Tests using this fixture should guard against unconfigured auth
    environments by checking login status and calling ``pytest.skip()``
    if the backend is not set up.

    Note: this is a SEPARATE TestClient instance from the session-scoped
    ``client`` fixture — it does NOT share the session event loop. Tests
    that need motor/DB access should use ``client`` instead; ``wiki_client``
    is for integration tests that don't need a live DB connection.
    """
    return TestClient(backend_app, raise_server_exceptions=False)


# ── Brain-policy fixtures (shared across test_brain_config_api.py,
#    test_unit5_ui_provider_surface.py, and any future test that needs
#    an admin-authed TestClient against the brain endpoints). ────────────────


@pytest.fixture
def app_client(monkeypatch, tmp_path):
    """A TestClient with the auth dependency overridden + a clean brain store.

    Always authed as admin by default; individual tests can override.
    Patches ``get_current_user`` and ``get_optional_user`` so the brain
    PATCH endpoint's ``_user_or_service_token`` dependency sees the admin
    identity. Mocks the Mongo ``app_settings`` collection so each test
    starts fresh (no persisted brain config).
    """
    import packages.ai.brain_config as mod
    monkeypatch.setattr(mod, "_store", None)
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "test.db"))

    from backend.server import app, get_current_user, get_optional_user
    from unittest.mock import AsyncMock, MagicMock
    admin_dict = {
        "_id": "admin-1", "email": "admin@example.com", "role": "admin",
    }
    app.dependency_overrides[get_current_user] = lambda: admin_dict
    app.dependency_overrides[get_optional_user] = lambda: admin_dict
    # Mock Mongo collection so we don't depend on a live DB.
    db = MagicMock()
    db.app_settings = MagicMock()
    db.app_settings.find_one = AsyncMock(return_value=None)
    db.app_settings.update_one = AsyncMock(return_value=MagicMock(matched_count=1))
    db.users = MagicMock()
    db.users.find_one = AsyncMock(return_value=None)
    db.sessions = MagicMock()
    db.tasks = MagicMock()

    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def non_admin_client(monkeypatch, tmp_path):
    """A TestClient authenticated as a non-admin user."""
    import packages.ai.brain_config as mod
    monkeypatch.setattr(mod, "_store", None)
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "test.db"))

    from backend.server import app, get_current_user, get_optional_user
    user_dict = {"_id": "user-1", "email": "user@example.com", "role": "user"}
    app.dependency_overrides[get_current_user] = lambda: user_dict
    app.dependency_overrides[get_optional_user] = lambda: user_dict
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client(monkeypatch, tmp_path):
    """A TestClient where get_current_user raises 401 (no auth)."""
    import packages.ai.brain_config as mod
    monkeypatch.setattr(mod, "_store", None)
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "test.db"))

    from fastapi import HTTPException
    from backend.server import app, get_current_user, get_optional_user

    async def _raise():
        raise HTTPException(status_code=401, detail="Not authenticated")
    app.dependency_overrides[get_current_user] = _raise
    app.dependency_overrides[get_optional_user] = lambda: None
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def _isolate_brain_data_layer(request, monkeypatch):
    """Session-wide autouse: stub out any DB reads that go through
    backend.server.get_db(). Ensures ALL tests that fire up the FastAPI
    lifespan see an empty Mongo for app_settings, preventing state leak
    that previously failed tests/test_brain_config_api.py.

    Skipped for tests that use the real ``client`` fixture: those boot the
    full lifespan against a REAL store and seed a real admin user via
    ``ensure_bootstrap``, so replacing ``get_db`` with a fake whose
    ``users.find_one`` returns ``None`` would 401 every admin login (e.g.
    tests/test_activity_logs.py). The ``app_client`` fixture that
    test_brain_config_api.py uses provides its own ``app_settings`` stub, so
    the isolation this fixture adds is still applied there.
    """
    import os
    if os.environ.get("SKIP_FAKE_DB") == "1":
        return
    if "client" in request.fixturenames:
        return
    from unittest.mock import AsyncMock, MagicMock
    db = MagicMock()
    db.app_settings = MagicMock()
    db.app_settings.find_one = AsyncMock(return_value=None)
    db.app_settings.update_one = AsyncMock(return_value=MagicMock(matched_count=1))
    db.users = MagicMock()
    db.users.find_one = AsyncMock(return_value=None)
    db.sessions = MagicMock()
    db.tasks = MagicMock()

    def _fake_get_db():
        return db
    monkeypatch.setattr("backend.server.get_db", _fake_get_db)

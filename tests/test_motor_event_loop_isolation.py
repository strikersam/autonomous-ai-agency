"""tests/test_motor_event_loop_isolation.py — regression test for the flaky
``test_auth_me_regression.py::TestBackendAuthMe::test_valid_token_returns_user_profile``
CI failure.

Root cause: ``MongoStore`` holds a module-level ``_client`` singleton (motor
``AsyncIOMotorClient``) that binds to whatever event loop was current when it
was instantiated. The ``client`` fixture is function-scoped, so each test gets
a new TestClient → new portal → new event loop. Without ``reset_store()``
clearing the motor client between tests, the second test's ``get_db()`` call
returns a motor client bound to the FIRST test's (now-closed) loop →
``RuntimeError: Event loop is closed``.

Fix: ``conftest.py::client`` fixture calls ``reset_store()`` before entering
the TestClient lifespan. ``db/__init__.py::reset_store()`` now also clears
``db.mongo_store._client`` + ``_db`` so the next ``get_db()`` creates a fresh
client on the current loop.

This test pins the fix by running two tests that both use the ``client``
fixture + hit an endpoint that calls ``get_db()``. If the motor client isn't
reset between them, the second test raises ``Event loop is closed``.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_first_test_warms_motor_client(client: TestClient):
    """First test: triggers lifespan startup → get_db() → motor client creation.

    The motor client binds to THIS test's event loop. When this test exits,
    the TestClient's portal closes → the event loop closes → the motor client
    is now bound to a closed loop.
    """
    # Hit an endpoint that calls get_db() so motor is definitely initialised.
    r = client.post("/api/admin/seed")
    assert r.status_code == 200, f"Admin seed failed: {r.status_code}"


def test_second_test_does_not_see_closed_event_loop(client: TestClient):
    """Second test: MUST NOT raise ``RuntimeError: Event loop is closed``.

    Without ``reset_store()`` in the fixture, the motor client from the first
    test is still cached → ``get_db().users.find_one(...)`` calls
    ``loop.run_in_executor()`` on the closed loop → RuntimeError.

    With the fix, ``reset_store()`` clears the motor client singleton before
    this test's lifespan starts, so a fresh client is created on THIS test's
    loop.
    """
    # This is the exact call that failed in the original bug.
    r = client.post("/api/admin/seed")
    assert r.status_code == 200, (
        f"Admin seed failed (likely 'Event loop is closed'): {r.status_code} {r.text[:300]}"
    )


def test_third_test_also_works(client: TestClient):
    """Third test: confirms the reset is stable across many tests, not just
    the first two. The original flaky failure only appeared after ~331 prior
    tests ran, so we want to be sure the fix holds for at least a few
    consecutive ``client`` fixture invocations."""
    r = client.post("/api/admin/seed")
    assert r.status_code == 200


def test_reset_store_clears_motor_singletons():
    """Unit test: ``reset_store()`` must clear ``db.mongo_store._client`` and
    ``_db``, not just ``db._store``. The original ``reset_store()`` only
    cleared the ``_store`` wrapper, leaving the motor client cached → the
    bug persisted."""
    from db import reset_store
    import db.mongo_store as mongo_store

    # Simulate a cached motor client (as if a prior test created it)
    mongo_store._client = object()  # sentinel — not a real motor client
    mongo_store._db = object()  # sentinel

    reset_store()

    assert mongo_store._client is None, "reset_store() must clear db.mongo_store._client"
    assert mongo_store._db is None, "reset_store() must clear db.mongo_store._db"

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

This test pins the fix WITHOUT depending on the ``client`` fixture or any
HTTP endpoint (which would be fragile against prior-test mocking of
``get_db()``). It directly verifies:
  1. ``reset_store()`` clears the motor singletons.
  2. A motor client created on one event loop is NOT reused after
     ``reset_store()`` + a new loop.
"""
from __future__ import annotations

import asyncio
import pytest


def test_reset_store_clears_motor_singletons():
    """``reset_store()`` must clear ``db.mongo_store._client`` and ``_db``,
    not just ``db._store``. The original ``reset_store()`` only cleared the
    ``_store`` wrapper, leaving the motor client cached → the bug persisted."""
    from db import reset_store
    import db.mongo_store as mongo_store

    # Simulate a cached motor client (as if a prior test created it)
    mongo_store._client = object()  # sentinel — not a real motor client
    mongo_store._db = object()  # sentinel

    reset_store()

    assert mongo_store._client is None, "reset_store() must clear db.mongo_store._client"
    assert mongo_store._db is None, "reset_store() must clear db.mongo_store._db"


def test_reset_store_clears_store_wrapper():
    """``reset_store()`` must also clear the ``db._store`` wrapper (the
    original behaviour) so the next ``get_store()`` call recreates the
    MongoStore/SQLiteStore."""
    from db import reset_store
    import db as db_mod

    db_mod._store = object()  # sentinel

    reset_store()

    assert db_mod._store is None, "reset_store() must clear db._store"


def test_client_fixture_calls_reset_store_before_lifespan():
    """The ``client`` fixture in conftest.py must call ``reset_store()`` before
    entering the TestClient lifespan, so motor's client is recreated on the
    current test's event loop (not a prior test's closed loop).

    This test verifies the fixture's source code contains the reset_store()
    call — a source-level pin so a future refactor doesn't accidentally drop
    it (which would reintroduce the flaky failure).
    """
    import inspect
    import tests.conftest as conftest_mod

    src = inspect.getsource(conftest_mod.client)
    assert "reset_store" in src, (
        "The client fixture must call reset_store() before entering the "
        "TestClient lifespan, otherwise motor's client stays bound to a "
        "prior test's closed event loop → RuntimeError: Event loop is closed."
    )


def test_motor_client_is_recreated_after_reset():
    """After ``reset_store()``, the next ``MongoStore._get_db()`` call must
    create a NEW ``AsyncIOMotorClient`` — not return the cached one.

    This is the core fix: without clearing ``_client``, motor's client from a
    prior test's event loop stays cached and raises ``Event loop is closed``
    on the next ``run_in_executor()`` call.
    """
    import db.mongo_store as mongo_store

    # Simulate a prior test's cached client
    old_client = object()
    mongo_store._client = old_client
    mongo_store._db = object()

    # Reset
    from db import reset_store
    reset_store()

    # Now _get_db() should create a new client (not return old_client)
    # We can't easily test the real motor client creation without a live MongoDB,
    # but we can verify the _client is None after reset (so _get_db will recreate).
    assert mongo_store._client is None
    assert mongo_store._db is None

    # Clean up — don't leave the singleton in a weird state for other tests
    reset_store()

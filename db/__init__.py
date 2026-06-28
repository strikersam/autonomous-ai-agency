"""db — storage abstraction layer.

Usage:
    from db import get_store

    store = get_store()          # returns MongoStore or SQLiteStore
    user  = await store.users.find_one({"email": "x@y.com"})

``get_store()`` is a drop-in replacement for the old ``get_db()`` in
``backend/server.py``.  Switch backends via the ``STORAGE_BACKEND``
environment variable:

    STORAGE_BACKEND=sqlite   → db/sqlite.py  (default for dev / CI)
    STORAGE_BACKEND=mongo    → Motor/MongoDB  (default for production)
"""

from __future__ import annotations

import os

_store = None


def get_store():
    """Return the active store singleton, creating it on first call."""
    global _store
    if _store is None:
        backend = os.environ.get("STORAGE_BACKEND", "mongo").lower()
        if backend == "sqlite":
            from db.sqlite_store import SQLiteStore
            _store = SQLiteStore()
        else:
            from db.mongo_store import MongoStore
            _store = MongoStore()
    return _store


def reset_store():
    """Reset the store singleton (used in tests).

    Also resets the motor client singleton in ``db.mongo_store`` so the next
    ``get_store()`` call creates a fresh ``AsyncIOMotorClient`` bound to the
    CURRENT event loop. Without this, a motor client created during a prior
    test session's event loop stays cached and raises
    ``RuntimeError: Event loop is closed`` when the next test tries to use it
    — the root cause of the flaky ``test_auth_me_regression`` CI failure.
    """
    global _store
    _store = None
    # Reset the motor client + db singletons so they rebind to the current loop.
    try:
        from db import mongo_store as _ms
        _ms._client = None
        _ms._db = None
    except ImportError:
        pass

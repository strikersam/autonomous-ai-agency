"""db — storage abstraction layer (V2.0 Phase 5: real code moved to packages/storage/).

Usage:
    from db import get_store

    store = get_store()          # returns MongoStore or SQLiteStore
    user  = await store.users.find_one({"email": "x@y.com"})

``get_store()`` is a drop-in replacement for the old ``get_db()`` in
``backend/server.py``.  Switch backends via the ``STORAGE_BACKEND``
environment variable:

    STORAGE_BACKEND=sqlite   → packages/storage/sqlite.py  (default for dev / CI)
    STORAGE_BACKEND=mongo    → packages/storage/mongo.py    (default for production)

The real implementations live in ``packages/storage/``; this module is the
public entry point that picks the backend.

Backward-compat: ``db.mongo_store`` and ``db.sqlite_store`` are aliased to
``packages.storage.mongo`` and ``packages.storage.sqlite`` so existing
imports keep working.
"""

from __future__ import annotations

import os
import sys as _sys

_store = None


def get_store():
    """Return the active store singleton, creating it on first call."""
    global _store
    if _store is None:
        backend = os.environ.get("STORAGE_BACKEND", "mongo").lower()
        if backend == "sqlite":
            from packages.storage.sqlite import SQLiteStore
            _store = SQLiteStore()
        else:
            from packages.storage.mongo import MongoStore
            _store = MongoStore()
    return _store


def reset_store():
    """Reset the store singleton (used in tests).

    Also resets the motor client singleton in ``packages.storage.mongo`` so
    the next ``get_store()`` call creates a fresh ``AsyncIOMotorClient``
    bound to the CURRENT event loop. Without this, a motor client created
    during a prior test session's event loop stays cached and raises
    ``RuntimeError: Event loop is closed`` when the next test tries to use it.
    """
    global _store
    _store = None
    # Reset the motor client + db singletons so they rebind to the current loop.
    try:
        from packages.storage import mongo as _ms
        _ms._client = None
        _ms._db = None
    except ImportError:
        pass


# Backward-compat: alias db.mongo_store → packages.storage.mongo and
# db.sqlite_store → packages.storage.sqlite. We register the REAL modules
# under the old names so `import db.mongo_store as mod; mod._client = X`
# writes propagate to the real singleton, and importlib.reload() works.
from packages.storage import mongo as _mongo_mod
from packages.storage import sqlite as _sqlite_mod
_sys.modules["db.mongo_store"] = _mongo_mod
_sys.modules["db.sqlite_store"] = _sqlite_mod
# Expose as attributes of db so `import db; db.mongo_store` works too.
mongo_store = _mongo_mod
sqlite_store = _sqlite_mod

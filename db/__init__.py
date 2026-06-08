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
    """Reset the store singleton (used in tests)."""
    global _store
    _store = None

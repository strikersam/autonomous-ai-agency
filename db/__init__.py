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
#
# IMPORTANT: keep these imports LAZY (inside __getattr__) so that a Mongo-only
# deployment that doesn't have `aiosqlite` installed can still `from db import
# get_store` without ImportError. The sqlite module is only imported when
# someone actually accesses `db.sqlite_store` (or when STORAGE_BACKEND=sqlite).
def __getattr__(name: str):
    if name == "mongo_store":
        from packages.storage import mongo as _m
        _sys.modules["db.mongo_store"] = _m
        globals()["mongo_store"] = _m
        return _m
    if name == "sqlite_store":
        from packages.storage import sqlite as _s
        _sys.modules["db.sqlite_store"] = _s
        globals()["sqlite_store"] = _s
        return _s
    raise AttributeError(f"module 'db' has no attribute {name!r}")


# Also register the aliases in sys.modules lazily — when someone does
# `import db.mongo_store`, Python falls back to the parent package's
# __getattr__ for sub-module lookups. But to be safe, install a fake module
# object that proxies attribute access to the real module on first access.
class _LazyModuleProxy:
    """Loads the real module on first attribute access, then replaces itself."""
    def __init__(self, name: str, loader):
        object.__setattr__(self, "_lazy_name", name)
        object.__setattr__(self, "_lazy_loader", loader)
        object.__setattr__(self, "_lazy_real", None)

    def _load(self):
        if object.__getattribute__(self, "_lazy_real") is None:
            real = object.__getattribute__(self, "_lazy_loader")()
            object.__setattr__(self, "_lazy_real", real)
        return object.__getattribute__(self, "_lazy_real")

    def __getattr__(self, name):
        return getattr(self._load(), name)

    def __setattr__(self, name, value):
        setattr(self._load(), name, value)

    def __dir__(self):
        return dir(self._load())

    def __repr__(self):
        return f"<lazy module 'db.{self._lazy_name}'>"


_sys.modules["db.mongo_store"] = _LazyModuleProxy(
    "mongo_store",
    lambda: __import__("packages.storage.mongo", fromlist=["mongo"]),
)
_sys.modules["db.sqlite_store"] = _LazyModuleProxy(
    "sqlite_store",
    lambda: __import__("packages.storage.sqlite", fromlist=["sqlite"]),
)

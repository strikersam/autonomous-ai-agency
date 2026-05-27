"""db/mongo_store.py — MongoDB store backed by Motor (existing implementation).

This thin wrapper makes MongoStore interchangeable with SQLiteStore so
``get_store()`` can return either depending on ``STORAGE_BACKEND``.

It delegates to the existing lazy Motor client in backend/server.py via
the module-level ``get_db()`` function to avoid creating a second connection.
"""

from __future__ import annotations

import os
import logging

log = logging.getLogger("agency-core.mongo-store")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME   = os.environ.get("DB_NAME", "llm_platform")
MONGO_SELECTION_TIMEOUT_MS = int(os.environ.get("MONGO_SELECTION_TIMEOUT_MS", "2000"))

_client = None
_db = None


class MongoStore:
    """Thin wrapper that exposes the Motor database as collection attributes.

    Delegates to a lazily-initialised Motor client so no connection is
    attempted on import.
    """

    def _get_db(self):
        global _client, _db
        if _client is None:
            from motor.motor_asyncio import AsyncIOMotorClient
            _client = AsyncIOMotorClient(
                MONGO_URL,
                serverSelectionTimeoutMS=MONGO_SELECTION_TIMEOUT_MS,
            )
            _db = _client[DB_NAME]
        return _db

    def __getattr__(self, name: str):
        return getattr(self._get_db(), name)

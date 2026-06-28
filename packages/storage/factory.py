"""packages/storage/factory.py — storage backend factory.

Returns the appropriate storage backend based on STORAGE_BACKEND env var.
This is the migration bridge — existing code uses get_db() from backend/server.py,
which will eventually delegate to this factory.
"""
from __future__ import annotations

from packages.config import settings


def get_storage():
    """Return the active storage backend.
    
    During migration, this delegates to the existing db.get_store() function.
    """
    from db import get_store
    return get_store()


def reset_storage():
    """Reset the storage singleton (for tests)."""
    from db import reset_store
    reset_store()

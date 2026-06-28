"""packages/storage/interface.py — storage interface.

Both MongoDB and SQLite backends implement this interface.
Components depend on the interface, not the implementation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


class StorageInterface(ABC):
    """Abstract storage interface — both backends implement this."""

    @abstractmethod
    async def find_one(self, collection: str, query: dict) -> dict | None:
        """Find a single document."""
        ...

    @abstractmethod
    async def find_many(self, collection: str, query: dict, *, limit: int = 100) -> list[dict]:
        """Find multiple documents."""
        ...

    @abstractmethod
    async def insert_one(self, collection: str, document: dict) -> str:
        """Insert a document. Returns the ID."""
        ...

    @abstractmethod
    async def update_one(self, collection: str, query: dict, update: dict) -> bool:
        """Update a single document."""
        ...

    @abstractmethod
    async def delete_one(self, collection: str, query: dict) -> bool:
        """Delete a single document."""
        ...

    @abstractmethod
    async def delete_many(self, collection: str, query: dict) -> int:
        """Delete multiple documents. Returns count."""
        ...

    @abstractmethod
    async def count(self, collection: str, query: dict | None = None) -> int:
        """Count documents in a collection."""
        ...

    @abstractmethod
    async def create_index(self, collection: str, field: str, *, unique: bool = False) -> None:
        """Create an index on a field."""
        ...

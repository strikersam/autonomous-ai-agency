"""packages/storage/interface.py — storage duck-typing contract.

Both MongoDB and SQLite backends expose collections via attribute access:
    store.users.find_one({"email": "x@y.com"})
    store.tasks.insert_one({...})

This module documents the contract. Backends are duck-typed (not formally
subclassed) because the Motor AsyncIOMotorDatabase API is large and
dynamically dispatched — wrapping every method through an ABC would hurt
performance and add maintenance burden without real safety gain.

New storage backends should:
  1. Expose collection objects as attributes (store.users, store.tasks, etc.)
  2. Each collection must support: find_one, find, insert_one, update_one,
     delete_one, delete_many, count_documents, create_index
  3. Be registered in packages/storage/factory.py
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CollectionLike(Protocol):
    """Minimum API every collection object must support."""

    async def find_one(self, query: dict | None = None, *args: Any, **kwargs: Any) -> dict | None: ...
    async def find(self, query: dict | None = None, *args: Any, **kwargs: Any) -> Any: ...
    async def insert_one(self, document: dict, *args: Any, **kwargs: Any) -> Any: ...
    async def update_one(self, query: dict, update: dict, *args: Any, **kwargs: Any) -> Any: ...
    async def delete_one(self, query: dict, *args: Any, **kwargs: Any) -> Any: ...
    async def delete_many(self, query: dict, *args: Any, **kwargs: Any) -> Any: ...
    async def count_documents(self, query: dict, *args: Any, **kwargs: Any) -> int: ...
    async def create_index(self, keys: Any, *args: Any, **kwargs: Any) -> Any: ...


@runtime_checkable
class StorageLike(Protocol):
    """Minimum API every storage backend must support."""

    def __getattr__(self, name: str) -> CollectionLike: ...
    def __getitem__(self, name: str) -> CollectionLike: ...

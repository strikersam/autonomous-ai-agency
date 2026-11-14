"""packages/runs/backend.py — the four atomic document operations the run layer needs.

Every durable write in ``packages/runs`` is one of: insert if absent, compare
and set, increment and read, or a plain read. Each backend provides them as a
single atomic operation:

* Mongo (``MongoStore`` or a raw Motor database): ``insert_one`` with a unique
  ``_id``, ``update_one`` with a filter, ``find_one_and_update`` with ``$inc``.
* SQLite (``SQLiteStore``): the single statement helpers in
  ``packages/storage/sqlite_atomic.py``, safe across processes on one file.
* Memory: a process local dict, for tests and storage less development.

``expect`` dicts use one small language on every backend: a scalar means
equality, ``None`` means missing or null, ``("lt", v)`` means less than ``v``;
``any_of`` is a list of such dicts of which one must match.
"""
from __future__ import annotations

import copy
import logging
from typing import Any, Protocol, Sequence

from packages.storage import sqlite_atomic

log = logging.getLogger("qwen-proxy")

Expect = dict[str, Any]


class DocTable(Protocol):
    """One collection seen through the atomic operations the run layer uses."""

    kind: str

    async def get(self, doc_id: str) -> dict[str, Any] | None: ...
    async def insert_if_absent(self, doc_id: str, doc: dict[str, Any]) -> bool: ...
    async def compare_and_set(self, doc_id: str, expect: Expect, set_: dict[str, Any],
                              any_of: Sequence[Expect] | None = None) -> bool: ...
    async def increment(self, doc_id: str, field: str, by: int = 1) -> int | None: ...
    async def find(self, query: dict[str, Any], *, sort: str | None = None,
                   descending: bool = False, limit: int = 0) -> list[dict[str, Any]]: ...


def _is_duplicate_key(exc: Exception) -> bool:
    return type(exc).__name__ == "DuplicateKeyError" or "E11000" in str(exc)


def _mongo_condition(expected: Any) -> Any:
    if isinstance(expected, tuple):
        if len(expected) != 2 or expected[0] != "lt":
            raise ValueError(f"unsupported condition: {expected!r}")
        return {"$lt": expected[1]}
    return expected  # None matches a missing field or an explicit null in Mongo


def _mongo_filter(doc_id: str, expect: Expect, any_of: Sequence[Expect] | None) -> dict[str, Any]:
    query: dict[str, Any] = {"_id": doc_id}
    query.update({k: _mongo_condition(v) for k, v in expect.items()})
    if any_of:
        query["$or"] = [{k: _mongo_condition(v) for k, v in g.items()} for g in any_of]
    return query


class MongoTable:
    """A Motor collection (or a test double with the same methods)."""

    kind = "mongo"

    def __init__(self, collection: Any) -> None:
        self._col = collection

    async def get(self, doc_id: str) -> dict[str, Any] | None:
        return await self._col.find_one({"_id": doc_id})

    async def insert_if_absent(self, doc_id: str, doc: dict[str, Any]) -> bool:
        try:
            await self._col.insert_one({**doc, "_id": doc_id})
            return True
        except Exception as exc:
            if _is_duplicate_key(exc):
                return False
            raise

    async def compare_and_set(self, doc_id: str, expect: Expect, set_: dict[str, Any],
                              any_of: Sequence[Expect] | None = None) -> bool:
        result = await self._col.update_one(_mongo_filter(doc_id, expect, any_of), {"$set": set_})
        return int(getattr(result, "matched_count", 0) or 0) == 1

    async def increment(self, doc_id: str, field: str, by: int = 1) -> int | None:
        # return_document=True is pymongo's ReturnDocument.AFTER.
        doc = await self._col.find_one_and_update(
            {"_id": doc_id}, {"$inc": {field: by}}, return_document=True
        )
        return int(doc[field]) if doc else None

    async def find(self, query: dict[str, Any], *, sort: str | None = None,
                   descending: bool = False, limit: int = 0) -> list[dict[str, Any]]:
        cursor = self._col.find(query)
        if sort:
            cursor = cursor.sort(sort, -1 if descending else 1)
        if limit:
            cursor = cursor.limit(limit)
        return await cursor.to_list(length=limit or None)


class SqliteTable:
    """A ``SQLiteStore`` collection; atomic writes go through ``sqlite_atomic``."""

    kind = "sqlite"

    def __init__(self, collection: Any) -> None:
        self._col = collection

    async def get(self, doc_id: str) -> dict[str, Any] | None:
        return await self._col.find_one({"_id": doc_id})

    async def insert_if_absent(self, doc_id: str, doc: dict[str, Any]) -> bool:
        return await sqlite_atomic.insert_if_absent(self._col, doc_id, doc)

    async def compare_and_set(self, doc_id: str, expect: Expect, set_: dict[str, Any],
                              any_of: Sequence[Expect] | None = None) -> bool:
        return await sqlite_atomic.compare_and_set(self._col, doc_id, expect, set_, any_of=any_of)

    async def increment(self, doc_id: str, field: str, by: int = 1) -> int | None:
        return await sqlite_atomic.increment_and_get(self._col, doc_id, field, by=by)

    async def find(self, query: dict[str, Any], *, sort: str | None = None,
                   descending: bool = False, limit: int = 0) -> list[dict[str, Any]]:
        cursor = self._col.find(query)
        if sort:
            cursor = cursor.sort(sort, -1 if descending else 1)
        if limit:
            cursor = cursor.limit(limit)
        return await cursor.to_list(length=limit or None)


def _memory_matches(doc: dict[str, Any], expect: Expect) -> bool:
    for field, expected in expect.items():
        value = doc.get(field)
        if isinstance(expected, tuple):
            if value is None or not value < expected[1]:
                return False
        elif value != expected:
            return False
    return True


class MemoryTable:
    """A process local table. Each method body has no ``await``, so it is atomic per loop."""

    kind = "memory"

    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    async def get(self, doc_id: str) -> dict[str, Any] | None:
        doc = self.docs.get(doc_id)
        return copy.deepcopy(doc) if doc is not None else None

    async def insert_if_absent(self, doc_id: str, doc: dict[str, Any]) -> bool:
        if doc_id in self.docs:
            return False
        self.docs[doc_id] = copy.deepcopy({**doc, "_id": doc_id})
        return True

    async def compare_and_set(self, doc_id: str, expect: Expect, set_: dict[str, Any],
                              any_of: Sequence[Expect] | None = None) -> bool:
        doc = self.docs.get(doc_id)
        if doc is None or not _memory_matches(doc, expect):
            return False
        if any_of and not any(_memory_matches(doc, g) for g in any_of):
            return False
        doc.update(copy.deepcopy(set_))
        return True

    async def increment(self, doc_id: str, field: str, by: int = 1) -> int | None:
        doc = self.docs.get(doc_id)
        if doc is None:
            return None
        doc[field] = int(doc.get(field) or 0) + by
        return doc[field]

    async def find(self, query: dict[str, Any], *, sort: str | None = None,
                   descending: bool = False, limit: int = 0) -> list[dict[str, Any]]:
        rows = [copy.deepcopy(d) for d in self.docs.values() if _memory_matches(d, query)]
        if sort:
            rows.sort(key=lambda d: (d.get(sort) is None, d.get(sort) or 0), reverse=descending)
        return rows[:limit] if limit else rows


def table_for(db: Any, name: str, memory: dict[str, MemoryTable] | None = None) -> DocTable:
    """The ``DocTable`` for collection *name* of *db*; ``None`` db means memory mode.

    ``MongoStore`` subscripting returns the raw Motor collection (it unwraps its
    lazy database), so the Mongo path talks to Motor directly.
    """
    if db is None:
        if memory is None:
            raise ValueError("memory mode needs a table registry")
        return memory.setdefault(name, MemoryTable())
    collection = db[name]
    if sqlite_atomic.is_sqlite_collection(collection):
        return SqliteTable(collection)
    return MongoTable(collection)


async def ensure_index(db: Any, name: str, keys: Any, **kwargs: Any) -> None:
    """Create a Mongo index; a no op on SQLite (indexed columns) and memory. Never raises."""
    if db is None:
        return
    collection = db[name]
    if sqlite_atomic.is_sqlite_collection(collection):
        return
    try:
        await collection.create_index(keys, **kwargs)
    except Exception:
        log.warning("runs: could not create index %s on %s", keys, name, exc_info=True)

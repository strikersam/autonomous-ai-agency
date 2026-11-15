"""Hermetic stand-in for a Motor database with the Mongo semantics the run layer relies on.

Each operation runs without an ``await`` inside it, so on one event loop it is
as atomic as the matching single-document Mongo operation. ``insert_one`` raises
an error named ``DuplicateKeyError`` (the name production code matches on) for
an existing ``_id``.
"""
from __future__ import annotations

import copy
from typing import Any


class DuplicateKeyError(Exception):
    """Same class name pymongo uses."""


class _Result:
    def __init__(self, matched: int = 0, modified: int = 0, deleted: int = 0) -> None:
        self.matched_count = matched
        self.modified_count = modified
        self.deleted_count = deleted


def _cmp(val: Any, op: str, arg: Any) -> bool:
    if op == "$exists":
        return (val is not None) == bool(arg)
    if op == "$in":
        return val in arg
    if op == "$ne":
        return val != arg
    if val is None:
        return False
    return {"$lt": val < arg, "$lte": val <= arg, "$gt": val > arg, "$gte": val >= arg}[op]


def match(doc: dict, query: dict) -> bool:
    """Subset of Mongo query matching: equality, None as missing, $or/$and and comparisons."""
    for key, cond in query.items():
        if key == "$or":
            if not any(match(doc, sub) for sub in cond):
                return False
            continue
        if key == "$and":
            if not all(match(doc, sub) for sub in cond):
                return False
            continue
        val = doc.get(key)
        if isinstance(cond, dict):
            if not all(_cmp(val, op, arg) for op, arg in cond.items()):
                return False
        elif val != cond:
            return False
    return True


def _apply(doc: dict, update: dict) -> None:
    for k, v in update.get("$set", {}).items():
        doc[k] = copy.deepcopy(v)
    for k, v in update.get("$inc", {}).items():
        doc[k] = (doc.get(k) or 0) + v
    for k, v in update.get("$push", {}).items():
        doc.setdefault(k, []).append(copy.deepcopy(v))


class _Cursor:
    def __init__(self, docs: list[dict]) -> None:
        self._docs = docs

    def sort(self, key: Any, direction: int = 1) -> "_Cursor":
        if isinstance(key, list):
            key, direction = key[0]
        self._docs.sort(key=lambda d: d.get(key) or 0, reverse=direction == -1)
        return self

    def limit(self, n: int) -> "_Cursor":
        if n:
            self._docs = self._docs[:n]
        return self

    async def to_list(self, length: int | None = None) -> list[dict]:
        return list(self._docs[:length] if length else self._docs)


class FakeCollection:
    """One collection; documents keyed by ``_id``."""

    def __init__(self) -> None:
        self.docs: dict[Any, dict] = {}
        self.indexes: list[tuple[Any, dict]] = []

    def _first(self, query: dict) -> dict | None:
        return next((d for d in self.docs.values() if match(d, query)), None)

    async def insert_one(self, doc: dict) -> Any:
        if doc["_id"] in self.docs:
            raise DuplicateKeyError("E11000 duplicate key error")
        self.docs[doc["_id"]] = copy.deepcopy(doc)
        return _Result(modified=1)

    async def find_one(self, query: dict, projection: Any = None) -> dict | None:
        doc = self._first(query)
        return copy.deepcopy(doc) if doc is not None else None

    def find(self, query: dict | None = None, projection: Any = None) -> _Cursor:
        return _Cursor([copy.deepcopy(d) for d in self.docs.values() if match(d, query or {})])

    async def update_one(self, query: dict, update: dict, upsert: bool = False) -> _Result:
        doc = self._first(query)
        if doc is None:
            return _Result()
        _apply(doc, update)
        return _Result(matched=1, modified=1)

    async def find_one_and_update(self, query: dict, update: dict, *, return_document: Any = False,
                                  upsert: bool = False, projection: Any = None) -> dict | None:
        doc = self._first(query)
        if doc is None:
            return None
        before = copy.deepcopy(doc)
        _apply(doc, update)
        return copy.deepcopy(doc) if return_document else before

    async def delete_one(self, query: dict) -> _Result:
        doc = self._first(query)
        if doc is None:
            return _Result()
        del self.docs[doc["_id"]]
        return _Result(deleted=1)

    async def create_index(self, keys: Any, **kwargs: Any) -> str:
        self.indexes.append((keys, kwargs))
        return str(keys)


class FakeMotorDb:
    """A database: collections by attribute or subscript, shared by every 'process'."""

    def __init__(self) -> None:
        self.cols: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        return self.cols.setdefault(name, FakeCollection())

    def __getattr__(self, name: str) -> FakeCollection:
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]

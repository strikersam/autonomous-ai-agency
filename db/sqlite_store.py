"""db/sqlite_store.py — Async SQLite storage backend.

Provides a Motor-compatible collection API so all ``get_db().collection.method()``
call sites in ``backend/server.py`` work without modification when
``STORAGE_BACKEND=sqlite`` is set.

Security notes:
- All values are bound via parameterised queries — no string interpolation.
- Column names in ORDER BY / schema are whitelisted; never interpolated from
  user input.
- The database file path is controlled by the ``SQLITE_DB_PATH`` env var,
  defaulting to a local file.  Ensure the file is not served over HTTP.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any

try:
    import aiosqlite
except ModuleNotFoundError as _e:  # pragma: no cover
    raise ModuleNotFoundError(
        "aiosqlite is required for STORAGE_BACKEND=sqlite. "
        "Install with: pip install aiosqlite"
    ) from _e

log = logging.getLogger("agency-core.sqlite")

_SQLITE_DB_PATH = os.environ.get("SQLITE_DB_PATH", ".data/agency.db")

# Collections that map to SQLite tables.
# Each collection is a single table with columns: id (PK), data (JSON blob),
# and common indexed fields extracted for fast lookup.
_COLLECTIONS = [
    "users",
    "chat_sessions",
    "api_keys",
    "wiki_pages",
    "providers",
    "activity_log",
    "agent_definitions",
    "tasks",
    "sources",
    "github_settings",
    "oauth_states",
    "local_metrics",
    "command",
    "companies",
    "user_secrets",
    "mcp_servers",
    "website_scans",
    "repo_scans",
    "workflows",
]

# Fields that are extracted into real columns for indexed lookup.
# This lets find_one({"email": ...}) hit an index instead of scanning JSON.
_INDEXED_FIELDS: dict[str, list[str]] = {
    "users":           ["email", "role"],
    "chat_sessions":   ["user_id", "updated_at"],
    "api_keys":        ["key_hash", "user_id"],
    "wiki_pages":      ["slug", "user_id"],
    "providers":       ["provider_id", "user_id"],
    "activity_log":    ["user_id", "action", "created_at"],
    "oauth_states":    ["state"],
    "github_settings": ["user_id"],
    "tasks":           ["user_id", "status"],
    "local_metrics":   ["user_id", "created_at"],
    "agent_definitions": ["agent_id"],
    "sources":         ["user_id"],
    "mcp_servers":     ["user_id", "created_at"],
    "website_scans":   ["company_id", "status", "completed_at"],
    "repo_scans":      ["company_id", "completed_at"],
    "workflows":       ["company_id", "is_active"],
}


def _new_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


class _Cursor:
    """Async iterator wrapping a list of dicts (already decoded from JSON)."""

    def __init__(self, rows: list[dict], sort_key: str | None = None,
                 sort_dir: int = 1, skip_n: int = 0, limit_n: int = 0):
        if sort_key:
            rows = sorted(rows, key=lambda r: r.get(sort_key) or "", reverse=(sort_dir == -1))
        if skip_n:
            rows = rows[skip_n:]
        if limit_n:
            rows = rows[:limit_n]
        self._rows = rows
        self._idx = 0

    def sort(self, key_or_pairs, direction: int = 1) -> "_Cursor":
        if isinstance(key_or_pairs, str):
            pairs = [(key_or_pairs, direction)]
        else:
            pairs = list(key_or_pairs)
        rows = list(self._rows)
        for key, d in reversed(pairs):
            rows = sorted(rows, key=lambda r: r.get(key) or "", reverse=(d == -1))
        return _Cursor(rows)

    def skip(self, n: int) -> "_Cursor":
        return _Cursor(self._rows[n:])

    def limit(self, n: int) -> "_Cursor":
        return _Cursor(self._rows[:n] if n else self._rows)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._rows):
            raise StopAsyncIteration
        row = self._rows[self._idx]
        self._idx += 1
        return row

    async def to_list(self, length: int | None = None) -> list[dict]:
        if length:
            return self._rows[:length]
        return list(self._rows)


class _InsertResult:
    def __init__(self, inserted_id: str):
        self.inserted_id = inserted_id


class _UpdateResult:
    def __init__(self, matched: int, modified: int):
        self.matched_count = matched
        self.modified_count = modified


class _DeleteResult:
    def __init__(self, deleted: int):
        self.deleted_count = deleted


def _match(doc: dict, query: dict) -> bool:
    """Return True if *doc* satisfies the MongoDB-style *query*.

    Supports: exact match, ``$in``, ``$nin``, ``$gt``, ``$gte``, ``$lt``,
    ``$lte``, ``$ne``, ``$exists``, ``$regex``, ``$or``, ``$and``.
    """
    import re as _re
    for key, val in query.items():
        if key == "$or":
            if not any(_match(doc, sub) for sub in val):
                return False
            continue
        if key == "$and":
            if not all(_match(doc, sub) for sub in val):
                return False
            continue
        doc_val = doc.get(key)
        if isinstance(val, dict):
            for op, operand in val.items():
                if op == "$in":
                    if doc_val not in operand:
                        return False
                elif op == "$nin":
                    if doc_val in operand:
                        return False
                elif op == "$gt":
                    if not (doc_val is not None and doc_val > operand):
                        return False
                elif op == "$gte":
                    if not (doc_val is not None and doc_val >= operand):
                        return False
                elif op == "$lt":
                    if not (doc_val is not None and doc_val < operand):
                        return False
                elif op == "$lte":
                    if not (doc_val is not None and doc_val <= operand):
                        return False
                elif op == "$ne":
                    if doc_val == operand:
                        return False
                elif op == "$exists":
                    if operand and key not in doc:
                        return False
                    if not operand and key in doc:
                        return False
                elif op == "$regex":
                    if not _re.search(operand, str(doc_val or ""), _re.IGNORECASE):
                        return False
        else:
            # Exact match — handle ObjectId-like string comparison
            str_val = str(val) if val is not None else None
            str_doc = str(doc_val) if doc_val is not None else None
            if str_doc != str_val:
                return False
    return True


def _apply_update(doc: dict, update: dict) -> dict:
    """Apply a MongoDB-style update operator dict to *doc* in place."""
    new = dict(doc)
    for op, fields in update.items():
        if op == "$set":
            for k, v in fields.items():
                # Support dot-notation: "a.b" → nested set
                parts = k.split(".")
                target = new
                for p in parts[:-1]:
                    target = target.setdefault(p, {})
                target[parts[-1]] = v
        elif op == "$unset":
            for k in fields:
                new.pop(k, None)
        elif op == "$push":
            for k, v in fields.items():
                lst = new.get(k, [])
                if not isinstance(lst, list):
                    lst = []
                each = v.get("$each", [v]) if isinstance(v, dict) and "$each" in v else [v]
                lst.extend(each)
                new[k] = lst
        elif op == "$addToSet":
            for k, v in fields.items():
                lst = new.get(k, [])
                if not isinstance(lst, list):
                    lst = []
                if v not in lst:
                    lst.append(v)
                new[k] = lst
        elif op == "$pull":
            for k, v in fields.items():
                lst = new.get(k, [])
                new[k] = [x for x in lst if not _match({"_val": x}, {"_val": v})]
        elif op == "$inc":
            for k, v in fields.items():
                new[k] = (new.get(k) or 0) + v
        elif op == "$currentDate":
            for k in fields:
                new[k] = _now_iso()
    new["updated_at"] = _now_iso()
    return new


class _Collection:
    """Motor-compatible async collection backed by a SQLite table.

    All I/O uses parameterised queries.  The full document is stored as a
    JSON blob in the ``data`` column; hot-path lookup fields are also
    extracted into their own columns and indexed.
    """

    def __init__(self, store: "SQLiteStore", name: str):
        self._store = store
        # Whitelist-validate: table names must come from the _COLLECTIONS list. This is a
        # hard fail-closed barrier against SQL injection in f-string SQL below — once
        # validated, the interpolated value is provably from a fixed allowlist.
        if name not in _COLLECTIONS:
            raise ValueError(f"refusing to bind to non-whitelisted table: {name!r}")
        self._name = name

    # ── internal helpers ──────────────────────────────────────────────────

    async def _conn(self) -> aiosqlite.Connection:
        return await self._store._get_conn()

    async def _all_docs(self) -> list[dict]:
        conn = await self._conn()
        async with conn.execute(f"SELECT data FROM {self._name}") as cur:  # nosec B608 — table name is whitelisted via _COLLECTIONS in _Collection.__init__
            rows = await cur.fetchall()
        return [json.loads(r[0]) for r in rows]

    async def _matching(self, query: dict) -> list[dict]:
        all_docs = await self._all_docs()
        return [d for d in all_docs if _match(d, query)]

    # ── public Motor-compatible API ───────────────────────────────────────

    async def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        docs = await self._matching(query)
        return docs[0] if docs else None

    def find(self, query: dict | None = None, projection: dict | None = None) -> _Cursor:
        """Return a _Cursor (evaluated lazily on first await/iteration)."""
        # We need to run the filter synchronously-ish; wrap in a coroutine
        # that resolves on __aiter__ / to_list.  For simplicity we return a
        # _PendingCursor that fetches on first use.
        return _PendingCursor(self, query or {})

    async def insert_one(self, document: dict) -> _InsertResult:
        doc = dict(document)
        if "_id" not in doc:
            doc["_id"] = _new_id()
        if "created_at" not in doc:
            doc["created_at"] = _now_iso()
        if "updated_at" not in doc:
            doc["updated_at"] = doc["created_at"]

        indexed = _INDEXED_FIELDS.get(self._name, [])
        cols = ["id", "data"] + indexed
        placeholders = ", ".join("?" * len(cols))
        col_names = ", ".join(cols)
        vals = [str(doc["_id"]), json.dumps(doc, default=str)] + [
            str(doc.get(f, "")) for f in indexed
        ]
        conn = await self._conn()
        await conn.execute(
            f"INSERT OR REPLACE INTO {self._name} ({col_names}) VALUES ({placeholders})",
            vals,
        )
        await conn.commit()
        return _InsertResult(doc["_id"])

    async def update_one(self, query: dict, update: dict,
                         upsert: bool = False) -> _UpdateResult:
        docs = await self._matching(query)
        if not docs:
            if upsert:
                new_doc = {}
                # Seed with equality conditions from the query filter so the
                # inserted document satisfies the original query.
                for k, v in query.items():
                    if not k.startswith("$") and not isinstance(v, dict):
                        new_doc[k] = v
                # Apply $set / $setOnInsert on top
                for op, fields in update.items():
                    if op in ("$set", "$setOnInsert"):
                        new_doc.update(fields)
                await self.insert_one(new_doc)
                return _UpdateResult(0, 1)
            return _UpdateResult(0, 0)

        doc = docs[0]
        new_doc = _apply_update(doc, update)
        indexed = _INDEXED_FIELDS.get(self._name, [])
        set_parts = ["data = ?"] + [f"{f} = ?" for f in indexed]
        vals = [json.dumps(new_doc, default=str)] + [
            str(new_doc.get(f, "")) for f in indexed
        ]
        vals.append(str(doc["_id"]))
        conn = await self._conn()
        await conn.execute(
            f"UPDATE {self._name} SET {', '.join(set_parts)} WHERE id = ?",  # nosec B608 — table name is whitelisted via _COLLECTIONS in _Collection.__init__
            vals,
        )
        await conn.commit()
        return _UpdateResult(1, 1)

    async def replace_one(self, query: dict, replacement: dict,
                          upsert: bool = False) -> _UpdateResult:
        docs = await self._matching(query)
        if not docs:
            if upsert:
                await self.insert_one(replacement)
                return _UpdateResult(0, 1)
            return _UpdateResult(0, 0)
        doc = docs[0]
        new_doc = dict(replacement)
        new_doc["_id"] = doc["_id"]
        new_doc["updated_at"] = _now_iso()
        indexed = _INDEXED_FIELDS.get(self._name, [])
        set_parts = ["data = ?"] + [f"{f} = ?" for f in indexed]
        vals = [json.dumps(new_doc, default=str)] + [
            str(new_doc.get(f, "")) for f in indexed
        ]
        vals.append(str(doc["_id"]))
        conn = await self._conn()
        await conn.execute(
            f"UPDATE {self._name} SET {', '.join(set_parts)} WHERE id = ?",  # nosec B608 — table name is whitelisted via _COLLECTIONS in _Collection.__init__
            vals,
        )
        await conn.commit()
        return _UpdateResult(1, 1)

    async def delete_one(self, query: dict) -> _DeleteResult:
        docs = await self._matching(query)
        if not docs:
            return _DeleteResult(0)
        doc = docs[0]
        conn = await self._conn()
        await conn.execute(f"DELETE FROM {self._name} WHERE id = ?", (str(doc["_id"]),))
        await conn.commit()
        return _DeleteResult(1)

    async def delete_many(self, query: dict) -> _DeleteResult:
        docs = await self._matching(query)
        if not docs:
            return _DeleteResult(0)
        conn = await self._conn()
        for doc in docs:
            await conn.execute(f"DELETE FROM {self._name} WHERE id = ?", (str(doc["_id"]),))
        await conn.commit()
        return _DeleteResult(len(docs))

    async def count_documents(self, query: dict) -> int:
        return len(await self._matching(query))

    async def aggregate(self, pipeline: list[dict]) -> _Cursor:
        """Minimal aggregate support: $match → $group($sum) / $sort / $limit."""
        docs = await self._all_docs()
        for stage in pipeline:
            if "$match" in stage:
                docs = [d for d in docs if _match(d, stage["$match"])]
            elif "$sort" in stage:
                for k, direction in reversed(list(stage["$sort"].items())):
                    docs = sorted(docs, key=lambda d: d.get(k) or "", reverse=(direction == -1))
            elif "$limit" in stage:
                docs = docs[:stage["$limit"]]
            elif "$group" in stage:
                # minimal: {_id: "$field", total: {$sum: "$field2"}}
                groups: dict[Any, dict] = {}
                gspec = stage["$group"]
                id_expr = gspec.get("_id")
                for d in docs:
                    if isinstance(id_expr, str) and id_expr.startswith("$"):
                        gkey = d.get(id_expr[1:])
                    else:
                        gkey = id_expr
                    if gkey not in groups:
                        groups[gkey] = {"_id": gkey}
                    for out_field, agg_expr in gspec.items():
                        if out_field == "_id":
                            continue
                        if isinstance(agg_expr, dict) and "$sum" in agg_expr:
                            src = agg_expr["$sum"]
                            if isinstance(src, str) and src.startswith("$"):
                                groups[gkey][out_field] = groups[gkey].get(out_field, 0) + (d.get(src[1:]) or 0)
                            else:
                                groups[gkey][out_field] = groups[gkey].get(out_field, 0) + src
                docs = list(groups.values())
            elif "$project" in stage:
                proj = stage["$project"]
                include = {k for k, v in proj.items() if v}
                if include:
                    docs = [{k: d.get(k) for k in include if k in d} for d in docs]
        return _Cursor(docs)

    async def distinct(self, field: str, query: dict | None = None) -> list:
        docs = await self._matching(query or {})
        seen: set = set()
        result = []
        for d in docs:
            v = d.get(field)
            key = str(v)
            if key not in seen:
                seen.add(key)
                result.append(v)
        return result

    async def create_index(self, *args, **kwargs) -> None:
        """No-op — indexes are pre-created in schema init."""

    async def drop(self) -> None:
        conn = await self._conn()
        await conn.execute(f"DELETE FROM {self._name}")
        await conn.commit()


class _PendingCursor:
    """A cursor that fetches its data lazily on first use."""

    def __init__(self, collection: _Collection, query: dict):
        self._col = collection
        self._query = query
        self._sort_key: str | None = None
        self._sort_dir: int = 1
        self._skip_n: int = 0
        self._limit_n: int = 0
        self._resolved: _Cursor | None = None

    def sort(self, key_or_pairs, direction: int = 1) -> "_PendingCursor":
        c = _PendingCursor(self._col, self._query)
        if isinstance(key_or_pairs, str):
            c._sort_key = key_or_pairs
            c._sort_dir = direction
        else:
            pairs = list(key_or_pairs)
            if pairs:
                c._sort_key, c._sort_dir = pairs[0]
        c._skip_n = self._skip_n
        c._limit_n = self._limit_n
        return c

    def skip(self, n: int) -> "_PendingCursor":
        c = _PendingCursor(self._col, self._query)
        c._sort_key = self._sort_key
        c._sort_dir = self._sort_dir
        c._skip_n = n
        c._limit_n = self._limit_n
        return c

    def limit(self, n: int) -> "_PendingCursor":
        c = _PendingCursor(self._col, self._query)
        c._sort_key = self._sort_key
        c._sort_dir = self._sort_dir
        c._skip_n = self._skip_n
        c._limit_n = n
        return c

    async def _resolve(self) -> _Cursor:
        if self._resolved is None:
            docs = await self._col._matching(self._query)
            self._resolved = _Cursor(docs, self._sort_key, self._sort_dir,
                                     self._skip_n, self._limit_n)
        return self._resolved

    def __aiter__(self):
        return self

    async def __anext__(self):
        cur = await self._resolve()
        return await cur.__anext__()

    async def to_list(self, length: int | None = None) -> list[dict]:
        cur = await self._resolve()
        return await cur.to_list(length)


class SQLiteStore:
    """Top-level store — exposes collections as attributes.

    Usage::

        store = SQLiteStore()
        user = await store.users.find_one({"email": "x@y.com"})
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or _SQLITE_DB_PATH
        self._conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()
        self._initialized = False
        # Pre-bind collection attributes
        for name in _COLLECTIONS:
            setattr(self, name, _Collection(self, name))

    async def _get_conn(self) -> aiosqlite.Connection:
        async with self._lock:
            if self._conn is None or not self._initialized:
                os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
                self._conn = await aiosqlite.connect(self._db_path)
                await self._conn.execute("PRAGMA journal_mode=WAL")
                await self._conn.execute("PRAGMA foreign_keys=ON")
                await self._init_schema()
                self._initialized = True
        return self._conn

    async def _init_schema(self) -> None:
        """Create tables if they don't already exist."""
        assert self._conn is not None
        for table in _COLLECTIONS:
            indexed = _INDEXED_FIELDS.get(table, [])
            # Whitelist: table names and column names come from our own
            # constants above, never from user input.
            extra_cols = "".join(f",\n    {col} TEXT" for col in indexed)
            await self._conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                    {extra_cols}
                )
            """)
            for col in indexed:
                await self._conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{table}_{col} ON {table}({col})"
                )
        await self._conn.commit()
        log.info("SQLiteStore schema ready at %s", self._db_path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
            self._initialized = False

    def __getattr__(self, name: str) -> _Collection:
        # Fallback for any collection not in _COLLECTIONS (e.g. dynamic names).
        # The whitelist check in _Collection.__init__ is the real guard — it raises
        # ValueError for non-whitelisted names. We convert to AttributeError here so
        # attribute-access semantics match "this attribute does not exist".
        try:
            return _Collection(self, name)
        except ValueError as e:
            # Only re-wrap our own guard's ValueError; let unrelated ValueErrors propagate.
            if "non-whitelisted table" not in str(e):
                raise
            raise AttributeError(str(e)) from None

    def __getitem__(self, name: str) -> _Collection:
        # Mongo/motor exposes collections via BOTH ``db.tasks`` and
        # ``db["tasks"]``. SQLiteStore previously supported only attribute access
        # (__getattr__), so code written for Mongo that used subscript access —
        # e.g. TaskStore/AgentStore's ``self._db["tasks"]`` — raised
        # ``TypeError: 'SQLiteStore' object is not subscriptable`` under
        # STORAGE_BACKEND=sqlite. Supporting __getitem__ makes the SQLite backend
        # a drop-in for the subscript pattern too.
        return _Collection(self, name)

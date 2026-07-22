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
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator


def _safe_sort_key(row: dict, key: str) -> Any:
    """Return a sort key that tolerates mixed float/str timestamp values.

    Some code paths write ``updated_at`` / ``created_at`` as ISO 8601 strings
    instead of float timestamps. When the sqlite adapter sorts rows by these
    fields, a ``float < str`` comparison crashes with ``TypeError: '<' not
    supported between instances of 'float' and 'str'``.

    This helper normalises any value to a float for sorting purposes:
    - float/int → returned as-is
    - ISO 8601 string → parsed to timestamp
    - numeric string → parsed to float
    - None → 0.0
    - unparseable → 0.0
    """
    v = row.get(key)
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return datetime.fromisoformat(str(v)).timestamp()
    except (ValueError, TypeError):
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0

# Sort keys are interpolated into ``json_extract(data, '$.<key>')`` for the SQL
# ORDER BY push-down, so they must be validated as bare identifiers (they come
# from our own callers, never user input, but validate defensively anyway).
_SAFE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

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
    "app_settings",
    "agent_specs",
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
    "tasks":           ["user_id", "status", "owner_id"],
    "local_metrics":   ["user_id", "created_at"],
    "agent_definitions": ["agent_id"],
    "sources":         ["user_id"],
    "mcp_servers":     ["user_id", "created_at"],
    "website_scans":   ["company_id", "status", "completed_at"],
    "repo_scans":      ["company_id", "completed_at"],
    "workflows":       ["company_id", "is_active"],
    "app_settings":    ["key"],
    "agent_specs":     ["spec_id", "status", "created_at"],
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
            rows = sorted(rows, key=lambda r: _safe_sort_key(r, sort_key), reverse=(sort_dir == -1))
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
            rows = sorted(rows, key=lambda r, _k=key: _safe_sort_key(r, _k), reverse=(d == -1))
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


def _is_pushable_scalar(v: Any) -> bool:
    """Scalar values whose `str()` form matches how they were stored in the
    indexed column (see ``insert_one``: ``str(doc.get(field, ""))``).

    ``None`` is excluded: a missing field is stored as ``""`` while a present
    ``None`` is stored as ``"None"``, so equality against ``None`` is ambiguous
    and must be left to the Python ``_match`` pass.
    """
    return isinstance(v, (str, int, float, bool))


def _push_down_where(name: str, query: dict) -> tuple[str, list[str]]:
    """Build a SQL ``WHERE`` suffix from the subset of *query* conditions that
    map onto indexed columns with equality / ``$in`` semantics.

    Every emitted clause is a *necessary* condition for ``_match`` to pass (all
    top-level query keys are ANDed together), so the WHERE can only ever narrow
    the candidate set — it can never drop a row that ``_match`` would accept.
    The full ``_match`` still runs in Python afterwards, so any over-inclusion
    (string coercion of typed values, missing-field rows) is harmless.

    Column names are taken from the ``_INDEXED_FIELDS`` whitelist, never from
    arbitrary caller input — a query key is only used after confirming it is a
    declared indexed column for this table.
    """
    indexed = set(_INDEXED_FIELDS.get(name, []))
    if not indexed:
        return "", []
    clauses: list[str] = []
    params: list[str] = []
    for key, val in query.items():
        if key not in indexed:
            # Not an indexed column (or an operator like $or/$and) — leave it to
            # the Python _match pass.
            continue
        if isinstance(val, dict):
            # Only a bare ``{"$in": [...]}`` of scalars is safely pushable.
            if set(val.keys()) == {"$in"}:
                operand = val["$in"]
                if (isinstance(operand, (list, tuple)) and operand
                        and all(_is_pushable_scalar(v) for v in operand)):
                    placeholders = ", ".join("?" * len(operand))
                    # nosec B608 — `key` is a whitelisted indexed column name
                    clauses.append(f"{key} IN ({placeholders})")
                    params.extend(str(v) for v in operand)
            continue
        if _is_pushable_scalar(val):
            # nosec B608 — `key` is a whitelisted indexed column name
            clauses.append(f"{key} = ?")
            params.append(str(val))
    if not clauses:
        return "", []
    return " WHERE " + " AND ".join(clauses), params


def _fully_pushable(name: str, query: dict) -> bool:
    """True if EVERY condition in *query* is expressible in the SQL WHERE.

    Unlike ``_push_down_where`` (which narrows but leaves residual conditions to
    the Python ``_match`` pass), this requires the SQL filter to be *equivalent*
    to the query — every key is an indexed column constrained by scalar equality
    or a ``$in`` of scalars. Only then is it safe to also push ``ORDER BY`` +
    ``LIMIT``/``OFFSET`` into SQL, because no post-filter can drop rows from the
    SQL-limited page.
    """
    indexed = set(_INDEXED_FIELDS.get(name, []))
    for key, val in query.items():
        if key not in indexed:
            return False
        if isinstance(val, dict):
            if set(val.keys()) != {"$in"}:
                return False
            operand = val["$in"]
            if not (isinstance(operand, (list, tuple)) and operand
                    and all(_is_pushable_scalar(v) for v in operand)):
                return False
        elif not _is_pushable_scalar(val):
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

    async def _all_docs(self, query: dict | None = None, *,
                        write_conn: bool = False) -> list[dict]:
        # Push indexed equality / $in conditions into SQL so the index does the
        # filtering, instead of pulling + JSON-decoding every row and scanning in
        # Python. The clause only narrows candidates; _matching still applies the
        # full _match in Python for the non-pushable conditions.
        where_sql, params = _push_down_where(self._name, query or {})
        sql = f"SELECT data FROM {self._name}{where_sql}"  # nosec B608 — table name whitelisted via _COLLECTIONS; column names via _INDEXED_FIELDS; values parameterised
        if write_conn:
            # Read-modify-write callers read through the writer connection so they
            # observe their own connection's latest committed view.
            conn = await self._conn()
            async with conn.execute(sql, params) as cur:
                rows = await cur.fetchall()
        else:
            # Pure reads use a pooled read connection so they run concurrently
            # with the writer (and each other) instead of serializing on it.
            async with self._store._read_conn() as conn:
                async with conn.execute(sql, params) as cur:
                    rows = await cur.fetchall()
        return [json.loads(r[0]) for r in rows]

    async def _matching(self, query: dict, *, write_conn: bool = False) -> list[dict]:
        all_docs = await self._all_docs(query, write_conn=write_conn)
        return [d for d in all_docs if _match(d, query)]

    async def _find_pushed(self, query: dict, sort_key: str | None,
                           sort_dir: int, skip_n: int, limit_n: int) -> list[dict] | None:
        """Try to satisfy a sorted/paginated find entirely in SQL.

        Returns the decoded page when the query is fully expressible as a SQL
        WHERE (so no Python post-filter is needed) and a valid sort key is
        given — letting SQLite do the ORDER BY + LIMIT/OFFSET and materialise
        only the requested page. Returns ``None`` to signal the caller to fall
        back to the load-all-then-filter-in-Python path.
        """
        if not sort_key or not _SAFE_IDENT.match(sort_key):
            return None
        if not _fully_pushable(self._name, query):
            return None
        where_sql, params = _push_down_where(self._name, query)
        indexed = set(_INDEXED_FIELDS.get(self._name, []))
        # Sort on the extracted column when indexed (cheap, uses the index);
        # otherwise read the value out of the JSON blob.
        order_col = sort_key if sort_key in indexed else f"json_extract(data, '$.{sort_key}')"
        direction = "DESC" if sort_dir == -1 else "ASC"
        # table name whitelisted via _COLLECTIONS; order_col is an indexed column
        # name (from _INDEXED_FIELDS) or json_extract of a key validated by
        # _SAFE_IDENT; WHERE values are parameterised. (inline nosec required —
        # Bandit only honours same-line suppressions.)
        sql = f"SELECT data FROM {self._name}{where_sql} ORDER BY {order_col} {direction}"  # nosec B608
        if limit_n:
            sql += f" LIMIT {int(limit_n)} OFFSET {int(skip_n)}"
        elif skip_n:
            sql += f" LIMIT -1 OFFSET {int(skip_n)}"
        async with self._store._read_conn() as conn:
            async with conn.execute(sql, params) as cur:
                rows = await cur.fetchall()
        return [json.loads(r[0]) for r in rows]

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
        docs = await self._matching(query, write_conn=True)
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

    async def update_many(self, query: dict, update: dict,
                          upsert: bool = False) -> _UpdateResult:
        """Apply *update* to every document matching *query* (Motor-compatible).

        Unlike ``update_one`` (which stops at the first match), this walks
        every matching row — needed for fan-out writes like clearing an
        ``is_default`` flag off every OTHER provider before setting it on
        the newly-chosen one (``backend/server.py``'s provider endpoints).
        """
        docs = await self._matching(query, write_conn=True)
        if not docs:
            if upsert:
                new_doc = {}
                for k, v in query.items():
                    if not k.startswith("$") and not isinstance(v, dict):
                        new_doc[k] = v
                for op, fields in update.items():
                    if op in ("$set", "$setOnInsert"):
                        new_doc.update(fields)
                await self.insert_one(new_doc)
                return _UpdateResult(0, 1)
            return _UpdateResult(0, 0)

        indexed = _INDEXED_FIELDS.get(self._name, [])
        conn = await self._conn()
        for doc in docs:
            new_doc = _apply_update(doc, update)
            set_parts = ["data = ?"] + [f"{f} = ?" for f in indexed]
            vals = [json.dumps(new_doc, default=str)] + [
                str(new_doc.get(f, "")) for f in indexed
            ]
            vals.append(str(doc["_id"]))
            await conn.execute(
                f"UPDATE {self._name} SET {', '.join(set_parts)} WHERE id = ?",  # nosec B608 — table name is whitelisted via _COLLECTIONS in _Collection.__init__
                vals,
            )
        await conn.commit()
        return _UpdateResult(len(docs), len(docs))

    async def replace_one(self, query: dict, replacement: dict,
                          upsert: bool = False) -> _UpdateResult:
        docs = await self._matching(query, write_conn=True)
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
        docs = await self._matching(query, write_conn=True)
        if not docs:
            return _DeleteResult(0)
        doc = docs[0]
        conn = await self._conn()
        await conn.execute(f"DELETE FROM {self._name} WHERE id = ?", (str(doc["_id"]),))
        await conn.commit()
        return _DeleteResult(1)

    async def delete_many(self, query: dict) -> _DeleteResult:
        docs = await self._matching(query, write_conn=True)
        if not docs:
            return _DeleteResult(0)
        conn = await self._conn()
        for doc in docs:
            await conn.execute(f"DELETE FROM {self._name} WHERE id = ?", (str(doc["_id"]),))
        await conn.commit()
        return _DeleteResult(len(docs))

    async def count_documents(self, query: dict) -> int:
        # Fast path: an unfiltered count never needs the row payloads — let
        # SQLite answer ``SELECT COUNT(*)`` straight from the table instead of
        # pulling and JSON-decoding every blob into Python just to call len().
        # The dashboard's /api/stats fires six unfiltered counts per refresh
        # (wiki_pages, sources, chat_sessions, activity_log, providers,
        # api_keys), and activity_log/local_metrics grow unbounded — so the old
        # full-table materialisation was the dominant cost of that endpoint.
        if not query:
            # Build the SQL on its own line so the inline ``# nosec`` attaches to
            # the flagged expression (Bandit only honours same-line suppressions);
            # the table name is whitelisted via _COLLECTIONS in __init__.
            count_sql = f"SELECT COUNT(*) FROM {self._name}"  # nosec B608 — table name whitelisted via _COLLECTIONS
            async with self._store._read_conn() as conn:
                async with conn.execute(count_sql) as cur:
                    row = await cur.fetchone()
            return int(row[0]) if row else 0
        return len(await self._matching(query))

    async def estimated_document_count(self) -> int:
        """Motor-compatible fast total count (no per-row deserialization)."""
        return await self.count_documents({})

    async def aggregate(self, pipeline: list[dict]) -> _Cursor:
        """Minimal aggregate support: $match → $group($sum) / $sort / $limit."""
        docs = await self._all_docs()
        for stage in pipeline:
            if "$match" in stage:
                docs = [d for d in docs if _match(d, stage["$match"])]
            elif "$sort" in stage:
                for k, direction in reversed(list(stage["$sort"].items())):
                    docs = sorted(docs, key=lambda d: _safe_sort_key(d, k), reverse=(direction == -1))
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
            # Fast path: push ORDER BY + LIMIT/OFFSET into SQL when the query is
            # fully expressible there, so only the requested page is decoded
            # (instead of materialising + sorting every matching row in Python).
            page = await self._col._find_pushed(
                self._query, self._sort_key, self._sort_dir,
                self._skip_n, self._limit_n,
            )
            if page is not None:
                # Already sorted/sliced by SQL — wrap without re-sorting.
                self._resolved = _Cursor(page)
            else:
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
        # Read-connection pool (WAL mode allows N concurrent readers + 1 writer).
        # Without it, every read shares the single writer connection, so dashboard
        # / task-board queries serialize behind the autonomous background loops'
        # writes on a busy single-process deploy. The pool lets reads run
        # concurrently with each other and with the writer.
        self._read_pool: asyncio.Queue[aiosqlite.Connection] | None = None
        self._read_lock = asyncio.Lock()
        try:
            self._read_pool_size = max(1, int(os.environ.get("SQLITE_READ_POOL_SIZE", "4")))
        except ValueError:
            self._read_pool_size = 4
        # An in-memory DB is private per connection, so a separate read pool would
        # see an empty database. Disable pooling there and read via the writer.
        self._pool_enabled = ":memory:" not in self._db_path
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
                # Wait (up to 5s) for a transient lock instead of failing fast with
                # "database is locked" under concurrent access.
                await self._conn.execute("PRAGMA busy_timeout=5000")
                await self._init_schema()
                self._initialized = True
        return self._conn

    async def _ensure_read_pool(self) -> None:
        """Lazily build the pool of read-only connections (idempotent)."""
        # Make sure the writer has created the schema / WAL file first.
        await self._get_conn()
        async with self._read_lock:
            if self._read_pool is not None:
                return
            pool: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue()
            created: list[aiosqlite.Connection] = []
            try:
                for _ in range(self._read_pool_size):
                    rc = await aiosqlite.connect(self._db_path)
                    # query_only fails closed if a read path ever attempts a write;
                    # busy_timeout lets a reader wait out the writer's brief lock.
                    await rc.execute("PRAGMA query_only=ON")
                    await rc.execute("PRAGMA busy_timeout=5000")
                    created.append(rc)
                    pool.put_nowait(rc)
            except Exception:
                # Don't leak the connections we already opened if a later
                # connect/PRAGMA fails — close them before propagating so a
                # retried read doesn't accumulate orphaned handles.
                for rc in created:
                    try:
                        await rc.close()
                    except Exception as exc:  # pragma: no cover - best effort
                        log.warning("error closing read connection during failed pool init: %s", exc)
                raise
            self._read_pool = pool

    @asynccontextmanager
    async def _read_conn(self) -> AsyncIterator[aiosqlite.Connection]:
        """Yield a read connection from the pool (falls back to the writer).

        On in-memory databases — or if pool creation fails — this yields the
        single writer connection so reads still work, just without concurrency.
        """
        if not self._pool_enabled:
            yield await self._get_conn()
            return
        try:
            await self._ensure_read_pool()
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("SQLite read pool unavailable, using writer connection: %s", exc)
            yield await self._get_conn()
            return
        # Bind the pool locally so a concurrent close() (which swaps
        # self._read_pool to None) can't strand the connection on return: if the
        # store's pool is no longer the one we borrowed from, close the handle
        # instead of returning it to a dead/replaced queue.
        pool = self._read_pool
        assert pool is not None
        conn = await pool.get()
        try:
            yield conn
        finally:
            if self._read_pool is pool:
                pool.put_nowait(conn)
            else:
                try:
                    await conn.close()
                except Exception as exc:  # pragma: no cover - best effort
                    log.warning("error closing read connection after pool teardown: %s", exc)

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
            # Auto-migrate pre-existing tables: CREATE TABLE IF NOT EXISTS won't
            # add columns declared in _INDEXED_FIELDS after the table was first
            # created. Add any missing indexed column and backfill it from the
            # JSON blob so the push-down WHERE/ORDER BY can use it immediately.
            cur = await self._conn.execute(f"PRAGMA table_info({table})")
            existing_cols = {row[1] for row in await cur.fetchall()}
            for col in indexed:
                if col not in existing_cols:
                    # nosec B608 — table/col are whitelisted constants, not input
                    await self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
                    await self._conn.execute(
                        f"UPDATE {table} SET {col} = json_extract(data, '$.{col}') "  # nosec B608
                        f"WHERE {col} IS NULL"
                    )
            for col in indexed:
                # app_settings stores exactly one row per setting key (set_setting
                # upserts on {"key": ...}); a UNIQUE index prevents concurrent
                # upserts from creating duplicate rows that would make find_one
                # nondeterministic.
                if table == "app_settings" and col == "key":
                    await self._conn.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS idx_app_settings_key "
                        "ON app_settings(key)"
                    )
                else:
                    await self._conn.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{table}_{col} ON {table}({col})"
                    )
        await self._conn.commit()
        log.info("SQLiteStore schema ready at %s", self._db_path)

    async def close(self) -> None:
        # Swap the pool reference to None under the same lock that guards pool
        # creation, so an in-flight _read_conn() observes a consistent state and
        # returns its borrowed connection via the `is pool` guard instead of into
        # a half-drained queue.
        async with self._read_lock:
            pool, self._read_pool = self._read_pool, None
        if pool is not None:
            while not pool.empty():
                rc = pool.get_nowait()
                try:
                    await rc.close()
                except Exception as exc:  # pragma: no cover - best effort
                    log.warning("error closing pooled read connection: %s", exc)
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

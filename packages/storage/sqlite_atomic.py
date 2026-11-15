"""packages/storage/sqlite_atomic.py — atomic helpers for the SQLite backend.

``SQLiteStore``'s ``update_one(upsert=True)`` with ``$inc`` is a read, a Python
add and a write, so two concurrent increments can both read the same total and
one is lost (and the first upsert drops the ``$inc`` entirely). The durable
token ledger needs exact totals, so it uses :func:`atomic_increment` here: one
``INSERT ... ON CONFLICT DO UPDATE`` statement, which SQLite executes atomically
(also across processes sharing the DB file).

:func:`purge_expired` is the SQLite substitute for MongoDB TTL indexes.

:func:`insert_if_absent`, :func:`compare_and_set` and :func:`increment_and_get`
give the durable run layer (``packages/runs``) the single document atomicity
Mongo has: insert if absent, conditional update, and increment then read, each
one statement.

All helpers take a ``SQLiteStore`` collection and work on its own connection,
so they share the store's file, WAL mode and busy timeout. Table names come from
the collection (already checked against the store's allowlist); field names are
validated as bare identifiers; every value is bound as a parameter.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Sequence

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_sqlite_collection(col: Any) -> bool:
    """True when *col* is a ``SQLiteStore`` collection (not Motor, not a test fake)."""
    try:
        from packages.storage.sqlite import _Collection
    except ImportError:  # aiosqlite missing -> the SQLite backend cannot be in use
        return False
    return isinstance(col, _Collection)


def _checked(*names: str) -> None:
    for name in names:
        if not _IDENT.match(name):
            raise ValueError(f"unsafe field name: {name!r}")


async def atomic_increment(
    col: Any, doc_id: str, inc: dict[str, int | float], *, set_on_insert: dict[str, Any] | None = None,
) -> None:
    """Add each ``inc`` value to its field of document *doc_id*, creating it if absent.

    A single SQL statement, so concurrent callers never lose an increment.
    ``set_on_insert`` fields are written only when the document is created.
    """
    if not inc:
        raise ValueError("atomic_increment needs at least one field")
    _checked(*inc)
    now = datetime.now(timezone.utc).isoformat()
    seed = {**(set_on_insert or {}), **inc, "_id": doc_id, "created_at": now, "updated_at": now}
    sets = ", ".join(
        f"'$.{f}', COALESCE(json_extract(data, '$.{f}'), 0) + ?" for f in inc
    )
    # Table is allowlisted by _Collection, fields pass _IDENT, values are bound.
    # (Bandit honours only a same-line nosec, so each SQL line carries one.)
    table = col._name
    sql = (
        f"INSERT INTO {table} (id, data) VALUES (?, ?) "  # nosec B608
        f"ON CONFLICT(id) DO UPDATE SET data = json_set(data, {sets}, '$.updated_at', ?)"  # nosec B608
    )
    params = [str(doc_id), json.dumps(seed, default=str), *inc.values(), now]
    conn = await col._conn()
    await conn.execute(sql, params)
    await conn.commit()


async def purge_expired(col: Any, field: str, now_ts: float) -> int:
    """Delete rows whose epoch-seconds *field* is past, missing or not a number.

    Readers already treat a missing or non-numeric expiry as expired (fail
    closed), so such rows are dead weight; a non-numeric one would also make
    the Python ``$gt`` matcher raise for every query on the table.
    Returns the number of rows deleted.
    """
    _checked(field)
    expr = f"json_extract(data, '$.{field}')"
    # Table is allowlisted by _Collection, field passes _IDENT, the cutoff is bound.
    where = f"typeof({expr}) NOT IN ('integer', 'real') OR {expr} < ?"
    sql = f"DELETE FROM {col._name} WHERE {where}"  # nosec B608
    conn = await col._conn()
    cur = await conn.execute(sql, [now_ts])
    await conn.commit()
    return max(int(cur.rowcount or 0), 0)


def _indexed(col: Any) -> list[str]:
    from packages.storage.sqlite import _INDEXED_FIELDS

    return list(_INDEXED_FIELDS.get(col._name, []))


async def insert_if_absent(col: Any, doc_id: str, doc: dict[str, Any]) -> bool:
    """Insert *doc* as *doc_id* unless that id exists; True when this call inserted it.

    One ``INSERT ... ON CONFLICT(id) DO NOTHING``: of any number of concurrent
    callers (also across processes sharing the file) exactly one gets True.
    Indexed columns are filled the way ``_Collection.insert_one`` fills them.
    """
    data = {**doc, "_id": doc_id}
    indexed = _indexed(col)
    cols = ", ".join(["id", "data", *indexed])
    marks = ", ".join("?" * (2 + len(indexed)))
    params = [str(doc_id), json.dumps(data, default=str), *(str(data.get(f, "")) for f in indexed)]
    # Table is allowlisted by _Collection, columns come from _INDEXED_FIELDS, values are bound.
    sql = f"INSERT INTO {col._name} ({cols}) VALUES ({marks}) ON CONFLICT(id) DO NOTHING"  # nosec B608
    conn = await col._conn()
    cur = await conn.execute(sql, params)
    await conn.commit()
    return int(cur.rowcount or 0) == 1


def _condition(field: str, expected: Any) -> tuple[str, list[Any]]:
    """One bound SQL condition: equality, ``None`` as missing, or ``("lt", value)``."""
    _checked(field)
    expr = f"json_extract(data, '$.{field}')"
    if expected is None:
        return f"{expr} IS NULL", []
    if isinstance(expected, tuple):
        if len(expected) != 2 or expected[0] != "lt":
            raise ValueError(f"unsupported condition for {field!r}: {expected!r}")
        return f"{expr} < ?", [expected[1]]
    if isinstance(expected, bool):
        return f"{expr} = ?", [int(expected)]
    if isinstance(expected, (str, int, float)):
        return f"{expr} = ?", [expected]
    raise ValueError(f"unsupported value type for {field!r}: {type(expected).__name__}")


def _all_of(expect: dict[str, Any]) -> tuple[str, list[Any]]:
    parts: list[str] = []
    params: list[Any] = []
    for field, expected in expect.items():
        sql, values = _condition(field, expected)
        parts.append(sql)
        params.extend(values)
    return " AND ".join(parts) or "1", params


def _where(expect: dict[str, Any], any_of: Sequence[dict[str, Any]] | None) -> tuple[str, list[Any]]:
    sql, params = _all_of(expect)
    if any_of:
        alternatives = [_all_of(group) for group in any_of]
        sql += " AND (" + " OR ".join(f"({alt})" for alt, _ in alternatives) + ")"
        for _, values in alternatives:
            params.extend(values)
    return sql, params


async def compare_and_set(
    col: Any, doc_id: str, expect: dict[str, Any], set_: dict[str, Any],
    *, any_of: Sequence[dict[str, Any]] | None = None,
) -> bool:
    """Set ``set_`` fields on *doc_id* only if its stored fields match; True when applied.

    One ``UPDATE ... WHERE``, so the check and the write cannot interleave with
    another writer. ``expect`` maps field to the required value: a scalar for
    equality, ``None`` for "missing or null", ``("lt", v)`` for "less than v".
    ``any_of`` adds a list of such dicts of which at least one must match
    (each dict is ANDed inside). Values are written as JSON, so booleans,
    lists and dicts keep their type; indexed columns are kept in step.
    """
    if not set_:
        raise ValueError("compare_and_set needs at least one field to set")
    _checked(*set_)
    indexed = set(_indexed(col))
    assigns = ", ".join(f"'$.{f}', json(?)" for f in set_)
    set_sql = f"data = json_set(data, {assigns})"
    params: list[Any] = [json.dumps(v, default=str) for v in set_.values()]
    for field in (f for f in set_ if f in indexed):
        set_sql += f", {field} = ?"
        params.append(str(set_[field]))
    where_sql, where_params = _where(expect, any_of)
    # Table is allowlisted by _Collection, fields pass _IDENT, values are bound.
    sql = f"UPDATE {col._name} SET {set_sql} WHERE id = ? AND {where_sql}"  # nosec B608
    conn = await col._conn()
    cur = await conn.execute(sql, [*params, str(doc_id), *where_params])
    await conn.commit()
    return int(cur.rowcount or 0) == 1


async def increment_and_get(col: Any, doc_id: str, field: str, *, by: int = 1) -> int | None:
    """Add *by* to *field* of an existing *doc_id* and return the new value, in one statement.

    ``UPDATE ... RETURNING`` reads the value this call wrote, so two concurrent
    callers can never be handed the same number (an increment followed by a
    separate read could). Returns ``None`` when the document does not exist.
    """
    _checked(field)
    expr = f"json_extract(data, '$.{field}')"
    # Table is allowlisted by _Collection, field passes _IDENT, the step is bound.
    sql = (
        f"UPDATE {col._name} SET data = json_set(data, '$.{field}', COALESCE({expr}, 0) + ?) "  # nosec B608
        f"WHERE id = ? RETURNING {expr}"  # nosec B608
    )
    conn = await col._conn()
    cur = await conn.execute(sql, [by, str(doc_id)])
    row = await cur.fetchone()
    await cur.close()
    await conn.commit()
    return int(row[0]) if row else None

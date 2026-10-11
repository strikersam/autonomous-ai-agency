"""packages/storage/sqlite_atomic.py — atomic helpers for the SQLite backend.

``SQLiteStore``'s ``update_one(upsert=True)`` with ``$inc`` is a read, a Python
add and a write, so two concurrent increments can both read the same total and
one is lost (and the first upsert drops the ``$inc`` entirely). The durable
token ledger needs exact totals, so it uses :func:`atomic_increment` here: one
``INSERT ... ON CONFLICT DO UPDATE`` statement, which SQLite executes atomically
(also across processes sharing the DB file).

:func:`purge_expired` is the SQLite substitute for MongoDB TTL indexes.

Both helpers take a ``SQLiteStore`` collection and work on its own connection,
so they share the store's file, WAL mode and busy timeout. Table names come from
the collection (already checked against the store's allowlist); field names are
validated as bare identifiers; every value is bound as a parameter.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

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
    sql = (  # nosec B608 - table is allowlisted by _Collection, fields pass _IDENT, values bound
        f"INSERT INTO {col._name} (id, data) VALUES (?, ?) "
        f"ON CONFLICT(id) DO UPDATE SET data = json_set(data, {sets}, '$.updated_at', ?)"
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
    sql = (  # nosec B608 - table is allowlisted by _Collection, field passes _IDENT
        f"DELETE FROM {col._name} WHERE typeof({expr}) NOT IN ('integer', 'real') OR {expr} < ?"
    )
    conn = await col._conn()
    cur = await conn.execute(sql, [now_ts])
    await conn.commit()
    return max(int(cur.rowcount or 0), 0)

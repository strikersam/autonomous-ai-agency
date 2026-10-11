"""Child-process body for the cross-process atomic increment test."""
from __future__ import annotations

import asyncio


def increment_many(db_path: str, doc_id: str, times: int) -> None:
    """Open an independent SQLiteStore on *db_path* and increment *times* times."""
    from packages.storage.sqlite import SQLiteStore
    from packages.storage.sqlite_atomic import atomic_increment

    async def _run() -> None:
        store = SQLiteStore(db_path)
        try:
            for _ in range(times):
                await atomic_increment(store.user_token_usage, doc_id, {"tokens": 1})
        finally:
            await store.close()

    asyncio.run(_run())

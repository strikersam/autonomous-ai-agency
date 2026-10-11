"""tasks/screenshots.py — screenshots attached to a task's verification report.

Rule 49 asks for screenshots as evidence for any UI change. The agent loop
captures them (agent/ui_evidence.py) and stores each one here; the report then
cites it as ``screenshot:<id> <page url>`` and the dashboard loads the image
through ``GET /api/tasks/{task_id}/screenshots/{shot_id}``, which only serves
an id the task's own report cites.

Stored in the ``task_screenshots`` collection next to ``tasks`` (MongoDB is the
durable store); a bounded in-memory map serves tests and local dev.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections import OrderedDict
from typing import Any

log = logging.getLogger("qwen-proxy")

_MEMORY_MAX = 64
_memory: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
SHOT_ID_RE = re.compile(r"^shot_[0-9a-f]{16}$")
EVIDENCE_RE = re.compile(r"^screenshot:(shot_[0-9a-f]{16})\b")


def _collection() -> Any:
    from tasks.store import get_task_store

    db = getattr(get_task_store(), "_db", None)
    if db is None or type(db).__module__.startswith("packages.storage"):
        return None
    return db["task_screenshots"]


async def save_screenshot(image: bytes, *, page_url: str, media_type: str = "image/jpeg") -> str:
    """Store *image* and return its id."""
    shot_id = f"shot_{uuid.uuid4().hex[:16]}"
    doc = {"_id": shot_id, "image": image, "media_type": media_type,
           "page_url": page_url[:1000], "created_at": time.time()}
    coll = _collection()
    if coll is not None:
        await coll.insert_one(doc)
    else:
        _memory[shot_id] = doc
        while len(_memory) > _MEMORY_MAX:
            _memory.popitem(last=False)
    return shot_id


async def get_screenshot(shot_id: str) -> dict[str, Any] | None:
    """Return ``{image, media_type, page_url}`` or None."""
    if not SHOT_ID_RE.match(shot_id or ""):
        return None
    coll = _collection()
    if coll is not None:
        return await coll.find_one({"_id": shot_id})
    return _memory.get(shot_id)


def cited_shot_ids(task: Any) -> set[str]:
    """Screenshot ids the task's verification report cites as evidence."""
    v = getattr(task, "verification", None)
    out: set[str] = set()
    for line in getattr(v, "evidence", None) or []:
        m = EVIDENCE_RE.match(str(line))
        if m:
            out.add(m.group(1))
    return out


def evidence_line(shot_id: str, page_url: str) -> str:
    """The report line that cites a stored screenshot."""
    return f"screenshot:{shot_id} {page_url}"

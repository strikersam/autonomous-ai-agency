"""tasks/improvement_throttle.py — keep self-improvement from flooding the queue.

Production 2026-10-15: the improvement loop's record of what it had already
filed lives in ``.claude/state/improvement-state.json``, which is gitignored and
so wiped on every deploy. After each deploy it re-filed the same ~14 fixes (TODO
markers, files without tests) as new, on top of the earlier copies, which had
failed. With no pass in 24 hours, those tasks used the free model quota and
produced nothing.

A scheduled ``auto-improvement`` job now becomes a task only when no task with
the same title is open or failed in the last day, and fewer than
``MAX_OPEN_IMPROVEMENT_TASKS`` self-improvement tasks are open. A skipped job is
not lost: the loop re-detects the issue on its next scan or deploy.
"""

from __future__ import annotations

import time
from typing import Any

from tasks.models import TaskStatus, _coerce_ts

AUTO_IMPROVEMENT_TAG = "auto-improvement"
MAX_OPEN_IMPROVEMENT_TASKS = 5
_OPEN = (TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW,
         TaskStatus.BLOCKED, TaskStatus.NEEDS_CLARIFICATION)
_PAGE = 200
_MAX_PAGES = 5
# Newest failed tasks checked for a duplicate title: the copies filed before
# the last deploy are among the most recent failures. A fix that failed longer
# ago than _RETRY_AFTER_SECONDS may be tried again.
_RECENT_FAILED = 200
_RETRY_AFTER_SECONDS = 24 * 3600


async def _tagged(store: Any, status: TaskStatus, *, pages: int) -> list[Any]:
    found: list[Any] = []
    for page in range(pages):
        batch = await store.list_all(status=status, limit=_PAGE, offset=page * _PAGE, include_log=False)
        found.extend(t for t in batch if AUTO_IMPROVEMENT_TAG in (t.tags or []))
        if len(batch) < _PAGE:
            break
    return found


async def skip_reason(store: Any, title: str, tags: list[str]) -> str | None:
    """Why this self-improvement job should not become a task, or None to proceed."""
    if AUTO_IMPROVEMENT_TAG not in tags:
        return None
    open_tasks: list[Any] = []
    for status in _OPEN:
        open_tasks.extend(await _tagged(store, status, pages=_MAX_PAGES))
    if any(t.title == title for t in open_tasks):
        return "a task for this fix is already open"
    cutoff = time.time() - _RETRY_AFTER_SECONDS
    recent_failed = [t for t in await _tagged(store, TaskStatus.FAILED, pages=_RECENT_FAILED // _PAGE)
                     if (_coerce_ts(t.updated_at) or 0) >= cutoff]
    if any(t.title == title for t in recent_failed):
        return "the last attempt at this fix failed; not repeating it"
    if len(open_tasks) >= MAX_OPEN_IMPROVEMENT_TASKS:
        return f"{len(open_tasks)} self-improvement tasks are already open (cap {MAX_OPEN_IMPROVEMENT_TASKS})"
    return None

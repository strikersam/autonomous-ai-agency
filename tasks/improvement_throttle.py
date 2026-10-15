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
# A fix that failed longer ago than _RETRY_AFTER_SECONDS may be tried again.
# Failed tasks are read newest-created first until they were created more than
# _FAILED_LOOKBACK_SECONDS ago (a refiled copy fails soon after it is created),
# bounded by _MAX_FAILED_PAGES so a large backlog cannot make this unbounded.
_RETRY_AFTER_SECONDS = 24 * 3600
_FAILED_LOOKBACK_SECONDS = 2 * _RETRY_AFTER_SECONDS
_MAX_FAILED_PAGES = 10


async def _tagged(store: Any, status: TaskStatus, *, pages: int) -> list[Any]:
    found: list[Any] = []
    for page in range(pages):
        batch = await store.list_all(status=status, limit=_PAGE, offset=page * _PAGE, include_log=False)
        found.extend(t for t in batch if AUTO_IMPROVEMENT_TAG in (t.tags or []))
        if len(batch) < _PAGE:
            break
    return found


async def _recently_failed(store: Any) -> list[Any]:
    """auto-improvement tasks that failed within the retry window."""
    now = time.time()
    found: list[Any] = []
    for page in range(_MAX_FAILED_PAGES):
        batch = await store.list_all(status=TaskStatus.FAILED, limit=_PAGE, offset=page * _PAGE,
                                     include_log=False)
        found.extend(t for t in batch if AUTO_IMPROVEMENT_TAG in (t.tags or [])
                     and (_coerce_ts(t.updated_at) or 0) >= now - _RETRY_AFTER_SECONDS)
        oldest = _coerce_ts(batch[-1].created_at) if batch else None
        if len(batch) < _PAGE or (oldest or 0) < now - _FAILED_LOOKBACK_SECONDS:
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
    if any(t.title == title for t in await _recently_failed(store)):
        return "the last attempt at this fix failed; not repeating it"
    if len(open_tasks) >= MAX_OPEN_IMPROVEMENT_TASKS:
        return f"{len(open_tasks)} self-improvement tasks are already open (cap {MAX_OPEN_IMPROVEMENT_TASKS})"
    return None

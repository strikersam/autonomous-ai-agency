"""services/company_cleanup.py — remove the scheduled work a deleted company leaves behind.

Onboarding a company creates state outside the company-graph rows: cron
schedules tagged ``company:<id>`` (``CompanyAgencyService.activate_company``),
CEO directives tagged the same way (``agent/agency.py``), and the tasks those
schedules and directives spawn (``tasks/automation.py`` copies the tags onto the
task). Deleting the company must remove all of it, and anything that slipped
through (companies deleted before this existed, a crash mid delete, a directive
racing the delete) must be found and removed without a manual script.

Three entry points share the helpers here:

* ``purge_company_schedules`` / ``cancel_company_tasks``: the cascade run by
  ``CompanyGraphService.delete_company``.
* ``reap_orphaned_company_state``: the sweep run by the ephemeral reaper loop.
* ``company_is_gone``: the guard the scheduler hook and the task dispatcher call
  before running anything tagged with a company.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Iterable

log = logging.getLogger("qwen-proxy")

COMPANY_TAG_PREFIX = "company:"
_ACTOR = "system:company-cleanup"
_PAGE = 200


def company_id_from_tags(tags: Iterable[str] | None) -> str | None:
    """The company a ``company:<id>`` tag points at, else None.

    ``company-agency`` (the marker tag every agency schedule also carries) has a
    hyphen, not a colon, so it never matches.
    """
    for tag in tags or []:
        if isinstance(tag, str) and tag.startswith(COMPANY_TAG_PREFIX) and len(tag) > len(COMPANY_TAG_PREFIX):
            return tag[len(COMPANY_TAG_PREFIX):]
    return None


async def company_is_gone(company_id: str, cache: dict[str, bool] | None = None) -> bool:
    """True only when the company store positively reports the company missing.

    Fails safe: a lookup error, or a store that holds no companies at all (a
    wiped or not yet bootstrapped store cannot tell us anything), reads as "not
    gone" so a storage hiccup can never delete live work.
    """
    if cache is not None and company_id in cache:
        return cache[company_id]
    gone = False
    try:
        from services.company_graph_store import get_company_graph_store

        store = get_company_graph_store()
        if await store.get_company(company_id) is None:
            gone = bool(await store.list_companies(limit=1))
    except Exception:  # noqa: BLE001 - never delete on a lookup error
        log.exception("company cleanup: lookup failed for %s; treating it as alive", company_id)
    if cache is not None:
        cache[company_id] = gone
    return gone


async def purge_company_schedules(company_id: str) -> dict[str, int]:
    """Remove all ``company:<id>`` schedules from memory, APScheduler and the store."""
    from packages.scheduler.scheduler import get_scheduler

    return await get_scheduler().delete_by_tag(f"{COMPANY_TAG_PREFIX}{company_id}")


def _task_company_id(task: Any) -> str | None:
    return getattr(task, "company_id", None) or company_id_from_tags(getattr(task, "tags", None))


def _open_statuses() -> list[Any]:
    from tasks.models import TaskStatus

    # FAILED is included: the dispatcher's reconciler re-queues failed tasks.
    return [TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW,
            TaskStatus.BLOCKED, TaskStatus.NEEDS_CLARIFICATION, TaskStatus.FAILED]


async def _open_company_tasks(store: Any) -> list[Any]:
    """Every not yet finished task that is bound to some company."""
    found: list[Any] = []
    for status in _open_statuses():
        offset = 0
        while True:
            page = await store.list_all(status=status, limit=_PAGE, offset=offset)
            found.extend(t for t in page if _task_company_id(t))
            if len(page) < _PAGE:
                break
            offset += _PAGE
    return found


async def _cancel_task(store: Any, task: Any, company_id: str) -> bool:
    from tasks.models import TaskStatus

    try:
        task.status = TaskStatus.WONT_DO
        task.pending_agent_run = False
        task.blocked_reason = None
        task.review_reason = None
        task.completed_at = time.time()
        task.add_log(
            f"Cancelled: company {company_id} no longer exists",
            event_type="status_changed", actor=_ACTOR, task_status=TaskStatus.WONT_DO,
            metadata={"company_id": company_id},
        )
        await store.update(task)
        return True
    except Exception:  # noqa: BLE001 - one bad row must not abort the cascade
        log.exception("company cleanup: could not cancel task %s", getattr(task, "task_id", "?"))
        return False


async def cancel_company_tasks(company_id: str, store: Any = None) -> dict[str, int]:
    """Cancel (``wont_do``, no longer dispatchable) every open task of a company.

    Finished tasks are kept as history. A task already running finishes its
    current step; it is never picked up again.
    """
    if store is None:
        from tasks.store import get_task_store

        store = get_task_store()
    summary = {"cancelled": 0, "failed": 0}
    for task in await _open_company_tasks(store):
        if _task_company_id(task) != company_id:
            continue
        ok = await _cancel_task(store, task, company_id)
        summary["cancelled" if ok else "failed"] += 1
    return summary


async def filter_orphaned_tasks(store: Any, tasks: list[Any]) -> list[Any]:
    """Drop (and cancel) tasks whose company is gone; return the runnable rest."""
    cache: dict[str, bool] = {}
    live: list[Any] = []
    for task in tasks:
        cid = _task_company_id(task)
        if cid and await company_is_gone(cid, cache):
            log.warning("Dispatcher: task %s belongs to deleted company %s; cancelling", task.task_id, cid)
            await _cancel_task(store, task, cid)
            continue
        live.append(task)
    return live


async def reap_orphaned_schedules() -> int:
    """Delete schedules tagged for companies that no longer exist."""
    from packages.scheduler.scheduler import get_scheduler

    try:
        sched = get_scheduler()
    except RuntimeError:  # scheduler not started in this process
        return 0
    cache: dict[str, bool] = {}
    removed = 0
    for tag in sorted(await sched.tag_values(COMPANY_TAG_PREFIX)):
        cid = company_id_from_tags([tag])
        if cid and await company_is_gone(cid, cache):
            res = await sched.delete_by_tag(tag)
            removed += res["removed"]
            log.info("Orphan schedule reaper: company %s is gone; removed %d schedule(s), %d failed",
                     cid, res["removed"], res["failed"])
    return removed


async def reap_orphaned_tasks() -> int:
    """Cancel open tasks bound to companies that no longer exist."""
    from tasks.store import get_task_store

    store = get_task_store()
    cache: dict[str, bool] = {}
    cancelled = 0
    for task in await _open_company_tasks(store):
        cid = _task_company_id(task)
        if cid and await company_is_gone(cid, cache) and await _cancel_task(store, task, cid):
            cancelled += 1
    if cancelled:
        log.info("Orphan task reaper: cancelled %d task(s) of deleted companies", cancelled)
    return cancelled


async def reap_orphaned_company_state() -> dict[str, int]:
    """One sweep: orphaned schedules first (stops new tasks), then orphaned tasks."""
    summary = {"schedules": 0, "tasks": 0}
    for key, sweep in (("schedules", reap_orphaned_schedules), ("tasks", reap_orphaned_tasks)):
        try:
            summary[key] = await sweep()
        except Exception:  # noqa: BLE001 - one sweep failing must not skip the other
            log.exception("Orphan %s reaper failed", key)
    return summary

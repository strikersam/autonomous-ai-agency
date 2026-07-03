"""tasks/store.py — MongoDB-backed task store.

Falls back to in-memory storage when MongoDB is unavailable so the
system degrades gracefully during development.
"""

from __future__ import annotations

import inspect
import logging
import os
import time
from typing import Any

from tasks.models import Task, TaskStatus, TaskPriority

log = logging.getLogger("qwen-proxy")

# Owner id used for tasks the agency creates for itself (scheduler/playbook,
# self-healing, error-interceptor, self-bootstrap). Surfaced on every operator's
# board so autonomous work is visible, not hidden behind owner-scoping.
_AGENCY_OWNER_ID = "system"


class TaskStore:
    """Persistent task store backed by MongoDB.

    Uses the same motor client pattern as the rest of the application.
    Falls back to an in-memory dict when no motor client is injected.
    """

    def __init__(self, db: Any = None) -> None:
        """
        Args:
            db: motor AsyncIOMotorDatabase instance, or None for in-memory mode.
        """
        self._db = db
        self._mem: dict[str, dict] = {}  # fallback in-memory store
        self._mode = "mongo" if db is not None else "memory"
        if self._mode == "memory":
            log.warning("TaskStore: running in in-memory mode (no MongoDB). Data will be lost on restart.")

    @property
    def _collection(self):
        return self._db["tasks"] if self._db is not None else None

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def create(self, task: Task) -> Task:
        doc = task.model_dump()
        if self._mode == "mongo":
            await self._collection.insert_one({**doc, "_id": task.task_id})
        else:
            self._mem[task.task_id] = doc
        return task

    async def get(self, task_id: str, owner_id: str | None = None) -> Task | None:
        """Fetch a task by ID.  If owner_id is set, enforces ownership."""
        if self._mode == "mongo":
            query: dict[str, Any] = {"task_id": task_id}
            if owner_id:
                query["owner_id"] = owner_id
            doc = await self._collection.find_one(query, {"_id": 0})
        else:
            doc = self._mem.get(task_id)
            if doc and owner_id and doc.get("owner_id") != owner_id:
                return None
        return Task.model_validate(doc) if doc else None

    async def find_by_source_id(self, source_id: str) -> Task | None:
        """Return the task previously created for an external ``source_id``
        (e.g. ``owner/repo#123``), or None. Used by issue-intake idempotency
        (Autonomy Charter G3) so replaying a webhook never duplicates a task.
        """
        if not source_id:
            return None
        if self._mode == "mongo":
            doc = await self._collection.find_one({"source_id": source_id}, {"_id": 0})
        else:
            doc = next(
                (d for d in self._mem.values() if d.get("source_id") == source_id),
                None,
            )
        return Task.model_validate(doc) if doc else None

    async def update(self, task: Task) -> Task:
        task.touch()
        doc = task.model_dump()
        if self._mode == "mongo":
            await self._collection.replace_one(
                {"task_id": task.task_id},
                {**doc, "_id": task.task_id},
                upsert=True,
            )
        else:
            self._mem[task.task_id] = doc
        return task

    async def delete(self, task_id: str, owner_id: str | None = None) -> bool:
        if self._mode == "mongo":
            q: dict[str, Any] = {"task_id": task_id}
            if owner_id:
                q["owner_id"] = owner_id
            result = await self._collection.delete_one(q)
            return result.deleted_count > 0
        else:
            if task_id in self._mem:
                if owner_id and self._mem[task_id].get("owner_id") != owner_id:
                    return False
                del self._mem[task_id]
                return True
            return False

    # ── Queries ───────────────────────────────────────────────────────────────

    async def list_for_user(
        self,
        owner_id: str,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        agent_id: str | None = None,
        tag: str | None = None,
        limit: int = 50,
        offset: int = 0,
        include_system: bool = True,
    ) -> list[Task]:
        """List tasks for a specific user with optional filters.

        ``include_system`` (default True) also surfaces the shared autonomous
        queue (tasks the agency creates for itself with ``owner_id="system"`` —
        scheduler/playbook, self-healing, error-interceptor, self-bootstrap).
        Without this, agent-created tasks were returned by the admin/global API
        but filtered out of the owner-scoped Task Board, so the human operator
        could never see what the agents were doing.
        """
        owner_match: Any = (
            {"$in": [owner_id, _AGENCY_OWNER_ID]} if include_system else owner_id
        )
        query: dict[str, Any] = {"owner_id": owner_match}
        if status:
            query["status"] = status.value
        if priority:
            query["priority"] = priority.value
        if agent_id:
            query["agent_id"] = agent_id
        if tag:
            query["tags"] = tag

        def _owner_ok(v: dict[str, Any]) -> bool:
            o = v.get("owner_id")
            return o == owner_id or (include_system and o == _AGENCY_OWNER_ID)

        if self._mode == "mongo":
            cursor = self._collection.find(query, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit)
            docs = await cursor.to_list(length=limit)
        else:
            docs = [
                v for v in self._mem.values()
                if _owner_ok(v)
                and (not status or v.get("status") == status.value)
                and (not priority or v.get("priority") == priority.value)
                and (not agent_id or v.get("agent_id") == agent_id)
                and (not tag or tag in (v.get("tags") or []))
            ]
            docs.sort(key=lambda d: d.get("created_at", 0), reverse=True)
            docs = docs[offset: offset + limit]

        return [Task.model_validate(d) for d in docs]

    async def list_all(
        self,
        *,
        status: TaskStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        """Admin-only: list all tasks across all users."""
        query: dict[str, Any] = {}
        if status:
            query["status"] = status.value

        if self._mode == "mongo":
            cursor = self._collection.find(query, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit)
            docs = await cursor.to_list(length=limit)
        else:
            docs = list(self._mem.values())
            if status:
                docs = [d for d in docs if d.get("status") == status.value]
            docs.sort(key=lambda d: d.get("created_at", 0), reverse=True)
            docs = docs[offset: offset + limit]

        return [Task.model_validate(d) for d in docs]

    async def list_pending(self, *, limit: int = 50) -> list[Task]:
        """Return tasks queued for agent execution."""
        if self._mode == "mongo":
            cursor = self._collection.find(
                {"pending_agent_run": True, "status": {"$in": [TaskStatus.TODO.value, TaskStatus.IN_PROGRESS.value]}},
                {"_id": 0},
            ).sort("updated_at", 1).limit(limit)
            docs = await cursor.to_list(length=limit)
        else:
            docs = [
                value for value in self._mem.values()
                if value.get("pending_agent_run") is True
                and value.get("status") in {TaskStatus.TODO.value, TaskStatus.IN_PROGRESS.value}
            ]
            docs.sort(key=lambda d: d.get("updated_at", d.get("created_at", 0)))
            docs = docs[:limit]
        return [Task.model_validate(d) for d in docs]

    async def list_blocked(self, *, limit: int = 50) -> list[Task]:
        """Return BLOCKED tasks that are candidates for auto-retry."""
        if self._mode == "mongo":
            cursor = self._collection.find(
                {"status": TaskStatus.BLOCKED.value},
                {"_id": 0},
            ).sort("updated_at", 1).limit(limit)
            docs = await cursor.to_list(length=limit)
        else:
            docs = [
                value for value in self._mem.values()
                if value.get("status") == TaskStatus.BLOCKED.value
            ]
            docs.sort(key=lambda d: d.get("updated_at", d.get("created_at", 0)))
            docs = docs[:limit]
        return [Task.model_validate(d) for d in docs]

    async def count_by_agent(
        self,
        *,
        owner_id: str | None = None,
        statuses: set[TaskStatus] | None = None,
    ) -> dict[str, int]:
        """Return task counts keyed by ``agent_id`` for the requested statuses."""
        status_values = {status.value for status in statuses} if statuses else None

        if self._mode == "mongo":
            match: dict[str, Any] = {"agent_id": {"$ne": None}}
            if owner_id is not None:
                match["owner_id"] = owner_id
            if status_values is not None:
                match["status"] = {"$in": sorted(status_values)}
            pipeline = [
                {"$match": match},
                {"$group": {"_id": "$agent_id", "count": {"$sum": 1}}},
            ]
            cursor = self._collection.aggregate(pipeline)
            if inspect.isawaitable(cursor):
                cursor = await cursor
            rows = await cursor.to_list(length=1000)
            return {
                str(row.get("_id")): int(row.get("count") or 0)
                for row in rows
                if row.get("_id")
            }

        counts: dict[str, int] = {}
        for task in self._mem.values():
            agent_id = task.get("agent_id")
            if not agent_id:
                continue
            if owner_id is not None and task.get("owner_id") != owner_id:
                continue
            if status_values is not None and task.get("status") not in status_values:
                continue
            counts[str(agent_id)] = counts.get(str(agent_id), 0) + 1
        return counts

    async def count_for_user(self, owner_id: str, *, include_system: bool = True) -> dict[str, int]:
        """Return counts per status for a user's tasks.

        Mirrors ``list_for_user``: by default also counts the shared autonomous
        queue (``owner_id="system"``) so the board column badges match the rows.
        """
        owner_match: Any = (
            {"$in": [owner_id, _AGENCY_OWNER_ID]} if include_system else owner_id
        )
        if self._mode == "mongo":
            pipeline = [
                {"$match": {"owner_id": owner_match}},
                {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            ]
            cursor = self._collection.aggregate(pipeline)
            if inspect.isawaitable(cursor):
                cursor = await cursor
            result = await cursor.to_list(length=20)
            return {r["_id"]: r["count"] for r in result}
        else:
            counts: dict[str, int] = {}
            for v in self._mem.values():
                o = v.get("owner_id")
                if o == owner_id or (include_system and o == _AGENCY_OWNER_ID):
                    s = v.get("status", "todo")
                    counts[s] = counts.get(s, 0) + 1
            return counts

    async def get_due_soon(self, within_hours: int = 24) -> list[Task]:
        """Return tasks due within the next N hours (any user)."""
        deadline = time.time() + within_hours * 3600
        if self._mode == "mongo":
            cursor = self._collection.find(
                {"due_date": {"$lte": deadline, "$ne": None}, "status": {"$nin": ["done"]}},
                {"_id": 0},
            ).sort("due_date", 1).limit(20)
            docs = await cursor.to_list(length=20)
        else:
            docs = [
                v for v in self._mem.values()
                if v.get("due_date") and v["due_date"] <= deadline and v.get("status") != "done"
            ]
            docs.sort(key=lambda d: d.get("due_date", 0))
            docs = docs[:20]
        return [Task.model_validate(d) for d in docs]


    async def reconcile_stranded_tasks(
        self,
        *,
        active_task_ids: set[str] | None = None,
        stale_threshold_s: float = 300.0,
        auto_retry_cap: int | None = None,
    ) -> int:
        """Reset tasks that are stuck IN_PROGRESS but no longer actively executing.

        A task is considered "stranded" when all of these are true:
        - status is IN_PROGRESS and pending_agent_run is False (execution was claimed)
        - task_id is NOT in active_task_ids (not currently executing in this process)
        - updated_at is older than stale_threshold_s (execution didn't complete)

        This handles crash-recovery: after a server restart the in-memory claim
        set is empty, so all mid-flight tasks are eligible for re-queue.

        Returns the number of tasks reconciled.
        """
        import time as _time
        if auto_retry_cap is None:
            try:
                auto_retry_cap = int(os.environ.get("TASK_AUTO_RETRY_MAX", "5"))
            except (TypeError, ValueError):
                auto_retry_cap = 5
        active = active_task_ids or set()
        cutoff = _time.time() - stale_threshold_s

        if self._mode == "mongo":
            cursor = self._collection.find(
                {
                    "status": TaskStatus.IN_PROGRESS.value,
                    "pending_agent_run": False,
                    "updated_at": {"$lt": cutoff},
                },
                {"_id": 0},
            )
            stranded = await cursor.to_list(length=500)
        else:
            stranded = [
                v for v in self._mem.values()
                if v.get("status") == TaskStatus.IN_PROGRESS.value
                and v.get("pending_agent_run") is False
                and v.get("updated_at", 0) < cutoff
            ]

        reconciled = 0
        for doc in stranded:
            task_id = doc.get("task_id") or doc.get("_id")
            if not task_id or task_id in active:
                continue
            if int(doc.get("auto_retry_count") or 0) >= auto_retry_cap:
                log.warning(
                    "Reconciler: not re-queuing stranded IN_PROGRESS task %s "
                    "(auto_retry_count=%d already at cap=%d; leaves it stranded "
                    "to avoid a reconciler-overrides-cap retry storm)",
                    task_id, int(doc.get("auto_retry_count") or 0), auto_retry_cap,
                )
                continue

            task = Task.model_validate(doc)
            task.status = TaskStatus.TODO
            task.pending_agent_run = True
            task.add_log(
                f"Task re-queued by reconciler (was stranded IN_PROGRESS for "
                f">{stale_threshold_s:.0f}s without completion)",
                event_type="reconciled",
                actor="system:reconciler",
                task_status=TaskStatus.TODO,
            )
            await self.update(task)
            reconciled += 1
            log.warning(
                "Reconciler: re-queued stranded task %s (stale for >%.0fs)",
                task_id, stale_threshold_s,
            )

        # Second pass: TODO tasks that were never queued for an agent run
        # (pending_agent_run=False). These are stranded the moment they exist —
        # the dispatcher only picks up pending_agent_run=True — so re-queue them
        # regardless of staleness (CodeRabbit #724).
        if self._mode == "mongo":
            cursor = self._collection.find(
                {"status": TaskStatus.TODO.value, "pending_agent_run": False},
                {"_id": 0},
            )
            unqueued_todo = await cursor.to_list(length=500)
        else:
            unqueued_todo = [
                v for v in self._mem.values()
                if v.get("status") == TaskStatus.TODO.value
                and v.get("pending_agent_run") is False
            ]

        for doc in unqueued_todo:
            task_id = doc.get("task_id") or doc.get("_id")
            if not task_id or task_id in active:
                continue
            task = Task.model_validate(doc)
            task.pending_agent_run = True
            task.add_log(
                "Task re-queued by reconciler (TODO was never queued for an agent run)",
                event_type="reconciled",
                actor="system:reconciler",
                task_status=TaskStatus.TODO,
            )
            await self.update(task)
            reconciled += 1
            log.info("Reconciler: re-queued unqueued TODO task %s", task_id)

        # Third pass (PR #923): FAILED tasks that haven't exceeded the auto-retry
        # cap. Previously, once a task hit FAILED status it was permanently stuck
        # (pending_agent_run=False, never picked up by the dispatcher). This meant
        # every transient failure (LLM timeout, NVIDIA 410, brain connection error
        # that slipped through) permanently killed the task. Now we re-queue FAILED
        # tasks that are under the retry cap so they get another chance after the
        # backend recovers. Tasks that have hit the cap stay FAILED (operator must
        # manually re-queue or delete them).
        #
        # PR #936: MIN_RETRY_AGE_S gate — don't re-queue a FAILED task until it
        # has been FAILED for at least 120s. Without this gate, the reconciler
        # re-queues failed tasks instantly, the dispatcher picks them up, they
        # fail again (e.g. brain is down), and the cycle repeats every few
        # seconds — saturating the CPU and making login time out. The 120s
        # cooldown gives the brain/provider time to recover between retries.
        import time as _retry_time
        MIN_RETRY_AGE_S = 120
        now_s = _retry_time.time()

        if self._mode == "mongo":
            cursor = self._collection.find(
                {"status": TaskStatus.FAILED.value},
                {"_id": 0},
            )
            failed_docs = await cursor.to_list(length=500)
        else:
            failed_docs = [
                v for v in self._mem.values()
                if v.get("status") == TaskStatus.FAILED.value
            ]

        for doc in failed_docs:
            task_id = doc.get("task_id") or doc.get("_id")
            if not task_id or task_id in active:
                continue
            retry_count = int(doc.get("auto_retry_count") or 0)
            if retry_count >= auto_retry_cap:
                continue  # at cap — leave FAILED, operator must intervene

            # Age gate: don't re-queue a FAILED task until it has cooled down.
            # This breaks the fail → re-queue → fail → re-queue hot loop that
            # saturates the CPU when the brain is down.
            updated_at = doc.get("updated_at")
            if updated_at is not None:
                age_s = now_s - float(updated_at)
                if age_s < MIN_RETRY_AGE_S:
                    continue  # too soon — let the brain recover first

            task = Task.model_validate(doc)
            task.status = TaskStatus.TODO
            task.pending_agent_run = True
            task.add_log(
                f"Task re-queued by reconciler (was FAILED, auto_retry_count={retry_count} < cap={auto_retry_cap})",
                event_type="reconciled",
                actor="system:reconciler",
                task_status=TaskStatus.TODO,
            )
            await self.update(task)
            reconciled += 1
            log.info("Reconciler: re-queued FAILED task %s (retry %d/%d)", task_id, retry_count, auto_retry_cap)

        if reconciled:
            log.info("Reconciler: reset %d stranded task(s) to TODO/pending", reconciled)
        return reconciled


_global_store: TaskStore | None = None


def get_task_store() -> TaskStore:
    """Get or create the global task store instance."""
    global _global_store
    if _global_store is None:
        _global_store = TaskStore()
    return _global_store


def set_task_store(store: TaskStore) -> None:
    """Set the global task store instance (e.g., during app startup with MongoDB)."""
    global _global_store
    _global_store = store

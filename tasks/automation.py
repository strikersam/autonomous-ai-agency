"""Helpers that turn scheduler and playbook activity into real tasks."""

from __future__ import annotations

import logging

from tasks.models import TaskStatus
from tasks.models import Task
from tasks.service import TaskWorkflowService
from tasks.store import TaskStore, get_task_store


log = logging.getLogger("qwen-proxy")


class TaskAutomationService:
    """Creates tasks from scheduler and playbook runs using one workflow."""

    def __init__(
        self,
        *,
        store: TaskStore | None = None,
        workflow: TaskWorkflowService | None = None,
        owner_id: str = "system",
    ) -> None:
        self.store = store or get_task_store()
        self.workflow = workflow or TaskWorkflowService(store=self.store)
        self.owner_id = owner_id

    async def handle_scheduled_job(self, job) -> Task | None:
        # Job tags (including "company:{id}" and "specialist-family:{family}")
        # are forwarded into the Task so _select_agent can route to the
        # right specialist.
        job_tags = list(getattr(job, "tags", []) or [])
        if await self._discard_if_company_gone(job, job_tags):
            return None
        from tasks.improvement_throttle import skip_reason
        reason = await skip_reason(self.store, job.name, job_tags)
        if reason:
            log.info("Scheduler: not creating a task for %s (%s): %s",
                     getattr(job, "job_id", "?"), job.name, reason)
            return None

        task = Task(
            owner_id=self.owner_id,
            title=job.name,
            description=f"Scheduled job fired from cron `{job.cron}`.",
            prompt=job.instruction,
            agent_id=getattr(job, "agent_id", None),
            runtime_id=getattr(job, "runtime_id", None),
            model_preference=getattr(job, "model", None),
            task_type=getattr(job, "task_type", "scheduled"),
            requires_approval=getattr(job, "requires_approval", False),
            tags=job_tags,
            status=getattr(job, "initial_status", None) or getattr(job, "status", None) or TaskStatus.TODO,
            source="scheduler",
            source_id=job.job_id,
            source_run_id=job.job_id,
            # The job's description is the why: for a CEO directive it is
            # "[role] directive title". Carried as the task's goal.
            goal=(getattr(job, "description", None) or None),
        )
        return await self.workflow.create_task(task, actor=f"scheduler:{job.job_id}")

    @staticmethod
    async def _discard_if_company_gone(job, job_tags: list[str]) -> bool:
        """Skip a job whose company was deleted, and reap that company's schedules.

        Self heals a schedule that survived the delete (rehydrated from the
        durable store, or created by a directive racing the delete).
        """
        from services.company_cleanup import (
            company_id_from_tags, company_is_gone, purge_company_schedules,
        )

        cid = company_id_from_tags(job_tags)
        if not cid or not await company_is_gone(cid):
            return False
        log.warning("Scheduler: job %s (%s) belongs to deleted company %s; not firing, removing its schedules",
                    getattr(job, "job_id", "?"), getattr(job, "name", "?"), cid)
        try:
            await purge_company_schedules(cid)
        except Exception:  # noqa: BLE001 - the periodic reaper retries
            log.exception("Scheduler: could not purge schedules of deleted company %s", cid)
        return True

    async def create_playbook_task(
        self,
        *,
        owner_id: str,
        playbook_id: str,
        run_id: str,
        playbook_name: str,
        step_id: int,
        instruction: str,
        agent_id: str | None = None,
        model: str | None = None,
        runtime_id: str | None = None,
        tags: list[str] | None = None,
    ) -> Task:
        task = Task(
            owner_id=owner_id,
            title=f"{playbook_name} · Step {step_id}",
            description=f"Playbook step {step_id} created from playbook {playbook_name}.",
            prompt=instruction,
            agent_id=agent_id,
            runtime_id=runtime_id,
            model_preference=model,
            task_type="scheduled",
            tags=list(tags or []),
            source="playbook",
            source_id=playbook_id,
            source_run_id=run_id,
        )
        return await self.workflow.create_task(task, actor=f"playbook:{playbook_id}")

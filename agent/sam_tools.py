"""agent/sam_tools.py — the actions SAM can take on the agency.

One catalogue, used by the natural-language router (``agent.sam_router``): each
:class:`SamTool` has a name, a one-line description the LLM reads, a Pydantic
argument model, an async handler that returns SAM's spoken reply, and a
``needs_confirmation`` rule.

Anything that is not in this catalogue is not lost: ``delegate`` turns it into an
agent task, and agents have every registered skill plus read-only web access —
under the same fail-closed approval gate as SAM's other delegation.

Safety (operator rule): a change to a safety control, or approving work parked at
the human gate, needs the Commander's explicit "confirm" in the same chat
session. Engaging the kill switch is the one exception — an emergency stop must
not wait on a second message.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, Field, ValidationError

log = logging.getLogger("qwen-proxy")

# Controls that keep autonomy bounded. Every RISK_HIGH control counts too.
_SAFETY_CONTROLS = frozenset({
    "AGENCY_KILL_SWITCH", "AGENCY_GATE_OUTWARD_FACING", "AGENCY_CANARY_ENABLED",
    "AGENT_DAILY_USD_CAP", "AGENT_DAILY_KTOKENS_CAP", "ALLOW_PAID_BRAIN",
    "SAM_AVATAR_SCOPE",
})
_ACTOR = "sam:{owner}"
_LIST_LIMIT = 10


class _NoArgs(BaseModel):
    model_config = {"extra": "forbid"}


class _Delegate(_NoArgs):
    instruction: str = Field(..., min_length=4, max_length=2000)


class _TaskList(_NoArgs):
    status: Literal["queued", "awaiting_approval", "blocked", "failed", "done"] = "queued"
    limit: int = Field(5, ge=1, le=_LIST_LIMIT)


class _TaskRef(_NoArgs):
    task: str = Field(..., min_length=2, max_length=200, description="task id or part of its title")


class _Reject(_TaskRef):
    reason: str = Field("", max_length=300)


class _ScheduleRef(_NoArgs):
    schedule: str = Field(..., min_length=2, max_length=120, description="schedule id or part of its name")


class _ControlKey(_NoArgs):
    key: str = Field(..., min_length=3, max_length=80)


class _SetControl(_ControlKey):
    value: str = Field(..., max_length=500)


class _Trends(_NoArgs):
    limit: int = Field(5, ge=1, le=_LIST_LIMIT)


class _Search(_NoArgs):
    query: str = Field(..., min_length=2, max_length=200)


Handler = Callable[[BaseModel, str], Awaitable[str]]


@dataclass(frozen=True)
class SamTool:
    name: str
    description: str
    args: type[BaseModel]
    handler: Handler
    confirm: Callable[[BaseModel], bool] = lambda _a: False
    summary: Callable[[BaseModel], str] = lambda _a: ""

    def parse(self, raw: dict[str, Any] | None) -> BaseModel | None:
        try:
            return self.args.model_validate(raw or {})
        except ValidationError:
            return None

    def arg_hint(self) -> str:
        fields = self.args.model_fields
        return ", ".join(f"{k}: {getattr(v.annotation, '__name__', str(v.annotation))}" for k, v in fields.items())


# ── safety classification ────────────────────────────────────────────────────

def is_safety_control(key: str) -> bool:
    from packages.config.control_registry import get_control
    from packages.config.control_specs import RISK_HIGH

    spec = get_control(key.upper())
    return key.upper() in _SAFETY_CONTROLS or (spec is not None and spec.risk == RISK_HIGH)


def _control_needs_confirm(args: BaseModel) -> bool:
    key = args.key.upper()
    if not is_safety_control(key):
        return False
    value = str(getattr(args, "value", "")).strip().lower()
    # Engaging the kill switch is an emergency stop: never make it wait.
    return not (key == "AGENCY_KILL_SWITCH" and value in {"true", "1", "on", "yes"})


# ── handlers ─────────────────────────────────────────────────────────────────

async def _brief(_a: BaseModel, owner: str) -> str:
    from agent.sam_orchestrator import build_brief
    return await build_brief()


async def _portfolio(_a: BaseModel, owner: str) -> str:
    from agent.sam_orchestrator import pick_up_portfolio
    return await pick_up_portfolio()


async def _triage(_a: BaseModel, owner: str) -> str:
    from agent.sam_orchestrator import run_triage
    return await run_triage()


async def _read_alerts(_a: BaseModel, owner: str) -> str:
    from agent.sam_actions import summarize_alerts
    return await summarize_alerts()


async def _fix_alerts(_a: BaseModel, owner: str) -> str:
    from agent.sam_actions import fix_alerts
    return await fix_alerts(owner)


async def _delegate(a: BaseModel, owner: str) -> str:
    from agent.sam_orchestrator import delegate_task
    return await delegate_task(a.instruction.strip().rstrip(".!?"), owner)


async def _list_tasks(a: BaseModel, owner: str) -> str:
    from tasks.models import TaskStatus
    from tasks.store import get_task_store

    store = get_task_store()
    if a.status == "queued":
        tasks = await store.list_pending(limit=a.limit)
    elif a.status == "awaiting_approval":
        tasks = await store.list_awaiting_approval(limit=a.limit)
    elif a.status == "blocked":
        tasks = await store.list_blocked(limit=a.limit)
    else:
        tasks = await store.list_all(status=TaskStatus(a.status), limit=a.limit, include_log=False)
    if not tasks:
        return f"No {a.status.replace('_', ' ')} tasks, Commander."
    lines = "; ".join(f"{t.title[:70]} ({t.task_id[:8]})" for t in tasks)
    return f"{len(tasks)} {a.status.replace('_', ' ')}: {lines}."


async def _resolve_task(ref: str, pool: list[Any]) -> tuple[Any | None, str]:
    """Match *ref* to one task in *pool* by id prefix or title fragment."""
    ref_l = ref.strip().lower()
    hits = [t for t in pool if t.task_id.lower().startswith(ref_l)] or \
           [t for t in pool if ref_l in (t.title or "").lower()]
    if len(hits) == 1:
        return hits[0], ""
    if not hits:
        return None, f"I couldn't find a task matching '{ref}'."
    names = "; ".join(f"{t.title[:50]} ({t.task_id[:8]})" for t in hits[:4])
    return None, f"'{ref}' matches {len(hits)} tasks: {names}. Which one?"


async def _decide(a: BaseModel, owner: str, *, approved: bool) -> str:
    from tasks.service import TaskWorkflowService
    from tasks.store import get_task_store

    store = get_task_store()
    task, problem = await _resolve_task(a.task, await store.list_awaiting_approval(limit=100))
    if task is None:
        return problem
    full = await store.get(task.task_id) or task
    reason = getattr(a, "reason", "") or None
    TaskWorkflowService(store=store).approve_execution(
        full, actor=_ACTOR.format(owner=owner), approved=approved, reason=reason)
    await store.update(full)
    verb = "Approved" if approved else "Rejected"
    return f"{verb}: {full.title[:80]}." + (" The agents will pick it up." if approved else "")


async def _approve(a: BaseModel, owner: str) -> str:
    return await _decide(a, owner, approved=True)


async def _reject(a: BaseModel, owner: str) -> str:
    return await _decide(a, owner, approved=False)


async def _retry(a: BaseModel, owner: str) -> str:
    from tasks.models import TaskStatus
    from tasks.service import TaskWorkflowService
    from tasks.store import get_task_store

    store = get_task_store()
    pool = await store.list_blocked(limit=50)
    pool += await store.list_all(status=TaskStatus.FAILED, limit=50, include_log=False)
    task, problem = await _resolve_task(a.task, pool)
    if task is None:
        return problem
    full = await store.get(task.task_id) or task
    TaskWorkflowService(store=store).retry(full, actor=_ACTOR.format(owner=owner))
    await store.update(full)
    return f"Re-queued: {full.title[:80]}."


def _schedules():
    from packages.scheduler.scheduler import get_scheduler
    return get_scheduler()


async def _list_schedules(_a: BaseModel, owner: str) -> str:
    jobs = _schedules().list()
    if not jobs:
        return "There are no schedules."
    active = [j for j in jobs if j.enabled]
    names = "; ".join(j.name[:50] for j in active[:8])
    return f"{len(active)} of {len(jobs)} schedules active: {names}."


async def _run_schedule(a: BaseModel, owner: str) -> str:
    sched = _schedules()
    ref = a.schedule.strip().lower()
    jobs = sched.list()
    hits = [j for j in jobs if j.job_id.lower() == ref] or [j for j in jobs if ref in j.name.lower()]
    if len(hits) != 1:
        return (f"I couldn't find a schedule matching '{a.schedule}'." if not hits else
                f"'{a.schedule}' matches {len(hits)} schedules: {'; '.join(j.name[:40] for j in hits[:4])}.")
    sched.trigger(hits[0].job_id)
    return f"Running '{hits[0].name}' now."


async def _get_control(a: BaseModel, owner: str) -> str:
    from packages.config import control_overrides
    from packages.config.control_registry import get_control

    spec = get_control(a.key.upper())
    if spec is None:
        return f"'{a.key}' isn't a platform control."
    value = control_overrides.effective_value(spec, await control_overrides.read_overrides())
    return f"{spec.label} ({spec.key}) is {value or 'unset'}."


async def _set_control(a: BaseModel, owner: str) -> str:
    from packages.config import control_overrides
    from packages.config.control_registry import get_control

    spec = get_control(a.key.upper())
    if spec is None:
        return f"'{a.key}' isn't a platform control."
    try:
        result = await control_overrides.set_overrides({spec.key: a.value}, actor=_ACTOR.format(owner=owner))
    except ValueError as exc:
        return f"That value doesn't fit {spec.label}: {exc}"
    restart = " It takes effect after a restart." if spec.key in result.get("restart_required", []) else ""
    log.info("SAM: %s set %s=%s", owner, spec.key, a.value)
    return f"Done: {spec.label} is now {a.value}.{restart}"


async def _reset_control(a: BaseModel, owner: str) -> str:
    from packages.config import control_overrides
    from packages.config.control_registry import get_control

    spec = get_control(a.key.upper())
    if spec is None:
        return f"'{a.key}' isn't a platform control."
    await control_overrides.clear_override(spec.key, actor=_ACTOR.format(owner=owner))
    log.info("SAM: %s reset %s", owner, spec.key)
    return f"Done: {spec.label} is back to its default."


async def _trends(a: BaseModel, owner: str) -> str:
    from agent.trend_watcher import get_trend_watcher

    watcher = get_trend_watcher()
    alerts = watcher.get_alerts(limit=a.limit) if watcher else []
    if not alerts:
        return "No recent trend alerts."
    return "Latest trends: " + "; ".join(str(x.get("title", ""))[:80] for x in alerts) + "."


async def _search(a: BaseModel, owner: str) -> str:
    from agent.web_reach import get_web_reach

    result = await asyncio.to_thread(get_web_reach().search_web, a.query, 5)
    hits = result.get("results") or []
    if not hits:
        return f"I found nothing for '{a.query}'."
    return "Top results: " + "; ".join(f"{h.get('title', '')[:70]} ({h.get('url', '')})" for h in hits[:3]) + "."


# ── catalogue ────────────────────────────────────────────────────────────────

def _ctl_summary(a: BaseModel) -> str:
    value = getattr(a, "value", None)
    return f"set {a.key.upper()} to {value}" if value is not None else f"reset {a.key.upper()} to its default"


TOOLS: dict[str, SamTool] = {t.name: t for t in (
    SamTool("brief", "Live status of the CEO loop, task queue, approvals and portfolio.", _NoArgs, _brief),
    SamTool("pick_up_portfolio", "Queue the top portfolio initiatives for the agents now.", _NoArgs, _portfolio),
    SamTool("triage_queue", "Run CEO triage on tasks parked for approval.", _NoArgs, _triage),
    SamTool("read_alerts", "Summarise open error and warning alerts.", _NoArgs, _read_alerts),
    SamTool("fix_alerts", "Queue fix tasks for open error alerts.", _NoArgs, _fix_alerts),
    SamTool("delegate", "Give the agents any job in plain English (code, research, docs, anything "
            "not covered by another tool). Risky work parks for approval.", _Delegate, _delegate),
    SamTool("list_tasks", "List tasks by status: queued, awaiting_approval, blocked, failed, done.",
            _TaskList, _list_tasks),
    SamTool("approve_task", "Approve a task waiting at the human gate.", _TaskRef, _approve,
            confirm=lambda _a: True, summary=lambda a: f"approve the parked task '{a.task}'"),
    SamTool("reject_task", "Reject a task waiting at the human gate.", _Reject, _reject),
    SamTool("retry_task", "Re-queue a blocked or failed task.", _TaskRef, _retry),
    SamTool("list_schedules", "List the agency's schedules.", _NoArgs, _list_schedules),
    SamTool("run_schedule", "Run a schedule now.", _ScheduleRef, _run_schedule),
    SamTool("get_control", "Read a platform control by its env-style key.", _ControlKey, _get_control),
    SamTool("set_control", "Change a platform control (env-style key, string value).", _SetControl,
            _set_control, confirm=_control_needs_confirm, summary=_ctl_summary),
    SamTool("reset_control", "Return a platform control to its default.", _ControlKey, _reset_control,
            confirm=_control_needs_confirm, summary=_ctl_summary),
    SamTool("trend_alerts", "Latest industry trend alerts the agency picked up.", _Trends, _trends),
    SamTool("web_search", "Search the web and return the top results.", _Search, _search),
)}


def catalogue_prompt() -> str:
    """The tool list as the router LLM reads it."""
    return "\n".join(f"- {t.name}({t.arg_hint()}): {t.description}" for t in TOOLS.values())

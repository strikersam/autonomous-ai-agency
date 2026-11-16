"""First-use and per-sweep CPU/DB work must not run on the event loop.

Production (2026-11-14, after #1967): the stall watchdog named three more sources, each
2-4 s: ``CEOSupervisor.sweep`` connecting to MongoDB and running ``open_goals``;
``tasks.store.list_all`` validating up to 10,000 tasks with pydantic; and
``skill_registry._extract_tech_relevance`` running hundreds of regexes per skill file.
"""
from __future__ import annotations

import asyncio
import base64
import inspect
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

from agent import skill_registry as sr
from services.ceo_ledger import CEOLedger, GoalRecord, SubtaskRecord, reset_ceo_ledger
from services.ceo_supervisor import CEOSupervisor, SupervisorConfig
from tasks import store as task_store

_BLOCK_S = 0.5
_MAX_GAP_S = 0.25


async def _max_gap_while(coro: Any) -> float:
    """Longest time the loop went without running a 10 ms ticker while ``coro`` ran."""
    stamps: list[float] = [time.monotonic()]
    stop = asyncio.Event()

    async def ticker() -> None:
        while not stop.is_set():
            stamps.append(time.monotonic())
            await asyncio.sleep(0.01)

    task = asyncio.create_task(ticker())
    await asyncio.sleep(0.05)
    try:
        await coro
    finally:
        stop.set()
        await task
    stamps.append(time.monotonic())
    return max(b - a for a, b in zip(stamps, stamps[1:]))


# ── Skill registry ───────────────────────────────────────────────────────────


class _Resp:
    status_code = 200
    headers: dict[str, str] = {}
    text = "# A skill\n\nUses react and postgres.\n"

    def json(self) -> dict[str, str]:
        return {"content": base64.b64encode(self.text.encode()).decode()}


class _Client:
    headers: dict[str, str] = {}

    async def get(self, url: str, headers: Any = None) -> _Resp:
        return _Resp()


_REG = {"owner": "o", "repo": "r", "id": "x"}


@pytest.mark.parametrize("fetcher", ["flat", "contents", "nested"])
async def test_skill_text_analysis_runs_off_the_loop(
    fetcher: str, tmp_path: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = sr.SkillRegistry(local_skills_dir=tmp_path)
    seen: list[int] = []

    def slow_scan(_raw: str) -> list[str]:
        seen.append(threading.get_ident())
        time.sleep(_BLOCK_S)  # deliberate: stands in for hundreds of regex scans
        return ["react"]

    monkeypatch.setattr(sr, "_extract_tech_relevance", slow_scan)
    client = _Client()
    holder: dict[str, Any] = {}

    async def run() -> None:
        if fetcher == "flat":
            holder["skill"] = await registry._fetch_flat_skill_file(
                client, _REG, {"path": "p/n.md", "name": "n.md", "html_url": "u"})
        elif fetcher == "contents":
            holder["skill"] = await registry._fetch_skill_file(
                client, _REG, {"path": "p", "name": "n", "html_url": "u"}, "SKILL.md")
        else:
            holder["skill"] = await registry._fetch_nested_skill_file(
                client, _REG, "cat/n/SKILL.md", "main")

    gap = await _max_gap_while(run())
    assert gap < _MAX_GAP_S, f"{fetcher} stalled the loop for {gap:.2f}s"
    assert seen and seen[0] != threading.get_ident()
    skill = holder["skill"]
    assert skill is not None and skill.tech_relevance == ["react"]


async def test_the_analysed_fields_match_the_inline_result(tmp_path: Any) -> None:
    """Moving the scan to a thread must not change what a skill looks like."""
    registry = sr.SkillRegistry(local_skills_dir=tmp_path)
    skill = await registry._fetch_flat_skill_file(
        _Client(), _REG, {"path": "p/n.md", "name": "n.md", "html_url": "u"})
    raw = _Resp.text
    assert skill is not None
    assert skill.tags == sr._extract_tags(raw)
    assert skill.tech_relevance == sr._extract_tech_relevance(raw)
    assert skill.workflow_relevance == sr._extract_workflow_relevance(raw)


# ── Task store ───────────────────────────────────────────────────────────────


async def test_a_large_task_list_is_validated_off_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[int] = []

    def slow_validate(docs: list[dict[str, Any]]) -> list[str]:
        seen.append(threading.get_ident())
        time.sleep(_BLOCK_S)  # deliberate: stands in for 10,000 pydantic validations
        return [d["id"] for d in docs]

    monkeypatch.setattr(task_store, "_validate_all", slow_validate)
    docs = [{"id": str(i)} for i in range(task_store._VALIDATE_OFFLOAD_MIN + 1)]
    holder: dict[str, Any] = {}

    async def run() -> None:
        holder["out"] = await task_store._validate_tasks(docs)

    gap = await _max_gap_while(run())
    assert gap < _MAX_GAP_S, f"validating a large list stalled the loop for {gap:.2f}s"
    assert seen and seen[0] != threading.get_ident()
    assert holder["out"] == [d["id"] for d in docs]


async def test_a_small_task_list_stays_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[int] = []
    monkeypatch.setattr(
        task_store, "_validate_all", lambda docs: seen.append(threading.get_ident()) or list(docs))
    await task_store._validate_tasks([{"id": "1"}])
    assert seen == [threading.get_ident()], "a tiny list should not pay for a thread hop"


# ── CEO supervisor ───────────────────────────────────────────────────────────


class _SlowLedger:
    """A real SQLite ledger whose reads and writes block like slow MongoDB calls."""

    def __init__(self, real: CEOLedger) -> None:
        self._real = real
        self.threads: list[tuple[str, int]] = []
        self.claim_result = True

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)

    def _slow(self, name: str, delay: float = _BLOCK_S) -> None:
        self.threads.append((name, threading.get_ident()))
        time.sleep(delay)

    def open_goals(self, *, limit: int = 100) -> list[GoalRecord]:
        self._slow("open_goals")
        return self._real.open_goals(limit=limit)

    def upsert(self, goal: GoalRecord) -> None:
        self._slow("upsert", 0.3)
        self._real.upsert(goal)

    def claim_intervention(self, goal_id: str, *, expected: int) -> bool:
        self._slow("claim", 0.3)
        return self.claim_result and self._real.claim_intervention(goal_id, expected=expected)


@pytest.fixture
def slow_ledger(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Any:
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("AGENCY_SQLITE_DB_PATH", str(tmp_path / "agency.db"))
    reset_ceo_ledger()
    ledger = _SlowLedger(CEOLedger(sqlite_path=str(tmp_path / "agency.db")))
    monkeypatch.setattr("services.ceo_ledger.get_ceo_ledger", lambda: ledger)
    yield ledger
    reset_ceo_ledger()


def _supervisor(**kw: Any) -> CEOSupervisor:
    return CEOSupervisor(config=SupervisorConfig(**{"wake_runtimes": False, **kw}))


def _stalled(goal_id: str) -> GoalRecord:
    goal = GoalRecord(goal_id=goal_id, goal="Ship it", request="Ship it",
                      last_progress_at=time.time() - 5000)
    goal.subtasks = [SubtaskRecord(subtask_id="s1", title="a", status="running")]
    return goal


async def test_sweep_loads_goals_off_the_loop(slow_ledger: _SlowLedger) -> None:
    gap = await _max_gap_while(_supervisor().sweep())
    assert gap < _MAX_GAP_S, f"sweep stalled the loop for {gap:.2f}s"
    names = dict(slow_ledger.threads)
    assert "open_goals" in names and names["open_goals"] != threading.get_ident()


async def test_sweep_writes_to_the_ledger_off_the_loop(
    slow_ledger: _SlowLedger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    done = GoalRecord(goal_id="done-1", goal="g", request="r")
    done.subtasks = [SubtaskRecord(subtask_id="s1", title="a", status="done")]
    slow_ledger._real.upsert(done)
    slow_ledger._real.upsert(_stalled("stalled-1"))

    class _FakeCEO:
        async def delegate(self, request: str, **kwargs: Any) -> None:
            return None

    monkeypatch.setattr("services.ceo_dispatcher.get_ceo_dispatcher", lambda: _FakeCEO())
    holder: dict[str, Any] = {}

    async def run() -> None:
        holder["report"] = await _supervisor(stall_s=600).sweep()
        await asyncio.sleep(0)

    gap = await _max_gap_while(run())
    assert gap < _MAX_GAP_S, f"sweep stalled the loop for {gap:.2f}s"
    report = holder["report"]
    assert report.closed == 1 and report.redriven == 1
    assert all(tid != threading.get_ident() for _, tid in slow_ledger.threads)


async def test_the_in_process_claim_is_taken_before_the_first_await(slow_ledger: _SlowLedger) -> None:
    """A sweep that runs while the ledger calls are in a thread must still skip the goal."""
    supervisor = _supervisor()
    goal = _stalled("g-claim")
    slow_ledger._real.upsert(goal)  # the real compare-and-set needs the goal to exist

    async def no_redrive(_goal: Any) -> None:
        return None

    supervisor._redrive = no_redrive  # type: ignore[method-assign]
    task = asyncio.create_task(supervisor._spawn_redrive_async(slow_ledger, goal))
    await asyncio.sleep(0.05)  # the claim is now in a worker thread
    assert supervisor.is_driving("g-claim")
    assert await task is True


async def test_a_lost_cas_releases_the_in_process_claim(slow_ledger: _SlowLedger) -> None:
    slow_ledger.claim_result = False
    supervisor = _supervisor()
    goal = _stalled("g-lost")
    assert await supervisor._spawn_redrive_async(slow_ledger, goal) is False
    assert not supervisor.is_driving("g-lost")
    assert goal.interventions == 0, "a lost claim must not count as an intervention"


def test_the_public_redrive_path_is_still_synchronous() -> None:
    """request_redrive is called by the HTTP route and must keep its synchronous contract."""
    assert not inspect.iscoroutinefunction(CEOSupervisor.request_redrive)
    assert not inspect.iscoroutinefunction(CEOSupervisor._spawn_redrive)
    assert inspect.iscoroutinefunction(CEOSupervisor._spawn_redrive_async)

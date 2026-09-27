"""The CEO learns from its own results (agent/ceo_playbook.py, agent/lessons.py).

Regression for a CEO that never saw how its directives ended. On 2026-09-26
four tasks timed out at 600s every ten minutes until each hit its retry cap.
The timeouts wrote no lesson, and the CEO kept issuing work with no idea it
was failing.
"""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

from agent import ceo_playbook, lessons
from agent.ceo_playbook import (
    beliefs,
    learn,
    outcome_of,
    render,
    role_of,
    scoreboard,
    signature,
    suppression_reason,
)
from agent.lessons import LessonStore, MongoLessonStore, record_task_timeout
from tasks.models import Task, TaskStatus

_DAY = 86400.0


def _task(title="agency: Refactor router", status="failed", role="dev", err="", **kw):
    tags = ["agency", role, "priority-5", "runtime-internal_agent"] if role else []
    return SimpleNamespace(
        task_id=kw.get("task_id", f"t-{title}-{status}-{time.monotonic_ns()}"),
        title=title, status=SimpleNamespace(value=status), tags=tags,
        error_message=err, blocked_reason=kw.get("blocked_reason", ""),
        updated_at=kw.get("updated_at", time.time()), task_type="scheduled",
    )


# ── Classification ────────────────────────────────────────────────────────────


def test_signature_matches_directive_and_task_titles():
    assert signature("agency: Fix 3 flaky tests") == signature("Fix 12 flaky tests")


def test_role_and_outcome_classification():
    assert role_of(_task(role="security")) == "security"
    assert role_of(_task(role=None)) is None
    assert outcome_of(_task(status="done")) == "success"
    assert outcome_of(_task(status="blocked", err="Execution timed out after 600s")) == "timeout"
    assert outcome_of(_task(status="failed")) == "failure"
    assert outcome_of(_task(status="todo")) == "open"


# ── Learning and beliefs ──────────────────────────────────────────────────────


def test_each_outcome_is_counted_once():
    doc: dict = {}
    t = _task(task_id="t1")
    assert learn(doc, [t]) == 1
    assert learn(doc, [t]) == 0  # same outcome, next cycle
    t.status = SimpleNamespace(value="done")
    assert learn(doc, [t]) == 1  # retried and later succeeded: new evidence
    entry = doc["subjects"][signature(t.title)]
    assert (entry["failure"], entry["success"]) == (1, 1)


def test_repeat_failures_become_an_avoid_belief_and_suppress_reissue():
    doc: dict = {}
    learn(doc, [_task(err="Execution timed out after 600s", status="blocked"),
                _task(), _task()])
    assert any(b.startswith('AVOID: "agency: Refactor router" failed 3x, 1 timed out')
               for b in beliefs(doc))
    assert "failed 3x" in suppression_reason(doc, "Refactor router")
    assert suppression_reason(doc, "Something new") is None


def test_success_weakens_a_belief_below_the_suppression_line():
    doc: dict = {}
    learn(doc, [_task(), _task(), _task(status="done")])
    assert suppression_reason(doc, "Refactor router") is None  # net evidence 1 < 2


def test_beliefs_fade_without_new_evidence():
    doc: dict = {}
    learn(doc, [_task(), _task(), _task()])
    later = time.time() + 30 * _DAY  # just over two half-lives: 3 -> ~0.7
    assert suppression_reason(doc, "Refactor router", now=later) is None
    assert beliefs(doc, now=later) == []


def test_role_beliefs_need_enough_samples():
    doc: dict = {}
    learn(doc, [_task(title=f"agency: t{i}", status="done", role="qa") for i in range(2)])
    assert beliefs(doc) == []
    learn(doc, [_task(title="agency: t9", status="done", role="qa")])
    assert "RELIABLE: role qa completed 3/3 directives." in beliefs(doc)
    learn(doc, [_task(title=f"agency: s{i}", role="scout") for i in range(4)])
    assert any(b.startswith("STRUGGLING: role scout completed only 0/4") for b in beliefs(doc))


def test_scoreboard_covers_the_last_week_only():
    old = _task(updated_at=time.time() - 10 * _DAY)
    board = scoreboard([old, _task(), _task(), _task(status="done")])
    assert board["roles"]["dev"] == {"failure": 2, "success": 1}
    assert board["repeat_failures"] == ["agency: Refactor router"]


def test_render_is_empty_without_evidence():
    assert render({"roles": {}, "repeat_failures": []}, [], "") == ""


# ── Wiring into the CEO ───────────────────────────────────────────────────────


@pytest.fixture()
def task_store(monkeypatch, tmp_path):
    from tasks.store import TaskStore, set_task_store

    store = TaskStore()
    set_task_store(store)
    monkeypatch.setattr(ceo_playbook, "_store", None)
    monkeypatch.setattr(ceo_playbook, "_doc", {})
    monkeypatch.setattr(lessons, "_store", LessonStore(tmp_path / "lessons.db"))
    return store


def test_learning_context_learns_from_the_task_store(task_store):
    for status in ("failed", "failed", "blocked"):
        task = Task(owner_id="system", title="agency: Rewrite scheduler",
                    tags=["agency", "dev"], status=TaskStatus(status),
                    error_message="Execution timed out after 600s" if status == "blocked" else None)
        asyncio.run(task_store.create(task))
    block = asyncio.run(ceo_playbook.learning_context())
    assert "## Outcomes, last 7 days" in block
    assert "## CEO Playbook" in block
    assert ceo_playbook.should_suppress("Rewrite scheduler")
    # A second cycle over the same tasks adds no evidence.
    before = dict(ceo_playbook._doc["subjects"])
    asyncio.run(ceo_playbook.learning_context())
    assert ceo_playbook._doc["subjects"] == before


def test_ceo_prompt_includes_what_it_learned():
    from agent.agency import _build_ceo_prompt

    prompt = _build_ceo_prompt({"learning": "## CEO Playbook\n  - AVOID: x"}, 1)
    assert "## CEO Playbook" in prompt
    assert prompt.index("## CEO Playbook") < prompt.index("## Instructions")


def test_ceo_cycle_drops_its_own_failing_directives_but_not_owner_requests(monkeypatch):
    from agent.agency import Agency, AgentDirective, AgentRole

    agency = Agency.__new__(Agency)
    agency._cycle_count, agency._directives, agency._history = 0, [], []
    agency._last_quick_notes = {}
    owner = AgentDirective("d1", AgentRole.DEV, "Refactor router", "owner asked")
    invented = AgentDirective("d2", AgentRole.DEV, "Refactor router", "again")
    fresh = AgentDirective("d3", AgentRole.REVIEWER, "Add tests", "new")
    dispatched: list[str] = []

    async def no_learning():
        return ""

    async def quick_notes():
        return [owner]

    async def company(_state):
        return []

    async def assess(_state):
        return "ok", [invented, fresh]

    monkeypatch.setenv("SELF_BOOTSTRAP_ENABLED", "false")
    monkeypatch.setattr(ceo_playbook, "learning_context", no_learning)
    monkeypatch.setattr(ceo_playbook, "should_suppress",
                        lambda title: "failed 3x" if title == "Refactor router" else None)
    agency._handle_quick_notes = quick_notes
    agency._company_directives = company
    agency._ceo_assess_llm = assess
    agency._build_state_context = lambda: {}
    agency._issue_count = lambda: 0
    agency._dispatch_directive = lambda d: dispatched.append(d.directive_id)
    asyncio.run(agency.run_cycle())
    # The owner's request goes out; the CEO's own identical reissue is a
    # duplicate of it this cycle; the fresh directive is untouched.
    assert dispatched == ["d1", "d3"]


def test_ceo_invented_directive_alone_is_suppressed(monkeypatch):
    from agent.agency import Agency, AgentDirective, AgentRole

    agency = Agency.__new__(Agency)
    agency._cycle_count, agency._directives, agency._history = 0, [], []
    agency._last_quick_notes = {}
    invented = AgentDirective("d2", AgentRole.DEV, "Refactor router", "again")
    dispatched: list[str] = []

    async def empty(*_a):
        return []

    async def no_learning():
        return ""

    async def assess(_state):
        return "ok", [invented]

    monkeypatch.setenv("SELF_BOOTSTRAP_ENABLED", "false")
    monkeypatch.setattr(ceo_playbook, "learning_context", no_learning)
    monkeypatch.setattr(ceo_playbook, "should_suppress", lambda title: "failed 3x")
    agency._handle_quick_notes = empty
    agency._company_directives = empty
    agency._ceo_assess_llm = assess
    agency._build_state_context = lambda: {}
    agency._issue_count = lambda: 0
    agency._dispatch_directive = lambda d: dispatched.append(d.directive_id)
    asyncio.run(agency.run_cycle())
    assert dispatched == []


# ── Timeouts teach, and lessons survive restarts ──────────────────────────────


def test_a_timeout_records_a_lesson(monkeypatch, tmp_path):
    store = LessonStore(tmp_path / "lessons.db")
    monkeypatch.setattr(lessons, "_store", store)
    record_task_timeout("Rewrite scheduler", "Rewrite scheduler", "Execution timed out after 600s")
    record_task_timeout("Rewrite scheduler", "Rewrite scheduler", "Execution timed out after 600s")
    top = store.recent(1)[0]
    assert top["phase"] == "dispatch" and top["hits"] == 2
    assert "Rewrite scheduler" in top["lesson"] and "smaller steps" in top["lesson"]


@pytest.mark.asyncio
async def test_coordinator_timeout_records_a_lesson(monkeypatch, tmp_path):
    from tasks.service import TaskExecutionCoordinator, TaskWorkflowService
    from tasks.store import TaskStore, set_task_store

    store = TaskStore()
    set_task_store(store)
    recorded: list[tuple] = []
    monkeypatch.setattr(lessons, "record_task_timeout", lambda *a: recorded.append(a))
    task = Task(owner_id="o", title="Slow job", prompt="x", pending_agent_run=True, goal="Ship it")
    await store.create(task)

    class _Slow:
        async def execute(self, spec):
            await asyncio.sleep(10)

    coordinator = TaskExecutionCoordinator(
        store=store, workflow=TaskWorkflowService(store=store), runtime_manager=_Slow(),
        workspace_root=str(tmp_path), execution_timeout_s=0.01,
    )
    await coordinator.execute(task.task_id)
    assert recorded and recorded[0][:2] == ("Slow job", "Ship it")


class _FakeLessons:
    """The Mongo operations MongoLessonStore uses."""

    def __init__(self):
        self.docs: dict[str, dict] = {}

    def update_one(self, query, update, upsert=False):
        doc = self.docs.get(query["_id"])
        if doc is None:
            doc = {"_id": query["_id"], "hits": 0, **update["$setOnInsert"]}
            self.docs[query["_id"]] = doc
        doc["hits"] += update["$inc"]["hits"]
        doc.update(update["$set"])

    def update_many(self, query, update):
        n = 0
        for doc in self.docs.values():
            if doc["goal"] == query["goal"] and doc["resolved"] < doc["hits"]:
                doc["resolved"] += 1
                n += 1
        return SimpleNamespace(modified_count=n)

    def find(self, _query):
        live = [d for d in self.docs.values() if d["resolved"] < d["hits"]]
        return SimpleNamespace(sort=lambda *_a: SimpleNamespace(limit=lambda _n: live))


def test_mongo_lesson_store_matches_the_sqlite_semantics():
    store = MongoLessonStore(_FakeLessons())
    store.record(phase="execute", issue="patch did not apply", goal="fix login")
    store.record(phase="execute", issue="patch did not apply", goal="fix login")
    store.record(phase="verify", issue="token ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2", goal="g")
    top = store.recent(5)
    assert top[0]["hits"] == 2
    assert all("A1b2C3d4" not in r["lesson"] for r in top)  # still redacted
    assert store.resolve_goal("fix login") == 1
    assert store.resolve_goal("fix login") == 1
    assert [r["lesson"] for r in store.recent(5)] == ["token ***"]


def test_enforcement_is_a_live_platform_control(monkeypatch):
    import os

    from packages.config import control_overrides

    doc: dict = {}
    learn(doc, [_task(), _task(), _task()])
    monkeypatch.setattr(ceo_playbook, "_doc", doc)
    before = os.environ.get("CEO_PLAYBOOK_ENFORCE")
    try:
        control_overrides.apply_overrides({"CEO_PLAYBOOK_ENFORCE": "false"})
        assert ceo_playbook.should_suppress("Refactor router") is None
        control_overrides.apply_overrides({"CEO_PLAYBOOK_ENFORCE": "true"})
        assert ceo_playbook.should_suppress("Refactor router")
    finally:
        control_overrides.apply_overrides({})
        if before is None:
            os.environ.pop("CEO_PLAYBOOK_ENFORCE", None)
        else:
            os.environ["CEO_PLAYBOOK_ENFORCE"] = before


def test_ceo_status_shows_what_it_learned(monkeypatch):
    from agent.agency import Agency

    doc: dict = {}
    learn(doc, [_task(), _task(), _task()])
    monkeypatch.setattr(ceo_playbook, "_doc", doc)
    agency = Agency.__new__(Agency)
    agency._running, agency._tick, agency._cycle_count = False, 900, 0
    agency._directives, agency._history = [], []
    playbook = agency.get_status()["playbook"]
    assert playbook["subjects"] == 1
    assert playbook["beliefs"][0].startswith('AVOID: "agency: Refactor router"')

"""Per-agent memory and dreaming (services/agent_memory)."""
from __future__ import annotations

import json

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

import services.agent_memory.service as mem_service
import services.agent_memory.store as mem_store_mod
from services.agent_memory.capture import parse_remember_lines, record_episode
from services.agent_memory.dream import dream_agent, enforce_index_cap, parse_ops
from services.agent_memory.models import MemoryNote, NoteKind, NoteLayer, NoteStatus
from services.agent_memory.recall import GUIDANCE, render_block, select_notes
from services.agent_memory.store import AgentMemoryStore


@pytest.fixture
def store(monkeypatch):
    """An in-memory store installed as the process singleton, with memory on."""
    s = AgentMemoryStore(db=None)
    monkeypatch.setattr(mem_store_mod, "_store", s)
    monkeypatch.setenv("AGENT_MEMORY_ENABLED", "true")
    monkeypatch.setenv("AGENT_DREAM_ENABLED", "true")
    monkeypatch.delenv("AGENCY_KILL_SWITCH", raising=False)
    return s


def _fake_llm(ops: list[dict]):
    calls: list[tuple[str, str]] = []

    async def llm(system: str, user: str) -> str:
        calls.append((system, user))
        return "Here you go:\n" + json.dumps({"ops": ops})

    llm.calls = calls  # type: ignore[attr-defined]
    return llm


# ── capture ──────────────────────────────────────────────────────────────

def test_parse_remember_lines_reads_kind_and_evidence():
    out = parse_remember_lines(
        "Done.\nREMEMBER(trap): the staging DB resets nightly | evidence: task t1 lost rows\n"
        "- REMEMBER: owner wants PRs small\nREMEMBER(nonsense): unknown kind falls back\n"
    )
    assert out[0] == (NoteKind.TRAP, "the staging DB resets nightly", "task t1 lost rows")
    assert out[1] == (NoteKind.FACT, "owner wants PRs small", "")
    assert out[2][0] == NoteKind.FACT


def test_parse_remember_lines_caps_notes_per_run():
    text = "\n".join(f"REMEMBER: note number {i}" for i in range(20))
    assert len(parse_remember_lines(text)) == 5


async def test_record_episode_keeps_notes_and_strips_them_from_excerpt(store):
    ep = await record_episode(store, "agent_a", task_id="t1", title="Fix login", success=True,
                              output="Fixed it.\nREMEMBER(rule): run migrations before tests")
    notes = await store.list_notes("agent_a")
    assert [n.text for n in notes] == ["run migrations before tests"]
    assert notes[0].status == NoteStatus.UNVERIFIED and notes[0].layer == NoteLayer.STORE
    assert ep.notes_written == [notes[0].note_id]
    assert "REMEMBER" not in ep.outcome_excerpt and "Fixed it." in ep.outcome_excerpt


async def test_near_duplicate_note_reinforces_instead_of_duplicating(store):
    await record_episode(store, "agent_a", task_id="t1", title="x", success=True,
                         output="REMEMBER: run the migrations before the tests")
    await record_episode(store, "agent_a", task_id="t2", title="y", success=True,
                         output="REMEMBER: run the migrations before tests")
    notes = await store.list_notes("agent_a")
    assert len(notes) == 1
    assert notes[0].source_task_ids == ["t1", "t2"]


# ── recall ───────────────────────────────────────────────────────────────

def _note(text: str, **kw) -> MemoryNote:
    return MemoryNote(memory_key="agent_a", text=text, **kw)


def test_select_notes_hides_refuted_caps_index_and_filters_by_relevance():
    notes = [
        _note("deploys go through render", layer=NoteLayer.INDEX, status=NoteStatus.VERIFIED),
        _note("second index note", layer=NoteLayer.INDEX),
        _note("wrong index note", layer=NoteLayer.INDEX, status=NoteStatus.REFUTED),
        _note("stripe webhooks need the raw request body"),
        _note("unrelated note about fonts"),
    ]
    index, relevant = select_notes(notes, "Fix the stripe webhook signature check",
                                   index_lines=1, recall_k=5)
    assert [n.text for n in index] == ["deploys go through render"]
    assert [n.text for n in relevant] == ["stripe webhooks need the raw request body"]


def test_render_block_with_empty_memory_still_explains_how_to_remember():
    block = render_block([], [])
    assert block.startswith("## Your memory") and GUIDANCE in block
    assert "Always-loaded" not in block


async def test_with_agent_memory_appends_block_and_counts_access(store):
    await store.save_note(_note("stripe webhooks need the raw request body"))
    out = await mem_service.with_agent_memory("Task title: stripe", "agent_a", "stripe webhook bug")
    assert out.startswith("Task title: stripe\n\n## Your memory")
    assert "stripe webhooks need the raw request body" in out
    assert (await store.list_notes("agent_a"))[0].access_count == 1


async def test_with_agent_memory_is_a_noop_when_disabled_or_broken(store, monkeypatch):
    monkeypatch.setenv("AGENT_MEMORY_ENABLED", "false")
    assert await mem_service.with_agent_memory("instr", "agent_a", "q") == "instr"
    monkeypatch.setenv("AGENT_MEMORY_ENABLED", "true")

    async def boom(_key):
        raise RuntimeError("db down")

    monkeypatch.setattr(store, "list_notes", boom)
    assert await mem_service.with_agent_memory("instr", "agent_a", "q") == "instr"
    await mem_service.record_task_outcome("agent_a", task_id="t", title="t", success=True,
                                          output="REMEMBER: x")  # must not raise


# ── dreaming ─────────────────────────────────────────────────────────────

async def _seed(store: AgentMemoryStore) -> dict[str, MemoryNote]:
    notes = {
        "good": _note("tests need TESTING=true"),
        "wrong": _note("the api lives on port 9000", layer=NoteLayer.INDEX),
        "dup1": _note("keep PRs small"),
        "dup2": _note("owner likes small PRs"),
        "junk": _note("the sky was blue during task 4"),
        "partly": _note("deploy with make deploy"),
    }
    for n in notes.values():
        await store.save_note(n)
    await record_episode(store, "agent_a", task_id="t9", title="Start API", success=False,
                         output="Connection refused on 9000; the API is on port 8001")
    return notes


async def test_dream_corrects_merges_adds_and_promotes(store):
    n = await _seed(store)
    llm = _fake_llm([
        {"op": "verify", "note_id": n["good"].note_id, "evidence": "ep shows it"},
        {"op": "refute", "note_id": n["wrong"].note_id, "evidence": "t9: API is on 8001"},
        {"op": "rewrite", "note_id": n["partly"].note_id, "text": "deploy by merging to master"},
        {"op": "merge", "note_ids": [n["dup1"].note_id, n["dup2"].note_id],
         "text": "the owner wants small PRs", "kind": "preference"},
        {"op": "add", "kind": "fact", "text": "the API listens on port 8001", "evidence": "t9"},
        {"op": "delete", "note_id": n["junk"].note_id},
        {"op": "promote", "note_id": n["good"].note_id},
        {"op": "verify", "note_id": "mem_does_not_exist"},
    ])
    result = await dream_agent(store, "agent_a", "Backend agent", llm=llm, index_cap=10)

    assert result["status"] == "dreamed" and result["ops_applied"] == 7
    by_text = {x.text: x for x in await store.list_notes("agent_a")}
    assert by_text["tests need TESTING=true"].status == NoteStatus.VERIFIED
    assert by_text["tests need TESTING=true"].layer == NoteLayer.INDEX
    wrong = by_text["the api lives on port 9000"]
    assert wrong.status == NoteStatus.REFUTED and wrong.layer == NoteLayer.STORE
    assert "deploy by merging to master" in by_text
    assert by_text["the owner wants small PRs"].kind == NoteKind.PREFERENCE
    assert "owner likes small PRs" not in by_text and "the sky was blue during task 4" not in by_text
    assert by_text["the API listens on port 8001"].status == NoteStatus.VERIFIED
    assert await store.list_episodes("agent_a", undreamed_only=True) == []
    assert "Backend agent" in llm.calls[0][1] and "port 8001" in llm.calls[0][1]


async def test_dream_with_unusable_reply_changes_nothing(store):
    await _seed(store)

    async def bad_llm(_s, _u):
        return "I could not decide."

    result = await dream_agent(store, "agent_a", "ctx", llm=bad_llm, index_cap=10)
    assert result["status"] == "no_usable_reply"
    assert len(await store.list_episodes("agent_a", undreamed_only=True)) == 1


def test_enforce_index_cap_demotes_unverified_and_least_used_first():
    notes = [
        _note("a", layer=NoteLayer.INDEX, status=NoteStatus.VERIFIED, access_count=1),
        _note("b", layer=NoteLayer.INDEX, access_count=50),
        _note("c", layer=NoteLayer.INDEX, status=NoteStatus.VERIFIED, access_count=9),
    ]
    assert enforce_index_cap(notes, 2) == 1
    assert [x.text for x in notes if x.layer == NoteLayer.INDEX] == ["a", "c"]


def test_parse_ops_rejects_non_json():
    assert parse_ops("no json here") is None
    assert parse_ops('{"ops": [{"op": "verify"}, "junk"]}') == [{"op": "verify"}]


async def test_dream_cycle_ranks_by_new_episodes_and_honours_kill_switch(store, monkeypatch):
    for i in range(3):
        await record_episode(store, "busy", task_id=f"b{i}", title="t", success=True, output="o")
    await record_episode(store, "quiet", task_id="q1", title="t", success=True, output="o")
    monkeypatch.setenv("AGENT_DREAM_MAX_AGENTS", "1")

    monkeypatch.setenv("AGENCY_KILL_SWITCH", "true")
    assert await mem_service.run_dream_cycle(llm=_fake_llm([])) == []
    monkeypatch.delenv("AGENCY_KILL_SWITCH")

    results = await mem_service.run_dream_cycle(llm=_fake_llm([]))
    assert [r["memory_key"] for r in results] == ["busy"]


async def test_maybe_spawn_dream_cycle_respects_interval(store, monkeypatch):
    spawned: list[int] = []

    async def fake_cycle(**_kw):
        spawned.append(1)
        return []

    monkeypatch.setattr(mem_service, "run_dream_cycle", fake_cycle)
    monkeypatch.setattr(mem_service, "_last_cycle_at", None)
    monkeypatch.setattr(mem_service, "_cycle_task", None)
    assert mem_service.maybe_spawn_dream_cycle() is True
    await mem_service._cycle_task
    assert mem_service.maybe_spawn_dream_cycle() is False  # interval not elapsed
    assert spawned == [1]


# ── wiring: the task coordinator ─────────────────────────────────────────

async def test_coordinator_injects_memory_and_records_what_the_agent_learned(store):
    from agents.store import AgentDefinition, AgentStore
    from runtimes.base import TaskResult
    from tasks.models import Task, TaskStatus
    from tasks.service import TaskExecutionCoordinator
    from tasks.store import TaskStore

    seen: list[str] = []

    class _Decision:
        selected_runtime_id, model_used, reason = "internal_agent", "stub", "test"
        fallback_runtime_id, fallback_attempted = None, False

    class _Runtime:
        async def execute(self, spec):
            seen.append(spec.instruction)
            return TaskResult(runtime_id="internal_agent", task_id=spec.task_id, success=True,
                              output="Done.\nREMEMBER(rule): billing exports need the UTC flag"), _Decision()

    agents, tasks = AgentStore(), TaskStore(db=None)
    await agents.create(AgentDefinition(agent_id="agent_bill", owner_id="u1", name="Billing"))
    coord = TaskExecutionCoordinator(store=tasks, agent_store=agents, runtime_manager=_Runtime())
    for title in ("Export billing report", "Export billing report again"):
        task = Task(owner_id="u1", title=title, agent_id="agent_bill", status=TaskStatus.TODO)
        task.pending_agent_run = True
        await tasks.create(task)
        await coord.execute(task.task_id)

    assert "## Your memory" in seen[0] and "billing exports need the UTC flag" not in seen[0]
    assert "billing exports need the UTC flag" in seen[1]
    assert len(await store.list_episodes("agent_bill")) == 2


# ── API ──────────────────────────────────────────────────────────────────

def _client(user: dict) -> TestClient:
    from agents.memory_api import agent_memory_router

    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        request.state.user = user
        return await call_next(request)

    app.include_router(agent_memory_router)
    return TestClient(app)


@pytest.fixture
def owned_agent(monkeypatch):
    import asyncio

    import agents.store as agents_store_mod
    from agents.store import AgentDefinition, AgentStore

    agents = AgentStore()
    monkeypatch.setattr(agents_store_mod, "_store", agents)
    asyncio.run(agents.create(AgentDefinition(agent_id="agent_x", owner_id="owner@x.com", name="X")))
    return "agent_x"


def test_api_owner_reads_and_deletes_notes_others_get_404(store, owned_agent):
    import asyncio

    note = _note("remember me")
    note.memory_key = owned_agent
    asyncio.run(store.save_note(note))
    owner = _client({"email": "owner@x.com", "role": "user"})
    body = owner.get(f"/api/agents/{owned_agent}/memory").json()
    assert [n["text"] for n in body["notes"]] == ["remember me"]

    stranger = _client({"email": "other@x.com", "role": "user"})
    assert stranger.get(f"/api/agents/{owned_agent}/memory").status_code == 404
    assert stranger.get("/api/agents/role:coder/memory").status_code == 404
    assert _client({"email": "a@x.com", "role": "admin"}).get("/api/agents/role:coder/memory").status_code == 200

    assert owner.delete(f"/api/agents/{owned_agent}/memory/{note.note_id}").status_code == 204
    assert owner.delete(f"/api/agents/{owned_agent}/memory/{note.note_id}").status_code == 404


def test_api_dream_runs_a_pass(store, owned_agent, monkeypatch):
    import asyncio

    asyncio.run(record_episode(store, owned_agent, task_id="t1", title="t", success=True, output="o"))
    monkeypatch.setattr(mem_service, "default_llm", _fake_llm([]))
    resp = _client({"email": "owner@x.com", "role": "user"}).post(f"/api/agents/{owned_agent}/memory/dream")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "dreamed"


# ── platform control (CLAUDE.md rule 37) ─────────────────────────────────

def test_platform_control_override_turns_memory_off(store, monkeypatch):
    from packages.config import control_overrides
    from packages.config.agent_memory import agent_memory_enabled, agent_memory_index_lines

    monkeypatch.setattr(control_overrides, "_applied", dict(control_overrides._applied))
    try:
        control_overrides.apply_overrides({"AGENT_MEMORY_ENABLED": "false", "AGENT_MEMORY_INDEX_LINES": "12"})
        assert agent_memory_enabled() is False
        assert agent_memory_index_lines() == 12
    finally:
        control_overrides.apply_overrides({})


def test_notes_reload_when_the_backend_rewrote_timestamps_as_iso_strings():
    # The SQLite backend rewrites ``updated_at`` to an ISO string on update_one;
    # reading the note back used to raise a ValidationError.
    note = MemoryNote(memory_key="k", text="t", updated_at="2026-11-07T06:53:53.995682+00:00",
                      created_at="2026-11-07T06:00:00+00:00")
    assert isinstance(note.updated_at, float) and note.updated_at > note.created_at


async def test_dream_merge_with_duplicate_or_malformed_ids_keeps_the_note(store):
    keep = _note("keep me")
    await store.save_note(keep)
    await record_episode(store, "agent_a", task_id="t1", title="t", success=True, output="o")
    llm = _fake_llm([
        {"op": "merge", "note_ids": [keep.note_id, keep.note_id], "text": "z"},
        {"op": "merge", "note_ids": [["x"], "q"], "text": "z"},
        {"op": "merge", "note_ids": "not-a-list", "text": "z"},
    ])
    result = await dream_agent(store, "agent_a", "ctx", llm=llm, index_cap=5)
    assert result["status"] == "dreamed" and result["ops_applied"] == 0
    assert [n.text for n in await store.list_notes("agent_a")] == ["keep me"]


def test_maybe_spawn_dream_cycle_without_a_loop_returns_false(store, monkeypatch):
    monkeypatch.setattr(mem_service, "_last_cycle_at", None)
    monkeypatch.setattr(mem_service, "_cycle_task", None)
    assert mem_service.maybe_spawn_dream_cycle() is False
    assert mem_service._last_cycle_at is None  # not consumed, so the next poll retries


def test_api_public_agent_memory_is_still_owner_only(store, monkeypatch):
    import asyncio

    import agents.store as agents_store_mod
    from agents.store import AgentDefinition, AgentStore

    agents = AgentStore()
    monkeypatch.setattr(agents_store_mod, "_store", agents)
    asyncio.run(agents.create(AgentDefinition(agent_id="agent_pub", owner_id="owner@x.com",
                                              name="Pub", is_public=True)))
    stranger = _client({"email": "other@x.com", "role": "user"})
    assert stranger.get("/api/agents/agent_pub/memory").status_code == 404
    assert stranger.post("/api/agents/agent_pub/memory/dream").status_code == 404
    assert _client({"email": "owner@x.com", "role": "user"}).get("/api/agents/agent_pub/memory").status_code == 200


def test_public_agent_run_by_another_user_gets_a_separate_memory():
    key = mem_service.memory_key_for
    assert key("agent_p", task_owner="owner@x.com", agent_owner="owner@x.com") == "agent_p"
    assert key("agent_p", task_owner="system", agent_owner="owner@x.com") == "agent_p"
    assert key("agent_p", task_owner="other@x.com", agent_owner="owner@x.com") == "agent_p|other@x.com"
    assert key(role="coder") == "role:coder"


async def test_coordinator_keeps_a_strangers_notes_out_of_the_owners_memory(store):
    from agents.store import AgentDefinition, AgentStore
    from runtimes.base import TaskResult
    from tasks.models import Task, TaskStatus
    from tasks.service import TaskExecutionCoordinator
    from tasks.store import TaskStore

    seen: list[str] = []

    class _Decision:
        selected_runtime_id, model_used, reason = "internal_agent", "stub", "test"
        fallback_runtime_id, fallback_attempted = None, False

    class _Runtime:
        async def execute(self, spec):
            seen.append(spec.instruction)
            return TaskResult(runtime_id="internal_agent", task_id=spec.task_id, success=True,
                              output="REMEMBER: injected instruction from a stranger"), _Decision()

    agents, tasks = AgentStore(), TaskStore(db=None)
    await agents.create(AgentDefinition(agent_id="agent_pub", owner_id="owner@x.com", name="P", is_public=True))
    coord = TaskExecutionCoordinator(store=tasks, agent_store=agents, runtime_manager=_Runtime())
    ids = {}
    for owner in ("other@x.com", "owner@x.com"):
        task = Task(owner_id=owner, title="Do a thing", agent_id="agent_pub", status=TaskStatus.TODO)
        task.pending_agent_run = True
        await tasks.create(task)
        await coord.execute(task.task_id)
        ids[owner] = task.task_id

    # The owner's run did not see the stranger's note, and the owner's memory holds
    # only what the owner's own run wrote.
    assert "injected instruction from a stranger" not in seen[1]
    owner_notes = await store.list_notes("agent_pub")
    assert [n.source_task_ids for n in owner_notes] == [[ids["owner@x.com"]]]
    stranger_notes = await store.list_notes("agent_pub|other@x.com")
    assert [n.source_task_ids for n in stranger_notes] == [[ids["other@x.com"]]]


async def test_dream_marks_only_the_episodes_it_showed_the_model(store):
    for i in range(35):
        await record_episode(store, "agent_a", task_id=f"t{i}", title="t", success=True, output="o")
    result = await dream_agent(store, "agent_a", "ctx", llm=_fake_llm([]), index_cap=5)
    assert result["episodes"] == 30
    assert len(await store.list_episodes("agent_a", undreamed_only=True)) == 5


def test_role_memory_is_per_user_for_directives_and_shared_for_agency_work():
    key = mem_service.memory_key_for
    assert key(role="coder", task_owner="a@x.com") == "role:coder|a@x.com"
    assert key(role="coder", task_owner="system") == "role:coder"
    assert key(role="coder") == "role:coder"


def test_render_block_keeps_guidance_and_whole_lines_when_index_is_huge():
    index = [_note("x" * 500, layer=NoteLayer.INDEX) for _ in range(40)]  # max-size notes
    relevant = [_note("stripe webhooks need the raw body " + "y" * 440)]  # too long for the index's leftovers
    block = render_block(index, relevant)
    assert block.endswith(GUIDANCE)
    assert len(block) <= 6000  # MAX_BLOCK_CHARS, guidance included
    assert "stripe webhooks need the raw body" in block  # a huge index cannot crowd it out
    assert all(line.endswith(")") for line in block.splitlines() if line.startswith("- ["))


async def test_workflow_orchestrator_scopes_ceo_role_memory_to_the_requesting_user(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    from services.ceo_dispatcher import CEOResult
    from services.workflow_orchestrator import (
        ClassifyOutput, ExecutionRequest, PlanOutput, SpecialistSelection,
        WorkflowOrchestrator, WorkflowRun,
    )

    fake_ceo = MagicMock()
    fake_ceo.delegate = AsyncMock(return_value=CEOResult(
        goal="g", specialists=[], summary="s", total_duration_s=0.1, complexity="medium",
        fanout_used=True, runtimes_woken=[], verdict="OK"))
    monkeypatch.setattr("services.workflow_orchestrator._get_ceo_dispatcher", lambda: fake_ceo)
    run = WorkflowRun()
    run.classify = ClassifyOutput(domain="dev", task_type="bug_fix", complexity="medium")
    run.plan = PlanOutput(goal="Fix it", steps=[{"description": "fix"}])
    run.specialist = SpecialistSelection(specialist_ids=["s1"], specialist_names=["dev"], families=["general"])
    await WorkflowOrchestrator()._handle_execute(run, ExecutionRequest(request="Fix it", user_id="a@x.com"))

    kwargs = fake_ceo.delegate.call_args.kwargs
    assert kwargs["memory_owner"] == "a@x.com"
    assert "user_id" not in kwargs  # ledger/push/runner ownership unchanged


async def test_ceo_delegate_keeps_each_users_role_notes_apart(store):
    from unittest.mock import patch

    from services.ceo_dispatcher import CEODispatcher
    from tests.test_ceo_dispatcher import _FakeRuntimeManager

    class _AnyRuntime(dict):
        def get(self, _key, _default=None):
            return "REMEMBER: user A's private detail"

    fake = _FakeRuntimeManager()
    fake._per_runtime = _AnyRuntime()  # every runtime returns the note
    with patch("runtimes.manager.get_runtime_manager", return_value=fake):
        await CEODispatcher().delegate("Quick lint fix", complexity="low", memory_owner="a@x.com")
        await CEODispatcher().delegate("Quick lint fix", complexity="low", memory_owner="b@x.com")

    role = fake.execute_calls[0].task_type
    assert len(await store.list_notes(f"role:{role}|a@x.com")) == 1
    assert await store.list_notes(f"role:{role}") == []
    assert "user A's private detail" not in fake.execute_calls[1].instruction


def test_ledger_round_trips_memory_owner_and_old_records_load():
    from services.ceo_ledger import GoalRecord

    rec = GoalRecord(goal_id="g1", goal="g", request="r", memory_owner="a@x.com")
    assert GoalRecord.from_dict(rec.as_dict()).memory_owner == "a@x.com"
    old = rec.as_dict()
    old.pop("memory_owner")
    assert GoalRecord.from_dict(old).memory_owner == ""  # records written before this field


async def test_supervisor_redrive_keeps_the_users_role_memory(store, monkeypatch):
    from unittest.mock import patch

    from services.ceo_dispatcher import CEODispatcher
    from services.ceo_ledger import GoalRecord
    from tests.test_ceo_dispatcher import _FakeRuntimeManager

    stored = GoalRecord(goal_id="goal-redrive", goal="g", request="r", memory_owner="a@x.com")

    class _Ledger:
        def get(self, goal_id):
            return stored if goal_id == "goal-redrive" else None

        def __getattr__(self, _name):
            return lambda *a, **k: None

    monkeypatch.setattr("services.ceo_ledger.get_ceo_ledger", lambda: _Ledger())

    class _AnyRuntime(dict):
        def get(self, _key, _default=None):
            return "REMEMBER: user A's re-driven detail"

    fake = _FakeRuntimeManager()
    fake._per_runtime = _AnyRuntime()
    with patch("runtimes.manager.get_runtime_manager", return_value=fake):
        # What CEOSupervisor._redrive sends for a workflow goal: no user, no memory_owner.
        await CEODispatcher().delegate("Quick lint fix", complexity="low", goal_id="goal-redrive")

    role = fake.execute_calls[0].task_type
    assert len(await store.list_notes(f"role:{role}|a@x.com")) == 1
    assert await store.list_notes(f"role:{role}") == []


def test_render_block_keeps_both_layers_when_relevant_notes_are_many():
    index = [_note("i" * 500, layer=NoteLayer.INDEX) for _ in range(20)]
    relevant = [_note("r" * 500) for _ in range(20)]
    block = render_block(index, relevant)
    assert "Always-loaded index:" in block and "Possibly relevant to this task:" in block
    assert len(block) <= 6000 and block.endswith(GUIDANCE)


async def test_access_count_only_counts_notes_that_were_shown(store):
    from services.agent_memory.recall import build_memory_block

    for _ in range(20):
        await store.save_note(_note("i" * 500, layer=NoteLayer.INDEX))
    block = await build_memory_block(store, "agent_a", "q", index_lines=20, recall_k=0)
    shown = [n for n in await store.list_notes("agent_a") if f"({n.note_id})" in block]
    hidden = [n for n in await store.list_notes("agent_a") if f"({n.note_id})" not in block]
    assert shown and hidden
    assert all(n.access_count == 1 for n in shown) and all(n.access_count == 0 for n in hidden)


def _redrive_runtime():
    from tests.test_ceo_dispatcher import _FakeRuntimeManager

    class _AnyRuntime(dict):
        def get(self, _key, _default=None):
            return "REMEMBER: re-driven detail"

    fake = _FakeRuntimeManager()
    fake._per_runtime = _AnyRuntime()
    return fake


@pytest.mark.parametrize("ledger_state", ["record_without_owner", "ledger_unavailable"])
async def test_redrive_with_unknown_owner_gets_no_memory(store, monkeypatch, ledger_state):
    from unittest.mock import patch

    from services.ceo_dispatcher import CEODispatcher
    from services.ceo_ledger import GoalRecord

    await store.save_note(MemoryNote(memory_key="role:dev", text="shared pool note about lint fix"))
    old = GoalRecord(goal_id="goal-old", goal="g", request="r")  # predates memory_owner

    class _Ledger:
        def get(self, goal_id):
            return old

        def __getattr__(self, _name):
            return lambda *a, **k: None

    def _broken():
        raise RuntimeError("ledger down")

    monkeypatch.setattr("services.ceo_ledger.get_ceo_ledger",
                        (lambda: _Ledger()) if ledger_state == "record_without_owner" else _broken)
    fake = _redrive_runtime()
    with patch("runtimes.manager.get_runtime_manager", return_value=fake):
        await CEODispatcher().delegate("Quick lint fix", complexity="low", goal_id="goal-old")

    assert "## Your memory" not in fake.execute_calls[0].instruction  # no recall
    assert [n.text for n in await store.list_notes("role:dev")] == ["shared pool note about lint fix"]
    assert await store.keys_with_undreamed() == {}  # no recording anywhere


async def test_supervisor_passes_the_stored_memory_owner(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    from services.ceo_ledger import GoalRecord
    from services.ceo_supervisor import CEOSupervisor

    fake_ceo = MagicMock()
    fake_ceo.delegate = AsyncMock()
    monkeypatch.setattr("services.ceo_dispatcher.get_ceo_dispatcher", lambda: fake_ceo)
    goal = GoalRecord(goal_id="g1", goal="g", request="r", memory_owner="a@x.com")
    await CEOSupervisor()._redrive(goal)
    assert fake_ceo.delegate.call_args.kwargs["memory_owner"] == "a@x.com"


async def test_owner_with_id_on_task_and_email_on_agent_shares_their_own_memory(monkeypatch):
    async def identities(identity):
        return {"64a1", "owner@x.com"} if identity in ("64a1", "owner@x.com") else {identity}

    monkeypatch.setattr(mem_service, "_user_identities", identities)
    resolve = mem_service.resolve_memory_key
    assert await resolve("agent_p", task_owner="64a1", agent_owner="owner@x.com") == "agent_p"
    assert await resolve("agent_p", task_owner="99zz", agent_owner="owner@x.com") == "agent_p|99zz"


async def test_failed_owner_lookup_keeps_the_isolated_key(monkeypatch):
    async def broken(_identity):
        raise RuntimeError("db down")

    monkeypatch.setattr(mem_service, "_user_identities", broken)
    assert await mem_service.resolve_memory_key(
        "agent_p", task_owner="64a1", agent_owner="owner@x.com") == "agent_p|64a1"

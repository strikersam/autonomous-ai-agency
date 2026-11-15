"""Phase 2 G: versioned checkpoints, corruption fallback and the durable mirror."""
from __future__ import annotations

import asyncio
import json

import pytest

import agent.checkpoint as ckpt
from agent.checkpoint import Checkpoint, CheckpointStore
from packages.runs import checkpoints as mirror
from packages.runs.store import RunStore, set_run_store


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    set_run_store(RunStore())
    mirror.reset()
    store = CheckpointStore(tmp_path / "ckpt")
    monkeypatch.setattr(ckpt, "_store", store, raising=False)
    monkeypatch.setenv("AGENT_CHECKPOINT_ENABLED", "true")
    monkeypatch.setenv("RUNS_LEDGER_ENABLED", "true")
    yield store
    set_run_store(None)
    mirror.reset()


def _save(store: CheckpointStore, step: int) -> None:
    store.save(Checkpoint(session_id="s1", step_index=step, goal=f"goal {step}"))


def test_a_corrupt_latest_falls_back_to_the_previous_good_checkpoint(_isolated):
    _save(_isolated, 1)
    _save(_isolated, 2)
    (_isolated._base_dir / "s1" / "checkpoint_0002.json").write_text("{torn write")
    cp = _isolated.load_latest("s1")
    assert cp is not None and cp.step_index == 1


def test_an_unsupported_schema_version_is_skipped(_isolated):
    _save(_isolated, 1)
    path = _isolated._base_dir / "s1" / "checkpoint_0005.json"
    path.write_text(json.dumps({"session_id": "s1", "step_index": 5, "schema_version": 99}))
    assert _isolated.load_latest("s1").step_index == 1


def test_a_file_without_a_version_reads_as_version_1(_isolated):
    path = _isolated._base_dir / "s1"
    path.mkdir(parents=True, exist_ok=True)
    (path / "checkpoint_0003.json").write_text(json.dumps({"session_id": "s1", "step_index": 3}))
    cp = _isolated.load_latest("s1")
    assert cp.step_index == 3 and cp.schema_version == 1
    assert Checkpoint(session_id="x", step_index=0, goal="").to_dict()["schema_version"] == 1


def test_every_checkpoint_corrupt_gives_none(_isolated):
    _save(_isolated, 1)
    (_isolated._base_dir / "s1" / "checkpoint_0001.json").write_text("nope")
    assert _isolated.load_latest("s1") is None


@pytest.mark.anyio
async def test_the_latest_checkpoint_is_mirrored_and_restores_without_the_files(_isolated):
    ckpt.checkpoint_agent_state("s1", 1, "goal", [], [1], [])
    ckpt.checkpoint_agent_state("s1", 2, "goal", [], [1, 2], [])
    await asyncio.gather(*list(ckpt._mirror_tasks))
    docs = await mirror.load_latest("s1")
    assert [d["step_index"] for d in docs] == [2, 1]
    _isolated.delete_session("s1")
    restored = await ckpt.restore_agent_state("s1")
    assert restored is not None and restored["resume_step"] == 3


@pytest.mark.anyio
async def test_a_corrupt_mirror_latest_falls_back_to_its_previous(_isolated):
    await mirror.save({"session_id": "s2", "step_index": 1, "goal": "g"})
    await mirror.save({"session_id": "s2", "step_index": 2, "schema_version": 42})
    restored = await ckpt.restore_agent_state("s2")
    assert restored["resume_step"] == 2


def test_no_running_loop_means_file_only(_isolated):
    ckpt.checkpoint_agent_state("s3", 1, "goal", [], [], [])
    assert _isolated.load_latest("s3").step_index == 1


@pytest.mark.anyio
async def test_orchestrator_checkpoint_store_reports_durability(monkeypatch):
    from services import orchestrator_checkpoint as oc

    store = oc.OrchestratorCheckpointStore()
    store._store = oc._NoopDB()
    assert await store.is_durable() is False
    store._store = object()
    assert await store.is_durable() is True
    assert oc.SCHEMA_VERSION == 1

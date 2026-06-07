"""Tests for durable agent checkpointing (PR #412)."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent.checkpoint import (
    Checkpoint,
    CheckpointStore,
    cleanup_checkpoints,
    checkpoint_agent_state,
    restore_agent_state,
)


class TestCheckpointModel:
    def test_to_dict_roundtrip(self) -> None:
        cp = Checkpoint(
            session_id="sess_abc",
            step_index=3,
            goal="Fix production bug",
            plan_steps=[{"id": 1, "description": "Read log"}],
            completed_steps=[0, 1],
            tool_call_history=[{"tool": "read_file", "args": {"path": "x.py"}}],
            scratchpad_raw="need to check auth module",
        )
        d = cp.to_dict()
        assert d["session_id"] == "sess_abc"
        assert d["step_index"] == 3
        assert len(d["tool_call_history"]) == 1
        assert d["scratchpad_raw"] == "need to check auth module"

    def test_from_dict(self) -> None:
        data = {
            "session_id": "sess_xyz",
            "step_index": 5,
            "goal": "Refactor module",
            "plan_steps": [],
            "completed_steps": [0, 1, 2, 3],
            "tool_call_history": [],
            "scratchpad_raw": "",
            "error_info": "timeout",
        }
        cp = Checkpoint.from_dict(data)
        assert cp.session_id == "sess_xyz"
        assert cp.step_index == 5
        assert cp.error_info == "timeout"

    def test_scratchpad_truncated(self) -> None:
        cp = Checkpoint(
            session_id="s",
            step_index=1,
            goal="g",
            scratchpad_raw="x" * 10000,
        )
        d = cp.to_dict()
        assert len(d["scratchpad_raw"]) <= 8000


class TestCheckpointStore:
    def test_save_and_load(self, tmp_path: Path) -> None:
        store = CheckpointStore(base_dir=tmp_path)
        cp = Checkpoint(session_id="sess_1", step_index=2, goal="Test")
        store.save(cp)

        restored = store.load_latest("sess_1")
        assert restored is not None
        assert restored.session_id == "sess_1"
        assert restored.step_index == 2
        assert restored.goal == "Test"

    def test_load_latest_returns_highest_step(self, tmp_path: Path) -> None:
        store = CheckpointStore(base_dir=tmp_path)
        for i in range(5):
            store.save(Checkpoint(session_id="sess", step_index=i, goal=f"step_{i}"))

        latest = store.load_latest("sess")
        assert latest is not None
        assert latest.step_index == 4

    def test_load_latest_nonexistent_session(self, tmp_path: Path) -> None:
        store = CheckpointStore(base_dir=tmp_path)
        assert store.load_latest("no_session") is None

    def test_list_checkpoints(self, tmp_path: Path) -> None:
        store = CheckpointStore(base_dir=tmp_path)
        store.save(Checkpoint(session_id="s", step_index=0, goal="g"))
        store.save(Checkpoint(session_id="s", step_index=1, goal="g"))

        files = store.list_checkpoints("s")
        assert len(files) == 2

    def test_delete_session(self, tmp_path: Path) -> None:
        store = CheckpointStore(base_dir=tmp_path)
        store.save(Checkpoint(session_id="sess_del", step_index=0, goal="g"))
        assert store.load_latest("sess_del") is not None

        store.delete_session("sess_del")
        assert store.load_latest("sess_del") is None

    def test_corrupt_checkpoint_handled(self, tmp_path: Path) -> None:
        store = CheckpointStore(base_dir=tmp_path)
        sd = store._session_dir("sess_bad")
        sd.mkdir(parents=True, exist_ok=True)
        with open(sd / "checkpoint_0000.json", "w") as f:
            f.write("{not valid json")

        assert store.load_latest("sess_bad") is None


class TestAsyncCheckpointAPI:
    @pytest.mark.asyncio
    async def test_checkpoint_and_restore(self, tmp_path: Path) -> None:
        import agent.checkpoint as ckpt

        ckpt._store = CheckpointStore(base_dir=tmp_path)

        checkpoint_agent_state(
            session_id="test_sess",
            step_index=4,
            goal="Implement feature",
            plan_steps=[{"id": 1, "description": "Write code"}],
            completed_steps=[0, 1, 2],
            tool_call_history=[{"tool": "write_file", "args": {}}],
            scratchpad_raw="Done with step 4",
        )

        restored = await restore_agent_state("test_sess")
        assert restored is not None
        assert restored["session_id"] == "test_sess"
        assert restored["resume_step"] == 5
        assert restored["goal"] == "Implement feature"
        assert len(restored["tool_call_history"]) == 1

    @pytest.mark.asyncio
    async def test_restore_nonexistent(self, tmp_path: Path) -> None:
        import agent.checkpoint as ckpt

        ckpt._store = CheckpointStore(base_dir=tmp_path)
        assert await restore_agent_state("nonexistent") is None

    @pytest.mark.asyncio
    async def test_checkpoint_with_error(self, tmp_path: Path) -> None:
        import agent.checkpoint as ckpt

        ckpt._store = CheckpointStore(base_dir=tmp_path)

        checkpoint_agent_state(
            session_id="err_sess",
            step_index=2,
            goal="Bug fix",
            plan_steps=[],
            completed_steps=[0],
            tool_call_history=[],
            error_info="Ollama connection timeout",
        )

        restored = await restore_agent_state("err_sess")
        assert restored is not None
        assert restored["had_error"] is True
        assert "timeout" in str(restored["error_info"])

    @pytest.mark.asyncio
    async def test_cleanup_checkpoints(self, tmp_path: Path) -> None:
        import agent.checkpoint as ckpt

        ckpt._store = CheckpointStore(base_dir=tmp_path)

        checkpoint_agent_state(
            session_id="cleanup_sess",
            step_index=0,
            goal="Test cleanup",
            plan_steps=[],
            completed_steps=[],
            tool_call_history=[],
        )
        assert await restore_agent_state("cleanup_sess") is not None

        await cleanup_checkpoints("cleanup_sess")
        assert await restore_agent_state("cleanup_sess") is None

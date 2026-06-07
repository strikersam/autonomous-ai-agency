"""Durable agent checkpointing for crash-recovery and resumption.

Provides serialisable snapshots of AgentRunner state so long-running
sessions can survive process restarts and resume from the last checkpoint.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("qwen-proxy")

DEFAULT_CHECKPOINT_DIR = ".data/checkpoints"


@dataclass
class Checkpoint:
    """Serialisable snapshot of agent execution state."""

    session_id: str
    step_index: int
    goal: str
    plan_steps: list[dict[str, Any]] = field(default_factory=list)
    completed_steps: list[int] = field(default_factory=list)
    tool_call_history: list[dict[str, Any]] = field(default_factory=list)
    scratchpad_raw: str = ""
    error_info: str | None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "step_index": self.step_index,
            "goal": self.goal,
            "plan_steps": self.plan_steps,
            "completed_steps": self.completed_steps,
            "tool_call_history": self.tool_call_history,
            "scratchpad_raw": self.scratchpad_raw[:8000],
            "error_info": self.error_info,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Checkpoint:
        return cls(
            session_id=data["session_id"],
            step_index=data.get("step_index", 0),
            goal=data.get("goal", ""),
            plan_steps=data.get("plan_steps", []),
            completed_steps=data.get("completed_steps", []),
            tool_call_history=data.get("tool_call_history", []),
            scratchpad_raw=data.get("scratchpad_raw", ""),
            error_info=data.get("error_info"),
            created_at=data.get("created_at", ""),
        )


class CheckpointStore:
    """File-backed checkpoint persistence.

    Each session gets a directory under ``_base_dir`` and checkpoints are
    written as numbered JSON files.  On restore the store returns the
    highest-numbered checkpoint for a session.
    """

    def __init__(self, base_dir: str | Path | None = None) -> None:
        import os

        self._base_dir = Path(
            base_dir or os.environ.get("AGENT_CHECKPOINT_DIR") or DEFAULT_CHECKPOINT_DIR
        )
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _session_dir(self, session_id: str) -> Path:
        d = self._base_dir / session_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save(self, checkpoint: Checkpoint) -> Path:
        """Persist a checkpoint to disk.  Returns the file path."""
        import time

        checkpoint.created_at = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )
        sd = self._session_dir(checkpoint.session_id)
        path = sd / f"checkpoint_{checkpoint.step_index:04d}.json"
        with open(path, "w") as f:
            json.dump(checkpoint.to_dict(), f, indent=2)
        log.debug(
            "CheckpointStore: saved checkpoint at step %d for session %s",
            checkpoint.step_index,
            checkpoint.session_id,
        )
        return path

    def load_latest(self, session_id: str) -> Checkpoint | None:
        """Return the latest checkpoint for a session, or None."""
        sd = self._session_dir(session_id)
        files = sorted(sd.glob("checkpoint_*.json"))
        if not files:
            return None
        latest = files[-1]
        try:
            with open(latest) as f:
                data = json.load(f)
            return Checkpoint.from_dict(data)
        except (json.JSONDecodeError, KeyError) as exc:
            log.warning(
                "CheckpointStore: corrupt checkpoint %s — %s", latest, exc
            )
            return None

    def list_checkpoints(self, session_id: str) -> list[Path]:
        """Return all checkpoint files for a session, sorted by step index."""
        sd = self._session_dir(session_id)
        return sorted(sd.glob("checkpoint_*.json"))

    def delete_session(self, session_id: str) -> None:
        """Remove all checkpoints for a session."""
        import shutil

        sd = self._base_dir / session_id
        if sd.exists():
            shutil.rmtree(sd)
            log.debug(
                "CheckpointStore: deleted checkpoints for session %s",
                session_id,
            )


def _get_checkpoint_store() -> CheckpointStore:
    """Return the process-wide singleton CheckpointStore."""
    global _store
    if "_store" not in globals():
        _store = CheckpointStore()
    return _store


def checkpoint_agent_state(
    session_id: str,
    step_index: int,
    goal: str,
    plan_steps: list[dict[str, Any]],
    completed_steps: list[int],
    tool_call_history: list[dict[str, Any]],
    scratchpad_raw: str = "",
    error_info: str | None = None,
) -> Checkpoint:
    """Save the current agent state as a durable checkpoint.

    Called at key lifecycle points (step boundaries, errors) so the session
    can be restored after a crash.
    """
    store = _get_checkpoint_store()
    cp = Checkpoint(
        session_id=session_id,
        step_index=step_index,
        goal=goal,
        plan_steps=plan_steps,
        completed_steps=completed_steps,
        tool_call_history=tool_call_history,
        scratchpad_raw=scratchpad_raw,
        error_info=error_info,
    )
    store.save(cp)
    return cp


async def restore_agent_state(session_id: str) -> dict[str, Any] | None:
    """Restore the latest checkpoint for a session.

    Returns a dict with the checkpointed state suitable for resuming an
    AgentRunner session, or None if no checkpoint exists.
    """
    import asyncio
    store = _get_checkpoint_store()
    cp = await asyncio.to_thread(store.load_latest, session_id)
    if cp is None:
        return None
    return {
        "session_id": cp.session_id,
        "resume_step": cp.step_index + 1,
        "goal": cp.goal,
        "plan_steps": cp.plan_steps,
        "completed_steps": cp.completed_steps,
        "tool_call_history": cp.tool_call_history,
        "scratchpad_raw": cp.scratchpad_raw,
        "had_error": cp.error_info is not None,
        "error_info": cp.error_info,
    }


async def cleanup_checkpoints(session_id: str) -> None:
    """Remove all checkpoints for a session (called on successful completion)."""
    import asyncio
    store = _get_checkpoint_store()
    await asyncio.to_thread(store.delete_session, session_id)

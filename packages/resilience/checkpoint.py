"""packages/resilience/checkpoint.py — Task checkpointing.

Saves task progress mid-execution so that if a provider fails, the task
can resume from the last checkpoint on a different provider — without
losing work.

Inspired by OBLITERATUS (state preservation, transparent recovery),
implemented natively using the existing packages/ai/ + packages/storage/
architecture.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("resilience.checkpoint")


@dataclass
class Checkpoint:
    """A snapshot of task execution state."""
    task_id: str
    step_id: str
    provider_id: str
    model: str
    state: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "step_id": self.step_id,
            "provider_id": self.provider_id,
            "model": self.model,
            "state": self.state,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Checkpoint:
        return cls(
            task_id=d["task_id"],
            step_id=d["step_id"],
            provider_id=d["provider_id"],
            model=d["model"],
            state=d.get("state", {}),
            created_at=d.get("created_at", ""),
        )


class CheckpointManager:
    """Manages task checkpoints for transparent recovery.

    When a provider fails mid-task, the checkpoint allows resuming
    on a different provider from the last successful step — without
    re-executing completed work.
    """

    def __init__(self) -> None:
        self._checkpoints: dict[str, list[Checkpoint]] = {}  # task_id → checkpoints

    def save(self, checkpoint: Checkpoint) -> None:
        """Save a checkpoint."""
        self._checkpoints.setdefault(checkpoint.task_id, []).append(checkpoint)
        log.info(
            "Checkpoint saved: task=%s, step=%s, provider=%s",
            checkpoint.task_id, checkpoint.step_id, checkpoint.provider_id,
        )

    def get_latest(self, task_id: str) -> Checkpoint | None:
        """Get the latest checkpoint for a task."""
        checkpoints = self._checkpoints.get(task_id, [])
        return checkpoints[-1] if checkpoints else None

    def get_all(self, task_id: str) -> list[Checkpoint]:
        """Get all checkpoints for a task."""
        return self._checkpoints.get(task_id, [])

    def can_resume(self, task_id: str, new_provider_id: str) -> bool:
        """Check if a task can be resumed on a new provider."""
        latest = self.get_latest(task_id)
        if latest is None:
            return False
        # Can resume if the new provider is different from the one that failed
        return latest.provider_id != new_provider_id

    def resume_state(self, task_id: str) -> dict[str, Any] | None:
        """Get the state to resume from."""
        latest = self.get_latest(task_id)
        if latest is None:
            return None
        return latest.state

    def clear(self, task_id: str) -> None:
        """Clear all checkpoints for a task (after successful completion)."""
        self._checkpoints.pop(task_id, None)

    async def save_to_db(self, task_id: str) -> None:
        """Persist checkpoints to the database for cross-process recovery."""
        checkpoints = self._checkpoints.get(task_id, [])
        if not checkpoints:
            return
        try:
            from db import get_store
            store = get_store()
            col = getattr(store, "task_checkpoints", None)
            if col is not None:
                await col.insert_one({
                    "_id": task_id,
                    "checkpoints": [cp.to_dict() for cp in checkpoints],
                })
        except Exception as exc:
            log.debug("Checkpoint DB persist failed (non-fatal): %s", exc)


# Singleton
_manager: CheckpointManager | None = None


def get_checkpoint_manager() -> CheckpointManager:
    """Return the global checkpoint manager singleton."""
    global _manager
    if _manager is None:
        _manager = CheckpointManager()
    return _manager

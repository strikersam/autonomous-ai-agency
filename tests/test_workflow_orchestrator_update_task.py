"""tests/test_workflow_orchestrator_update_task.py
Pytest coverage for ``services.workflow_orchestrator.WorkflowOrchestrator.update_task``.

The bot's ``/redirect <run_id> <instruction>`` command and the
``POST /api/workflow/orchestrator/update-task/{run_id}`` endpoint both
delegate to this method. We mock the checkpoint store so tests don't
touch the real Mongo checkpoint backend (which isn't part of the test
DB), but everything else runs against the real orchestration code path.
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import workflow_orchestrator as wo  # noqa: E402


class _NoopCheckpointStore:
    """Stand-in for the real Mongo checkpoint store."""

    def __init__(self) -> None:
        self.saved: list = []

    async def save(self, run) -> None:
        self.saved.append(run)

    async def restore_in_flight_runs(self) -> list:
        return []


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


class TestUpdateTask(unittest.TestCase):
    def setUp(self) -> None:
        wo.reset_orchestrator()
        self.orch = wo.get_workflow_orchestrator()
        self.orch._checkpoint_store = _NoopCheckpointStore()

    def tearDown(self) -> None:
        wo.reset_orchestrator()

    def _build_run(self, status: str = "running") -> wo.WorkflowRun:
        run = wo.WorkflowRun(run_id="wfo_ut01", user_id="op@example.com")
        run.status = status
        run._request = wo.ExecutionRequest(
            request="original task description",
            user_id="op@example.com",
        )
        self.orch._runs[run.run_id] = run
        return run

    def test_update_task_happy_path_metadata_injection(self) -> None:
        run = self._build_run()
        updated = _run(
            self.orch.update_task(
                run.run_id,
                additional_instructions="focus only on tests X and Y",
                operator="telegram:42",
            )
        )
        # Status unchanged \u2014 update_task is meant to be a no-op on the
        # orchestrator state machine.
        self.assertEqual(updated.status, "running")
        meta = dict(updated._request.metadata or {})
        self.assertEqual(
            meta.get("additional_instructions"),
            "focus only on tests X and Y",
        )
        self.assertEqual(meta.get("updated_by"), "telegram:42")
        self.assertIn("updated_at_utc", meta)
        # Checkpoint ran
        self.assertEqual(len(self.orch._checkpoint_store.saved), 1)

    def test_update_task_idempotent_overwrite(self) -> None:
        """Two consecutive updates collapse: the latest instruction wins.
        This matches Telegram re-delivery after bot restart \u2014 the operator's
        freshest intent must beat any stale redirect.
        """
        run = self._build_run()
        _run(self.orch.update_task(run.run_id, additional_instructions="first"))
        _run(self.orch.update_task(run.run_id, additional_instructions="second"))
        meta = dict(self.orch._runs[run.run_id]._request.metadata or {})
        self.assertEqual(meta["additional_instructions"], "second")
        self.assertEqual(len(self.orch._checkpoint_store.saved), 2)

    def test_update_task_rejects_terminal_status(self) -> None:
        for terminal in ("done", "failed", "cancelled"):
            run = self._build_run(status=terminal)
            with self.assertRaises(ValueError) as ctx:
                _run(self.orch.update_task(run.run_id, additional_instructions="x"))
            self.assertIn(terminal, str(ctx.exception))

    def test_update_task_keyerror_for_missing_run(self) -> None:
        with self.assertRaises(KeyError):
            _run(self.orch.update_task("wfo_does_not_exist", additional_instructions="x"))

    def test_update_task_valueerror_for_run_without_request(self) -> None:
        run = self._build_run()
        run._request = None  # simulate a checkpoint-rehydrated run with no request
        with self.assertRaises(ValueError):
            _run(self.orch.update_task(run.run_id, additional_instructions="x"))

    def test_update_task_preserves_existing_metadata(self) -> None:
        run = self._build_run()
        run._request = wo.ExecutionRequest(
            request="r",
            metadata={"pre_existing": "keep-me", "another": 1},
        )
        _run(self.orch.update_task(run.run_id, additional_instructions="new"))
        meta = dict(self.orch._runs[run.run_id]._request.metadata or {})
        # Both pre-existing keys survive
        self.assertEqual(meta["pre_existing"], "keep-me")
        self.assertEqual(meta["another"], 1)
        self.assertEqual(meta["additional_instructions"], "new")


if __name__ == "__main__":
    unittest.main()

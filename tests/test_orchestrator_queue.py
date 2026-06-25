"""tests/test_orchestrator_queue.py — Tests for async FIFO run queue (#522)."""
from __future__ import annotations

import asyncio
import pytest


class TestOrchestratorQueue:
    """FIFO queue lifecycle, concurrency, and edge cases."""

    @pytest.fixture
    def queue(self):
        from services.orchestrator_queue import OrchestratorQueue, _queue as _q_singleton
        _q_backup = _q_singleton
        q = OrchestratorQueue(max_concurrent=2)
        # Replace singleton so enqueue calls find it
        import services.orchestrator_queue as mod
        mod._queue = q
        yield q
        mod._queue = _q_backup

    async def test_start_stop(self, queue):
        await queue.start()
        assert queue._running is True
        await queue.stop()
        assert queue._running is False

    async def test_enqueue_and_drain(self, queue):
        results = []

        async def _worker(run_id):
            results.append(run_id)
            return f"done:{run_id}"

        await queue.start()
        await queue.enqueue("r1", _worker, "r1")
        await asyncio.sleep(0.2)
        await queue.stop()
        assert "r1" in results, f"Worker never ran: {results}"

    async def test_concurrency_limit_respected(self, queue):
        running = 0
        max_seen = 0
        lock = asyncio.Lock()

        async def _worker(run_id):
            nonlocal running, max_seen
            async with lock:
                running += 1
                max_seen = max(max_seen, running)
            await asyncio.sleep(0.1)
            async with lock:
                running -= 1
            return f"done:{run_id}"

        await queue.start()
        for i in range(5):
            await queue.enqueue(f"r{i}", _worker, f"r{i}")
        await asyncio.sleep(0.8)
        await queue.stop()
        assert max_seen <= 2, f"Concurrency limit violated: {max_seen} > 2"

    async def test_fifo_ordering(self, queue):
        order = []

        async def _worker(run_id):
            order.append(run_id)
            return f"done:{run_id}"

        await queue.start()
        await queue.enqueue("a", _worker, "a")
        await queue.enqueue("b", _worker, "b")
        await queue.enqueue("c", _worker, "c")
        await asyncio.sleep(0.3)
        await queue.stop()
        assert order == ["a", "b", "c"], f"FIFO violated: {order}"

    async def test_queue_status(self, queue):
        await queue.start()
        s = queue.status()
        assert s["max_concurrent"] == 2
        assert s["active"] >= 0
        assert s["queued"] >= 0
        assert isinstance(s["active_run_ids"], list)
        await queue.stop()

    async def test_fire_and_forget_failure_no_unretrieved_exception_warning(self, queue):
        """enqueue() (fire-and-forget) is used by the supervisor and restore
        path, whose futures are never awaited. A failing job must NOT call
        set_exception() on that future — doing so triggers asyncio's "Future
        exception was never retrieved" log spam once the entry is GC'd."""
        import gc

        async def _failing(run_id):
            raise RuntimeError(f"boom-{run_id}")

        unraisable: list[dict] = []
        loop = asyncio.get_event_loop()
        orig_handler = loop.get_exception_handler()
        loop.set_exception_handler(lambda loop, context: unraisable.append(context))

        try:
            await queue.start()
            await queue.enqueue("fail-1", _failing, "fail-1")
            await asyncio.sleep(0.2)
            await queue.stop()
            gc.collect()
            await asyncio.sleep(0)
        finally:
            loop.set_exception_handler(orig_handler)

        bad = [c for c in unraisable if "never retrieved" in str(c.get("message", "")).lower()]
        assert not bad, f"Unexpected 'never retrieved' warning(s): {bad}"

    async def test_enqueue_and_wait_still_propagates_exceptions(self, queue):
        """enqueue_and_wait() callers DO await the future, so failures must
        still raise for them."""
        async def _failing(run_id):
            raise RuntimeError(f"boom-{run_id}")

        await queue.start()
        with pytest.raises(RuntimeError, match="boom-fail-2"):
            await queue.enqueue_and_wait("fail-2", _failing, "fail-2")
        await queue.stop()

    async def test_empty_queue_indexerror_handled(self, queue):
        """Drain loop must handle dequeue from empty queue gracefully."""
        await queue.start()
        # No items enqueued; drain loop must not crash.
        await asyncio.sleep(0.1)
        assert queue.queue_depth == 0
        assert queue.active_count == 0
        await queue.stop()


class TestApproveAsync:
    """approve_async uses the queue to return 202 immediately."""

    async def test_approve_async_sets_queued_status(self):
        from services.workflow_orchestrator import (
            ExecutionRequest,
            get_workflow_orchestrator,
            reset_orchestrator,
        )

        reset_orchestrator()
        orch = get_workflow_orchestrator()

        req = ExecutionRequest(
            request="test approve async",
            auto_approve=False,
            max_steps=1,
        )
        run1 = await orch.execute(req)
        assert run1.status == "awaiting_approval"

        # approve_async should return immediately with queued status
        import services.orchestrator_queue as oq_mod
        q = oq_mod.OrchestratorQueue(max_concurrent=2)
        oq_mod._queue = q
        await q.start()

        run2 = await orch.approve_async(run1.run_id, approved_by="test")
        assert run2.status == "queued", f"Expected queued, got {run2.status!r}"
        assert run2.approved is True

        await asyncio.sleep(0.3)
        await q.stop()

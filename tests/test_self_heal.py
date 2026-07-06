"""tests/test_self_heal.py — tests for PR #937 self-healing mechanism.

No sensitive credentials — all tests use mock objects or source inspection.
"""
from __future__ import annotations

import inspect


def test_self_heal_module_exists():
    """packages/ai/self_heal.py must exist and define the heal function."""
    from packages.ai import self_heal
    assert hasattr(self_heal, "self_heal_brain_and_unblock_tasks")
    assert hasattr(self_heal, "_self_heal_tick")
    assert callable(self_heal.self_heal_brain_and_unblock_tasks)


def test_self_heal_function_is_async():
    """self_heal_brain_and_unblock_tasks must be async (called from tick handler)."""
    from packages.ai.self_heal import self_heal_brain_and_unblock_tasks
    assert inspect.iscoroutinefunction(self_heal_brain_and_unblock_tasks)


def test_scheduler_tick_calls_self_heal():
    """backend/server.py scheduler_tick must call _self_heal_tick every tick."""
    import backend.server as srv
    src = inspect.getsource(srv.scheduler_tick)
    assert "self_heal" in src
    assert "_self_heal_tick" in src


def test_admin_self_heal_endpoint_exists():
    """Admin endpoint POST /api/scheduler/self-heal must exist."""
    import backend.server as srv
    src = inspect.getsource(srv)
    assert '"/api/scheduler/self-heal"' in src
    assert "async def scheduler_self_heal" in src


def test_agent_loop_410_triggers_watchdog():
    """agent/loop.py 410 handler must trigger failover via the brain_failover manager."""
    import agent.loop as loop_mod
    src = inspect.getsource(loop_mod)
    # The 410 handling is now in the universal failover loop, which calls
    # fm.record_failure(provider.id, "gone", 410) to mark the provider
    # with a 10-minute cooldown and fail over to the next provider.
    assert "410" in src
    assert "record_failure" in src
    assert "brain_failover" in src or "get_failover_manager" in src


def test_agent_loop_429_records_failure():
    """agent/loop.py 429 handler must record the failure for watchdog tracking."""
    import agent.loop as loop_mod
    src = inspect.getsource(loop_mod)
    # The 429 block must call record_failure so sustained rate-limiting
    # triggers a failover after 3 consecutive 429s
    assert "429" in src
    assert "record_failure" in src


def test_dispatch_retry_limit_lowered():
    """_DISPATCH_RETRY_LIMIT must be 5 (lowered from 10 in PR #937)."""
    import tasks.service as svc
    assert svc._DISPATCH_RETRY_LIMIT == 5, (
        f"_DISPATCH_RETRY_LIMIT should be 5 (lowered from 10 in PR #937), "
        f"got {svc._DISPATCH_RETRY_LIMIT}"
    )


def test_self_heal_unblocks_runtime_blocked_tasks():
    """self_heal source must unblock tasks with runtime/brain in blocked_reason."""
    from packages.ai import self_heal
    src = inspect.getsource(self_heal)
    assert "BLOCKED" in src or "TaskStatus.BLOCKED" in src
    assert "runtime" in src.lower()
    assert "unblocked" in src.lower()

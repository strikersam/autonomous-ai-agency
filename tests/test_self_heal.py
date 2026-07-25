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


# The provider-dispatch loop no longer lives in agent/loop.py. It was extracted
# to packages/ai/failover_client.py so backend.server.call_llm (the agency CEO's
# path) could share the same provider chain instead of falling back across a
# narrower set. These two tests therefore assert against the module that now owns
# the per-status handling, plus the fact that the loop still delegates to it —
# which is the property that actually matters. Asserting on agent/loop.py's
# source alone would pass again the moment anyone re-inlined the loop.


def test_agent_loop_410_triggers_watchdog():
    """410 must mark the provider failed and fail over to the next one."""
    import packages.ai.failover_client as fc
    src = inspect.getsource(fc)
    # 410 Gone is per-MODEL: try the next model on the same provider first.
    assert "410" in src
    assert "record_failure" in src

    import agent.loop as loop_mod
    loop_src = inspect.getsource(loop_mod)
    assert "failover_chat_completion" in loop_src, (
        "agent/loop.py no longer delegates to the shared failover client, so the "
        "410 handling asserted above is not reachable from the agent loop"
    )


def test_agent_loop_429_records_failure():
    """429 must record the failure so sustained rate-limiting trips failover."""
    import packages.ai.failover_client as fc
    src = inspect.getsource(fc)
    assert "429" in src
    assert "record_failure" in src
    assert "get_failover_manager" in src

    import agent.loop as loop_mod
    assert "failover_chat_completion" in inspect.getsource(loop_mod)


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

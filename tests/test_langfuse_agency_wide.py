"""tests/test_langfuse_agency_wide.py — tests for PR #961 agency-wide Langfuse.

Verifies emit_agency_observation exists and is called from every agency
touchpoint: task execution, CEO directives, SAM voice, scheduler tick,
self-heal. No sensitive credentials — source-inspection tests only.
"""
from __future__ import annotations

import inspect


def test_emit_agency_observation_exists():
    """langfuse_obs.py must define emit_agency_observation."""
    import langfuse_obs
    assert hasattr(langfuse_obs, "emit_agency_observation")
    assert callable(langfuse_obs.emit_agency_observation)


def test_emit_agency_observation_returns_none_when_disabled():
    """emit_agency_observation must be a no-op when Langfuse is not configured."""
    import langfuse_obs
    # Should not raise even with no env vars set
    result = langfuse_obs.emit_agency_observation(operation="test")
    assert result is None


def test_task_service_traces_execution():
    """tasks/service.py must call emit_agency_observation for task execution."""
    import tasks.service as svc
    src = inspect.getsource(svc)
    assert "emit_agency_observation" in src
    assert 'operation="task_execute"' in src
    # Must trace both success + failure + timeout
    assert 'status="ok"' in src
    assert 'status="timeout"' in src
    assert 'status="failed"' in src


def test_agency_py_traces_ceo_directives():
    """agent/agency.py must call emit_agency_observation for CEO directives."""
    import agent.agency as agency
    src = inspect.getsource(agency)
    assert "emit_agency_observation" in src
    assert 'operation="ceo_directive"' in src


def test_sam_py_traces_voice_commands():
    """agent/sam.py must call emit_agency_observation for voice commands."""
    import agent.sam as sam
    src = inspect.getsource(sam)
    assert "emit_agency_observation" in src
    assert 'operation="sam_voice"' in src


def test_scheduler_tick_traces():
    """backend/server.py scheduler_tick must call emit_agency_observation."""
    import backend.server as srv
    src = inspect.getsource(srv.scheduler_tick)
    assert "emit_agency_observation" in src
    assert 'operation="scheduler_tick"' in src


def test_self_heal_traces():
    """packages/ai/self_heal.py must call emit_agency_observation."""
    from packages.ai import self_heal
    src = inspect.getsource(self_heal)
    assert "emit_agency_observation" in src
    assert 'operation="self_heal"' in src


def test_emit_agency_observation_accepts_all_params():
    """emit_agency_observation must accept all documented parameters."""
    import langfuse_obs
    sig = inspect.signature(langfuse_obs.emit_agency_observation)
    params = set(sig.parameters.keys())
    expected = {"operation", "actor", "task_id", "task_title", "task_type",
                "status", "duration_ms", "model", "input_text", "output_text",
                "metadata", "error"}
    assert expected.issubset(params), f"missing params: {expected - params}"

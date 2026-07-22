"""Tests for CEODispatcher._maybe_cross_verify (opt-in risky-module re-check)."""
from __future__ import annotations

import asyncio

import pytest

from services.ceo_dispatcher import CEODispatcher, CEOResult


def _base_result() -> CEOResult:
    return CEOResult(goal="g", specialists=[], summary="s", total_duration_s=1.0)


def test_cross_verify_noop_when_disabled(monkeypatch):
    monkeypatch.delenv("AGENT_CROSS_VERIFY_ENABLED", raising=False)
    ceo = CEODispatcher()
    result = _base_result()
    specialists = [{"status": "ok", "changed_files": ["admin_auth.py"]}]
    asyncio.run(
        ceo._maybe_cross_verify(
            result, request="r", specialists_out=specialists,
            workspace_root=None, ollama_base=None, github_token=None, user_id=None,
        )
    )
    assert result.cross_verification is None


def test_cross_verify_noop_when_no_risky_files(monkeypatch):
    monkeypatch.setenv("AGENT_CROSS_VERIFY_ENABLED", "true")
    ceo = CEODispatcher()
    result = _base_result()
    specialists = [{"status": "ok", "changed_files": ["frontend/src/App.js"]}]
    asyncio.run(
        ceo._maybe_cross_verify(
            result, request="r", specialists_out=specialists,
            workspace_root=None, ollama_base=None, github_token=None, user_id=None,
        )
    )
    assert result.cross_verification is None


def test_cross_verify_runs_and_attaches_result_for_risky_files(monkeypatch):
    monkeypatch.setenv("AGENT_CROSS_VERIFY_ENABLED", "true")

    async def fake_cross_verify(*, instruction, changed_files, runner_factory, max_steps=2):
        assert "admin_auth.py" in changed_files
        return {"cross_verified": False, "issues": ["looks off"], "raw": {}}

    monkeypatch.setattr(
        "agent.verification_strategies.cross_verify", fake_cross_verify
    )

    ceo = CEODispatcher()
    result = _base_result()
    specialists = [{"status": "ok", "changed_files": ["admin_auth.py"]}]
    asyncio.run(
        ceo._maybe_cross_verify(
            result, request="Fix auth bug", specialists_out=specialists,
            workspace_root=None, ollama_base=None, github_token=None, user_id=None,
        )
    )
    assert result.cross_verification is not None
    assert result.cross_verification["cross_verified"] is False
    assert result.as_dict()["cross_verification"]["issues"] == ["looks off"]


def test_cross_verify_actually_runs_under_default_orchestrator_mode(monkeypatch, tmp_path):
    """Regression: AgentRunner.run() raises immediately unless legacy mode or
    the _BYPASS contextvar is set (its own DEPRECATION guard). The default
    production setting is AGENCY_WORKFLOW_MODE=orchestrator, not legacy —
    but conftest's autouse `_set_legacy_workflow_mode` fixture patches every
    test to legacy mode by default, which is exactly why the original stub-
    based tests above never caught that cross_verify's runner_factory would
    always fail with "blocked in orchestrator mode" in real deployments.
    This test explicitly restores orchestrator mode and exercises a REAL
    AgentRunner (not a stub) through the full call path.
    """
    import services.workflow_orchestrator as wf_orch
    monkeypatch.setattr(wf_orch, "WORKFLOW_MODE", "orchestrator")
    assert wf_orch.is_legacy_mode() is False  # sanity: orchestrator mode is really active

    monkeypatch.setenv("AGENT_CROSS_VERIFY_ENABLED", "true")

    from agent.loop import AgentRunner

    responses = iter([
        '{"goal":"Review","steps":[]}',  # planner: no steps needed, review-only
    ])

    async def fake_chat_text(self, model, messages):
        return next(responses)

    monkeypatch.setattr(AgentRunner, "_chat_text", fake_chat_text)

    ceo = CEODispatcher()
    result = _base_result()
    specialists = [{"status": "ok", "changed_files": ["admin_auth.py"]}]
    asyncio.run(
        ceo._maybe_cross_verify(
            result, request="Fix auth bug", specialists_out=specialists,
            workspace_root=str(tmp_path), ollama_base="http://localhost:11434",
            github_token=None, user_id=None,
        )
    )
    assert result.cross_verification is not None
    # The key assertion: it actually ran (cross_verified reflects a real
    # outcome), not the generic "cross_verify_error: ... blocked in
    # orchestrator mode" failure this bug produced.
    assert "cross_verify_error" not in " ".join(result.cross_verification.get("issues", []))
    assert result.cross_verification["cross_verified"] is True


def test_cross_verify_resets_bypass_after_running(monkeypatch):
    """The _BYPASS contextvar must not leak true after cross_verify finishes,
    or every subsequent AgentRunner/MultiAgentSwarm call would silently skip
    the orchestrator-mode guard for the rest of the process."""
    import services.workflow_orchestrator as wf_orch
    monkeypatch.setattr(wf_orch, "WORKFLOW_MODE", "orchestrator")

    async def fake_cross_verify(*, instruction, changed_files, runner_factory, max_steps=2):
        # Assert the bypass is active *during* the call.
        assert wf_orch.is_legacy_mode() is True
        return {"cross_verified": True, "issues": [], "raw": {}}

    monkeypatch.setattr("agent.verification_strategies.cross_verify", fake_cross_verify)
    monkeypatch.setenv("AGENT_CROSS_VERIFY_ENABLED", "true")

    ceo = CEODispatcher()
    result = _base_result()
    specialists = [{"status": "ok", "changed_files": ["admin_auth.py"]}]
    asyncio.run(
        ceo._maybe_cross_verify(
            result, request="r", specialists_out=specialists,
            workspace_root=None, ollama_base=None, github_token=None, user_id=None,
        )
    )
    # Bypass must be reset after the call — orchestrator mode restored.
    assert wf_orch.is_legacy_mode() is False


def test_cross_verify_swallows_errors(monkeypatch):
    monkeypatch.setenv("AGENT_CROSS_VERIFY_ENABLED", "true")

    async def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("agent.verification_strategies.cross_verify", boom)

    ceo = CEODispatcher()
    result = _base_result()
    specialists = [{"status": "ok", "changed_files": ["agent/tools.py"]}]
    # Should not raise.
    asyncio.run(
        ceo._maybe_cross_verify(
            result, request="r", specialists_out=specialists,
            workspace_root=None, ollama_base=None, github_token=None, user_id=None,
        )
    )
    assert result.cross_verification is None

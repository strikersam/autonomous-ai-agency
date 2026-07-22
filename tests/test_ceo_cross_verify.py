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

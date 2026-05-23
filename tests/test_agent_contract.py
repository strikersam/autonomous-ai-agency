"""Tests for agent/contract.py — typed AgentJobRequest / AgentJobResult / AgentJobError."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent.contract import (
    AgentJobError,
    AgentJobRequest,
    AgentJobResult,
    AgentJobSnapshot,
)


# ─── AgentJobRequest ──────────────────────────────────────────────────────────

class TestAgentJobRequest:
    def test_minimal_valid(self) -> None:
        req = AgentJobRequest(session_id="s-1", instruction="Do something")
        assert req.session_id == "s-1"
        assert req.instruction == "Do something"
        assert req.owner_id is None
        assert req.runtime_id == "internal_agent"
        assert req.allow_commercial_fallback is True

    def test_full_fields(self) -> None:
        req = AgentJobRequest(
            session_id="sess-abc",
            owner_id="user-xyz",
            instruction="Refactor this module.",
            requested_model="qwen3-coder",
            provider_id="ollama-local",
            runtime_id="claude_code",
            allow_commercial_fallback=False,
        )
        assert req.requested_model == "qwen3-coder"
        assert req.allow_commercial_fallback is False

    def test_blank_instruction_rejected(self) -> None:
        with pytest.raises(ValidationError, match="blank"):
            AgentJobRequest(session_id="s-1", instruction="   ")

    def test_empty_instruction_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentJobRequest(session_id="s-1", instruction="")

    def test_blank_session_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentJobRequest(session_id="", instruction="Do something")

    def test_whitespace_stripped_from_strings(self) -> None:
        req = AgentJobRequest(session_id="  s-1  ", instruction="  Do it  ")
        assert req.session_id == "s-1"
        assert req.instruction == "Do it"

    def test_model_is_immutable(self) -> None:
        req = AgentJobRequest(session_id="s-1", instruction="Do it")
        with pytest.raises(Exception):  # ValidationError or AttributeError depending on Pydantic version
            req.instruction = "changed"  # type: ignore[misc]

    def test_instruction_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentJobRequest(session_id="s-1", instruction="x" * 33_000)


# ─── AgentJobResult ───────────────────────────────────────────────────────────

class TestAgentJobResult:
    def test_from_string(self) -> None:
        result = AgentJobResult.model_validate("Hello from the agent")
        assert result.response == "Hello from the agent"
        assert result.raw == "Hello from the agent"

    def test_from_dict_with_response(self) -> None:
        result = AgentJobResult.model_validate({"response": "Done", "raw": {"debug": True}})
        assert result.response == "Done"

    def test_from_dict_with_summary_fallback(self) -> None:
        result = AgentJobResult.model_validate({"summary": "Summarised result"})
        assert result.response == "Summarised result"

    def test_from_dict_with_output_fallback(self) -> None:
        result = AgentJobResult.model_validate({"output": "Final output"})
        assert result.response == "Final output"

    def test_from_dict_with_report_string_fallback(self) -> None:
        result = AgentJobResult.model_validate({"report": "Report text"})
        assert result.response == "Report text"

    def test_from_empty_dict(self) -> None:
        result = AgentJobResult.model_validate({})
        assert result.response == ""

    def test_immutable(self) -> None:
        result = AgentJobResult(response="Done")
        with pytest.raises(Exception):
            result.response = "changed"  # type: ignore[misc]


# ─── AgentJobError ────────────────────────────────────────────────────────────

class TestAgentJobError:
    def test_known_codes_preserved(self) -> None:
        for code in ("runtime_preflight", "runtime_unavailable", "runtime_execution_error", "unknown"):
            err = AgentJobError(code=code, type="SomeError", message="oops")
            assert err.code == code

    def test_unknown_code_normalised(self) -> None:
        err = AgentJobError(code="bizarre_custom_code", type="E", message="x")
        assert err.code == "unknown"

    def test_defaults(self) -> None:
        err = AgentJobError()
        assert err.code == "unknown"
        assert err.type == "Exception"
        assert err.message == ""
        assert err.report is None

    def test_with_report(self) -> None:
        err = AgentJobError(
            code="runtime_preflight",
            type="RuntimePreflightError",
            message="preflight failed",
            report={"checks": ["docker missing"]},
        )
        assert err.report == {"checks": ["docker missing"]}


# ─── AgentJobSnapshot ─────────────────────────────────────────────────────────

class TestAgentJobSnapshot:
    def _make_job(self, **overrides):
        """Build a minimal mock AgentJob-like object."""
        from types import SimpleNamespace
        defaults = dict(
            job_id="aj_abc123",
            session_id="s-1",
            instruction="Do it",
            owner_id="u-1",
            status="succeeded",
            phase="completed",
            runtime_id="internal_agent",
            workspace_path=None,
            requested_model=None,
            provider_id=None,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:01:00Z",
            heartbeat_at="2026-01-01T00:01:00Z",
            progress_events=[{"phase": "completed", "message": "Done"}],
            result={"response": "All done", "raw": {}},
            error=None,
        )
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def test_from_succeeded_job(self) -> None:
        job = self._make_job()
        snap = AgentJobSnapshot.from_agent_job(job)
        assert snap.job_id == "aj_abc123"
        assert snap.status == "succeeded"
        assert snap.result is not None
        assert snap.result.response == "All done"
        assert snap.final_message == "All done"
        assert snap.error is None

    def test_from_failed_job(self) -> None:
        job = self._make_job(
            status="failed",
            phase="failed",
            result=None,
            error={"code": "runtime_unavailable", "type": "RuntimeUnavailableError", "message": "No provider"},
        )
        snap = AgentJobSnapshot.from_agent_job(job)
        assert snap.status == "failed"
        assert snap.error is not None
        assert snap.error.code == "runtime_unavailable"
        assert snap.final_message == "No provider"
        assert snap.result is None

    def test_from_queued_job(self) -> None:
        job = self._make_job(status="queued", phase="queued", result=None, error=None)
        snap = AgentJobSnapshot.from_agent_job(job)
        assert snap.final_message is None

    def test_serialises_to_dict(self) -> None:
        job = self._make_job()
        snap = AgentJobSnapshot.from_agent_job(job)
        d = snap.model_dump()
        assert d["job_id"] == "aj_abc123"
        assert d["result"]["response"] == "All done"

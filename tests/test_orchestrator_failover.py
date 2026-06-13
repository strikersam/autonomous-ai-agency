"""tests/test_orchestrator_failover.py — Provider failover, brain resolution, llm_provenance.

Verifies that when a provider fails during execution, the orchestrator's retry
loop (via _run_phase_with_timeout) picks the next-highest-priority provider and
llm_provenance records the change (#522).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from services.workflow_orchestrator import (
    ExecutionRequest,
    WorkflowOrchestrator,
    _resolve_brain_provider,
    reset_orchestrator,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mock_provider_records(*providers: dict) -> AsyncMock:
    """Return an AsyncMock that returns the given provider list."""
    return AsyncMock(return_value=list(providers))


# ── _resolve_brain_provider (module-level) ────────────────────────────────────


class TestResolveBrainProvider:
    """Unit tests for the module-level _resolve_brain_provider function."""

    async def test_env_override_wins(self, monkeypatch):
        """AGENT_LLM_BASE_URL overrides all configured providers."""
        monkeypatch.setenv("AGENT_LLM_BASE_URL", "http://env-provider.local")
        monkeypatch.setenv("AGENT_LLM_API_KEY", "env-key-123")
        monkeypatch.setenv("AGENT_LLM_MODEL", "env-model")

        base, headers, model = await _resolve_brain_provider()

        assert base == "http://env-provider.local"
        assert headers == {"Authorization": "Bearer env-key-123"}
        assert model == "env-model"

    async def test_env_override_no_key_returns_no_headers(self, monkeypatch):
        """AGENT_LLM_BASE_URL without key still works (headers=None)."""
        monkeypatch.setenv("AGENT_LLM_BASE_URL", "http://env-no-key.local")

        base, headers, model = await _resolve_brain_provider()

        assert base == "http://env-no-key.local"
        assert headers is None

    async def test_highest_priority_selected_first(self, monkeypatch):
        """The provider with the highest priority value is selected."""
        records = _mock_provider_records(
            {"provider_id": "low", "base_url": "http://low.local", "type": "openai", "api_key": "k1", "default_model": "low-model", "priority": 1},
            {"provider_id": "high", "base_url": "http://high.local", "type": "openai", "api_key": "k2", "default_model": "high-model", "priority": 10},
            {"provider_id": "mid", "base_url": "http://mid.local", "type": "openai", "api_key": "k3", "default_model": "mid-model", "priority": 5},
        )
        with patch("backend.server._list_configured_provider_records", records):
            base, headers, model = await _resolve_brain_provider()

        assert base == "http://high.local/v1"
        assert model == "high-model"

    async def test_excluded_url_is_skipped(self, monkeypatch):
        """When a base URL is excluded, the next-highest-priority provider is picked."""
        records = _mock_provider_records(
            {"provider_id": "primary", "base_url": "http://primary.local", "type": "openai", "api_key": "k1", "default_model": "primary-model", "priority": 10},
            {"provider_id": "fallback", "base_url": "http://fallback.local", "type": "openai", "api_key": "k2", "default_model": "fallback-model", "priority": 5},
        )
        with patch("backend.server._list_configured_provider_records", records):
            base, headers, model = await _resolve_brain_provider(
                exclude_base_urls={"http://primary.local/v1"}
            )

        assert base == "http://fallback.local/v1"
        assert model == "fallback-model"

    async def test_multiple_excluded_urls(self, monkeypatch):
        """Multiple excluded URLs are all skipped."""
        records = _mock_provider_records(
            {"provider_id": "first", "base_url": "http://first.local", "type": "openai", "api_key": "k1", "default_model": "first-model", "priority": 10},
            {"provider_id": "second", "base_url": "http://second.local", "type": "openai", "api_key": "k2", "default_model": "second-model", "priority": 8},
            {"provider_id": "third", "base_url": "http://third.local", "type": "openai", "api_key": "k3", "default_model": "third-model", "priority": 5},
        )
        with patch("backend.server._list_configured_provider_records", records):
            base, headers, model = await _resolve_brain_provider(
                exclude_base_urls={"http://first.local/v1", "http://second.local/v1"}
            )

        assert base == "http://third.local/v1"
        assert model == "third-model"

    async def test_exclude_set_is_empty_by_default(self, monkeypatch):
        """Without exclude_base_urls, the highest-priority provider is always selected."""
        records = _mock_provider_records(
            {"provider_id": "only", "base_url": "http://only.local", "type": "openai", "api_key": "k1", "default_model": "only-model", "priority": 1},
        )
        with patch("backend.server._list_configured_provider_records", records):
            base, headers, model = await _resolve_brain_provider()
            assert base == "http://only.local/v1"

            # Calling without exclude should still return the same provider.
            base2, _, model2 = await _resolve_brain_provider()
            assert base2 == "http://only.local/v1"

    async def test_providers_without_key_are_skipped(self, monkeypatch):
        """Non-Ollama providers without an API key are skipped."""
        records = _mock_provider_records(
            {"provider_id": "no-key", "base_url": "http://no-key.local", "type": "openai", "api_key": "", "default_model": "bad", "priority": 10},
            {"provider_id": "has-key", "base_url": "http://has-key.local", "type": "openai", "api_key": "k1", "default_model": "good", "priority": 5},
        )
        with patch("backend.server._list_configured_provider_records", records):
            base, _, model = await _resolve_brain_provider()

        assert base == "http://has-key.local/v1"
        assert model == "good"

    async def test_ollama_type_does_not_require_key(self, monkeypatch):
        """Ollama-type providers don't need an API key."""
        records = _mock_provider_records(
            {"provider_id": "local-ollama", "base_url": "http://ollama.local", "type": "ollama", "api_key": "", "default_model": "llama3", "priority": 10},
        )
        with patch("backend.server._list_configured_provider_records", records):
            base, headers, model = await _resolve_brain_provider()

        assert base == "http://ollama.local/v1"
        assert headers is None
        assert model == "llama3"

    async def test_records_list_failure_falls_back_to_ollama_env(self, monkeypatch):
        """When _list_configured_provider_records raises, falls back to OLLAMA_BASE."""
        monkeypatch.setenv("OLLAMA_BASE", "http://my-ollama:11434")

        async def _fail():
            raise RuntimeError("DB offline")

        with patch("backend.server._list_configured_provider_records", _fail):
            base, headers, model = await _resolve_brain_provider()

        assert base == "http://my-ollama:11434"
        assert headers is None
        assert model is None

    async def test_excluded_url_with_fallback_to_ollama(self, monkeypatch):
        """When all configured providers are excluded, falls back to Ollama."""
        monkeypatch.setenv("OLLAMA_BASE", "http://ollama-fallback:11434")
        records = _mock_provider_records(
            {"provider_id": "only", "base_url": "http://only.local", "type": "openai", "api_key": "k1", "default_model": "only-model", "priority": 10},
        )
        with patch("backend.server._list_configured_provider_records", records):
            base, _, model = await _resolve_brain_provider(
                exclude_base_urls={"http://only.local/v1"}
            )

        # No non-excluded provider found → falls back to Ollama.
        assert base == "http://ollama-fallback:11434"


# ── Full orchestrator failover flow ────────────────────────────────────────────


class TestOrchestratorProviderFailover:
    """End-to-end provider failover through the WorkflowOrchestrator."""

    @pytest.fixture(autouse=True)
    def _reset(self):
        reset_orchestrator()
        yield
        reset_orchestrator()

    async def test_failover_records_correct_provenance(self, monkeypatch):
        """First provider fails → retry picks next → llm_provenance tracks the winner."""
        call_count = 0

        async def _runner_run(self, instruction, history, requested_model, auto_commit, max_steps, user_id, session_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("provider A unreachable")
            return {"summary": "success on fallback", "steps": [], "judge": {}}

        records = _mock_provider_records(
            {"provider_id": "primary", "base_url": "http://primary-fail.local", "type": "openai", "api_key": "k1", "default_model": "primary-model", "priority": 10},
            {"provider_id": "fallback", "base_url": "http://fallback-ok.local", "type": "openai", "api_key": "k2", "default_model": "fallback-model", "priority": 5},
        )

        orchestrator = WorkflowOrchestrator()
        req = ExecutionRequest(request="test failover", auto_approve=True)

        with patch("agent.loop.AgentRunner.run", _runner_run):
            with patch("backend.server._list_configured_provider_records", records):
                run = await orchestrator.execute(req)

        assert run.llm_provenance["execute"] == "fallback-model"
        assert run.phase_attempts.get("execute", 0) == 2
        assert call_count == 2

    async def test_failover_tracks_failed_providers(self, monkeypatch):
        """The _failed_execute key in llm_provenance records the URLs that failed."""
        call_count = 0

        async def _runner_run(self, instruction, history, requested_model, auto_commit, max_steps, user_id, session_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("first failure")
            if call_count == 2:
                raise ConnectionError("second failure")
            return {"summary": "third time's a charm", "steps": [], "judge": {}}

        records = _mock_provider_records(
            {"provider_id": "a", "base_url": "http://a.local", "type": "openai", "api_key": "k1", "default_model": "a-model", "priority": 30},
            {"provider_id": "b", "base_url": "http://b.local", "type": "openai", "api_key": "k2", "default_model": "b-model", "priority": 20},
            {"provider_id": "c", "base_url": "http://c.local", "type": "openai", "api_key": "k3", "default_model": "c-model", "priority": 10},
        )

        orchestrator = WorkflowOrchestrator()
        req = ExecutionRequest(request="triple failover", auto_approve=True)

        with patch("agent.loop.AgentRunner.run", _runner_run):
            with patch("backend.server._list_configured_provider_records", records):
                run = await orchestrator.execute(req)

        assert run.llm_provenance["execute"] == "c-model"
        assert run.phase_attempts.get("execute", 0) == 3
        assert call_count == 3
        # _failed_execute tracks the two that failed.
        # URLs are stored in the normalized /v1 form that _resolve_brain_provider
        # compares against during exclusion.
        failed = run.llm_provenance.get("_failed_execute", "")
        failed_set = set(failed.split(",")) if failed else set()
        assert "http://a.local/v1" in failed_set
        assert "http://b.local/v1" in failed_set

    async def test_non_retryable_error_does_not_failover(self, monkeypatch):
        """A non-retryable error (e.g. ValueError) does not trigger failover."""
        call_count = 0

        async def _runner_run(self, instruction, history, requested_model, auto_commit, max_steps, user_id, session_id):
            nonlocal call_count
            call_count += 1
            raise ValueError("this is not retryable")

        records = _mock_provider_records(
            {"provider_id": "only", "base_url": "http://only.local", "type": "openai", "api_key": "k1", "default_model": "only-model", "priority": 10},
            {"provider_id": "backup", "base_url": "http://backup.local", "type": "openai", "api_key": "k2", "default_model": "backup-model", "priority": 5},
        )

        orchestrator = WorkflowOrchestrator()
        req = ExecutionRequest(request="non-retryable", auto_approve=True)

        with patch("agent.loop.AgentRunner.run", _runner_run):
            with patch("backend.server._list_configured_provider_records", records):
                run = await orchestrator.execute(req)

        # Non-retryable error — run fails immediately with only 1 attempt.
        assert run.status == "failed"
        assert call_count == 1
        assert run.phase_attempts.get("execute", 0) == 1

    async def test_timeout_triggers_failover(self, monkeypatch):
        """A TimeoutError is retryable and should trigger provider failover."""
        call_count = 0

        async def _runner_run(self, instruction, history, requested_model, auto_commit, max_steps, user_id, session_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncio.TimeoutError("provider A timed out")
            return {"summary": "fallback worked", "steps": [], "judge": {}}

        records = _mock_provider_records(
            {"provider_id": "slow", "base_url": "http://slow.local", "type": "openai", "api_key": "k1", "default_model": "slow-model", "priority": 10},
            {"provider_id": "fast", "base_url": "http://fast.local", "type": "openai", "api_key": "k2", "default_model": "fast-model", "priority": 5},
        )

        orchestrator = WorkflowOrchestrator()
        req = ExecutionRequest(request="timeout failover", auto_approve=True)

        with patch("agent.loop.AgentRunner.run", _runner_run):
            with patch("backend.server._list_configured_provider_records", records):
                run = await orchestrator.execute(req)

        assert run.llm_provenance["execute"] == "fast-model"
        assert call_count == 2

    async def test_llm_provenance_is_none_for_phases_without_llm(self, monkeypatch):
        """Phases that don't use an LLM (CLASSIFY, PERSIST, etc.) don't record provenance."""
        records = _mock_provider_records(
            {"provider_id": "only", "base_url": "http://only.local", "type": "openai", "api_key": "k1", "default_model": "only-model", "priority": 10},
        )

        orchestrator = WorkflowOrchestrator()
        req = ExecutionRequest(request="provenance check", auto_approve=True)

        with patch("agent.loop.AgentRunner.run", AsyncMock(return_value={
            "summary": "ok", "steps": [], "judge": {},
        })):
            with patch("backend.server._list_configured_provider_records", records):
                run = await orchestrator.execute(req)

        # Only "execute" has provenance; other phases don't.
        assert "execute" in run.llm_provenance
        assert run.llm_provenance["execute"] == "only-model"
        # CLASSIFY doesn't call _resolve_brain_provider.
        assert "classify" not in run.llm_provenance
        # VERIFY doesn't call _resolve_brain_provider.
        assert "verify" not in run.llm_provenance

    async def test_phase_attempts_incremented_on_each_retry(self, monkeypatch):
        """phase_attempts tracks the attempt count per phase through retries."""
        call_count = 0

        async def _runner_run(self, instruction, history, requested_model, auto_commit, max_steps, user_id, session_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("fail 1")
            if call_count == 2:
                raise ConnectionError("fail 2")
            return {"summary": "success", "steps": [], "judge": {}}

        records = _mock_provider_records(
            {"provider_id": "a", "base_url": "http://a.local", "type": "openai", "api_key": "k1", "default_model": "a", "priority": 30},
            {"provider_id": "b", "base_url": "http://b.local", "type": "openai", "api_key": "k2", "default_model": "b", "priority": 20},
            {"provider_id": "c", "base_url": "http://c.local", "type": "openai", "api_key": "k3", "default_model": "c", "priority": 10},
        )

        orchestrator = WorkflowOrchestrator()
        req = ExecutionReques
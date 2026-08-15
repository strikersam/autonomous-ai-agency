"""Regression tests for the production bugs reported by the MiniMax audit.

Each test pins a specific bug that was confirmed real against the code and would
have re-appeared without a guard. The two reported issues that turned out to be
false positives (frontend token-refresh "race" — already a correct single-flight
queue; OAuth CSRF state — validated server-side in every callback) are documented
in the changelog rather than tested here, since there was no code change.
"""
from __future__ import annotations

import asyncio
import inspect

import pytest


# ── Bug 1: JWT secret regenerated on every restart ──────────────────────────────


# Fake admin-credential fixtures for the derivation tests. Held in variables
# (not passed as string literals to the `admin_password=` kwarg) so Bandit's
# B106 hardcoded-password-funcarg check does not flag these test-only values.
_ADMIN_CRED = "unit-test-admin-value"
_ADMIN_CRED_ALT = "unit-test-admin-value-2"


class TestJwtSecretStability:
    def test_explicit_secret_is_used_verbatim(self) -> None:
        from backend.server import _resolve_jwt_secret

        assert (
            _resolve_jwt_secret("explicit-key", admin_password=_ADMIN_CRED, testing=False)
            == "explicit-key"
        )

    def test_fallback_is_stable_across_calls(self) -> None:
        """The bug: an unset JWT_SECRET minted a fresh random key each process
        start, invalidating every session on restart. The fallback must now be
        deterministic for a given ADMIN_PASSWORD."""
        from backend.server import _resolve_jwt_secret

        a = _resolve_jwt_secret(None, admin_password=_ADMIN_CRED, testing=False)
        b = _resolve_jwt_secret(None, admin_password=_ADMIN_CRED, testing=False)
        assert a == b
        assert a  # non-empty
        # Different admin passwords derive different keys.
        c = _resolve_jwt_secret(None, admin_password=_ADMIN_CRED_ALT, testing=False)
        assert c != a

    def test_testing_uses_ephemeral_key(self) -> None:
        from backend.server import _resolve_jwt_secret

        a = _resolve_jwt_secret(None, admin_password=_ADMIN_CRED, testing=True)
        b = _resolve_jwt_secret(None, admin_password=_ADMIN_CRED, testing=True)
        assert a != b  # random per call under TESTING


# ── Bugs 2 & 6: scheduler dispatch / deprecated get_event_loop ───────────────────


def test_scheduler_on_fire_is_a_coroutine() -> None:
    """The old sync callback called the deprecated ``asyncio.get_event_loop()``
    from APScheduler's worker thread and ran the orchestrator on a throwaway loop
    (cross-loop hang). It is now a coroutine so AgentScheduler dispatches it onto
    the attached main loop via ``run_coroutine_threadsafe``."""
    from backend.server import _scheduler_on_fire

    assert inspect.iscoroutinefunction(_scheduler_on_fire)


# ── Bug 3: unbounded in-memory chat session storage ─────────────────────────────


class TestLimitedChatSessionCap:
    def test_lru_eviction_when_over_cap(self, monkeypatch) -> None:
        import backend.server as srv

        monkeypatch.setattr(srv, "_LIMITED_CHAT_SESSIONS_MAX", 3)
        srv._LIMITED_CHAT_SESSIONS.clear()
        try:
            for i in range(5):
                srv._save_limited_chat_session(f"s{i}", {"user_id": "u", "n": i})
            # Only the cap's worth are retained.
            assert len(srv._LIMITED_CHAT_SESSIONS) == 3
            # Oldest (s0, s1) evicted; newest survive.
            assert "s0" not in srv._LIMITED_CHAT_SESSIONS
            assert "s4" in srv._LIMITED_CHAT_SESSIONS
        finally:
            srv._LIMITED_CHAT_SESSIONS.clear()

    def test_read_touch_protects_from_eviction(self, monkeypatch) -> None:
        import backend.server as srv

        monkeypatch.setattr(srv, "_LIMITED_CHAT_SESSIONS_MAX", 3)
        srv._LIMITED_CHAT_SESSIONS.clear()
        try:
            for i in range(3):
                srv._save_limited_chat_session(f"s{i}", {"user_id": "u", "n": i})
            # Touch s0 so it is most-recently-used.
            assert srv._get_limited_chat_session("s0", "u") is not None
            # Adding a 4th evicts the LRU, which is now s1 — not the touched s0.
            srv._save_limited_chat_session("s3", {"user_id": "u", "n": 3})
            assert "s0" in srv._LIMITED_CHAT_SESSIONS
            assert "s1" not in srv._LIMITED_CHAT_SESSIONS
        finally:
            srv._LIMITED_CHAT_SESSIONS.clear()


# ── Bug 8: container detection missed Podman / OCI ──────────────────────────────


class TestContainerDetection:
    def test_podman_container_env_var_detected(self, monkeypatch) -> None:
        """Podman/systemd-nspawn set ``container=podman`` but no /.dockerenv."""
        import backend.server as srv

        monkeypatch.setenv("container", "podman")
        assert srv._in_container() is True

    def test_kubernetes_detected(self, monkeypatch) -> None:
        import backend.server as srv

        monkeypatch.delenv("container", raising=False)
        monkeypatch.delenv("IN_DOCKER", raising=False)
        monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.0.0.1")
        assert srv._in_container() is True

    def test_ollama_url_rewritten_in_container(self, monkeypatch) -> None:
        import backend.server as srv

        monkeypatch.setattr(srv, "_in_container", lambda: True)
        assert (
            srv._resolve_ollama_url("http://localhost:11434")
            == "http://ollama:11434"
        )

    def test_ollama_url_untouched_outside_container(self, monkeypatch) -> None:
        import backend.server as srv

        monkeypatch.setattr(srv, "_in_container", lambda: False)
        assert (
            srv._resolve_ollama_url("http://localhost:11434")
            == "http://localhost:11434"
        )


# ── Bug 9: stale audit event data in summary ────────────────────────────────────


class TestAuditSummaryCumulativeTotals:
    def test_totals_survive_ring_buffer_wrap(self) -> None:
        """The bug: cost/tokens/would_block/by_agent were summed over the bounded
        ring buffer, so once it wrapped the "total_*" figures silently
        undercounted. They must now be true all-time accumulators."""
        from packages.governance.audit import AuditEvent, AuditLog

        log = AuditLog(capacity=2)
        for i in range(5):
            log.record(
                AuditEvent(
                    agent_id="agent:x",
                    decision="deny" if i % 2 == 0 else "allow",
                    cost_usd=1.0,
                    total_tokens=10,
                )
            )
        summary = log.summary()
        # Ring buffer only holds the last 2 events...
        assert summary["buffered_events"] == 2
        assert summary["capacity"] == 2
        # ...but the totals reflect all 5.
        assert summary["total_recorded"] == 5
        assert summary["total_cost_usd"] == pytest.approx(5.0)
        assert summary["total_tokens"] == 50
        assert summary["would_block"] == 3  # events 0, 2, 4 were "deny"
        assert summary["by_agent"] == {"agent:x": 5}

    def test_clear_resets_totals(self) -> None:
        from packages.governance.audit import AuditEvent, AuditLog

        log = AuditLog(capacity=10)
        log.record(AuditEvent(agent_id="a", cost_usd=2.0, total_tokens=5))
        log.clear()
        summary = log.summary()
        assert summary["total_recorded"] == 0
        assert summary["total_cost_usd"] == 0.0
        assert summary["total_tokens"] == 0
        assert summary["by_agent"] == {}

"""Regression: tests must never page a human via Telegram.

The self-heal escalation path (``agent/self_healing.py::_escalate``) sends a
Telegram message through ``NotificationDispatcher``. A test that drives a heal
to escalation (e.g. ``test_autonomy_hardening_audit`` with its "recurring boom"
signature) would otherwise fire a *real* Telegram message on every suite run in
any environment that has ``TELEGRAM_BOT_TOKEN`` set — CI, nightly-regression,
continuous-improvement, or a live deploy running the suite. That is exactly the
recurring "🔴 Self-heal escalation — recurring boom" page the operator saw.

These tests pin the systemic guard: under pytest, outbound Telegram sends are
suppressed unless ``ALLOW_TEST_TELEGRAM=1`` is explicitly set.
"""
from __future__ import annotations

import telegram_service
from telegram_service import NotificationDispatcher, _telegram_sends_suppressed


def test_suppressed_under_pytest():
    """PYTEST_CURRENT_TEST is set during every test, so sends are suppressed."""
    assert _telegram_sends_suppressed() is True


def test_opt_in_override(monkeypatch):
    monkeypatch.setenv("ALLOW_TEST_TELEGRAM", "1")
    assert _telegram_sends_suppressed() is False


def test_configured_dispatcher_does_not_hit_network(monkeypatch):
    """Even with a token + chat id configured, no HTTP send happens under pytest."""
    sends: list[str] = []

    class _Boom:
        def __init__(self, *a, **k): ...
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, *a, **k):  # pragma: no cover - must never be reached
            sends.append("post")
            raise AssertionError("Telegram send attempted during a test!")

    # If the guard fails, the fake client's .post() raises loudly.
    monkeypatch.setattr(telegram_service, "httpx", type("X", (), {"Client": _Boom}), raising=False)

    disp = NotificationDispatcher(telegram_token="123:abc", telegram_chat_ids=[42])
    disp.send_manual_notification("🔴 escalation — recurring boom")

    assert sends == []


def test_self_heal_escalation_is_silent_in_tests(monkeypatch):
    """The actual escalation path must not page a human when run under pytest."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")

    posted: list[str] = []

    class _Boom:
        def __init__(self, *a, **k): ...
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, *a, **k):  # pragma: no cover - must never be reached
            posted.append("post")
            raise AssertionError("Telegram send attempted during self-heal escalation!")

    monkeypatch.setattr(telegram_service, "httpx", type("X", (), {"Client": _Boom}), raising=False)

    from agent.self_healing import SelfHealingAgent, heal_signature

    healer = SelfHealingAgent()
    sig = heal_signature("manual", "recurring boom")
    # Drive straight to escalation; must not raise and must not send.
    import asyncio

    async def _run():
        await healer.on_manual_report("recurring boom", "context", signature=sig)
        ev = healer._by_signature[sig]
        for _ in range(healer_max_attempts := 5):
            healer._escalate(ev)

    asyncio.run(_run())
    assert posted == []

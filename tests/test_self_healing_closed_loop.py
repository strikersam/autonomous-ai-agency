"""Closed-loop self-heal tests (Autonomy Charter G2).

Verifies the heal lifecycle: dedup (exactly one active heal per signature),
fix-landed → verifying window, resolve-on-quiet, regress-on-recurrence + retry,
and escalation to a human after HEAL_MAX_ATTEMPTS.
"""
from __future__ import annotations

import asyncio

import pytest

import agent.self_healing as sh
from agent.self_healing import HealState, SelfHealingAgent, heal_signature


@pytest.fixture
def healer():
    # Fresh agent per test; do NOT start the background sweeper (call sweep()
    # explicitly so timing is deterministic).
    return SelfHealingAgent()


# ── signature + dedup ────────────────────────────────────────────────────────


def test_heal_signature_stable_and_distinct():
    a = heal_signature("manual", "Boom in module X")
    b = heal_signature("manual", "Boom in module X")
    c = heal_signature("manual", "Different error")
    assert a == b
    assert a != c
    assert len(a) == 16


async def test_dedup_one_active_heal_per_signature(healer):
    """A recurring error must produce exactly ONE active heal (no thrash)."""
    sig = heal_signature("manual", "DB connection refused")
    e1 = await healer.on_manual_report("DB connection refused", "boom", signature=sig)
    e2 = await healer.on_manual_report("DB connection refused", "boom again", signature=sig)
    assert e1.event_id == e2.event_id
    assert len([e for e in healer.get_events()]) == 1
    assert e1.attempts == 1  # dispatched once, not twice


# ── fix-landed → verifying → resolved ────────────────────────────────────────


async def test_resolves_after_quiet_window(healer, monkeypatch):
    monkeypatch.setattr(sh, "HEAL_VERIFY_WINDOW_SEC", 0)  # deadline = now → resolves on sweep
    sig = heal_signature("manual", "flaky thing")
    await healer.on_manual_report("flaky thing", "x", signature=sig)
    assert healer.mark_fix_landed(sig) is True
    ev = healer._by_signature[sig]
    assert ev.state == HealState.VERIFYING.value

    resolved = healer.sweep()
    assert resolved == 1
    assert ev.state == HealState.RESOLVED.value
    assert ev.resolved is True
    assert ev.resolved_at is not None


async def test_does_not_resolve_before_window(healer, monkeypatch):
    monkeypatch.setattr(sh, "HEAL_VERIFY_WINDOW_SEC", 9999)
    sig = heal_signature("manual", "slow heal")
    await healer.on_manual_report("slow heal", "x", signature=sig)
    healer.mark_fix_landed(sig)
    assert healer.sweep() == 0
    assert healer._by_signature[sig].state == HealState.VERIFYING.value


# ── regress on recurrence → retry ────────────────────────────────────────────


async def test_recurrence_during_verifying_regresses_and_retries(healer, monkeypatch):
    monkeypatch.setattr(sh, "HEAL_VERIFY_WINDOW_SEC", 9999)
    monkeypatch.setattr(sh, "HEAL_MAX_ATTEMPTS", 3)
    sig = heal_signature("manual", "leak")
    ev = await healer.on_manual_report("leak", "x", signature=sig)
    assert ev.attempts == 1
    healer.mark_fix_landed(sig)
    assert ev.state == HealState.VERIFYING.value

    # The error came back while verifying → regress + re-dispatch.
    assert healer.note_recurrence(sig) is True
    for _ in range(3):
        await asyncio.sleep(0)  # let the fire-and-forget re-dispatch run

    assert ev.attempts == 2
    assert ev.state == HealState.FIXING.value  # re-dispatched
    assert ev.last_recurrence_at is not None


async def test_note_recurrence_unknown_signature_is_noop(healer):
    assert healer.note_recurrence("deadbeefdeadbeef") is False


# ── escalation after max attempts ────────────────────────────────────────────


async def test_escalates_to_human_after_max_attempts(healer, monkeypatch):
    monkeypatch.setattr(sh, "HEAL_VERIFY_WINDOW_SEC", 9999)
    monkeypatch.setattr(sh, "HEAL_MAX_ATTEMPTS", 1)

    sent: list[str] = []

    class _FakeDispatcher:
        def send_manual_notification(self, message: str) -> None:
            sent.append(message)

    from packages.notifications import service as telegram_service
    monkeypatch.setattr(telegram_service, "NotificationDispatcher", _FakeDispatcher)

    sig = heal_signature("manual", "unfixable")
    ev = await healer.on_manual_report("unfixable", "x", signature=sig)
    assert ev.attempts == 1  # == HEAL_MAX_ATTEMPTS
    healer.mark_fix_landed(sig)

    # Recurrence with attempts already at the cap → escalate, not retry.
    healer.note_recurrence(sig)
    await asyncio.sleep(0)

    assert ev.state == HealState.AWAITING_HUMAN.value
    assert sent and "escalation" in sent[0].lower()
    assert ev.event_id in sent[0]


# ── mark_fix_landed guards ───────────────────────────────────────────────────


async def test_mark_fix_landed_by_event(healer, monkeypatch):
    monkeypatch.setattr(sh, "HEAL_VERIFY_WINDOW_SEC", 9999)
    sig = heal_signature("manual", "by-event")
    ev = await healer.on_manual_report("by-event", "x", signature=sig)
    assert healer.mark_fix_landed_by_event(ev.event_id) is True
    assert ev.state == HealState.VERIFYING.value


def test_mark_fix_landed_unknown_signature(healer):
    assert healer.mark_fix_landed("nope") is False

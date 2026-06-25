"""Regression tests for robustness bugs found in the autonomy-paths audit.

- P1-3 (self-heal): a re-dispatch failure during REGRESSED must escalate the heal
  to a human, not silently strand it in REGRESSED forever (``_verify_deadline`` is
  zeroed there, so the sweeper can never resolve it).
- P0-2 (trend-watcher): ``dispatch_high_relevance_to_hermes`` must be a coroutine
  that no-ops cleanly when ``HERMES_BASE_URL`` is unset — the previous body called
  ``asyncio.run()`` from inside the already-running fetch loop, which always raised.
"""
from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

from agent.self_healing import HealState, SelfHealingAgent, heal_signature
from agent.trend_watcher import TrendWatcher


async def test_regress_redispatch_failure_escalates(monkeypatch):
    """If the re-dispatch coroutine raises, the heal escalates instead of stranding."""
    healer = SelfHealingAgent()
    sig = heal_signature("manual", "recurring boom")
    await healer.on_manual_report("recurring boom", "context", signature=sig)
    assert healer.mark_fix_landed(sig) is True
    ev = healer._by_signature[sig]
    assert ev.state == HealState.VERIFYING.value

    async def _boom(event):  # the re-dispatch fails
        raise RuntimeError("dispatch backend down")

    monkeypatch.setattr(healer, "_dispatch_fix", _boom)

    # Recurrence during verification -> _regress -> re-dispatch -> fails -> escalate.
    healer.note_recurrence(sig)
    for _ in range(10):  # let the scheduled re-dispatch task run
        await asyncio.sleep(0)

    assert ev.state == HealState.AWAITING_HUMAN.value


def test_hermes_dispatch_is_a_coroutine():
    assert inspect.iscoroutinefunction(TrendWatcher.dispatch_high_relevance_to_hermes)


async def test_hermes_dispatch_noop_without_url(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("HERMES_BASE_URL", raising=False)
    tw = TrendWatcher(cache_path=tmp_path / "trend-cache.json")
    # Must return cleanly with no network call and no "asyncio.run() in a running
    # loop" RuntimeError, even though we're inside a running event loop here.
    await tw.dispatch_high_relevance_to_hermes([])

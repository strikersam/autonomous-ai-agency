"""Production 2026-11-08: a stale portfolio cache rebuilt on the event loop
(blocking GitHub/trend HTTP calls), freezing every request; Render's 5 s health
check failed and Cloudflare served "invalid or incomplete response"."""
from __future__ import annotations

import asyncio
import threading
import time

import agents.portfolio_api as pa


def _slow_service(monkeypatch, seconds: float, builds: list):
    svc = pa.PortfolioService()

    def slow_build(**kwargs):
        builds.append(threading.current_thread().name)
        time.sleep(seconds)  # what the real build does: blocking network I/O
        return pa.PortfolioManager()

    monkeypatch.setattr(svc.intelligence, "build", slow_build)
    monkeypatch.setattr(svc.intelligence, "last_build", {}, raising=False)
    return svc


async def test_stale_rebuild_does_not_freeze_the_event_loop(monkeypatch):
    builds: list = []
    svc = _slow_service(monkeypatch, 0.6, builds)
    monkeypatch.setattr(pa, "get_service", lambda: svc)

    async def other_request():
        await asyncio.sleep(0.05)
        return time.monotonic()

    start = time.monotonic()
    board_task = asyncio.create_task(pa.get_board())
    answered_at = await other_request()
    await board_task

    assert answered_at - start < 0.3  # served while the rebuild ran
    assert builds and builds[0] != threading.main_thread().name


async def test_concurrent_stale_requests_build_once(monkeypatch):
    builds: list = []
    svc = _slow_service(monkeypatch, 0.2, builds)
    await asyncio.gather(svc.ensure_fresh_async(), svc.ensure_fresh_async(), svc.ensure_fresh_async())
    assert len(builds) == 1

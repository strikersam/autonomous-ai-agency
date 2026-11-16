"""router/health.py probed Ollama with a blocking request on the event loop, and never
remembered a failed probe, so a deploy with no Ollama (Render) re-probed on every routing
call. It was the most frequent loop stall in production, 2026-11-15/16."""
from __future__ import annotations

import asyncio
import threading
import time

import pytest

from router import health


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setenv("ROUTER_HEALTH_CHECK_ENABLED", "true")
    health.invalidate_cache()
    health._refresh_running.clear()
    yield
    health.invalidate_cache()
    health._refresh_running.clear()


class _Resp:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"models": [{"name": "qwen3-coder:30b-q4_K_M"}]}


def _client(calls: list, fail: bool = False, delay: float = 0.0):
    class _C:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            calls.append((url, threading.current_thread()))
            if delay:
                time.sleep(delay)
            if fail:
                raise ConnectionError("refused")
            return _Resp()

    return _C


def test_a_failed_probe_is_remembered_so_the_next_calls_do_not_retry(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(health.httpx, "Client", _client(calls, fail=True))
    assert health.get_available_models() == set()
    assert health.get_available_models() == set()
    assert health.is_model_available("anything") is True, "empty set means no filtering"
    assert len(calls) == 1, "an unreachable Ollama must not be probed on every call"


def test_a_failed_probe_is_retried_after_the_window(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(health.httpx, "Client", _client(calls, fail=True))
    health.get_available_models()
    health._fail_ts = time.monotonic() - 1000
    health.get_available_models()
    assert len(calls) == 2


def test_a_good_cache_survives_a_failed_refresh(monkeypatch) -> None:
    monkeypatch.setattr(health.httpx, "Client", _client([]))
    first = health.get_available_models()
    assert "qwen3-coder:30b" in first
    health._cache_ts = time.monotonic() - 1000  # stale
    monkeypatch.setattr(health.httpx, "Client", _client([], fail=True))
    assert health.get_available_models() == first, "do not overwrite a good value with a failure"


def test_a_stale_read_on_the_loop_does_not_wait_for_the_probe(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(health.httpx, "Client", _client(calls, delay=0.5))

    async def go():
        start = time.monotonic()
        value = health.get_available_models()
        return value, time.monotonic() - start

    value, elapsed = asyncio.run(go())
    assert elapsed < 0.25, "the loop thread waited on the Ollama probe"
    assert value == set(), "first call: no filtering until the refresh lands"
    deadline = time.monotonic() + 3
    while not health._ever_fetched and time.monotonic() < deadline:
        time.sleep(0.02)
    assert health._ever_fetched and "qwen3-coder:30b" in health._cache_models
    assert calls[0][1] is not threading.main_thread()


def test_concurrent_stale_reads_on_the_loop_start_one_probe(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(health.httpx, "Client", _client(calls, delay=0.3))

    async def go():
        for _ in range(5):
            health.get_available_models()

    asyncio.run(go())
    time.sleep(0.6)
    assert len(calls) == 1


def test_sync_callers_still_probe_inline(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(health.httpx, "Client", _client(calls))
    assert "qwen3-coder:30b" in health.get_available_models()
    assert calls[0][1] is threading.main_thread()


def test_disabled_health_checks_still_mean_available(monkeypatch) -> None:
    monkeypatch.setenv("ROUTER_HEALTH_CHECK_ENABLED", "false")
    assert health.get_available_models() == set()
    assert health.is_model_available("whatever") is True

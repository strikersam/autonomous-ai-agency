"""Anonymous heartbeat endpoints: open for keepalive, but not unlimited.

/api/scheduler/tick ran for anyone when CRON_SECRET was unset and compared the
secret with ``!=``; /api/autonomy/tick (the CEO loop + one task dispatch) ran on
every anonymous GET. Both now admit one un-authenticated tick per interval.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import backend.server as server


@pytest.fixture()
def anon(monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "_anon_tick_last", {})
    return TestClient(server.app, raise_server_exceptions=False)


def test_scheduler_tick_without_secret_is_rate_limited(anon, monkeypatch) -> None:
    monkeypatch.delenv("CRON_SECRET", raising=False)
    assert anon.post("/api/scheduler/tick").status_code == 200
    assert anon.post("/api/scheduler/tick").status_code == 429


def test_scheduler_tick_with_secret_checks_it_and_is_not_throttled(anon, monkeypatch) -> None:
    monkeypatch.setenv("CRON_SECRET", "s3cret-value")
    assert anon.post("/api/scheduler/tick", headers={"x-cron-secret": "wrong"}).status_code == 403
    ok = {"x-cron-secret": "s3cret-value"}
    assert anon.post("/api/scheduler/tick", headers=ok).status_code == 200
    assert anon.post("/api/scheduler/tick", headers=ok).status_code == 200


def test_autonomy_tick_second_anonymous_call_is_skipped(anon, monkeypatch) -> None:
    monkeypatch.delenv("CRON_SECRET", raising=False)
    monkeypatch.setitem(server._anon_tick_last, "autonomy", __import__("time").monotonic())
    resp = anon.get("/api/autonomy/tick")
    assert resp.status_code == 200
    assert resp.json()["ceo"]["skipped"] == "throttled"

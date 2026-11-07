"""Runtime quarantine: a runtime whose real work is refused leaves rotation.

Regression for production 2026-11-07: Hermes answered every task with
``HTTP 401: Invalid Hermes API key`` while ``/health`` stayed 200, and E2B
answered ``403: team is blocked: credit_exhausted``. Both kept reading as
available, so every task tried them first and 283 of 483 tasks ended blocked.
"""
from __future__ import annotations

import time

import httpx
import pytest

from runtimes import quarantine as q
from runtimes.adapters import hermes as hermes_mod
from runtimes.adapters.e2b import _is_account_refusal
from runtimes.adapters.hermes import HermesAdapter
from runtimes.base import RuntimeExecutionError, RuntimeUnavailableError, TaskSpec


@pytest.fixture(autouse=True)
def _reset():
    q.clear()
    yield
    q.clear()


def test_quarantine_expires(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(q.time, "monotonic", lambda: now[0])
    q.quarantine("hermes", "bad key", ttl_sec=60)
    assert q.quarantined("hermes") == "bad key"
    now[0] += 61
    assert q.quarantined("hermes") is None


class _Client:
    """Stand in for httpx.AsyncClient returning one fixed response."""

    def __init__(self, status: int, body: dict | None = None) -> None:
        self._status = status
        self._body = body or {}

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, **kwargs):
        return httpx.Response(self._status, json=self._body, request=httpx.Request("POST", url))

    async def get(self, url, **kwargs):
        return httpx.Response(self._status, json=self._body, request=httpx.Request("GET", url))


def _spec() -> TaskSpec:
    return TaskSpec(task_id="t1", instruction="do it", context={})


@pytest.mark.asyncio
async def test_hermes_401_quarantines_and_health_goes_red(monkeypatch):
    adapter = HermesAdapter({"base_url": "http://hermes.test", "api_key": "wrong"})
    monkeypatch.setattr(hermes_mod.httpx, "AsyncClient",
                        _Client(401, {"detail": "Invalid Hermes API key"}))
    with pytest.raises(RuntimeUnavailableError) as exc:
        await adapter.execute(_spec())
    assert "HERMES_API_KEY" in str(exc.value)
    assert "wrong" not in str(exc.value)

    # /health would still answer 200; the quarantine must win over it.
    monkeypatch.setattr(hermes_mod.httpx, "AsyncClient", _Client(200, {"status": "ok"}))
    health = await adapter.health_check()
    assert health.available is False
    assert "HERMES_API_KEY" in (health.error or "")


@pytest.mark.asyncio
async def test_hermes_500_is_not_quarantined(monkeypatch):
    adapter = HermesAdapter({"base_url": "http://hermes.test"})
    monkeypatch.setattr(hermes_mod.httpx, "AsyncClient", _Client(500, {"detail": "boom"}))
    with pytest.raises(RuntimeExecutionError):
        await adapter.execute(_spec())
    assert q.quarantined("hermes") is None


@pytest.mark.parametrize("message,refused", [
    ("E2B sandbox create failed: 403: team is blocked: credit_exhausted", True),
    ("401 unauthorized", True),
    ("quota exceeded", False),
    ("timeout while starting sandbox", False),
    ("sandbox 7f3a401b9c timeout", False),
    ("connection reset on port 4031", False),
    ("HTTP 403: forbidden", True),
])
def test_e2b_account_refusal_detection(message, refused):
    assert _is_account_refusal(RuntimeError(message)) is refused


@pytest.mark.asyncio
async def test_e2b_health_reports_quarantine(monkeypatch):
    from runtimes.adapters.e2b import E2BAdapter
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")
    q.quarantine("e2b", "E2B account refused sandbox creation: credit_exhausted")
    health = await E2BAdapter().health_check()
    assert health.available is False
    assert "credit_exhausted" in (health.error or "")


def test_quarantine_uses_monotonic_clock():
    q.quarantine("x", "r", ttl_sec=5)
    assert q._until["x"] > time.monotonic()


def test_health_service_rejects_quarantined_runtime_before_next_poll():
    from runtimes.base import RuntimeHealth
    from runtimes.health import RuntimeHealthService

    svc = RuntimeHealthService.__new__(RuntimeHealthService)
    svc._circuits = {}
    svc._cache = {"hermes": RuntimeHealth(runtime_id="hermes", available=True)}
    assert svc.is_available("hermes") is True
    q.quarantine("hermes", "HTTP 401")
    assert svc.is_available("hermes") is False


# ── shared E2B opener honours the quarantine (CodeRabbit on #1907) ──────────

def _enable_e2b(monkeypatch):
    import services.e2b_sandbox as sb
    monkeypatch.setattr(sb, "e2b_enabled", lambda: True)
    monkeypatch.setattr(sb, "is_e2b_sdk_importable", lambda: True)
    monkeypatch.setattr(sb, "resolve_e2b_config", lambda: object())
    return sb


class _Runner:
    _mcp = None


@pytest.mark.asyncio
async def test_attach_skips_e2b_while_quarantined(monkeypatch):
    from runtimes import quarantine as q
    sb = _enable_e2b(monkeypatch)
    opened = []
    monkeypatch.setattr(sb, "E2BSandboxSession", lambda config: opened.append(config))
    q.clear()
    q.quarantine(q.E2B_RUNTIME_ID, "credit_exhausted")
    try:
        assert await sb.maybe_attach_e2b(_Runner()) is None
        assert opened == []
    finally:
        q.clear()


@pytest.mark.asyncio
async def test_attach_quarantines_on_account_refusal(monkeypatch):
    from agent.mcp_client import MCPUnavailableError
    from runtimes import quarantine as q
    sb = _enable_e2b(monkeypatch)

    class _Refused:
        def __init__(self, config):
            pass

        async def open(self):
            raise MCPUnavailableError("403: team is blocked: credit_exhausted")

    monkeypatch.setattr(sb, "E2BSandboxSession", _Refused)
    q.clear()
    try:
        assert await sb.maybe_attach_e2b(_Runner()) is None
        assert q.quarantined(q.E2B_RUNTIME_ID)
    finally:
        q.clear()

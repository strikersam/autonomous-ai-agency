"""Unit tests for services/background.py — start_background_services wiring.

Mirrors test_backend_runtime_bootstrap.py but tests the extracted module directly.
All heavy dependencies are stubbed so no real DB or runtimes are needed.
"""
from __future__ import annotations

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test-secret-for-tests-only")


# ─── Stubs ────────────────────────────────────────────────────────────────────

class _StubRegistry:
    def ids(self) -> list[str]:
        return ["internal_agent"]


class _StubRuntimeManager:
    def __init__(self) -> None:
        self._registry = _StubRegistry()
        self.start_calls = 0
        self.stop_calls = 0

    async def start(self) -> None:
        self.start_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1


class _StubDispatcher:
    def __init__(self, *, workspace_root: str, poll_interval_s: float) -> None:
        self.workspace_root = workspace_root
        self.poll_interval_s = poll_interval_s
        self.stop_calls = 0

    async def run_forever(self) -> None:
        # Block until cancelled
        await asyncio.sleep(1000)

    def stop(self) -> None:
        self.stop_calls += 1


class _StubTaskAutomation:
    def __init__(self, *, store) -> None:
        self.store = store

    def handle_scheduled_job(self, *args, **kwargs) -> None:
        pass


class _StubScheduler:
    def __init__(self) -> None:
        self.on_fire_handler = None
        self.attached_loop = None

    def set_on_fire(self, handler) -> None:
        self.on_fire_handler = handler

    def attach_main_loop(self, loop) -> None:
        # Mirror AgentScheduler.attach_main_loop so the lifespan wiring
        # (services/background.py) can capture the FastAPI main loop on the
        # stub during tests.
        self.attached_loop = loop


# ─── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_start_background_services_starts_runtime_manager(monkeypatch):
    """start_background_services() must start the RuntimeManager."""
    import services.background as bg_mod

    manager = _StubRuntimeManager()
    scheduler = _StubScheduler()
    dispatchers: list[_StubDispatcher] = []

    def make_dispatcher(*, workspace_root, poll_interval_s):
        d = _StubDispatcher(workspace_root=workspace_root, poll_interval_s=poll_interval_s)
        dispatchers.append(d)
        return d

    monkeypatch.setattr(bg_mod, "_schedule_self_bootstrap", lambda: None)
    monkeypatch.setenv("SELF_BOOTSTRAP_ENABLED", "false")

    with (
        patch("services.background.get_runtime_manager", return_value=manager),
        patch("services.background.TaskDispatcher", side_effect=make_dispatcher),
        patch("services.background.TaskAutomationService", _StubTaskAutomation),
    ):
        bg = await bg_mod.start_background_services(
            workspace_root="/tmp/test",  # nosec B108 — test-only path, no real temp file
            task_store=MagicMock(),
            scheduler=scheduler,
        )

    assert manager.start_calls == 1
    assert len(dispatchers) == 1
    assert dispatchers[0].poll_interval_s == bg_mod._DEFAULT_POLL_INTERVAL

    # Stop the background services
    await bg.stop()
    assert manager.stop_calls == 1
    assert dispatchers[0].stop_calls == 1


@pytest.mark.anyio
async def test_start_background_services_wires_scheduler(monkeypatch):
    """Scheduler's on_fire handler is set to TaskAutomation.handle_scheduled_job."""
    import services.background as bg_mod

    manager = _StubRuntimeManager()
    scheduler = _StubScheduler()
    automation_instances: list[_StubTaskAutomation] = []

    class _TrackedAutomation(_StubTaskAutomation):
        def __init__(self, *, store):
            super().__init__(store=store)
            automation_instances.append(self)

    monkeypatch.setattr(bg_mod, "_schedule_self_bootstrap", lambda: None)

    with (
        patch("services.background.get_runtime_manager", return_value=manager),
        patch("services.background.TaskDispatcher", side_effect=lambda **kw: _StubDispatcher(**kw)),
        patch("services.background.TaskAutomationService", _TrackedAutomation),
    ):
        bg = await bg_mod.start_background_services(
            workspace_root="/tmp/test",  # nosec B108 — test-only path, no real temp file
            task_store=MagicMock(),
            scheduler=scheduler,
        )

    assert scheduler.on_fire_handler is not None
    assert scheduler.on_fire_handler == automation_instances[0].handle_scheduled_job
    await bg.stop()


@pytest.mark.anyio
async def test_stop_is_idempotent(monkeypatch):
    """Calling bg.stop() twice must not raise or double-stop."""
    import services.background as bg_mod

    manager = _StubRuntimeManager()
    scheduler = _StubScheduler()

    monkeypatch.setattr(bg_mod, "_schedule_self_bootstrap", lambda: None)

    with (
        patch("services.background.get_runtime_manager", return_value=manager),
        patch("services.background.TaskDispatcher", side_effect=lambda **kw: _StubDispatcher(**kw)),
        patch("services.background.TaskAutomationService", _StubTaskAutomation),
    ):
        bg = await bg_mod.start_background_services(
            workspace_root="/tmp/test",  # nosec B108 — test-only path, no real temp file
            task_store=MagicMock(),
            scheduler=scheduler,
        )

    await bg.stop()
    await bg.stop()  # second call must be a no-op
    assert manager.stop_calls == 1  # only stopped once


def test_run_background_in_web_default():
    """RUN_BACKGROUND_IN_WEB defaults to True."""
    from services.background import run_background_in_web

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("RUN_BACKGROUND_IN_WEB", None)
        assert run_background_in_web() is True


def test_run_background_in_web_false():
    from services.background import run_background_in_web

    with patch.dict(os.environ, {"RUN_BACKGROUND_IN_WEB": "false"}):
        assert run_background_in_web() is False


def test_run_background_in_web_true_variants():
    from services.background import run_background_in_web

    for val in ("true", "1", "yes", "TRUE", "YES"):
        with patch.dict(os.environ, {"RUN_BACKGROUND_IN_WEB": val}):
            assert run_background_in_web() is True, f"Expected True for {val!r}"


# ─── Hermes startup: bounded well under Render's health-check timeout ───────
#
# render.yaml's healthCheckPath times out at 5s, and uvicorn does not open its
# listening socket until the FastAPI lifespan returns. _start_hermes_in_process()
# used to block on _await_hermes_ready() for up to 20s — an in-process,
# no-network-dependency uvicorn server that normally binds in milliseconds, but
# on a slow boot (free-tier CPU contention, a cold import) held the port closed
# for up to 4x Render's own timeout on every restart attempt. Confirmed live via
# Render's Events tab: a repeating "Instance failed: HTTP health check failed
# (timed out after 5 seconds)" / "Service recovered" cycle every few minutes.

def test_hermes_startup_timeout_is_well_under_renders_health_check_window():
    """The constant itself must leave real margin under Render's 5s timeout."""
    import services.background as bg_mod

    assert bg_mod._HERMES_STARTUP_TIMEOUT_SEC <= 3.0, (
        f"_HERMES_STARTUP_TIMEOUT_SEC={bg_mod._HERMES_STARTUP_TIMEOUT_SEC}s leaves no "
        "margin under Render's 5s health-check timeout (render.yaml healthCheckPath)"
    )


@pytest.mark.anyio
async def test_hermes_readiness_wait_gives_up_within_its_budget():
    """A Hermes that never reports ready must not be waited on past the budget.

    Against the previous 20.0s constant, this test would itself take ~20s and
    still pass — the regression that matters is the constant above. This pins
    the *behavior*: _await_hermes_ready actually raises at the budget, it
    doesn't drift past it.
    """
    import services.background as bg_mod

    class _NeverStartedServer:
        started = False

    class _NeverDoneTask:
        def done(self) -> bool:
            return False

    start = asyncio.get_running_loop().time()
    with pytest.raises(RuntimeError, match="did not start within timeout"):
        await bg_mod._await_hermes_ready(_NeverStartedServer(), _NeverDoneTask())
    elapsed = asyncio.get_running_loop().time() - start

    assert elapsed < bg_mod._HERMES_STARTUP_TIMEOUT_SEC + 1.0, (
        f"readiness wait took {elapsed:.1f}s, past its "
        f"{bg_mod._HERMES_STARTUP_TIMEOUT_SEC}s budget"
    )

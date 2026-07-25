"""Hermes must actually run on a single-service deployment.

``RUN_HERMES_IN_PROCESS`` and ``settings.is_hermes_in_process`` existed since the
flag was introduced, and ``CLAUDE.md`` documents "Hermes in-process :8100" as
production behaviour — but nothing consumed the flag. The only way to run Hermes
was ``Dockerfile.hermes`` as the separate ``agency-hermes`` Render service. On a
one-service deployment the adapter probed its default ``http://localhost:8100``,
found nothing, and reported the runtime permanently offline, so
``RUNTIME_CODE_GENERATION=hermes`` silently fell back to ``internal_agent``
forever — with no error anywhere, because falling back is by design.

These tests use a real socket on a real port: the failure being prevented is
"nothing is listening", which a mock cannot observe.
"""
from __future__ import annotations

import asyncio
import socket

import httpx
import pytest

import services.background as bg


def _free_port() -> int:
    """A port the OS says is free, so a busy 8100 never flakes the suite."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def hermes_enabled(monkeypatch):
    """Enable the in-process server on a free port, and always tear it down."""
    from packages.config.settings import settings

    monkeypatch.setattr(settings, "run_hermes_in_process", "true", raising=False)
    monkeypatch.setattr(settings, "testing", "", raising=False)
    monkeypatch.setattr(bg, "_HERMES_PORT", _free_port())
    monkeypatch.setattr(bg, "_hermes_server", None)
    monkeypatch.setattr(bg, "_hermes_task", None)
    yield
    server, task = bg._hermes_server, bg._hermes_task
    if server is not None:
        server.should_exit = True
    if task is not None and not task.done():
        try:
            asyncio.get_event_loop().run_until_complete(
                asyncio.wait_for(task, timeout=10)
            )
        except Exception:  # noqa: BLE001 — teardown is best-effort
            task.cancel()
    bg._hermes_server = None
    bg._hermes_task = None


class TestInProcessServer:
    @pytest.mark.asyncio
    async def test_it_listens_and_answers_the_health_probe(
        self, hermes_enabled
    ) -> None:
        task = await bg._start_hermes_in_process()
        assert task is not None, "the flag is on; the server must start"

        async with httpx.AsyncClient() as c:
            r = await c.get(f"http://127.0.0.1:{bg._HERMES_PORT}/health", timeout=10)

        assert r.status_code == 200
        body = r.json()
        assert body["runtime"] == "hermes"
        assert body["ours"] is True, "this must be the agency's own Hermes"

    @pytest.mark.asyncio
    async def test_the_real_adapter_reports_it_available(
        self, hermes_enabled, monkeypatch
    ) -> None:
        """The whole point: HermesAdapter must stop reporting the runtime down.

        Goes through the real adapter rather than asserting on the socket, because
        "a port is open" and "the runtime is usable" are different claims and only
        the second one matters.
        """
        await bg._start_hermes_in_process()
        monkeypatch.setenv("HERMES_BASE_URL", f"http://127.0.0.1:{bg._HERMES_PORT}")

        from runtimes.adapters.hermes import HermesAdapter
        health = await HermesAdapter().health_check()

        assert health.available is True, (
            f"Hermes still reports down: {health.error!r} — a single-service "
            f"deployment would keep falling back to internal_agent"
        )
        assert health.version

    @pytest.mark.asyncio
    async def test_starting_twice_reuses_the_running_server(
        self, hermes_enabled
    ) -> None:
        """Web lifespan and worker_main can both call into one process."""
        first = await bg._start_hermes_in_process()
        second = await bg._start_hermes_in_process()

        assert first is second, "a second bind on the same port would fail"

    @pytest.mark.asyncio
    async def test_the_flag_switches_it_off(self, hermes_enabled, monkeypatch) -> None:
        from packages.config.settings import settings

        monkeypatch.setattr(settings, "run_hermes_in_process", "false", raising=False)
        assert await bg._start_hermes_in_process() is None

    @pytest.mark.asyncio
    async def test_a_failure_to_start_degrades_instead_of_breaking_boot(
        self, hermes_enabled, monkeypatch
    ) -> None:
        """Hermes is an optimisation. It must never take the backend down with it."""
        import uvicorn

        def _boom(*a, **k):
            raise OSError("address already in use")

        monkeypatch.setattr(uvicorn, "Server", _boom)

        assert await bg._start_hermes_in_process() is None  # no exception


class TestShutdown:
    @pytest.mark.asyncio
    async def test_stop_releases_the_port(self, hermes_enabled) -> None:
        """A leaked listener makes the NEXT boot fail to bind, costing the runtime."""
        port = bg._HERMES_PORT
        task = await bg._start_hermes_in_process()

        services = bg.BackgroundServices(
            runtime_manager=_NullRuntimeManager(),
            dispatcher=_NullDispatcher(),
            dispatcher_task=asyncio.create_task(asyncio.sleep(0)),
            hermes_task=task,
        )
        await services.stop()

        with socket.socket() as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))  # raises OSError if still held


class _NullDispatcher:
    def stop(self) -> None:
        return None


class _NullRuntimeManager:
    async def stop(self) -> None:
        return None


# ── What makes Hermes different from internal_agent ─────────────────────────

class TestCodingModelPreference:
    """Without this, routing a task to Hermes buys nothing.

    ``hermes_server`` executes through ``InternalAgentAdapter``, so on the same
    model it is byte-for-byte what the fallback would have done, plus an HTTP
    hop. The differentiation is that Hermes resolves the coding-specialist model
    when the caller expresses no preference.
    """

    @pytest.mark.asyncio
    async def test_it_resolves_the_coding_model_when_none_is_requested(
        self, monkeypatch
    ) -> None:
        captured: dict = {}

        class _Adapter:
            async def execute(self, spec):
                captured["model"] = spec.model_preference
                return type("R", (), {"success": True, "output": "ok",
                                       "artifacts": [], "model_used": "x"})()

        import runtimes.adapters.internal_agent as ia
        monkeypatch.setattr(ia, "InternalAgentAdapter", _Adapter)
        monkeypatch.setattr(
            "packages.ai.brain_config.resolve_coding_model_preference",
            lambda: "north-mini-code-1.0",
        )

        from services.hermes_server import TaskIn, run_task
        await run_task(TaskIn(instruction="refactor this"), authorization=None)

        assert captured["model"] == "north-mini-code-1.0", (
            "Hermes must pick the coding specialist, or it is internal_agent "
            "with extra latency"
        )

    @pytest.mark.asyncio
    async def test_an_explicit_model_from_the_caller_wins(self, monkeypatch) -> None:
        captured: dict = {}

        class _Adapter:
            async def execute(self, spec):
                captured["model"] = spec.model_preference
                return type("R", (), {"success": True, "output": "ok",
                                       "artifacts": [], "model_used": "x"})()

        import runtimes.adapters.internal_agent as ia
        monkeypatch.setattr(ia, "InternalAgentAdapter", _Adapter)
        monkeypatch.setattr(
            "packages.ai.brain_config.resolve_coding_model_preference",
            lambda: "north-mini-code-1.0",
        )

        from services.hermes_server import TaskIn, run_task
        await run_task(
            TaskIn(instruction="x", model="meta/llama-3.3-70b-instruct"),
            authorization=None,
        )

        assert captured["model"] == "meta/llama-3.3-70b-instruct"

    @pytest.mark.asyncio
    async def test_a_resolver_failure_never_fails_the_task(
        self, monkeypatch
    ) -> None:
        """A model preference is an optimisation, not a precondition."""
        captured: dict = {}

        class _Adapter:
            async def execute(self, spec):
                captured["model"] = spec.model_preference
                return type("R", (), {"success": True, "output": "ok",
                                       "artifacts": [], "model_used": "x"})()

        import runtimes.adapters.internal_agent as ia
        monkeypatch.setattr(ia, "InternalAgentAdapter", _Adapter)

        def _boom():
            raise RuntimeError("catalog unavailable")

        monkeypatch.setattr(
            "packages.ai.brain_config.resolve_coding_model_preference", _boom
        )

        from services.hermes_server import TaskIn, run_task
        out = await run_task(TaskIn(instruction="x"), authorization=None)

        assert out["success"] is True
        assert captured["model"] is None, "falls back to the default brain"

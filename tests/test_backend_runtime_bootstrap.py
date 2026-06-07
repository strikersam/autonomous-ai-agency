import os
# Set the environment variable for MONGO_URL to a dummy value that we will mock
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test-secret-for-tests-only")
os.environ.setdefault("ADMIN_EMAIL", "admin@test.local")

from unittest.mock import MagicMock, patch

# Mock the AsyncIOMotorClient from motor.motor_asyncio to avoid connection attempts
with patch('motor.motor_asyncio.AsyncIOMotorClient') as mock_client:
    # Create a mock client instance
    mock_client_instance = MagicMock()
    # The server calls client.get_database(DB_NAME) so we need to mock that
    mock_client_instance.get_database.return_value = MagicMock()
    mock_client.return_value = mock_client_instance

    # Now we can import the server module
    import backend.server as server

class _StubRuntimeRegistry:
    def ids(self) -> list[str]:
        return ["hermes"]

class _StubRuntimeManager:
    def __init__(self) -> None:
        self._registry = _StubRuntimeRegistry()
        self.started = 0
        self.stopped = 0

    async def start(self) -> None:
        self.started += 1

    async def stop(self) -> None:
        self.stopped += 1

class _StubTaskDispatcher:
    def __init__(self, *, workspace_root: str, poll_interval_s: float) -> None:
        self.workspace_root = workspace_root
        self.poll_interval_s = poll_interval_s
        self.stop_called = 0

    async def run_forever(self) -> None:
        return None

    def stop(self) -> None:
        self.stop_called += 1

class _StubTask:
    def __init__(self, coro) -> None:
        self._coro = coro
        self.cancel_called = 0

    def cancel(self) -> None:
        self.cancel_called += 1

    def __await__(self):
        return self._coro.__await__()

import pytest
import services.background as bg_mod

@pytest.mark.anyio
async def test_backend_lifespan_starts_runtime_manager_and_dispatcher(monkeypatch):
    """Web lifespan delegates to start_background_services when RUN_BACKGROUND_IN_WEB=true."""
    called: list[str] = []

    async def fake_start_background_services(**kwargs):
        called.append("start")
        # Return a stub BackgroundServices-like object
        class _FakeBg:
            async def stop(self):
                called.append("stop")
        return _FakeBg()

    async def fake_ensure_bootstrap() -> None:
        return None

    monkeypatch.setenv("SELF_BOOTSTRAP_ENABLED", "false")
    monkeypatch.setenv("RUN_BACKGROUND_IN_WEB", "true")
    monkeypatch.setattr(server, "ensure_bootstrap", fake_ensure_bootstrap)
    monkeypatch.setattr(bg_mod, "start_background_services", fake_start_background_services)

    lifecycle = server.lifespan(server.app)
    await lifecycle.__aenter__()
    assert "start" in called

    await lifecycle.__aexit__(None, None, None)
    assert "stop" in called


@pytest.mark.anyio
async def test_backend_lifespan_skips_bg_when_flag_false(monkeypatch):
    """RUN_BACKGROUND_IN_WEB=false: lifespan starts but background services are NOT started."""
    started: list[bool] = []

    async def fake_start_background_services(**kwargs):
        started.append(True)

    async def fake_ensure_bootstrap() -> None:
        return None

    monkeypatch.setenv("RUN_BACKGROUND_IN_WEB", "false")
    monkeypatch.setattr(server, "ensure_bootstrap", fake_ensure_bootstrap)
    monkeypatch.setattr(bg_mod, "start_background_services", fake_start_background_services)

    lifecycle = server.lifespan(server.app)
    await lifecycle.__aenter__()
    assert not started, "start_background_services should NOT be called when flag is false"
    await lifecycle.__aexit__(None, None, None)

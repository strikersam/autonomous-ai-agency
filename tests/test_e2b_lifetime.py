"""E2B sandbox lifetime, command exit codes and the preview URL.

Production regression: the sandbox was created with a 300s lifetime while a
task attempt may run 600s, so the sandbox died mid-run and the task was
re-queued in a loop for hours. Non-zero command exits were also reported as
"sandbox unavailable", hiding a failing test run.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from services import e2b_sandbox as mod
from services.e2b_config import E2BConfig, resolve_e2b_config


class _Exit(Exception):
    """Shaped like e2b's CommandExitException (carries the command's result)."""

    def __init__(self, code: int, stdout: str = "", stderr: str = ""):
        super().__init__(f"exit {code}")
        self.exit_code, self.stdout, self.stderr = code, stdout, stderr


class _Result:
    def __init__(self, stdout="", stderr="", exit_code=0):
        self.stdout, self.stderr, self.exit_code = stdout, stderr, exit_code


class _Commands:
    def __init__(self, sb):
        self.sb = sb

    async def run(self, cmd, timeout=60, background=None):
        self.sb.cmds.append((cmd, background))
        if "fail-me" in cmd:
            raise _Exit(1, stdout="1 failed", stderr="boom")
        if "dead" in cmd:
            raise ConnectionError("sandbox gone")
        return _Result(stdout="ok")


class _Sandbox:
    def __init__(self):
        self.cmds: list = []
        self.timeouts: list[int] = []
        self.commands = _Commands(self)

    async def set_timeout(self, timeout):
        self.timeouts.append(timeout)

    def get_host(self, port):
        return f"{port}-sbx123.e2b.app"


def _session(timeout_sec=660):
    s = mod.E2BSandboxSession(E2BConfig(api_key="e2b_x", timeout_sec=timeout_sec))
    s._sandbox = _Sandbox()
    return s


def test_default_lifetime_outlasts_one_task_attempt(monkeypatch):
    monkeypatch.setenv("E2B_ENABLED", "true")
    monkeypatch.setenv("E2B_API_KEY", "e2b_x")
    monkeypatch.delenv("E2B_TIMEOUT_SEC", raising=False)
    assert resolve_e2b_config().timeout_sec > 600


def test_call_tool_refreshes_lifetime_at_most_once_a_minute(monkeypatch):
    s = _session()
    clock = [1000.0]
    monkeypatch.setattr(mod.time, "monotonic", lambda: clock[0])
    asyncio.run(s.call_tool("run_command", {"cmd": "true"}))
    asyncio.run(s.call_tool("run_command", {"cmd": "true"}))
    assert s._sandbox.timeouts == [660]
    clock[0] += 61
    asyncio.run(s.call_tool("run_command", {"cmd": "true"}))
    assert s._sandbox.timeouts == [660, 660]


def test_keepalive_failure_never_fails_the_call(monkeypatch):
    s = _session()

    async def broken(_t):
        raise RuntimeError("api down")

    s._sandbox.set_timeout = broken
    out = json.loads(asyncio.run(s.call_tool("run_command", {"cmd": "true"})))
    assert out["exit_code"] == 0


def test_nonzero_exit_is_returned_not_treated_as_dead_sandbox():
    s = _session()
    out = json.loads(asyncio.run(s.call_tool("run_command", {"cmd": "fail-me"})))
    assert out == {"stdout": "1 failed", "stderr": "boom", "exit_code": 1}


def test_real_sandbox_error_still_raises():
    s = _session()
    with pytest.raises(mod.MCPUnavailableError):
        asyncio.run(s.call_tool("run_command", {"cmd": "dead"}))


def test_preview_url_serves_workdir_and_returns_public_host():
    s = _session()
    url = asyncio.run(s.preview_url(4173))
    assert url == "https://4173-sbx123.e2b.app"
    started = [c for c, bg in s._sandbox.cmds if bg]
    assert started and "http.server 4173" in started[0] and mod.SANDBOX_WORKDIR in started[0]
    # Second call reuses the running server.
    assert asyncio.run(s.preview_url(4173)) == url
    assert len([c for c, bg in s._sandbox.cmds if bg]) == 1


def test_preview_url_none_when_closed():
    s = mod.E2BSandboxSession(E2BConfig(api_key="e2b_x"))
    assert asyncio.run(s.preview_url()) is None

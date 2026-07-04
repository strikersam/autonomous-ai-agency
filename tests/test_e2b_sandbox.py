"""tests/test_e2b_sandbox.py — E2BSandboxSession behaviour, mocked at the SDK seam.

Never hits live E2B. Mocks ``AsyncSandbox`` (the SDK class) so the tests cover:
  * call_tool maps write_file / read_file / run_command / clone_repo /
    git_commit / git_push / git_diff to the right SDK calls.
  * MCPUnavailableError is raised when the SDK is missing / sandbox open
    fails / call_tool errors — the existing circuit-breaker fallback in
    ``AgentRunner._dispatch_tool`` engages on this signal.
  * Token scrubbing in clone / push matches the mcp_server.workspace pattern.
  * maybe_attach_e2b returns None when E2B is disabled (graceful degradation).
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import pytest

from agent.mcp_client import MCPUnavailableError
from services import e2b_config
from services.e2b_sandbox import (
    E2BSandboxSession,
    _inject_token,
    _scrub_token,
    maybe_attach_e2b,
)


@pytest.fixture(autouse=True)
def _clean_e2b_env(monkeypatch):
    """Strip every E2B-related env var before each test."""
    for k in ("E2B_API_KEY", "E2B_ENABLED", "RUNTIME_E2B_ENABLED",
              "E2B_TEMPLATE", "E2B_TIMEOUT_SEC", "E2B_SANDBOX_METADATA",
              "AGENT_SANDBOX_MODE", "GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    yield


# ── _scrub_token / _inject_token helpers ──────────────────────────────────


def test_scrub_token_replaces_token():
    assert _scrub_token("error: https://abc123@github.com", "abc123") == "error: https://***@github.com"


def test_scrub_token_noop_when_no_token():
    assert _scrub_token("error msg", None) == "error msg"
    assert _scrub_token("error msg", "") == "error msg"


def test_inject_token_github_https():
    authed, clean = _inject_token("https://github.com/owner/repo", "tok_123")
    assert authed == "https://tok_123@github.com/owner/repo"
    assert clean == "https://github.com/owner/repo"


def test_inject_token_noop_when_no_token():
    authed, clean = _inject_token("https://github.com/owner/repo", None)
    assert authed == "https://github.com/owner/repo"
    assert clean == "https://github.com/owner/repo"


def test_inject_token_noop_for_non_github():
    authed, clean = _inject_token("https://gitlab.com/owner/repo", "tok_123")
    assert authed == "https://gitlab.com/owner/repo"
    assert clean == "https://gitlab.com/owner/repo"


# ── Fake SDK + sandbox fixtures ───────────────────────────────────────────


class _FakeCommandResult:
    def __init__(self, stdout: str = "", stderr: str = "", exit_code: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.returncode = exit_code  # alias some SDKs use


class _FakeFiles:
    def __init__(self):
        self.written: dict[str, str] = {}
        self._read_contents: dict[str, str] = {}

    async def write(self, path: str, content: str) -> None:
        self.written[path] = content

    async def read(self, path: str) -> str:
        if path not in self._read_contents:
            raise FileNotFoundError(path)
        return self._read_contents[path]

    def seed_read(self, path: str, content: str) -> None:
        self._read_contents[path] = content


class _FakeSandbox:
    """Mimics e2b_code_interpreter.AsyncSandbox for tests."""

    def __init__(self):
        self.files = _FakeFiles()
        self.commands_run: list[tuple[str, int]] = []
        self.killed = False
        # Configurable per-command results keyed by substring match on the cmd.
        self._command_results: dict[str, _FakeCommandResult] = {}
        self._default_result = _FakeCommandResult(stdout="", stderr="", exit_code=0)

    def set_command_result(self, cmd_substr: str, result: _FakeCommandResult) -> None:
        self._command_results[cmd_substr] = result

    async def commands_run(self, cmd: str, timeout: int = 60) -> _FakeCommandResult:  # type: ignore[override]
        return await self.commands.run(cmd, timeout=timeout)

    async def commands_run_method(self, cmd: str, timeout: int = 60) -> _FakeCommandResult:
        return await self.commands.run(cmd, timeout=timeout)

    async def kill(self) -> None:
        self.killed = True


class _FakeCommands:
    def __init__(self, sandbox: _FakeSandbox):
        self._sandbox = sandbox

    async def run(self, cmd: str, timeout: int = 60) -> _FakeCommandResult:
        self._sandbox.commands_run.append((cmd, timeout))
        for substr, result in self._sandbox._command_results.items():
            if substr in cmd:
                return result
        return self._sandbox._default_result


def _make_fake_sandbox() -> _FakeSandbox:
    sb = _FakeSandbox()
    # Plug the commands attribute after init (circular dep on the sandbox).
    sb.commands = _FakeCommands(sb)  # type: ignore[attr-defined]
    return sb


@pytest.fixture
def fake_sandbox():
    return _make_fake_sandbox()


class _FakeAsyncSandboxClass:
    """Stand-in for e2b_code_interpreter.AsyncSandbox used by E2BSandboxSession.open()."""

    last_created: list[dict[str, Any]] = []
    next_sandbox: _FakeSandbox | None = None
    raise_on_create: Exception | None = None

    @classmethod
    async def create(cls, **kwargs: Any) -> _FakeSandbox:
        cls.last_created.append(kwargs)
        if cls.raise_on_create is not None:
            raise cls.raise_on_create
        if cls.next_sandbox is None:
            cls.next_sandbox = _make_fake_sandbox()
        return cls.next_sandbox


@pytest.fixture
def patched_async_sandbox(monkeypatch):
    """Patch the AsyncSandbox name in the e2b_code_interpreter module so
    E2BSandboxSession.open() picks up the fake."""
    _FakeAsyncSandboxClass.last_created = []
    _FakeAsyncSandboxClass.next_sandbox = None
    _FakeAsyncSandboxClass.raise_on_create = None

    import e2b_code_interpreter as _sdk
    monkeypatch.setattr(_sdk, "AsyncSandbox", _FakeAsyncSandboxClass)
    return _FakeAsyncSandboxClass


# ── Session lifecycle ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_session_open_and_close(monkeypatch, patched_async_sandbox):
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    session = E2BSandboxSession()
    await session.open()
    assert session.is_open is True
    # The create kwargs must include the api_key and timeout.
    assert _FakeAsyncSandboxClass.last_created
    create_kwargs = _FakeAsyncSandboxClass.last_created[0]
    assert create_kwargs.get("api_key") == "e2b_test_key_abc123"
    assert create_kwargs.get("timeout") == 300
    await session.close()
    assert session.is_open is False


@pytest.mark.asyncio
async def test_session_open_raises_when_sdk_missing(monkeypatch):
    """When the SDK is missing, open() raises MCPUnavailableError."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    # Force is_e2b_sdk_importable to return False
    monkeypatch.setattr(e2b_config, "is_e2b_sdk_importable", lambda: False)
    session = E2BSandboxSession()
    with pytest.raises(MCPUnavailableError):
        await session.open()


@pytest.mark.asyncio
async def test_session_open_raises_on_create_failure(monkeypatch, patched_async_sandbox):
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    _FakeAsyncSandboxClass.raise_on_create = RuntimeError("quota exceeded")
    session = E2BSandboxSession()
    with pytest.raises(MCPUnavailableError) as exc_info:
        await session.open()
    assert "quota exceeded" in str(exc_info.value)


@pytest.mark.asyncio
async def test_session_close_is_idempotent(monkeypatch, patched_async_sandbox):
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    session = E2BSandboxSession()
    await session.open()
    await session.close()
    await session.close()  # second close must not raise
    assert session.is_open is False


# ── call_tool routing ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_tool_write_file(monkeypatch, patched_async_sandbox, fake_sandbox):
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    _FakeAsyncSandboxClass.next_sandbox = fake_sandbox
    session = E2BSandboxSession()
    await session.open()
    result = await session.call_tool("write_file", {"path": "test.py", "content": "print('hi')"})
    assert "test.py" in fake_sandbox.files.written
    assert fake_sandbox.files.written["test.py"] == "print('hi')"
    assert "written" in result
    assert "test.py" in result


@pytest.mark.asyncio
async def test_call_tool_read_file(monkeypatch, patched_async_sandbox, fake_sandbox):
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    _FakeAsyncSandboxClass.next_sandbox = fake_sandbox
    fake_sandbox.files.seed_read("existing.py", "print('existing')")
    session = E2BSandboxSession()
    await session.open()
    result = await session.call_tool("read_file", {"path": "existing.py"})
    assert "print('existing')" in result


@pytest.mark.asyncio
async def test_call_tool_read_file_missing(monkeypatch, patched_async_sandbox, fake_sandbox):
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    _FakeAsyncSandboxClass.next_sandbox = fake_sandbox
    session = E2BSandboxSession()
    await session.open()
    with pytest.raises(MCPUnavailableError):
        await session.call_tool("read_file", {"path": "missing.py"})


@pytest.mark.asyncio
async def test_call_tool_run_command(monkeypatch, patched_async_sandbox, fake_sandbox):
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    _FakeAsyncSandboxClass.next_sandbox = fake_sandbox
    fake_sandbox.set_command_result("ls", _FakeCommandResult(stdout="file1\nfile2\n", exit_code=0))
    session = E2BSandboxSession()
    await session.open()
    result = await session.call_tool("run_command", {"cmd": "ls -la", "timeout": 30})
    data = json.loads(result)
    assert data["stdout"] == "file1\nfile2\n"
    assert data["exit_code"] == 0


@pytest.mark.asyncio
async def test_call_tool_unknown_tool_raises(monkeypatch, patched_async_sandbox, fake_sandbox):
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    _FakeAsyncSandboxClass.next_sandbox = fake_sandbox
    session = E2BSandboxSession()
    await session.open()
    with pytest.raises(MCPUnavailableError):
        await session.call_tool("nonexistent_tool", {})


@pytest.mark.asyncio
async def test_call_tool_when_not_open_raises(monkeypatch):
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    session = E2BSandboxSession()
    # Don't call open() — call_tool should raise MCPUnavailableError
    with pytest.raises(MCPUnavailableError):
        await session.call_tool("write_file", {"path": "x", "content": "y"})


# ── clone_repo + token scrubbing ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_tool_clone_repo_success(monkeypatch, patched_async_sandbox, fake_sandbox):
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret_token_abc")
    _FakeAsyncSandboxClass.next_sandbox = fake_sandbox
    fake_sandbox.set_command_result("git clone", _FakeCommandResult(stdout="", exit_code=0))
    fake_sandbox.set_command_result("git -C repo remote set-url", _FakeCommandResult(stdout="", exit_code=0))
    session = E2BSandboxSession()
    await session.open()
    result = await session.call_tool("clone_repo", {
        "repo_url": "https://github.com/owner/repo",
        "branch": "main",
    })
    data = json.loads(result)
    assert data["cloned"] is True
    # Verify the clone command included the token-injected URL
    clone_cmd = next((c for c, _ in fake_sandbox.commands_run if "git clone" in c), None)
    assert clone_cmd is not None
    assert "ghp_secret_token_abc@github.com" in clone_cmd
    # Verify the remote URL was scrubbed back to the clean URL afterward
    scrub_cmd = next((c for c, _ in fake_sandbox.commands_run if "remote set-url" in c), None)
    assert scrub_cmd is not None
    assert "ghp_secret_token_abc" not in scrub_cmd
    assert "https://github.com/owner/repo" in scrub_cmd


@pytest.mark.asyncio
async def test_call_tool_clone_repo_no_token(monkeypatch, patched_async_sandbox, fake_sandbox):
    """clone_repo without a GitHub token uses the bare URL (no injection)."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    _FakeAsyncSandboxClass.next_sandbox = fake_sandbox
    fake_sandbox.set_command_result("git clone", _FakeCommandResult(stdout="", exit_code=0))
    session = E2BSandboxSession()
    await session.open()
    await session.call_tool("clone_repo", {
        "repo_url": "https://github.com/owner/repo",
        "branch": "main",
    })
    clone_cmd = next((c for c, _ in fake_sandbox.commands_run if "git clone" in c), None)
    assert clone_cmd is not None
    # No '@github.com' token injection
    assert "@" not in clone_cmd.split("github.com")[0]


@pytest.mark.asyncio
async def test_call_tool_clone_repo_scrubs_token_from_error(monkeypatch, patched_async_sandbox, fake_sandbox):
    """A git clone failure must not leak the token via stderr in the error."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret_token_xyz")
    _FakeAsyncSandboxClass.next_sandbox = fake_sandbox
    fake_sandbox.set_command_result(
        "git clone",
        _FakeCommandResult(stderr="fatal: bad credentials for ghp_secret_token_xyz", exit_code=1),
    )
    session = E2BSandboxSession()
    await session.open()
    with pytest.raises(MCPUnavailableError) as exc_info:
        await session.call_tool("clone_repo", {
            "repo_url": "https://github.com/owner/repo",
            "branch": "main",
        })
    err_msg = str(exc_info.value)
    assert "ghp_secret_token_xyz" not in err_msg
    assert "***" in err_msg


# ── git_commit / git_push ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_tool_git_commit(monkeypatch, patched_async_sandbox, fake_sandbox):
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    _FakeAsyncSandboxClass.next_sandbox = fake_sandbox
    fake_sandbox.set_command_result("git -C repo add", _FakeCommandResult(stdout="", exit_code=0))
    fake_sandbox.set_command_result("git -C repo commit", _FakeCommandResult(stdout="", exit_code=0))
    session = E2BSandboxSession()
    await session.open()
    result = await session.call_tool("git_commit", {"message": "test commit"})
    data = json.loads(result)
    assert data["committed"] is True


@pytest.mark.asyncio
async def test_call_tool_git_push_scrubs_token(monkeypatch, patched_async_sandbox, fake_sandbox):
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_push_token_abc")
    _FakeAsyncSandboxClass.next_sandbox = fake_sandbox
    # First call: get-url returns the clean URL
    fake_sandbox.set_command_result("git -C repo remote get-url", _FakeCommandResult(stdout="https://github.com/owner/repo\n", exit_code=0))
    fake_sandbox.set_command_result("git -C repo remote set-url", _FakeCommandResult(stdout="", exit_code=0))
    fake_sandbox.set_command_result("git -C repo push", _FakeCommandResult(stdout="", exit_code=0))
    session = E2BSandboxSession()
    await session.open()
    result = await session.call_tool("git_push", {"branch": "feature-x"})
    data = json.loads(result)
    assert data["pushed"] is True
    # Verify the push command included the token-injected URL temporarily
    set_url_cmds = [c for c, _ in fake_sandbox.commands_run if "remote set-url" in c]
    # Should be called twice: once to inject, once to restore
    assert len(set_url_cmds) >= 2
    # The first set-url should contain the token (injecting)
    assert "ghp_push_token_abc@github.com" in set_url_cmds[0]
    # The last set-url should NOT contain the token (restoring)
    assert "ghp_push_token_abc" not in set_url_cmds[-1]


# ── git_diff ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_tool_git_diff(monkeypatch, patched_async_sandbox, fake_sandbox):
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    _FakeAsyncSandboxClass.next_sandbox = fake_sandbox
    fake_sandbox.set_command_result("git -C repo diff", _FakeCommandResult(stdout="diff content here", exit_code=0))
    session = E2BSandboxSession()
    await session.open()
    result = await session.call_tool("git_diff", {})
    assert "diff content here" in result


# ── maybe_attach_e2b ──────────────────────────────────────────────────────


class _FakeRunner:
    """Minimal stand-in for AgentRunner — only needs ``_mcp`` attribute."""
    def __init__(self):
        self._mcp = None


@pytest.mark.asyncio
async def test_maybe_attach_e2b_disabled_returns_none(monkeypatch):
    """When E2B is disabled, maybe_attach_e2b returns None and runner._mcp is untouched."""
    monkeypatch.delenv("E2B_API_KEY", raising=False)
    runner = _FakeRunner()
    result = await maybe_attach_e2b(runner)
    assert result is None
    assert runner._mcp is None


@pytest.mark.asyncio
async def test_maybe_attach_e2b_sdk_missing_returns_none(monkeypatch):
    """When the SDK is missing, maybe_attach_e2b returns None (graceful degradation)."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setattr(e2b_config, "is_e2b_sdk_importable", lambda: False)
    runner = _FakeRunner()
    result = await maybe_attach_e2b(runner)
    assert result is None
    assert runner._mcp is None


@pytest.mark.asyncio
async def test_maybe_attach_e2b_open_failure_returns_none(monkeypatch, patched_async_sandbox):
    """When sandbox open fails, maybe_attach_e2b returns None and runner._mcp untouched."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    _FakeAsyncSandboxClass.raise_on_create = RuntimeError("network down")
    runner = _FakeRunner()
    result = await maybe_attach_e2b(runner)
    assert result is None
    assert runner._mcp is None


@pytest.mark.asyncio
async def test_maybe_attach_e2b_success(monkeypatch, patched_async_sandbox, fake_sandbox):
    """When everything works, runner._mcp is set to the session and the session is returned."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    _FakeAsyncSandboxClass.next_sandbox = fake_sandbox
    runner = _FakeRunner()
    prior_mcp = object()
    runner._mcp = prior_mcp
    session = await maybe_attach_e2b(runner)
    assert session is not None
    assert runner._mcp is session
    # The prior _mcp is stashed for restoration
    assert session._prior_mcp is prior_mcp
    await session.close()

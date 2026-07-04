"""tests/test_e2b_adapter.py — E2BAdapter behaviour, mocked at the SDK seam.

Covers:
  * health_check unavailable without a key (operator kill-switch).
  * health_check unavailable when the SDK is missing.
  * required_dependencies declares E2B_API_KEY as a required env dep.
  * execute() happy path: opens sandbox, runs AgentRunner, returns TaskResult.
  * execute() with repo_url clones into the sandbox.
  * execute() in-sandbox pytest verifier retries on failure.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import pytest

from runtimes.adapters.e2b import E2BAdapter
from runtimes.base import RuntimeExecutionError, TaskSpec
from services import e2b_config


@pytest.fixture(autouse=True)
def _clean_e2b_env(monkeypatch):
    for k in ("E2B_API_KEY", "E2B_ENABLED", "RUNTIME_E2B_ENABLED",
              "E2B_TEMPLATE", "E2B_TIMEOUT_SEC", "E2B_SANDBOX_METADATA",
              "AGENT_SANDBOX_MODE", "GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    yield


# ── health_check ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_unavailable_without_key(monkeypatch):
    """No E2B_API_KEY → health_check reports unavailable."""
    monkeypatch.delenv("E2B_API_KEY", raising=False)
    adapter = E2BAdapter()
    health = await adapter.health_check()
    assert health.available is False
    assert health.runtime_id == "e2b"
    assert "not set" in (health.error or "").lower() or "e2b_api_key" in (health.error or "").lower()


@pytest.mark.asyncio
async def test_health_unavailable_with_kill_switch(monkeypatch):
    """E2B_ENABLED=false wins over a present key."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "false")
    adapter = E2BAdapter()
    health = await adapter.health_check()
    assert health.available is False


@pytest.mark.asyncio
async def test_health_unavailable_when_sdk_missing(monkeypatch):
    """Key present but SDK missing → unavailable with a clear error."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    # Patch in BOTH the config module and the adapter module (the adapter
    # imports the function directly into its own namespace via `from ... import`).
    monkeypatch.setattr(e2b_config, "is_e2b_sdk_importable", lambda: False)
    from runtimes.adapters import e2b as _e2b_adapter_mod
    monkeypatch.setattr(_e2b_adapter_mod, "is_e2b_sdk_importable", lambda: False)
    adapter = E2BAdapter()
    health = await adapter.health_check()
    assert health.available is False
    assert "sdk" in (health.error or "").lower() or "install" in (health.error or "").lower()


@pytest.mark.asyncio
async def test_health_available_when_configured(monkeypatch):
    """Key present + SDK importable → available with template/timeout details."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    adapter = E2BAdapter()
    health = await adapter.health_check()
    assert health.available is True
    assert health.details.get("template") == "base"
    assert health.details.get("timeout_sec") == 300


# ── required_dependencies ────────────────────────────────────────────────


def test_required_dependencies_declares_api_key():
    """The preflight readiness report must surface E2B_API_KEY as required env."""
    adapter = E2BAdapter()
    deps = adapter.required_dependencies()
    assert any(d.name == "E2B_API_KEY" and d.kind == "env" for d in deps)
    api_key_dep = next(d for d in deps if d.name == "E2B_API_KEY")
    assert api_key_dep.required is True
    assert api_key_dep.config_var == "E2B_API_KEY"
    assert api_key_dep.install_hint and "e2b.dev" in api_key_dep.install_hint


# ── Adapter metadata ──────────────────────────────────────────────────────


def test_adapter_metadata():
    """Class-level metadata is set correctly for the router."""
    assert E2BAdapter.RUNTIME_ID == "e2b"
    from runtimes.base import RuntimeTier
    assert E2BAdapter.TIER == RuntimeTier.FIRST_CLASS
    # Must declare the capabilities listed in the integration plan
    from runtimes.base import RuntimeCapability as RC
    for cap in (RC.SHELL_EXEC, RC.REPO_EDITING, RC.GIT_OPERATIONS,
                RC.FILE_READ_WRITE, RC.CODE_GENERATION, RC.CODE_REVIEW,
                RC.MULTI_FILE_EDIT, RC.AUTONOMOUS_LOOP):
        assert cap in E2BAdapter.CAPABILITIES


# ── execute() — mocked AgentRunner + sandbox ─────────────────────────────


class _FakeCommandResult:
    def __init__(self, stdout: str = "", stderr: str = "", exit_code: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.returncode = exit_code


class _FakeFiles:
    def __init__(self):
        self.written: dict[str, str] = {}

    async def write(self, path: str, content: str) -> None:
        self.written[path] = content

    async def read(self, path: str) -> str:
        raise FileNotFoundError(path)


class _FakeCommands:
    def __init__(self):
        self.run_log: list[tuple[str, int]] = []
        self._results: dict[str, _FakeCommandResult] = {}
        self._default = _FakeCommandResult()

    def set_result(self, cmd_substr: str, result: _FakeCommandResult) -> None:
        self._results[cmd_substr] = result

    async def run(self, cmd: str, timeout: int = 60) -> _FakeCommandResult:
        self.run_log.append((cmd, timeout))
        for substr, result in self._results.items():
            if substr in cmd:
                return result
        return self._default


class _FakeSandbox:
    def __init__(self):
        self.files = _FakeFiles()
        self.commands = _FakeCommands()
        self.killed = False

    async def kill(self) -> None:
        self.killed = True


class _FakeAsyncSandboxClass:
    last_created: list[dict[str, Any]] = []
    next_sandbox: _FakeSandbox | None = None
    raise_on_create: Exception | None = None

    @classmethod
    async def create(cls, **kwargs: Any) -> _FakeSandbox:
        cls.last_created.append(kwargs)
        if cls.raise_on_create is not None:
            raise cls.raise_on_create
        if cls.next_sandbox is None:
            cls.next_sandbox = _FakeSandbox()
        return cls.next_sandbox


@pytest.fixture
def patched_async_sandbox(monkeypatch):
    _FakeAsyncSandboxClass.last_created = []
    _FakeAsyncSandboxClass.next_sandbox = None
    _FakeAsyncSandboxClass.raise_on_create = None
    import e2b_code_interpreter as _sdk
    monkeypatch.setattr(_sdk, "AsyncSandbox", _FakeAsyncSandboxClass)
    return _FakeAsyncSandboxClass


@pytest.fixture
def patched_agent_runner(monkeypatch):
    """Patch AgentRunner inside runtimes.adapters.e2b so execute() can run
    without invoking the real LLM/agent loop. The fake runner records the
    instruction + returns a controlled result dict."""
    captured: dict[str, Any] = {}

    class _FakeRunner:
        def __init__(self, **kwargs: Any):
            captured["init_kwargs"] = kwargs
            self._mcp = None

        async def run(self, **kwargs: Any):
            captured["run_kwargs"] = kwargs
            # Return a result dict shaped like AgentRunner.run's return value.
            return {
                "steps": [{"status": "applied", "changed_files": ["src/changed.py"]}],
                "report": "Test report: changes applied",
                "summary": "Changes applied",
                "judge": {"verdict": "PASS"},
                "model_used": "test-model",
            }

    # Patch the import path used inside E2BAdapter.execute
    import sys
    fake_module = type(sys)("agent.loop")
    fake_module.AgentRunner = _FakeRunner  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "agent.loop", fake_module)
    return captured, _FakeRunner


@pytest.mark.asyncio
async def test_execute_happy_path(monkeypatch, patched_async_sandbox, patched_agent_runner):
    """execute() opens a sandbox, runs the agent, returns a TaskResult."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    captured, _ = patched_agent_runner
    adapter = E2BAdapter()
    spec = TaskSpec(
        task_id="task-1",
        instruction="Add a function",
        task_type="code_generation",
        context={},
    )
    result = await adapter.execute(spec)
    assert result.runtime_id == "e2b"
    assert result.success is True
    assert "Test report" in result.output
    assert result.model_used == "test-model"
    assert result.provider_used == "e2b-sandbox"
    # Verify the runner was constructed
    assert "init_kwargs" in captured
    # Verify the runner.run was called with the instruction
    assert captured["run_kwargs"]["instruction"] == "Add a function"


@pytest.mark.asyncio
async def test_execute_with_repo_url_clones(monkeypatch, patched_async_sandbox, patched_agent_runner):
    """When spec.context['repo_url'] is set, execute() clones it into the sandbox."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    _FakeAsyncSandboxClass.next_sandbox = _FakeSandbox()
    # Stub git clone success
    _FakeAsyncSandboxClass.next_sandbox.commands.set_result("git clone", _FakeCommandResult(exit_code=0))
    _FakeAsyncSandboxClass.next_sandbox.commands.set_result("git -C repo remote", _FakeCommandResult(exit_code=0))
    _FakeAsyncSandboxClass.next_sandbox.commands.set_result("git -C repo diff", _FakeCommandResult(stdout="", exit_code=0))
    # Stub in-sandbox pytest to pass (exit code 0)
    _FakeAsyncSandboxClass.next_sandbox.commands.set_result("pytest", _FakeCommandResult(stdout="1 passed", exit_code=0))

    adapter = E2BAdapter()
    spec = TaskSpec(
        task_id="task-2",
        instruction="Fix the bug",
        task_type="repo_editing",
        context={
            "repo_url": "https://github.com/owner/repo",
            "base_branch": "main",
            "github_token": "ghp_test_token",
        },
    )
    result = await adapter.execute(spec)
    assert result.runtime_id == "e2b"
    # Verify clone was called
    clone_cmd = next((c for c, _ in _FakeAsyncSandboxClass.next_sandbox.commands.run_log if "git clone" in c), None)
    assert clone_cmd is not None
    assert "ghp_test_token@github.com" in clone_cmd  # token injected
    # Verify the metadata includes the E2B block
    assert "e2b" in result.metadata
    assert result.metadata["e2b"]["test_passed"] is True


@pytest.mark.asyncio
async def test_execute_in_sandbox_pytest_retry(monkeypatch, patched_async_sandbox, patched_agent_runner):
    """When in-sandbox pytest fails, execute() retries once with failure feedback."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    fake_sb = _FakeSandbox()
    _FakeAsyncSandboxClass.next_sandbox = fake_sb
    # First pytest call fails, second passes
    call_count = {"n": 0}

    original_run = fake_sb.commands.run

    async def counting_run(cmd: str, timeout: int = 60):
        call_count["n"] += 1
        if "pytest" in cmd:
            if call_count["n"] <= 1:
                return _FakeCommandResult(stdout="FAILED test_foo", exit_code=1)
            return _FakeCommandResult(stdout="1 passed", exit_code=0)
        if "git clone" in cmd:
            return _FakeCommandResult(exit_code=0)
        if "git -C repo remote" in cmd:
            return _FakeCommandResult(exit_code=0)
        if "git -C repo diff" in cmd:
            return _FakeCommandResult(stdout="", exit_code=0)
        return _FakeCommandResult()

    fake_sb.commands.run = counting_run  # type: ignore[assignment]

    adapter = E2BAdapter()
    spec = TaskSpec(
        task_id="task-3",
        instruction="Fix the failing test",
        task_type="repo_editing",
        context={
            "repo_url": "https://github.com/owner/repo",
            "base_branch": "main",
        },
    )
    result = await adapter.execute(spec)
    assert result.runtime_id == "e2b"
    # The retry should have produced a test_passed=True after the second pytest run
    assert result.metadata["e2b"]["test_passed"] is True


@pytest.mark.asyncio
async def test_execute_no_key_raises(monkeypatch, patched_async_sandbox):
    """execute() raises RuntimeExecutionError when E2B_API_KEY is not set."""
    monkeypatch.delenv("E2B_API_KEY", raising=False)
    adapter = E2BAdapter()
    spec = TaskSpec(task_id="task-4", instruction="do something", context={})
    with pytest.raises(RuntimeExecutionError):
        await adapter.execute(spec)


@pytest.mark.asyncio
async def test_execute_sandbox_open_failure_raises(monkeypatch, patched_async_sandbox, patched_agent_runner):
    """When sandbox open fails, execute() raises RuntimeExecutionError (so the
    coordinator can fall back to internal_agent)."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    _FakeAsyncSandboxClass.raise_on_create = RuntimeError("quota exceeded")
    adapter = E2BAdapter()
    spec = TaskSpec(task_id="task-5", instruction="do something", context={})
    with pytest.raises(RuntimeExecutionError) as exc_info:
        await adapter.execute(spec)
    assert "sandbox open failed" in str(exc_info.value).lower() or "quota" in str(exc_info.value).lower()

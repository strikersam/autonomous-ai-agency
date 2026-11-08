"""tests/test_sandbox_fallbacks.py — Daytona and InstaBox fallback sandbox providers.

The SDKs are replaced by in-memory fakes that record calls; the shims must give
the E2B-shaped surface E2BSandboxSession relies on.
"""
from __future__ import annotations

import shlex
import types
from typing import Any

import pytest

from services import daytona_sandbox, e2b_sandbox, instabox_sandbox
from services import sandbox_providers as reg
from services.daytona_sandbox import DaytonaSandboxShim
from services.e2b_config import (
    PROVIDER_DAYTONA,
    PROVIDER_E2B,
    PROVIDER_FREESTYLE,
    PROVIDER_INSTABOX,
    SANDBOX_PROVIDERS,
    E2BConfig,
    resolve_sandbox_configs,
    sandbox_providers,
)
from services.instabox_sandbox import InstaboxSandboxShim, open_instabox_sandbox

_KEYS = {"FREESTYLE_API_KEY": "fs", "DAYTONA_API_KEY": "dt", "INSTABOX_API_KEY": "ib", "E2B_API_KEY": "e2"}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in (*_KEYS, "SANDBOX_PROVIDER", "E2B_ENABLED", "RUNTIME_E2B_ENABLED", "AGENT_SANDBOX_MODE",
              "DAYTONA_SNAPSHOT", "INSTABOX_SNAPSHOT", "DAYTONA_API_URL", "INSTABOX_API_URL"):
        monkeypatch.delenv(k, raising=False)


# ── Default order ─────────────────────────────────────────────────────────


def test_default_order_is_freestyle_then_daytona_instabox_e2b(monkeypatch):
    assert SANDBOX_PROVIDERS == (PROVIDER_FREESTYLE, PROVIDER_DAYTONA, PROVIDER_INSTABOX, PROVIDER_E2B)
    for k, v in _KEYS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("E2B_ENABLED", "true")
    assert sandbox_providers() == list(SANDBOX_PROVIDERS)
    assert [(c.provider, c.api_key) for c in resolve_sandbox_configs()] == [
        ("freestyle", "fs"), ("daytona", "dt"), ("instabox", "ib"), ("e2b", "e2")]


def test_generic_env_names_per_provider(monkeypatch):
    monkeypatch.setenv("INSTABOX_API_KEY", "ib")
    monkeypatch.setenv("INSTABOX_SNAPSHOT", "sn_repo")
    monkeypatch.setenv("INSTABOX_API_URL", "https://ib.example")
    monkeypatch.setenv("E2B_ENABLED", "true")
    (cfg,) = resolve_sandbox_configs()
    assert (cfg.provider, cfg.template, cfg.api_url) == (PROVIDER_INSTABOX, "sn_repo", "https://ib.example")


def test_every_default_provider_has_an_opener():
    assert all(reg.get_opener(p) is not None for p in SANDBOX_PROVIDERS)


# ── Daytona shim ──────────────────────────────────────────────────────────


class _Resp:
    def __init__(self, result: str, exit_code: int) -> None:
        self.result, self.exit_code = result, exit_code


class _FakeDaytona:
    id = "sb-1"

    def __init__(self) -> None:
        self.execs: list[tuple[str, Any]] = []
        self.files: dict[str, bytes] = {}
        self.deleted = self.refreshed = False
        self.process = self.fs = self

    async def exec(self, command, timeout=None):
        self.execs.append((command, timeout))
        if command.startswith("test -e "):
            return _Resp("", 0 if shlex.split(command)[2] in self.files else 1)
        failing = "false" in command
        return _Resp("boom" if failing else "ok", 1 if failing else 0)

    async def upload_file(self, src, dst):
        assert isinstance(src, bytes), "a str source would be read as a local path"
        self.files[dst] = src

    async def download_file(self, path):
        if path not in self.files:
            raise type("DaytonaNotFoundError", (Exception,), {})(path)
        return self.files[path]

    async def refresh_activity(self):
        self.refreshed = True

    async def create_signed_preview_url(self, port, expires_in_seconds=None):
        return types.SimpleNamespace(url=f"https://{port}-tok.proxy.daytona.works/")

    async def delete(self):
        self.deleted = True


class _FakeAsyncClient:
    closed = False

    async def close(self):
        self.closed = True


async def test_daytona_shim_surface():
    sb, client = _FakeDaytona(), _FakeAsyncClient()
    s = DaytonaSandboxShim(client, sb, idle_minutes=11)
    ok = await s.commands.run("cd /x && echo hi", timeout=30)
    bad = await s.commands.run("false", timeout=0)
    assert (ok.stdout, ok.exit_code, bad.stdout, bad.exit_code) == ("ok", 0, "boom", 1)
    assert sb.execs[0] == (f"bash -c {shlex.quote('cd /x && echo hi')}", 30)
    assert sb.execs[1][1] is None
    await s.files.write("/home/user/repo/a.py", "print('é')\n")
    assert await s.files.read("/home/user/repo/a.py") == "print('é')\n"
    with pytest.raises(FileNotFoundError):
        await s.files.read("/nope")
    await s.set_timeout(660)
    assert sb.refreshed
    assert await s.get_host(4173) == "4173-tok.proxy.daytona.works"
    await s.kill()
    assert sb.deleted and client.closed


# ── InstaBox shim ─────────────────────────────────────────────────────────


class _NotFound(Exception):
    pass


class _FakeInstabox:
    """Stands in for ``instabox.Client`` (sync, like the real SDK)."""

    def __init__(self, fail_create: Exception | None = None, publish_out: str = "") -> None:
        self.created: dict[str, Any] = {}
        self.execs: list[tuple[str, int]] = []
        self.files: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.closed = False
        self.fail_create = fail_create
        self.publish_out = publish_out or "Published: https://4173-box1.instabox.run/\n"
        self.machines = types.SimpleNamespace(create=self._create, exec=self._exec, delete=self._delete)
        self.files_api = types.SimpleNamespace(write=self._write, read_bytes=self._read)

    def _create(self, **kw):
        if self.fail_create:
            raise self.fail_create
        self.created = kw
        return types.SimpleNamespace(id="m_box1")

    def _exec(self, machine, cmd, timeout=60):
        self.execs.append((cmd, timeout))
        if "instabox-port publish" in cmd:
            return types.SimpleNamespace(stdout=self.publish_out, stderr="", exit_code=0)
        failing = "false" in cmd
        return types.SimpleNamespace(stdout="out", stderr="err" if failing else "", exit_code=1 if failing else 0)

    def _write(self, machine, path, data):
        self.files[path] = data

    def _read(self, machine, path):
        if path not in self.files:
            raise _NotFound(path)
        return self.files[path]

    def _delete(self, machine):
        self.deleted.append(machine)

    def close(self):
        self.closed = True


@pytest.fixture
def ibx(monkeypatch):
    fake_mod = types.ModuleType("instabox")
    fake_mod.NotFoundError = _NotFound  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "instabox", fake_mod)

    return _FakeInstabox


def _ib_config(**kw) -> E2BConfig:
    return E2BConfig(api_key="ib", template=kw.get("template", ""), timeout_sec=660,
                     metadata=kw.get("metadata"), provider=PROVIDER_INSTABOX)


def _client(fake: _FakeInstabox) -> Any:
    """The shape of ``instabox.Client`` the shim uses: machines, files, close."""
    return types.SimpleNamespace(machines=fake.machines, files=fake.files_api, close=fake.close)


async def test_instabox_open_creates_with_backstop_and_workdir(ibx):
    fake = ibx()
    shim = await open_instabox_sandbox(_ib_config(template="sn_1", metadata={"task": "t"}), client=_client(fake))
    assert shim.sandbox_id == "m_box1"
    assert fake.created == {"delete_after_seconds": 21600, "fail_fast": True, "timeout": 300,
                            "snapshot_id": "sn_1", "metadata": {"task": "t"}}
    assert "mkdir -p /home/user/repo" in fake.execs[0][0]


async def test_instabox_commands_run_as_root_when_sudo_allows(ibx):
    fake = ibx()
    shim = InstaboxSandboxShim(_client(fake), "m_box1")
    ok = await shim.commands.run("cd /x && echo hi", timeout=30)
    bad = await shim.commands.run("false", timeout=0)
    assert (ok.stdout, ok.exit_code, bad.stderr, bad.exit_code) == ("out", 0, "err", 1)
    sent, limit = fake.execs[0]
    assert sent.startswith("if sudo -n true") and shlex.quote("cd /x && echo hi") in sent
    assert limit == 30 and fake.execs[1][1] == 600  # 0 means the API's 600 s cap


async def test_instabox_files_preview_and_kill(ibx):
    fake = ibx()
    shim = InstaboxSandboxShim(_client(fake), "m_box1")
    await shim.files.write("/home/user/repo/a.txt", "hé")
    assert fake.files["/home/user/repo/a.txt"] == "hé".encode()
    assert await shim.files.read("/home/user/repo/a.txt") == "hé"
    with pytest.raises(FileNotFoundError):
        await shim.files.read("/nope")
    assert await shim.get_host(4173) == "4173-box1.instabox.run"
    await shim.kill()
    assert fake.deleted == ["m_box1"] and fake.closed


async def test_instabox_preview_without_url_raises(ibx):
    fake = ibx(publish_out="no url here")
    shim = InstaboxSandboxShim(_client(fake), "m_box1")
    with pytest.raises(RuntimeError, match="publish 4173 failed"):
        await shim.get_host(4173)


async def test_instabox_create_failure_closes_client(ibx):
    fake = ibx(fail_create=RuntimeError("429 quota_exceeded"))
    with pytest.raises(RuntimeError, match="quota_exceeded"):
        await open_instabox_sandbox(_ib_config(), client=_client(fake))
    assert fake.closed


# ── Chain end to end ──────────────────────────────────────────────────────


async def test_session_falls_through_the_whole_chain_to_instabox(monkeypatch, ibx):
    for k, v in _KEYS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("E2B_ENABLED", "true")
    tried: list[str] = []
    fake = ibx()

    async def _down(config):
        tried.append(config.provider)
        raise RuntimeError(f"{config.provider} unavailable")

    async def _instabox(config):
        tried.append(config.provider)
        return await open_instabox_sandbox(config, client=_client(fake))

    monkeypatch.setattr(reg, "_openers", {"freestyle": _down, "daytona": _down,
                                          "instabox": _instabox, "e2b": _down})
    session = e2b_sandbox.E2BSandboxSession()
    await session.open()
    assert tried == ["freestyle", "daytona", "instabox"]
    assert session._config.provider == PROVIDER_INSTABOX
    await session.call_tool("write_file", {"path": "z.txt", "content": "ok"})
    assert fake.files["/home/user/repo/z.txt"] == b"ok"
    await session.close()
    assert fake.deleted == ["m_box1"]


async def test_all_four_down_reports_each(monkeypatch):
    for k, v in _KEYS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("E2B_ENABLED", "true")

    async def _down(config):
        raise RuntimeError("down")

    monkeypatch.setattr(reg, "_openers", {p: _down for p in SANDBOX_PROVIDERS})
    with pytest.raises(e2b_sandbox.MCPUnavailableError) as exc:
        await e2b_sandbox.E2BSandboxSession().open()
    assert all(f"{p}: down" in str(exc.value) for p in SANDBOX_PROVIDERS)


async def test_daytona_generic_download_error_on_missing_file_is_not_found():
    sb, client = _FakeDaytona(), _FakeAsyncClient()

    async def _generic(path):
        raise type("DaytonaError", (Exception,), {})("download failed")

    sb.download_file = _generic  # type: ignore[method-assign]
    s = DaytonaSandboxShim(client, sb, idle_minutes=11)
    with pytest.raises(FileNotFoundError):
        await s.files.read("/home/user/repo/missing.py")
    sb.files["/home/user/repo/there.py"] = b"x"
    with pytest.raises(Exception, match="download failed"):
        await s.files.read("/home/user/repo/there.py")

"""tests/test_freestyle_sandbox.py — Freestyle VMs as a sandbox provider behind E2BSandboxSession.

The Freestyle API is faked with ``httpx.MockTransport``: these tests pin the
request shapes taken from the official TypeScript SDK (``freestyle@0.2.21``)
and the E2B-shaped surface the session relies on.
"""
from __future__ import annotations

import json
import shlex
from typing import Any

import httpx
import pytest

from services import e2b_sandbox, freestyle_sandbox
from services.e2b_config import (
    PROVIDER_E2B,
    PROVIDER_FREESTYLE,
    E2BConfig,
    e2b_enabled,
    is_e2b_sdk_importable,
    resolve_e2b_config,
    resolve_sandbox_configs,
    sandbox_provider,
    sandbox_providers,
)
from services.freestyle_sandbox import FreestyleApi, open_freestyle_sandbox

_ENV = ("E2B_API_KEY", "E2B_ENABLED", "RUNTIME_E2B_ENABLED", "AGENT_SANDBOX_MODE",
        "SANDBOX_PROVIDER", "FREESTYLE_API_KEY", "FREESTYLE_API_URL", "FREESTYLE_SNAPSHOT",
        "E2B_TEMPLATE", "E2B_TIMEOUT_SEC", "E2B_SANDBOX_METADATA")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in _ENV:
        monkeypatch.delenv(k, raising=False)


# ── Provider selection ────────────────────────────────────────────────────


def test_auto_prefers_free_freestyle_over_e2b(monkeypatch):
    monkeypatch.setenv("E2B_API_KEY", "e2b_x")
    monkeypatch.setenv("FREESTYLE_API_KEY", "fs_x")
    assert sandbox_provider() == PROVIDER_FREESTYLE


def test_e2b_only_install_is_unchanged(monkeypatch):
    monkeypatch.setenv("E2B_API_KEY", "e2b_x")
    monkeypatch.setenv("E2B_ENABLED", "true")
    assert sandbox_providers() == [PROVIDER_E2B]
    assert resolve_e2b_config().provider == PROVIDER_E2B


def test_auto_uses_freestyle_when_only_its_key_is_set(monkeypatch):
    monkeypatch.setenv("FREESTYLE_API_KEY", "fs_x")
    monkeypatch.setenv("E2B_ENABLED", "true")
    assert sandbox_provider() == PROVIDER_FREESTYLE
    assert e2b_enabled() is True
    assert is_e2b_sdk_importable() is True  # httpx is all Freestyle needs
    cfg = resolve_e2b_config()
    assert cfg is not None and (cfg.provider, cfg.api_key, cfg.template) == (PROVIDER_FREESTYLE, "fs_x", "")
    assert "fs_x" not in repr(cfg)


def test_explicit_freestyle_overrides_an_exhausted_e2b_key(monkeypatch):
    monkeypatch.setenv("E2B_API_KEY", "e2b_out_of_credit")
    monkeypatch.setenv("FREESTYLE_API_KEY", "fs_x")
    monkeypatch.setenv("SANDBOX_PROVIDER", "freestyle")
    monkeypatch.setenv("E2B_ENABLED", "true")
    monkeypatch.setenv("FREESTYLE_SNAPSHOT", "repo-deps")
    cfg = resolve_e2b_config()
    assert (cfg.provider, cfg.api_key, cfg.template, cfg.api_url) == (
        PROVIDER_FREESTYLE, "fs_x", "repo-deps", None)


def test_freestyle_still_needs_the_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("FREESTYLE_API_KEY", "fs_x")
    assert e2b_enabled() is False
    assert resolve_e2b_config() is None


def test_freestyle_selected_without_its_key_is_disabled(monkeypatch):
    monkeypatch.setenv("E2B_API_KEY", "e2b_x")
    monkeypatch.setenv("SANDBOX_PROVIDER", "freestyle")
    monkeypatch.setenv("E2B_ENABLED", "true")
    assert e2b_enabled() is False


def test_unknown_provider_is_dropped(monkeypatch):
    monkeypatch.setenv("SANDBOX_PROVIDER", "nope,freestyle")
    monkeypatch.setenv("FREESTYLE_API_KEY", "fs_x")
    assert sandbox_providers() == [PROVIDER_FREESTYLE]


def test_chain_keeps_order_dedupes_and_skips_unkeyed(monkeypatch):
    monkeypatch.setenv("E2B_API_KEY", "e2b_x")
    monkeypatch.setenv("FREESTYLE_API_KEY", "fs_x")
    monkeypatch.setenv("E2B_ENABLED", "true")
    monkeypatch.setenv("SANDBOX_PROVIDER", "freestyle, e2b, freestyle")
    assert sandbox_providers() == [PROVIDER_FREESTYLE, PROVIDER_E2B]
    cfgs = resolve_sandbox_configs()
    assert [(c.provider, c.api_key) for c in cfgs] == [(PROVIDER_FREESTYLE, "fs_x"), (PROVIDER_E2B, "e2b_x")]
    assert cfgs[1].template == "base"
    monkeypatch.delenv("E2B_API_KEY")
    assert sandbox_providers() == [PROVIDER_FREESTYLE]


def test_auto_is_every_keyed_provider_freestyle_first(monkeypatch):
    monkeypatch.setenv("E2B_API_KEY", "e2b_x")
    monkeypatch.setenv("FREESTYLE_API_KEY", "fs_x")
    assert sandbox_providers() == [PROVIDER_FREESTYLE, PROVIDER_E2B]


def test_provider_override_from_platform_controls_takes_effect(monkeypatch):
    from packages.config import control_overrides
    from packages.config.control_registry import get_control

    spec = get_control("SANDBOX_PROVIDER")
    assert spec is not None and spec.live
    monkeypatch.setenv("E2B_API_KEY", "e2b_x")
    monkeypatch.setenv("FREESTYLE_API_KEY", "fs_x")
    assert sandbox_provider() == PROVIDER_FREESTYLE
    control_overrides.apply_overrides({"SANDBOX_PROVIDER": "e2b,freestyle"})
    try:
        assert sandbox_providers() == [PROVIDER_E2B, PROVIDER_FREESTYLE]
    finally:
        monkeypatch.delenv("SANDBOX_PROVIDER", raising=False)


# ── Fake Freestyle API ────────────────────────────────────────────────────


class FakeFreestyle:
    """In-memory stand-in for the ``/v5`` endpoints the shim calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any]] = []
        self.files: dict[str, bytes] = {}
        self.uploads: dict[str, dict[str, Any]] = {}
        self.deleted: set[str] = set()
        self.defer_next_exec = False

    def handler(self, req: httpx.Request) -> httpx.Response:
        path, q = req.url.path, dict(req.url.params)
        body = json.loads(req.content) if req.headers.get("content-type") == "application/json" else req.content
        self.calls.append((req.method, path, body))
        assert req.headers["authorization"] == "Bearer fs_key"
        if (req.method, path) == ("POST", "/v5/vms"):
            return httpx.Response(200, json={"id": "vm123abc"})
        if path.endswith("/exec-await"):
            return self._exec(body)
        if path == "/v5/background-requests/bg1":
            return httpx.Response(200, json={"stdout": "late", "stderr": "", "statusCode": 0})
        if path.endswith("/fs/write"):
            self.files[q["path"]] = req.content
            return httpx.Response(200)
        if path.endswith("/fs/read"):
            if q["path"] not in self.files:
                return httpx.Response(404, json={"code": "FILE_NOT_FOUND", "message": "nope"})
            return httpx.Response(200, content=self.files[q["path"]],
                                  headers={"content-type": "application/octet-stream"})
        return self._uploads_tls_delete(req, path, q, body)

    def _exec(self, body: dict[str, Any]) -> httpx.Response:
        if self.defer_next_exec:
            self.defer_next_exec = False
            return httpx.Response(202, headers={"x-freestyle-background-request-id": "bg1"}, json={})
        failing = "false" in body["command"]
        return httpx.Response(200, json={"stdout": "out", "stderr": "err" if failing else "",
                                         "statusCode": 1 if failing else 0})

    def _uploads_tls_delete(self, req, path, q, body) -> httpx.Response:
        if (req.method, path) == ("POST", "/v5/vms/vm123abc/fs/uploads"):
            self.uploads["u1"] = {"path": body["path"], "data": b""}
            return httpx.Response(200, json={"uploadId": "u1", "receivedBytes": 0})
        if req.method == "PUT" and path.endswith("/fs/uploads/u1"):
            up = self.uploads["u1"]
            assert int(q["offset"]) == len(up["data"])
            up["data"] += req.content
            return httpx.Response(200, json={"receivedBytes": len(up["data"])})
        if path.endswith("/fs/uploads/u1/commit"):
            self.files[self.uploads["u1"]["path"]] = self.uploads["u1"]["data"]
            return httpx.Response(200)
        if (req.method, path) == ("POST", "/v5/tls"):
            return httpx.Response(200, json={"id": "rule1"})
        if req.method == "DELETE":
            self.deleted.add(path)
            return httpx.Response(200)
        return httpx.Response(500, json={"code": "UNEXPECTED", "message": path})


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(freestyle_sandbox, "_BG_POLL_S", 0)
    return FakeFreestyle()


def _api(fake: FakeFreestyle) -> FreestyleApi:
    http = httpx.AsyncClient(base_url="https://api.freestyle.test",
                             headers={"Authorization": "Bearer fs_key"},
                             transport=httpx.MockTransport(fake.handler))
    return FreestyleApi("fs_key", "https://api.freestyle.test", http=http)


def _config(**kw) -> E2BConfig:
    return E2BConfig(api_key="fs_key", template=kw.get("template", ""), timeout_sec=660,
                     metadata=kw.get("metadata"), provider=PROVIDER_FREESTYLE)


async def test_open_boots_vm_with_firewall_lifecycle_and_workdir(fake):
    shim = await open_freestyle_sandbox(_config(template="snap1", metadata={"task": "t1"}), api=_api(fake))
    assert shim.sandbox_id == "vm123abc"
    create = fake.calls[0][2]
    assert create["firewall"]["rules"][0]["destination"] == {"public": True}
    assert (create["idleTimeoutSeconds"], create["ttlSeconds"], create["autoDeleteSeconds"]) == (660, 6 * 3600, 0)
    assert (create["snapshotId"], create["metadata"]) == ("snap1", {"task": "t1"})
    setup = fake.calls[1][2]
    assert setup["linuxUser"] == "root" and "mkdir -p /home/user/repo" in setup["command"]


async def test_commands_run_as_root_under_bash_and_report_exit_code(fake):
    shim = await open_freestyle_sandbox(_config(), api=_api(fake))
    ok = await shim.commands.run("cd /x && echo hi", timeout=30)
    bad = await shim.commands.run("false", timeout=0)
    assert (ok.stdout, ok.exit_code) == ("out", 0)
    assert (bad.stderr, bad.exit_code) == ("err", 1)
    sent = fake.calls[-2][2]
    assert sent["command"] == f"bash -c {shlex.quote('cd /x && echo hi')}"
    assert sent["timeoutMs"] == 30_000 and sent["env"]["HOME"] == "/root"
    assert fake.calls[-1][2]["timeoutMs"] == 300_000  # 0 means the API's five-minute cap


async def test_long_exec_answered_202_is_polled(fake):
    shim = await open_freestyle_sandbox(_config(), api=_api(fake))
    fake.defer_next_exec = True
    res = await shim.commands.run("sleep 30", timeout=120)
    assert (res.stdout, res.exit_code) == ("late", 0)


async def test_background_command_is_detached(fake):
    shim = await open_freestyle_sandbox(_config(), api=_api(fake))
    await shim.commands.run("python3 -m http.server 4173", background=True, timeout=0)
    assert "nohup" in fake.calls[-1][2]["command"]


async def test_files_round_trip_missing_file_and_chunked_upload(fake, monkeypatch):
    shim = await open_freestyle_sandbox(_config(), api=_api(fake))
    await shim.files.write("/home/user/repo/a.py", "print('é')\n")
    assert await shim.files.read("/home/user/repo/a.py") == "print('é')\n"
    with pytest.raises(FileNotFoundError):
        await shim.files.read("/nope")
    monkeypatch.setattr(freestyle_sandbox, "_SINGLE_PUT_MAX", 10)
    monkeypatch.setattr(freestyle_sandbox, "_CHUNK", 7)
    blob = bytes(range(25))
    await shim.files.write("/tmp/seed.tar.gz", blob)
    assert fake.files["/tmp/seed.tar.gz"] == blob


async def test_preview_rule_and_kill(fake):
    shim = await open_freestyle_sandbox(_config(), api=_api(fake))
    host = await shim.get_host(4173)
    assert host == "agency-vm123abc-4173.style.dev"
    rule = fake.calls[-1][2]
    assert rule["destination"] == {"vmId": "vm123abc", "port": 4173} and rule["source"] == {"public": True}
    await shim.kill()
    assert "/v5/vms/vm123abc" in fake.deleted


async def test_failed_setup_deletes_the_vm(fake, monkeypatch):
    api = _api(fake)
    real = fake._exec
    fake._exec = lambda body: httpx.Response(500, json={"code": "BOOM", "message": "x"})  # type: ignore[method-assign]
    with pytest.raises(freestyle_sandbox.FreestyleApiError):
        await open_freestyle_sandbox(_config(), api=api)
    fake._exec = real  # type: ignore[method-assign]
    assert "/v5/vms/vm123abc" in fake.deleted


# ── Session wiring ────────────────────────────────────────────────────────


@pytest.fixture
def freestyle_session(monkeypatch, fake):
    monkeypatch.setenv("FREESTYLE_API_KEY", "fs_key")
    monkeypatch.setenv("SANDBOX_PROVIDER", "freestyle")
    monkeypatch.setenv("E2B_ENABLED", "true")
    real_open = freestyle_sandbox.open_freestyle_sandbox

    async def _open(config):
        assert config.provider == PROVIDER_FREESTYLE
        return await real_open(config, api=_api(fake))

    monkeypatch.setattr(freestyle_sandbox, "open_freestyle_sandbox", _open)
    return e2b_sandbox.E2BSandboxSession()


async def test_session_runs_tools_through_freestyle(freestyle_session, fake):
    session = freestyle_session
    await session.open()
    await session.call_tool("write_file", {"path": "x.txt", "content": "hi"})
    assert fake.files["/home/user/repo/x.txt"] == b"hi"
    assert await session.call_tool("read_file", {"path": "x.txt"}) == "hi"
    out = json.loads(await session.call_tool("run_command", {"cmd": "false"}))
    assert (out["exit_code"], out["stderr"]) == (1, "err")
    assert await session.preview_url(4173) == "https://agency-vm123abc-4173.style.dev"
    await session.close()
    assert "/v5/vms/vm123abc" in fake.deleted


async def test_session_open_failure_degrades_to_unavailable(monkeypatch, freestyle_session):
    async def _boom(config):
        raise RuntimeError("quota")

    monkeypatch.setattr(freestyle_sandbox, "open_freestyle_sandbox", _boom)
    with pytest.raises(e2b_sandbox.MCPUnavailableError, match="freestyle: quota"):
        await freestyle_session.open()


# ── Registry and failover ─────────────────────────────────────────────────


async def test_failover_opens_the_next_provider_and_records_it(monkeypatch):
    from services import sandbox_providers as reg

    opened: list[str] = []

    async def _down(config):
        opened.append(config.provider)
        raise RuntimeError("out of credit")

    async def _up(config):
        opened.append(config.provider)
        return "sandbox"

    monkeypatch.setattr(reg, "_openers", {"e2b": _down, "freestyle": _up})
    cfgs = [_config(), E2BConfig(api_key="k", provider=PROVIDER_E2B)]
    cfgs.reverse()  # e2b first, then freestyle
    sandbox, used = await reg.open_first_available(cfgs)
    assert (sandbox, used.provider, opened) == ("sandbox", PROVIDER_FREESTYLE, ["e2b", "freestyle"])


async def test_all_providers_down_names_each_failure(monkeypatch):
    from services import sandbox_providers as reg

    async def _down(config):
        raise RuntimeError(f"{config.provider} quota")

    monkeypatch.setattr(reg, "_openers", {"freestyle": _down})
    cfgs = [_config(), E2BConfig(api_key="k", provider="custom")]
    with pytest.raises(RuntimeError, match="freestyle quota; custom: no opener registered"):
        await reg.open_first_available(cfgs)


async def test_registered_custom_provider_is_used(monkeypatch):
    from services import sandbox_providers as reg

    monkeypatch.setattr(reg, "_openers", dict(reg._openers))

    async def _mine(config):
        return f"vm-for-{config.api_key}"

    reg.register_sandbox_provider("Mine", _mine)
    sandbox, _ = await reg.open_first_available([E2BConfig(api_key="k1", provider="mine")])
    assert sandbox == "vm-for-k1"


async def test_session_fails_over_from_e2b_to_freestyle(monkeypatch, fake):
    from services import sandbox_providers as reg

    monkeypatch.setenv("E2B_API_KEY", "e2b_out_of_credit")
    monkeypatch.setenv("FREESTYLE_API_KEY", "fs_key")
    monkeypatch.setenv("E2B_ENABLED", "true")
    monkeypatch.setenv("SANDBOX_PROVIDER", "e2b,freestyle")

    async def _e2b_broke(config):
        raise RuntimeError("402 insufficient balance")

    async def _fs(config):
        return await open_freestyle_sandbox(config, api=_api(fake))

    monkeypatch.setattr(reg, "_openers", {"e2b": _e2b_broke, "freestyle": _fs})
    session = e2b_sandbox.E2BSandboxSession()
    await session.open()
    assert session._config.provider == PROVIDER_FREESTYLE
    await session.call_tool("write_file", {"path": "y.txt", "content": "ok"})
    assert fake.files["/home/user/repo/y.txt"] == b"ok"
    await session.close()


def test_naming_only_unkeyed_providers_warns(monkeypatch, caplog):
    from services import e2b_config

    monkeypatch.setattr(e2b_config, "_warned_unkeyed", set())
    monkeypatch.setenv("E2B_API_KEY", "e2b_x")
    monkeypatch.setenv("E2B_ENABLED", "true")
    monkeypatch.setenv("SANDBOX_PROVIDER", "freestyle")
    with caplog.at_level("WARNING", logger="qwen-proxy"):
        assert e2b_enabled() is False
    assert "FREESTYLE_API_KEY" in caplog.text and "sandboxing is off" in caplog.text


async def test_background_poll_survives_a_transient_failure(fake):
    api = _api(fake)
    shim = await open_freestyle_sandbox(_config(), api=api)
    real = fake.handler
    hits = {"n": 0}

    def flaky(req):
        if req.url.path == "/v5/background-requests/bg1" and hits["n"] == 0:
            hits["n"] += 1
            return httpx.Response(503)
        return real(req)

    api._http._transport = httpx.MockTransport(flaky)
    fake.defer_next_exec = True
    res = await shim.commands.run("sleep 30", timeout=120)
    assert (res.stdout, hits["n"]) == ("late", 1)

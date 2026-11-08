"""services/freestyle_sandbox.py — Freestyle VMs behind :class:`E2BSandboxSession`.

Freestyle's Free plan gives 200 vCPU-hours and 400 GiB-hours of memory a month
and never bills: VMs pause when the allowance runs out. There is no Python SDK
for VMs, so this module calls the REST API (``/v5``) the official TypeScript SDK
calls, with ``httpx``.

``E2BSandboxSession`` drives its sandbox through six calls: ``commands.run``,
``files.write``, ``files.read``, ``set_timeout``, ``get_host`` and ``kill``.
:class:`FreestyleSandboxShim` gives a Freestyle VM that same surface, so every
caller of the session works unchanged when ``SANDBOX_PROVIDER=freestyle``.

Differences from E2B that the shim absorbs:

* Exec runs through the guest's ``sh`` with no ``HOME`` and a bare ``PATH``;
  the shim runs every command as root under ``bash -c`` with both set.
  Files written through the file API are root-owned, so commands run as
  root too, or the agent could not edit what it wrote.
* A non-zero exit is a value, not an exception, as the session expects.
* One exec is capped at five minutes; longer timeouts are clamped.
* Long calls answer ``202`` and are polled, as the SDK does.
* Files over 8 MiB go up as a chunked upload session (a repo seed tarball).
* Previews are a TLS rule from a free ``*.style.dev`` name to the VM port.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import shlex
from typing import Any

import httpx

log = logging.getLogger("qwen-proxy")

_BG_AFTER_HEADER = "x-freestyle-background-after-secs"
_BG_ID_HEADER = "x-freestyle-background-request-id"
_BG_POLL_S = 2.0
_BG_MAX_POLLS = 300  # 10 minutes
_BG_TRANSIENT = {408, 429, 500, 502, 503, 504}
_TTL_SECONDS = 6 * 3600  # leak backstop; far above any task attempt
_MAX_EXEC_MS = 300_000
_SINGLE_PUT_MAX = 8 * 1024 * 1024
_CHUNK = 16 * 1024 * 1024
_ENV = {"HOME": "/root", "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"}


class FreestyleApiError(RuntimeError):
    """A non-2xx answer from the Freestyle API. Carries ``status`` and ``code``."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"Freestyle API {status} {code}: {message}"[:500])
        self.status = status
        self.code = code


class FreestyleCommandResult:
    """E2B-shaped command result: ``stdout``, ``stderr``, ``exit_code``."""

    def __init__(self, stdout: str, stderr: str, exit_code: int) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code


class FreestyleApi:
    """Minimal async client for the Freestyle REST API."""

    def __init__(self, api_key: str, base_url: str, http: httpx.AsyncClient | None = None) -> None:
        self._http = http or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(60.0, connect=15.0),
        )

    async def request(self, method: str, path: str, *, json: Any = None,
                      params: dict[str, Any] | None = None, content: bytes | None = None) -> Any:
        """Send one call; poll it to completion when the API defers it (202)."""
        headers = {_BG_AFTER_HEADER: "5"}
        if content is not None:
            headers["Content-Type"] = "application/octet-stream"
        resp = await self._http.request(method, path, json=json, params=params,
                                        content=content, headers=headers)
        if resp.status_code == 202:
            resp = await self._poll(resp)
        return self._finalize(resp)

    async def _poll(self, accepted: httpx.Response) -> httpx.Response:
        body = _safe_json(accepted) or {}
        request_id = accepted.headers.get(_BG_ID_HEADER) or body.get("requestId")
        result_path = body.get("resultUrl") or (f"/v5/background-requests/{request_id}" if request_id else None)
        if not result_path:
            raise FreestyleApiError(202, "BACKGROUND_PROTOCOL_ERROR", "no background request id")
        for _ in range(_BG_MAX_POLLS):
            await asyncio.sleep(_BG_POLL_S)
            try:
                resp = await self._http.get(result_path)
            except httpx.TransportError as exc:  # a dropped poll is retried, as the SDK does
                log.debug("Freestyle poll transport error (retrying): %s", exc)
                continue
            if resp.status_code == 202 or (resp.status_code in _BG_TRANSIENT
                                            and _BG_ID_HEADER not in resp.headers):
                continue
            return resp
        raise FreestyleApiError(408, "BACKGROUND_TIMEOUT", "background request did not finish")

    @staticmethod
    def _finalize(resp: httpx.Response) -> Any:
        if resp.is_success:
            if not resp.content:
                return None
            if resp.headers.get("content-type", "").startswith("application/json"):
                return resp.json()
            return resp.content
        body = _safe_json(resp) or {}
        raise FreestyleApiError(resp.status_code, str(body.get("code") or "UNKNOWN_ERROR"),
                                str(body.get("message") or resp.text[:200]))

    async def close(self) -> None:
        await self._http.aclose()


def _safe_json(resp: httpx.Response) -> dict[str, Any] | None:
    try:
        data = resp.json()
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


class _Commands:
    def __init__(self, api: FreestyleApi, vm_path: str) -> None:
        self._api, self._path = api, vm_path

    async def run(self, cmd: str, timeout: float | None = 60, background: bool = False) -> FreestyleCommandResult:
        """Run *cmd* as root under bash. ``timeout=0`` means the five-minute cap."""
        if background:
            # Detach with output redirected, or exec waits for the process to exit.
            cmd = f"nohup bash -c {shlex.quote(cmd)} >/tmp/bg-$$.log 2>&1 &"
            timeout = 30
        ms = _MAX_EXEC_MS if not timeout else min(int(timeout * 1000), _MAX_EXEC_MS)
        body = {"command": f"bash -c {shlex.quote(cmd)}", "linuxUser": "root",
                "timeoutMs": ms, "env": dict(_ENV)}
        data = await self._api.request("POST", f"{self._path}/exec-await", json=body) or {}
        code = data.get("statusCode")
        # statusCode is null when the timeout killed the command: report 124 like `timeout`.
        return FreestyleCommandResult(data.get("stdout") or "", data.get("stderr") or "",
                                      124 if code is None else int(code))


class _Files:
    def __init__(self, api: FreestyleApi, vm_path: str) -> None:
        self._api, self._path = api, vm_path

    async def write(self, path: str, data: str | bytes) -> None:
        payload = data.encode("utf-8") if isinstance(data, str) else data
        digest = hashlib.sha256(payload).hexdigest()
        if len(payload) <= _SINGLE_PUT_MAX:
            await self._api.request("PUT", f"{self._path}/fs/write", content=payload,
                                    params={"path": path, "sha256": digest})
            return
        await self._write_chunked(path, payload, digest)

    async def _write_chunked(self, path: str, payload: bytes, digest: str) -> None:
        session = await self._api.request("POST", f"{self._path}/fs/uploads",
                                          json={"path": path, "size": len(payload), "sha256": digest})
        upload = f"{self._path}/fs/uploads/{session['uploadId']}"
        try:
            offset = int(session.get("receivedBytes") or 0)
            while offset < len(payload):
                status = await self._api.request("PUT", upload, content=payload[offset:offset + _CHUNK],
                                                 params={"offset": offset})
                offset = int(status["receivedBytes"])
            await self._api.request("POST", f"{upload}/commit")
        except BaseException:
            try:
                await self._api.request("DELETE", upload)
            except Exception:  # noqa: BLE001 - freeing the spool is best-effort
                pass
            raise

    async def read(self, path: str) -> str:
        """Return the file as text; a missing file raises ``FileNotFoundError``."""
        try:
            raw = await self._api.request("GET", f"{self._path}/fs/read", params={"path": path})
        except FreestyleApiError as exc:
            if exc.status == 404:
                raise FileNotFoundError(path) from exc
            raise
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        return "" if raw is None else str(raw)


class FreestyleSandboxShim:
    """A Freestyle VM behind the E2B ``AsyncSandbox`` surface."""

    def __init__(self, api: FreestyleApi, vm_id: str) -> None:
        self._api = api
        self.sandbox_id = vm_id
        self._path = f"/v5/vms/{vm_id}"
        self.commands = _Commands(api, self._path)
        self.files = _Files(api, self._path)

    async def set_timeout(self, timeout_sec: int) -> None:
        """No-op: every tool call execs in the VM, which keeps it from idling."""

    async def get_host(self, port: int) -> str:
        """Route a free ``*.style.dev`` name to *port* and return that host."""
        domain = f"agency-{self.sandbox_id[:16].lower()}-{int(port)}.style.dev"
        await self._api.request("POST", "/v5/tls", json={
            "action": "allow", "domain": domain, "source": {"public": True},
            "destination": {"vmId": self.sandbox_id, "port": int(port)},
        })
        return domain

    async def kill(self) -> None:
        """Delete the VM (its preview rules go with it) and close the client."""
        try:
            await self._api.request("DELETE", self._path)
        finally:
            await self._api.close()


async def open_freestyle_sandbox(config: Any, api: FreestyleApi | None = None) -> FreestyleSandboxShim:
    """Boot a Freestyle VM for *config* (an ``E2BConfig`` with provider ``freestyle``).

    Raises on failure; :meth:`E2BSandboxSession.open` turns that into
    ``MCPUnavailableError`` so callers fall back to local tools.
    """
    api = api or FreestyleApi(config.api_key, config.api_url or "https://api.freestyle.sh")
    body: dict[str, Any] = {
        # Required: a Freestyle VM reaches nothing it is not allowed to.
        "firewall": {"rules": [{"action": "allow", "source": {}, "destination": {"public": True}}]},
        "idleTimeoutSeconds": int(config.timeout_sec),
        # A leaked VM is deleted at this deadline even if something keeps it busy.
        "ttlSeconds": _TTL_SECONDS,
        "autoDeleteSeconds": 0,
    }
    if config.template:
        body["snapshotId"] = config.template
    if config.metadata:
        body["metadata"] = {str(k): str(v) for k, v in config.metadata.items()}
    try:
        data = await api.request("POST", "/v5/vms", json=body)
        shim = FreestyleSandboxShim(api, str(data["id"]))
    except BaseException:
        await api.close()
        raise
    try:
        await shim.commands.run(
            "mkdir -p /home/user/repo && (command -v git >/dev/null || "
            "(apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git))",
            timeout=180,
        )
    except BaseException:
        await shim.kill()
        raise
    return shim

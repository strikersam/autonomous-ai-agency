"""services/instabox_sandbox.py — InstaBox machines behind :class:`E2BSandboxSession`.

InstaBox's Free plan runs one 4 vCPU / 8 GiB Firecracker machine with no usage
cap (30-minute idle pause, 8-hour runs). Only one machine may exist at a time on
Free, paused or stopped ones included, so the shim always deletes its machine on
``kill``; a second concurrent sandbox fails to create and the provider chain
moves on to the next provider.

Uses the official ``instabox-sdk`` (imports as ``instabox``; httpx only). The SDK
is synchronous, so every call runs in a worker thread (``asyncio.to_thread``).

Differences from E2B that the shim absorbs:

* Exec already runs under ``bash -lc``; the shim runs commands as root when the
  guest allows passwordless sudo (the file API writes as root), else as the
  default user.
* A non-zero exit is a value; ``timeout`` is capped at 600 s by the API.
* Previews: ``instabox-port publish`` inside the machine prints the public URL.
"""
from __future__ import annotations

import asyncio
import re
import shlex
from typing import Any

_MAX_EXEC_S = 600
_URL = re.compile(r"https://[^\s'\"<>]+")


def _as_root(cmd: str) -> str:
    """Run *cmd* as root when sudo allows it without a password, else as is."""
    q = shlex.quote(cmd)
    return f"if sudo -n true 2>/dev/null; then sudo -n -E bash -c {q}; else bash -c {q}; fi"


class InstaboxCommandResult:
    """E2B-shaped command result: ``stdout``, ``stderr``, ``exit_code``."""

    def __init__(self, stdout: str, stderr: str, exit_code: int) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code


class _Commands:
    def __init__(self, client: Any, machine_id: str) -> None:
        self._c, self._id = client, machine_id

    async def run(self, cmd: str, timeout: float | None = 60, background: bool = False) -> InstaboxCommandResult:
        """Run *cmd*. ``timeout=0`` means the API's 600-second cap."""
        if background:
            cmd = f"nohup bash -c {shlex.quote(cmd)} >/tmp/bg-$$.log 2>&1 &"
            timeout = 30
        limit = _MAX_EXEC_S if not timeout else min(int(timeout), _MAX_EXEC_S)
        res = await asyncio.to_thread(self._c.machines.exec, self._id, _as_root(cmd), timeout=limit)
        return InstaboxCommandResult(res.stdout or "", res.stderr or "", int(res.exit_code))


class _Files:
    def __init__(self, client: Any, machine_id: str) -> None:
        self._c, self._id = client, machine_id

    async def write(self, path: str, data: str | bytes) -> None:
        payload = data.encode("utf-8") if isinstance(data, str) else data
        await asyncio.to_thread(self._c.files.write, self._id, path, payload)

    async def read(self, path: str) -> str:
        """Return the file as text; a missing file raises ``FileNotFoundError``."""
        from instabox import NotFoundError

        try:
            raw = await asyncio.to_thread(self._c.files.read_bytes, self._id, path)
        except NotFoundError as exc:
            raise FileNotFoundError(path) from exc
        return raw.decode("utf-8", errors="replace")


class InstaboxSandboxShim:
    """An InstaBox machine behind the E2B ``AsyncSandbox`` surface."""

    def __init__(self, client: Any, machine_id: str) -> None:
        self._c = client
        self.sandbox_id = machine_id
        self.commands = _Commands(client, machine_id)
        self.files = _Files(client, machine_id)

    async def set_timeout(self, timeout_sec: int) -> None:
        """No-op: exec counts as activity, which resets the idle pause."""

    async def get_host(self, port: int) -> str:
        """Publish *port* publicly and return its host (scheme stripped, as E2B returns)."""
        res = await self.commands.run(
            f"command -v instabox-port >/dev/null || exit 127; instabox-port publish {int(port)} --public",
            timeout=60,
        )
        match = _URL.search(res.stdout + "\n" + res.stderr)
        if res.exit_code != 0 or not match:
            raise RuntimeError(f"instabox-port publish {port} failed (exit {res.exit_code})")
        return match.group(0).split("://", 1)[1].split("?", 1)[0].rstrip("/")

    async def kill(self) -> None:
        """Delete the machine (Free allows only one), then close the client."""
        try:
            await asyncio.to_thread(self._c.machines.delete, self.sandbox_id)
        finally:
            await asyncio.to_thread(self._c.close)


async def open_instabox_sandbox(config: Any, client: Any = None) -> InstaboxSandboxShim:
    """Create an InstaBox machine for *config* (an ``E2BConfig`` with provider ``instabox``).

    Raises on failure (including ``429 quota_exceeded`` when the one free machine
    is in use); :meth:`E2BSandboxSession.open` turns that into
    ``MCPUnavailableError`` after trying the remaining providers.
    """
    if client is None:
        from instabox import Client

        client = Client(config.api_key, base_url=config.api_url or None)
    kwargs: dict[str, Any] = {
        # Leak backstop: a machine left behind is deleted after 6 hours.
        "delete_after_seconds": 6 * 3600,
        "fail_fast": True,
        "timeout": 300,
    }
    if config.template:
        kwargs["snapshot_id"] = config.template
    if config.metadata:
        kwargs["metadata"] = {str(k): str(v) for k, v in config.metadata.items()}
    try:
        machine = await asyncio.to_thread(client.machines.create, **kwargs)
    except BaseException:
        await asyncio.to_thread(client.close)
        raise
    shim = InstaboxSandboxShim(client, str(machine.id))
    try:
        await shim.commands.run(
            "mkdir -p /home/user/repo && (command -v git >/dev/null || "
            "(apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git))",
            timeout=300,
        )
    except BaseException:
        await shim.kill()
        raise
    return shim

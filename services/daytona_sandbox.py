"""services/daytona_sandbox.py — Daytona sandboxes behind :class:`E2BSandboxSession`.

Daytona is not free past its one-time $200 signup credit, so it sits behind
Freestyle in the default provider chain as a fallback.

Differences from E2B that :class:`DaytonaSandboxShim` absorbs:

* Daytona returns stdout and stderr combined in one ``result`` string and
  never raises on a non-zero exit. The shim returns it as ``stdout`` with the
  real ``exit_code``; callers already check the exit code.
* Daytona runs commands under zsh in its default snapshot; the shim wraps
  every command in ``bash -c`` so the session's bash idioms behave as on E2B.
* ``fs.upload_file`` treats a ``str`` source as a local path, so text is
  always encoded to bytes first.
* The sandbox user is ``daytona``, not ``user``: :func:`open_daytona_sandbox`
  creates ``/home/user/repo`` (with sudo when needed).
* Lifetime is idle-based (auto-stop minutes); ``set_timeout`` refreshes activity.
"""
from __future__ import annotations

import logging
import shlex
from typing import Any

log = logging.getLogger("qwen-proxy")

_WORKDIR_PARENT = "/home/user"


class DaytonaCommandResult:
    """E2B-shaped command result: ``stdout``, ``stderr``, ``exit_code``."""

    def __init__(self, stdout: str, exit_code: int) -> None:
        self.stdout = stdout
        self.stderr = ""
        self.exit_code = exit_code


class _Commands:
    def __init__(self, sandbox: Any) -> None:
        self._sb = sandbox

    async def run(self, cmd: str, timeout: float | None = 60, background: bool = False) -> DaytonaCommandResult:
        """Run *cmd* under bash. ``timeout=0`` means no limit, as on E2B."""
        if background:
            # Detach with output redirected, or exec blocks until the process exits.
            cmd = f"nohup bash -c {shlex.quote(cmd)} >/tmp/bg-$$.log 2>&1 &"
            limit: int | None = 30
        else:
            limit = int(timeout) if timeout else None
        resp = await self._sb.process.exec(f"bash -c {shlex.quote(cmd)}", timeout=limit)
        code = resp.exit_code if resp.exit_code is not None else 0
        return DaytonaCommandResult(resp.result or "", int(code))


class _Files:
    def __init__(self, sandbox: Any) -> None:
        self._sb = sandbox

    async def write(self, path: str, data: str | bytes) -> None:
        payload = data.encode("utf-8") if isinstance(data, str) else data
        await self._sb.fs.upload_file(payload, path)

    async def read(self, path: str) -> str:
        """Return the file as text; a missing file raises ``FileNotFoundError``."""
        try:
            raw = await self._sb.fs.download_file(path)
        except Exception as exc:
            if type(exc).__name__ in {"DaytonaNotFoundError", "DaytonaFileNotFoundError"}:
                raise FileNotFoundError(path) from exc
            raise
        if raw is None:
            raise FileNotFoundError(path)
        return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)


class DaytonaSandboxShim:
    """A Daytona ``AsyncSandbox`` behind the E2B ``AsyncSandbox`` surface."""

    def __init__(self, client: Any, sandbox: Any, idle_minutes: int) -> None:
        self._client = client
        self._sb = sandbox
        self._idle_minutes = idle_minutes
        self.sandbox_id = str(getattr(sandbox, "id", ""))
        self.commands = _Commands(sandbox)
        self.files = _Files(sandbox)

    async def set_timeout(self, timeout_sec: int) -> None:
        """Keepalive: reset the idle clock (Daytona does not count in-sandbox processes)."""
        await self._sb.refresh_activity()

    async def get_host(self, port: int) -> str:
        """Host of a signed public preview URL for *port* (scheme stripped, as E2B returns)."""
        signed = await self._sb.create_signed_preview_url(
            int(port), expires_in_seconds=max(self._idle_minutes, 1) * 60
        )
        return str(signed.url).split("://", 1)[-1].rstrip("/")

    async def kill(self) -> None:
        try:
            await self._sb.delete()
        finally:
            try:
                await self._client.close()
            except Exception as exc:  # noqa: BLE001 - client cleanup is best-effort
                log.debug("Daytona client close failed (best-effort): %s", exc)


async def open_daytona_sandbox(config: Any) -> DaytonaSandboxShim:
    """Create a Daytona sandbox for *config* (an ``E2BConfig`` with provider ``daytona``)."""
    from daytona import AsyncDaytona, CreateSandboxFromSnapshotParams, DaytonaConfig

    client = AsyncDaytona(DaytonaConfig(api_key=config.api_key, api_url=config.api_url or None))
    idle_minutes = max(1, (config.timeout_sec + 59) // 60)
    params = CreateSandboxFromSnapshotParams(
        snapshot=config.template or None,
        language="python",
        labels=dict(config.metadata) if config.metadata else None,
        auto_stop_interval=idle_minutes,
        # A stopped sandbox still bills for disk; delete it once it stops.
        auto_delete_interval=0,
    )
    try:
        sandbox = await client.create(params, timeout=120)
    except BaseException:
        await client.close()
        raise
    shim = DaytonaSandboxShim(client, sandbox, idle_minutes)
    try:
        await shim.commands.run(
            f"mkdir -p {_WORKDIR_PARENT}/repo 2>/dev/null || "
            f"(sudo mkdir -p {_WORKDIR_PARENT}/repo && sudo chown -R $(id -u):$(id -g) {_WORKDIR_PARENT})",
            timeout=30,
        )
    except BaseException:
        await shim.kill()
        raise
    return shim

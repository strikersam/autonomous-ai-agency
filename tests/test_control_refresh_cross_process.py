"""Phase 2 E: a control saved in the dashboard reaches the worker process.

The web process saves an override (``set_overrides``) into the shared settings
store; the worker is a *separate* Python process with its own environment, which
only learns the change through the dispatcher's periodic refresh
(``TaskDispatcher._refresh_controls``, at most every 15 s, idle or not).
"""
from __future__ import annotations

import json
import os
import subprocess  # nosec B404 - runs this repo's own interpreter in list form
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

_WORKER = """
import asyncio, json, os
from packages.config.autonomy_limits import kill_switch_engaged
from tasks.dispatcher import TaskDispatcher
from tasks.store import TaskStore

async def main():
    before = kill_switch_engaged()
    d = TaskDispatcher(workspace_root=".", store=TaskStore())
    await d._refresh_controls()
    after = kill_switch_engaged()
    os.environ.pop("AGENCY_KILL_SWITCH", None)
    await d._refresh_controls()  # within 15 s: not re-read
    throttled = kill_switch_engaged()
    print(json.dumps({"before": before, "after": after, "throttled": throttled}), flush=True)
    import db
    if db._store is not None:
        await db._store.close()  # its connection thread would keep the process alive

asyncio.run(main())
"""


def _worker_env(db_path: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k != "AGENCY_KILL_SWITCH"}
    env.update({"STORAGE_BACKEND": "sqlite", "SQLITE_DB_PATH": db_path, "TESTING": "true",
                "PYTHONPATH": str(ROOT)})
    return env


@pytest.mark.anyio
async def test_a_dashboard_kill_switch_reaches_a_separate_worker(tmp_path, monkeypatch):
    import db
    from packages.config import control_overrides
    from packages.storage.sqlite import SQLiteStore

    db_path = str(tmp_path / "shared.db")
    web_store = SQLiteStore(db_path)
    monkeypatch.setattr(db, "_store", web_store)
    before_env = os.environ.get("AGENCY_KILL_SWITCH")
    import app_settings

    applied_before = dict(control_overrides._applied)
    cache_before = dict(app_settings._cache)
    try:
        await control_overrides.set_overrides({"AGENCY_KILL_SWITCH": "true"}, actor="test")
    finally:
        await web_store.close()
        if before_env is None:
            os.environ.pop("AGENCY_KILL_SWITCH", None)
        else:
            os.environ["AGENCY_KILL_SWITCH"] = before_env
        control_overrides._applied.clear()
        control_overrides._applied.update(applied_before)
        app_settings._cache.clear()
        app_settings._cache.update(cache_before)

    proc = subprocess.run(  # nosec B603 - fixed argv, no shell
        [sys.executable, "-c", _WORKER], cwd=str(ROOT), env=_worker_env(db_path),
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    assert result == {"before": False, "after": True, "throttled": False}


@pytest.mark.anyio
async def test_a_failed_settings_read_does_not_revert_applied_overrides(monkeypatch):
    from packages.config import control_overrides
    from tasks.dispatcher import TaskDispatcher
    from tasks.store import TaskStore

    applied = []

    async def broken():
        raise RuntimeError("settings store unreachable")

    monkeypatch.setattr(control_overrides, "read_overrides", broken)
    monkeypatch.setattr(control_overrides, "apply_overrides", lambda o: applied.append(o))
    d = TaskDispatcher(workspace_root=".", store=TaskStore())
    await d._refresh_controls()  # logs, never raises
    assert applied == []

"""scripts/monitor_colibri.py — CLI for the colibri + GLM-5.2 monitor stack.

Subcommands:

* ``status``       — one-shot snapshot: download status, supervisor state, PID
                     file, model-server liveness.
* ``wait``         — block until the HF download completes + the colibri server
                     answers 200 on ``/v1/models`` with the expected model id.
* ``supervise``    — long-running watchdog. Restart on crash with exponential
                     backoff. Respects manual operator stops (pid file removed).
* ``autostart-install`` — register a Windows Task Scheduler entry that runs
                     ``supervise`` on boot (macros ``<COLIBRI>`` etc.).

Designed to be called from PowerShell wrappers; every output is also
emitted to stdout so operators can tail the log without parsing JSON.

Exit codes:

* 0 — success / healthy
* 1 — probe timed out OR supervisor exceeded max crashes
* 2 — invalid subcommand / argument
* 3 — required dependency missing
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence

# Allow `python scripts/monitor_colibri.py ...` to import monitor_lib from
# the same directory even when PYTHONPATH is unset.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from monitor_lib import (  # noqa: E402
    DownloadStatus,
    SupervisorState,
    await_ready,
    colibri_dir,
    colibri_model_id,
    colibri_url,
    download_log_path,
    download_status,
    is_process_alive,
    model_dir,
    pid_file,
    read_pid_file,
    read_supervisor_state,
    supervisor_state_path,
    supervise_loop,
)

log = logging.getLogger("monitor_colibri")


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _start_colibri_fn() -> None:
    """Subprocess wrapper around ``scripts/start_colibri_server.ps1``.

    Falls back to writing ``.colibri.pid`` ourselves only if the script is
    missing — the start script is the canonical path. Timeout is
    env-overridable via ``COLIBRI_START_TIMEOUT_S`` (default 1800 s, comfortably
    covers a 370 GB cold start where experts stream in from disk).
    """
    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / "scripts" / "start_colibri_server.ps1"
    if not script.exists():
        log.error("start_colibri_server.ps1 missing at %s", script)
        return
    timeout_s = int(os.environ.get("COLIBRI_START_TIMEOUT_S", "1800"))
    # Prefer pwsh (PowerShell Core) when available — python 3.13 / Windows 11
    # boxes may not have the legacy `powershell.exe` shim on PATH. Fall back
    # to plain `powershell` if pwsh is missing.
    shell = "pwsh" if _which("pwsh") else "powershell"
    cmd = [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    log.info("invoking: %s (timeout=%ss)", " ".join(cmd), timeout_s)
    try:
        result = subprocess.run(cmd, check=False, timeout=timeout_s)
        if result.returncode != 0:
            log.warning("start script returned %s", result.returncode)
    except subprocess.TimeoutExpired:
        log.warning("start script timed out after %ss — probe /v1/models to confirm", timeout_s)


def _which(name: str) -> Optional[str]:
    """Return PATH-resolved path for *name* if available, else None."""
    from shutil import which as _shutil_which
    return _shutil_which(name)


def _status_snapshot() -> dict[str, object]:
    pid_path = pid_file()
    pid = read_pid_file(pid_path)
    state = read_supervisor_state(supervisor_state_path())
    dl: DownloadStatus = download_status()
    ready = False
    alive = pid is not None and is_process_alive(pid) if pid else False
    if alive:
        try:
            ready = await_ready(colibri_url(), colibri_model_id(), timeout_s=4)
        except Exception:
            ready = False
    return {
        "download": {
            "complete": dl.complete,
            "on_disk_bytes": dl.on_disk_bytes,
            "incomplete_count": dl.incomplete_count,
            "log_present": dl.log_present,
            "log_mtime_age_seconds": round(dl.log_mtime_age_seconds, 1),
            "detail": dl.detail,
        },
        "colibri_server": {
            "pid_file": str(pid_path),
            "pid": pid,
            "process_alive": alive,
            "ready_for_inference": ready,
            "url": colibri_url(),
            "model_id": colibri_model_id(),
        },
        "supervisor": {
            "state_file": str(supervisor_state_path()),
            "consecutive_crashes": state.consecutive_crashes,
            "total_crashes": state.total_crashes,
            "note": state.note,
        },
    }


def cmd_status(args: argparse.Namespace) -> int:
    snapshot = _status_snapshot()
    print(json.dumps(snapshot, indent=2))
    healthy = bool(snapshot["colibri_server"]["ready_for_inference"]) or (
        args.allow_no_brain and not snapshot["colibri_server"]["pid"]
    )
    return 0 if healthy else 1


def cmd_wait(args: argparse.Namespace) -> int:
    """Block until download completes + colibri answers /v1/models."""
    import time as _t
    # Clamp poll_s so a CLI typo (`--poll-s 0`) cannot degenerate the loop
    # into a tight spin. Operators who want busy polling should pass
    # `--poll-s 1`.
    args.poll_s = max(1, int(args.poll_s))
    log.info("waiting for HF download to complete (log: %s)", download_log_path())
    deadline = args.max_wait_s
    waited_download = 0
    last_phase_log = 0.0
    while True:
        dl = download_status()
        now = _t.time()
        if now - last_phase_log >= 30:
            log.info(
                "download: %.2f GiB on disk, %d .incomplete files, detail=%s",
                dl.on_disk_bytes / (1024 ** 3),
                dl.incomplete_count,
                dl.detail,
            )
            last_phase_log = now
        if dl.complete:
            break
        if waited_download >= deadline:
            log.error("download never completed within %ss", deadline)
            return 1
        _t.sleep(args.poll_s)
        waited_download += args.poll_s

    log.info("download complete. waiting for colibri /v1/models → 200 + %s", colibri_model_id())
    remaining = max(deadline - waited_download, 30)
    last_ready_log = 0.0
    while remaining > 0:
        if _t.time() - last_ready_log >= 30:
            log.info("still waiting for colibri /v1/models (remaining %ss)…", remaining)
            last_ready_log = _t.time()
        ok_one_tick = await_ready(
            colibri_url(), colibri_model_id(), timeout_s=1, poll_s=args.poll_s
        )
        if ok_one_tick:
            break
        remaining -= args.poll_s
    else:
        log.error("colibri did not become ready within %ss", remaining)
        return 1
    log.info("colibri is ready. brain can answer.")
    snap = _status_snapshot()
    print(json.dumps(snap, indent=2))
    return 0


def cmd_supervise(args: argparse.Namespace) -> int:
    log.info(
        "supervise: pid_file=%s state_file=%s max_crashes=%d",
        pid_file(),
        supervisor_state_path(),
        args.max_consecutive_crashes,
    )
    ok = supervise_loop(
        _start_colibri_fn,
        pid_path=pid_file(),
        state_path=supervisor_state_path(),
        max_consecutive_crashes=args.max_consecutive_crashes,
        base_backoff_s=args.base_backoff_s,
        max_backoff_s=args.max_backoff_s,
        tick_s=args.tick_s,
        heartbeat_s=args.heartbeat_s,
    )
    return 0 if ok else 1


_AUTOSTART_TASK_NAME = "ColibriMonitor"
_AUTOSTART_INSTALL_SCRIPT = "scripts/setup_monitor_autostart.ps1"


def cmd_autostart_install(args: argparse.Namespace) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / _AUTOSTART_INSTALL_SCRIPT
    if not script.exists():
        log.error("autostart script missing: %s", script)
        return 3
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    if args.force:
        cmd += ["-Force"]
    log.info("registering Windows scheduled task via %s", script)
    result = subprocess.run(cmd, check=False)
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="monitor_colibri",
        description="CLI for the colibri + GLM-5.2 monitor stack.",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="emit debug-level logs")
    sub = p.add_subparsers(dest="subcommand", required=True)

    p_status = sub.add_parser("status", help="one-shot snapshot of download + server + supervisor state")
    p_status.add_argument(
        "--allow-no-brain",
        action="store_true",
        help="exit 0 even when colibri isn't running (status command only).",
    )
    p_status.set_defaults(func=cmd_status)

    p_wait = sub.add_parser("wait", help="block until download completes AND colibri is ready")
    p_wait.add_argument("--max-wait-s", type=int, default=60 * 60 * 12, help="upper bound (default: 12 h)")
    p_wait.add_argument("--poll-s", type=int, default=10, help="disk + http poll interval")
    p_wait.set_defaults(func=cmd_wait)

    p_sup = sub.add_parser("supervise", help="long-running supervisor (restart-on-crash, manual-stop respected)")
    p_sup.add_argument("--max-consecutive-crashes", type=int, default=5)
    p_sup.add_argument("--base-backoff-s", type=int, default=4)
    p_sup.add_argument("--max-backoff-s", type=int, default=300)
    p_sup.add_argument("--tick-s", type=float, default=3.0)
    p_sup.add_argument("--heartbeat-s", type=float, default=30.0)
    p_sup.set_defaults(func=cmd_supervise)

    p_auto = sub.add_parser("autostart-install", help="register Task Scheduler entry that supervises on boot")
    p_auto.add_argument("--force", action="store_true", help="re-create the task even if it already exists")
    p_auto.set_defaults(func=cmd_autostart_install)

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

"""scripts/monitor_lib.py — shared logic for the colibri + GLM-5.2 monitor stack.

Pure std-lib helper module used by ``scripts/monitor_colibri.py`` and the
``tests/test_monitor_lib.py`` suite. Three responsibilities:

1. **Download completion detection** for the GLM-5.2 weights. Distinguishes
   "in-progress", "stalled mid-fetch", and "fully done" so the watcher can
   resume the ``hf download`` if needed without operator spam.
2. **Readiness probe** — blocks until the local colibri server answers 200 on
   ``/v1/models`` AND the requested model id is listed in the response. Powers
   ``start_colibri_server.ps1`` callers that want a "wait until ready" signal.
3. **Process supervisor** — inspects the colibri ``.pid`` file, distinguishes
   "operator stopped manually" from "process crashed", and drives the
   crash-counter / exponential-backoff state machine.

All file-system paths default to the operator layout under
``D:/hfkld-qg7ky/local-models/`` and accept env overrides for tests +
alternative layouts. No third-party deps. ANSI logging only — no console
prints.

Env overrides (all optional):

==========================  ==================================================
COLIBRI_DIR                  Directory holding the cloned ``coli`` source +
                             state files (``.colibri.pid``, supervisor state).
COLIBRI_MODEL_DIR            Directory holding the GLM-5.2 weights.
COLIBRI_DOWNLOAD_LOG         Path to ``glm-5.2.download.log``.
COLIBRI_URL                  Base URL of the local colibri OAI-compat server.
COLIBRI_MODEL_ID             Required model id once ``/v1/models`` responds.
============================ ==================================================
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("monitor_colibri")


# ── Paths (env-overridable) ──────────────────────────────────────────────────


def colibri_dir() -> Path:
    return Path(os.environ.get("COLIBRI_DIR", r"D:\hfkld-qg7ky\local-models\colibri"))


def model_dir() -> Path:
    return Path(os.environ.get("COLIBRI_MODEL_DIR", r"D:\hfkld-qg7ky\local-models\glm-5.2"))


def download_log_path() -> Path:
    return Path(os.environ.get("COLIBRI_DOWNLOAD_LOG", r"D:\hfkld-qg7ky\local-models\glm-5.2.download.log"))


def pid_file() -> Path:
    return colibri_dir() / ".colibri.pid"


def supervisor_state_path() -> Path:
    return colibri_dir() / ".colibri.supervisor.state"


def monitor_log_path() -> Path:
    return colibri_dir() / ".colibri.monitor.log"


def colibri_url() -> str:
    return os.environ.get("COLIBRI_URL", "http://localhost:8081/v1").rstrip("/")


def colibri_model_id() -> str:
    return os.environ.get("COLIBRI_MODEL_ID", "glm-5.2")


# ── Download completion detection ────────────────────────────────────────────


_INCOMPLETE_GLOB = "*.incomplete"
_DONE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bDone\b\.?"),
    re.compile(r"(?i)\b100\s*%"),
    re.compile(r"(?i)completed in"),
)

STALL_THRESHOLD_S = 15 * 60  # log mtime older than this w/o "done" signal = stalled


@dataclass(frozen=True)
class DownloadStatus:
    """Snapshot of the GLM-5.2 download state at a moment in time."""

    complete: bool
    on_disk_bytes: int
    incomplete_count: int
    log_present: bool
    log_tail_has_done_signal: bool
    log_mtime_age_seconds: float
    detail: str  # "done" | "stalled" | "in-progress" | "no-log" | "missing-dir"


def _read_log_tail(path: Path, chunk_bytes: int = 8192) -> str:
    if not path.exists():
        return ""
    try:
        size = path.stat().st_size
        if size <= chunk_bytes:
            return path.read_text(encoding="utf-8", errors="replace")
        with path.open("rb") as fh:
            fh.seek(size - chunk_bytes)
            return fh.read().decode("utf-8", errors="replace")
    except OSError as exc:
        log.debug("log read failed: %s", exc)
        return ""


def download_status(
    log_path: Optional[Path] = None,
    model_dir_path: Optional[Path] = None,
    now_epoch: Optional[float] = None,
) -> DownloadStatus:
    log_path = log_path or download_log_path()
    model_dir_path = model_dir_path or model_dir()
    now_epoch = now_epoch if now_epoch is not None else time.time()

    if not model_dir_path.exists():
        return DownloadStatus(
            complete=False,
            on_disk_bytes=0,
            incomplete_count=0,
            log_present=log_path.exists(),
            log_tail_has_done_signal=False,
            log_mtime_age_seconds=now_epoch - log_path.stat().st_mtime if log_path.exists() else float("inf"),
            detail="missing-dir",
        )

    on_disk = 0
    incomplete: list[Path] = []
    for f in model_dir_path.rglob("*"):
        try:
            if f.is_file():
                if f.name.endswith(".incomplete"):
                    incomplete.append(f)
                else:
                    on_disk += f.stat().st_size
        except OSError:
            continue

    log_present = log_path.exists()
    if not log_present:
        return DownloadStatus(
            complete=False,
            on_disk_bytes=on_disk,
            incomplete_count=len(incomplete),
            log_present=False,
            log_tail_has_done_signal=False,
            log_mtime_age_seconds=float("inf"),
            detail="no-log",
        )

    log_tail = _read_log_tail(log_path)
    has_done = any(p.search(log_tail) for p in _DONE_PATTERNS)
    log_age = now_epoch - log_path.stat().st_mtime
    stalled = log_age > STALL_THRESHOLD_S and not has_done and not incomplete

    complete = (not incomplete) and has_done and not stalled
    if complete:
        detail = "done"
    elif stalled:
        detail = "stalled"
    else:
        detail = "in-progress"

    return DownloadStatus(
        complete=complete,
        on_disk_bytes=on_disk,
        incomplete_count=len(incomplete),
        log_present=True,
        log_tail_has_done_signal=has_done,
        log_mtime_age_seconds=log_age,
        detail=detail,
    )


# ── Readiness probe ─────────────────────────────────────────────────────────


def _list_models_payload(payload: object) -> list[str]:
    """Normalise an OAI ``/v1/models`` response into a list of model ids."""
    ids: list[str] = []
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict):
                    mid = entry.get("id") or entry.get("model")
                    if mid:
                        ids.append(str(mid))
    elif isinstance(payload, list):
        for entry in payload:
            if isinstance(entry, dict):
                mid = entry.get("id") or entry.get("model")
                if mid:
                    ids.append(str(mid))
            elif isinstance(entry, str):
                ids.append(entry)
    return ids


def await_ready(
    base_url: str,
    model_id: Optional[str],
    timeout_s: int = 600,
    poll_s: int = 2,
    deadline_epoch: Optional[float] = None,
    sleeper: Callable[[float], None] = time.sleep,
    now_fn: Callable[[], float] = time.monotonic,
) -> bool:
    """Block until ``GET <base_url>/models`` returns 200 + (optionally) ``model_id``.

    Returns True when ready, False on timeout. ``sleeper`` + ``now_fn`` are
    injected to keep tests deterministic.
    """
    deadline = deadline_epoch if deadline_epoch is not None else now_fn() + timeout_s
    url = base_url.rstrip("/") + "/models"
    while now_fn() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:  # noqa: S310 — localhost URL
                if resp.status == 200:
                    body = resp.read().decode("utf-8", errors="replace")
                    try:
                        payload = json.loads(body)
                    except json.JSONDecodeError:
                        payload = None
                    if model_id is None:
                        return True
                    if model_id.lower() in (mid.lower() for mid in _list_models_payload(payload)):
                        return True
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            pass
        sleeper(poll_s)
    return False


# ── PID file + liveness ─────────────────────────────────────────────────────


def read_pid_file(path: Path) -> Optional[int]:
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not raw:
        return None
    try:
        return int(raw.split()[0])
    except (ValueError, IndexError):
        return None


def is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if platform.system() == "Windows":
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
            text = (out.stdout or "") + (out.stderr or "")
            if "INFO: No tasks" in text:
                return False
            # Pin both image-name + PID + column boundary to defend against
            # PID reuse: the row must START at line-begin with the CSV row
            # shape '"image.exe","<pid>","'.
            row_pattern = re.compile(
                rf'^"[A-Za-z0-9._-]+","{re.escape(str(pid))}",',
                re.MULTILINE,
            )
            return bool(row_pattern.search(out.stdout))
        except (subprocess.TimeoutExpired, OSError):
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


# ── Supervisor state machine ────────────────────────────────────────────────


@dataclass
class SupervisorState:
    consecutive_crashes: int = 0
    last_crash_at: float = 0.0
    last_heartbeat_at: float = 0.0
    note: str = ""
    total_crashes: int = 0
    started_at: float = 0.0


def read_supervisor_state(path: Path) -> SupervisorState:
    if not path.exists():
        return SupervisorState()
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return SupervisorState()
    known = {f.name for f in fields(SupervisorState)}
    filtered = {k: v for k, v in payload.items() if k in known}
    try:
        return SupervisorState(**filtered)
    except TypeError:
        return SupervisorState()


def write_supervisor_state(path: Path, state: SupervisorState) -> None:
    """Atomic write — temp file + rename so a power loss mid-write can't
    corrupt the supervisor state file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")
    tmp.replace(path)


# Tuple of (action, state). Action ∈ {"noop", "heartbeat", "crash-restart",
# "manual-stop", "adopted"}.
SupervisorTick = tuple[str, SupervisorState]


def supervise_tick(
    pid_path: Path,
    state: SupervisorState,
    now_epoch: Optional[float] = None,
) -> SupervisorTick:
    """One-shot inspect of ``pid_path``. Returns (action, new_state).

    - **manual-stop**: pid file absent → operator ran stop script. State intact.
    - **noop**: pid file absent + we already acknowledged it.
    - **adopted**: pid file present + process alive AND state had a non-zero
      crash counter (operator re-started while supervisor was sleeping).
    - **heartbeat**: pid file present + process alive, normal case.
    - **crash-restart**: pid file present + process dead → bump counter.
    """
    now = now_epoch if now_epoch is not None else time.time()
    pid = read_pid_file(pid_path)
    if pid is None:
        return ("manual-stop", state)
    alive = is_process_alive(pid)
    if not alive:
        state.consecutive_crashes += 1
        state.total_crashes += 1
        state.last_crash_at = now
        return ("crash-restart", state)
    if state.consecutive_crashes:
        return ("adopted", SupervisorState())  # fresh start succeeded; reset
    return ("heartbeat", state)


def supervise_loop(
    start_fn: Callable[[], None],
    pid_path: Path = ...,
    state_path: Path = ...,
    max_consecutive_crashes: int = 5,
    base_backoff_s: int = 4,
    max_backoff_s: int = 300,
    tick_s: float = 3.0,
    heartbeat_s: float = 30.0,
) -> bool:
    """Block forever, supervising the colibri server.

    Returns False only after ``max_consecutive_crashes`` exceeds threshold
    (intentionally raises the bar for the operator's attention).
    """
    state = read_supervisor_state(state_path)
    last_heartbeat = 0.0
    while True:
        action, state = supervise_tick(pid_path, state)
        if action == "crash-restart":
            write_supervisor_state(state_path, state)
            if state.consecutive_crashes > max_consecutive_crashes:
                _heartbeat_to_file(
                    f"GIVING UP: {state.total_crashes} total crashes, "
                    f"{state.consecutive_crashes} consecutive (>max={max_consecutive_crashes})."
                )
                return False
            backoff = min(base_backoff_s * (2 ** (state.consecutive_crashes - 1)), max_backoff_s)
            _heartbeat_to_file(
                f"colibri crashed (consecutive={state.consecutive_crashes}, total={state.total_crashes}). "
                f"Restarting after {backoff}s backoff."
            )
            time.sleep(backoff)
            _heartbeat_to_file("supervisor: invoking start_fn()")
            start_fn()
            # Do NOT reset the counter here. The next supervise_tick will
            # return ("adopted", SupervisorState()) once a heartbeat confirms
            # health — resetting immediately would let a permanently-broken
            # coli restart forever (counter stays at 1 on every restart, the
            # `> max_consecutive_crashes` guard never fires).
        elif action == "adopted":
            _heartbeat_to_file("supervisor: external start detected — adopting healthy colibri.")
            write_supervisor_state(state_path, state)
        elif action == "manual-stop":
            if state.consecutive_crashes or state.note:
                _heartbeat_to_file("supervisor: operator stopped colibri manually — idle.")
                state = SupervisorState()
                write_supervisor_state(state_path, state)
            time.sleep(tick_s)
            continue
        elif action == "heartbeat":
            now = time.time()
            if now - last_heartbeat > heartbeat_s:
                _heartbeat_to_file("colibri healthy.")
                last_heartbeat = now
            time.sleep(tick_s)
        else:
            time.sleep(tick_s)


def _heartbeat_to_file(message: str) -> None:
    """Append a single timestamped line to the monitor log + emit via logger."""
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}\n"
    try:
        monitor_log_path().parent.mkdir(parents=True, exist_ok=True)
        with monitor_log_path().open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass
    log.info(message)

#!/usr/bin/env python3
"""scripts/local_controller.py — cross-machine toggle daemon for the local GLM 5.2 brain.

Architecture (see ``docs/plans/db-brain-switcher.md`` + thinker verdict):

  1. Operator pushes the toggle on the Cloudflare-deployed admin Providers page
     (``POST /api/local-brain/toggle`` via Cloudflare Worker → Render backend).
  2. The cloud writes ``desired_state=on`` into the shared brain-config mirror db.
  3. THIS script polls the cloud's ``GET /api/local-brain/state`` every
     ``--interval`` seconds (or one-shot via ``--once``).
  4. When desired_state flips to on:
       - check that the local binary exists (.env ``LOCAL_BRAIN_BIN`` OR default
         ``D:\\hfkld-qg7ky\\local-models\\llama.cpp\\build\\bin\\Release\\llama-server.exe``)
       - check that the model file exists (.env ``LOCAL_BRAIN_MODEL_PATH`` OR default
         ``D:\\hfkld-qg7ky\\local-models\\GLM-5.2\\glm-5.2-instruct-Q4_K_M.gguf``)
       - run ``scripts\\start_local_glm_server.ps1`` (writes PID to
         ``logs\\local_brain.pid``)
       - poll ``http://localhost:8072/v1/models`` (default port) until glm-5.2
         shows up OR ``--start-timeout`` elapses.
  5. When desired_state flips to off or the lease expires:
       - run ``scripts\\stop_local_glm_server.ps1`` to kill the PID tree
       - on Windows this must use ``taskkill /T /F`` to free VRAM (otherwise
         the next llama-server start fails to bind 8072).
  6. POST every action outcome back to the cloud's
     ``POST /api/local-brain/heartbeat`` so the admin UI can show:
       - "starting…" → "listening; glm-5.2 loaded" → "leasing to machine <UUID>"
       - or "binary missing: install llama.cpp" / "model missing: hf download
         ``openai/glm-5.2`` first" / "VRAM exhausted" / etc.

Security:
  - The daemon sends ``X-Service-Token: <LOCAL_BRAIN_TOKEN>`` (or the same
    SERVICE_TOKEN the cloud uses for brain PATCH). The router requires this
    on all 3 endpoints; without it the daemon's POST returns 503/401.
  - The daemon does NOT need inbound network — everything is outbound HTTPS.
  - Multiple machines can run this daemon; the cloud keeps a "lease" on the
    first successful heartbeat. Subsequent machines either act as standby
    (when desired_state flips to off later the cloud triggers failover) or
    stay idle until the lease expires.

Modes:
  --once      Run a single tick: read state, sync local, heartbeat. Exit 0.
  --daemon    Foreground loop (default). Ctrl-C to stop.
  --diagnose  One-shot health check (binary? model? lease?). Exit 0/1.

Env vars:
  AGENCY_URL              base URL of the cloud agency (default: https://local-llm-server.strikersam.workers.dev)
                          Falls back to AGENCY_BASE_URL or BACKEND_URL.
  LOCAL_BRAIN_TOKEN       SERVICE_TOKEN value (required — without it the
                          daemon cannot post heartbeats)
  LOCAL_BRAIN_HTTP_PORT   port llama-server listens on (default: 8072)
  LOCAL_BRAIN_HTTP_PORTS  comma-separated port list to PROBE that may serve
                          a local brain (default: "8072,8081"). Order is
                          probe-order; the first port whose /v1/models
                          responds with a model id matching
                          LOCAL_BRAIN_MODEL_ID wins. Used so the heartbeat
                          flips green as soon as ANY local brain
                          (llama-server.exe on 8072, colibri on 8081,
                          ollama on 11434, custom on 9000, etc.) is up.
  LOCAL_BRAIN_HOST        bind addr (default: 127.0.0.1 — never expose publicly)
  LOCAL_BRAIN_BIN         override path to llama-server.exe
  LOCAL_BRAIN_MODEL_PATH  override path to glm-5.2 model GGUF
  LOCAL_BRAIN_CTX         context length (default: 8192)
  LOCAL_BRAIN_THREADS     CPU threads (default: 8)
  LOCAL_BRAIN_GPU_LAYERS  GPU offload layers (default: 99)
  LOCAL_BRAIN_INTERVAL    poll interval seconds (default: 30)
  LOCAL_BRAIN_START_TIMEOUT  max seconds to wait for /v1/models (default: 240)
  LOCAL_BRAIN_MODEL_ID    model id to register with llama-server (default: glm-5.2)
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

DEFAULT_HTTP_PORT = 8072
DEFAULT_INTERVAL = 30
DEFAULT_START_TIMEOUT = 2400
DEFAULT_HTTP_PORTS: tuple[int, ...] = (8072, 8081)
DEFAULT_CTX = 8192
DEFAULT_THREADS = 8
DEFAULT_GPU_LAYERS = 99
DEFAULT_MODEL_ID = "glm-5.2"

DEFAULT_BIN_WINDOWS = (
    "D:\\hfkld-qg7ky\\local-models\\llama.cpp\\build\\bin\\Release\\llama-server.exe"
)
DEFAULT_MODEL_WINDOWS = (
    "D:\\hfkld-qg7ky\\local-models\\GLM-5.2\\glm-5.2-instruct-Q4_K_M.gguf"
)
DEFAULT_START_SCRIPT_WINDOWS = (
    "C:\\Users\\swami\\qwen-server\\scripts\\start_local_glm_server.ps1"
)
DEFAULT_STOP_SCRIPT_WINDOWS = (
    "C:\\Users\\swami\\qwen-server\\scripts\\stop_local_glm_server.ps1"
)
DEFAULT_PID_FILE_WINDOWS = "C:\\Users\\swami\\qwen-server\\logs\\local_brain.pid"
DEFAULT_LOG_FILE_WINDOWS = "C:\\Users\\swami\\qwen-server\\logs\\local_brain.log"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off", ""):
        return default
    return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _parse_http_ports(cli_override: int | None) -> list[int]:
    """Return ordered, de-duplicated list of ports to probe for a local brain.

    Resolution order (FIFO probe priority):
      1. ``LOCAL_BRAIN_HTTP_PORT`` (single-port legacy env var)  -> always first
      2. ``LOCAL_BRAIN_HTTP_PORTS`` (comma-separated multi-port env var)
      3. ``DEFAULT_HTTP_PORTS`` (8072, 8081)

    The CLI ``--http-port`` overrides #1 if supplied. All other entries are
    prepended in discovery order; duplicates are dropped.
    """
    out: list[int] = []
    primary_env = os.environ.get("LOCAL_BRAIN_HTTP_PORT", "").strip()
    if primary_env.isdigit():
        out.append(int(primary_env))
    multi_env = os.environ.get("LOCAL_BRAIN_HTTP_PORTS", "").strip()
    if multi_env:
        for chunk in multi_env.split(","):
            chunk = chunk.strip()
            if chunk.isdigit():
                p = int(chunk)
                if p not in out:
                    out.append(p)
    if cli_override and isinstance(cli_override, int) and cli_override not in out:
        out.insert(0, cli_override)
    if not out:
        out.extend(DEFAULT_HTTP_PORTS)
    return out


def _choose_local_brain(
    ports: list[int],
) -> tuple[int | None, str, list[dict], bool, str]:
    """Probe ``ports`` in order; return the first responding listener.

    Returns ``(chosen_port, port_state, models, has_glm52, err)``. When no
    port responds, ``chosen_port`` is ``None`` and the rest mirrors a dead
    probe so callers don't have to special-case the empty-list case.
    """
    for port in ports:
        base = f"http://127.0.0.1:{port}"
        port_state, models, has_glm52, err = _probe_v1_models(base)
        if port_state == "listening":
            return port, port_state, models, has_glm52, err
    return None, "dead", [], False, ""


def _default_agency_url() -> str:
    for key in ("AGENCY_URL", "AGENCY_BASE_URL", "BACKEND_URL"):
        v = os.environ.get(key, "").strip().rstrip("/")
        if v:
            return v
    return "https://local-llm-server.strikersam.workers.dev"


def _default_machine_id_file() -> str:
    """The zero-config default machine-id path.

    The Windows literal below is the operator's own daily-driver path for
    this daemon (see the module docstring: it runs on their Windows machine
    to control a local Windows-hosted GLM server) — a real default, not a
    placeholder. But it's a Windows path, and pathlib treats backslashes as
    literal characters (not separators) on POSIX, so on Linux/macOS this
    string resolves to one garbage filename full of backslashes and colons
    dropped straight into the current working directory instead of a real
    nested path — confirmed: this created exactly that stray file the one
    time this script ran in a non-Windows session without
    LOCAL_BRAIN_MACHINE_ID_FILE set. Machine-id generation itself is a
    cross-platform concern (any environment probing this daemon's cloud
    lease state needs a stable id), so only this path gets a real
    cross-platform fallback — the operator's other Windows-only daemon
    paths (binary, model, start/stop scripts) are left as-is.
    """
    if sys.platform == "win32":
        return "C:\\Users\\swami\\qwen-server\\logs\\local_brain.machine_id"
    return str(Path.home() / ".local-brain" / "local_brain.machine_id")


def _machine_id_path() -> Path:
    """A persistent file holding the local machine UUID (generated on first run).

    Pinning the UUID means the cloud's lease doesn't bounce every restart.
    Lives next to the daemon's logs so it's discoverable to operators.
    """
    raw = os.environ.get(
        "LOCAL_BRAIN_MACHINE_ID_FILE", _default_machine_id_file()
    ).strip()
    p = Path(raw)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _get_or_create_machine_id() -> str:
    p = _machine_id_path()
    if p.is_file():
        try:
            existing = p.read_text(encoding="utf-8").strip()
            if existing:
                return existing[:80]
        except Exception:
            pass
    new_id = f"{socket.gethostname()}-{uuid.uuid4().hex[:12]}"
    try:
        p.write_text(new_id, encoding="utf-8")
    except Exception:
        pass
    return new_id[:80]


def _log_path() -> Path:
    raw = os.environ.get("LOCAL_BRAIN_LOG_FILE", DEFAULT_LOG_FILE_WINDOWS).strip()
    p = Path(raw)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _log(line: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{stamp}] {line}"
    try:
        with _log_path().open("a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except Exception:
        pass
    print(msg, flush=True)


def _http_json(
    url: str, *, method: str = "GET", body: dict | None = None,
    headers: dict[str, str] | None = None, timeout: float = 15.0,
):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    request_headers = {"Accept": "application/json", "User-Agent": "local-controller/1.0"}
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(url, data=data, method=method, headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, raw
    except urllib.error.HTTPError as exc:
        return exc.code, (exc.read().decode("utf-8", errors="replace") if exc.fp else "")
    except urllib.error.URLError as exc:
        return 0, f"url-error: {exc.reason}"
    except (TimeoutError, socket.timeout):
        return 0, "timeout"
    except Exception as exc:
        return 0, f"error: {exc.__class__.__name__}: {exc}"


def _read_pid_file() -> int | None:
    raw = os.environ.get("LOCAL_BRAIN_PID_FILE", DEFAULT_PID_FILE_WINDOWS).strip()
    p = Path(raw)
    if not p.is_file():
        return None
    try:
        text = p.read_text(encoding="utf-8").strip()
        if text.isdigit():
            return int(text)
    except Exception:
        return None
    return None


def _pid_alive(pid: int) -> bool:
    """Cross-platform liveness check that survives stale pidfiles."""
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            # ``tasklist`` is the canonical Windows liveness signal.
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5.0,
            ).stdout
            return str(pid) in out
        os.kill(pid, 0)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _probe_v1_models(base_url: str, *, timeout: float = 4.0) -> tuple[str, list[dict], bool, str]:
    """Probe the local server's /v1/models. Returns (port_state, models, has_glm52, err)."""
    url = f"{base_url.rstrip('/')}/v1/models"
    status, raw = _http_json(url, timeout=timeout)
    if status != 200:
        if status in (0,):
            return "dead", [], False, raw or "unreachable"
        return "dead", [], False, f"http {status}"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return "listening", [], False, "non-json response"
    models = payload.get("data") or payload.get("models") or []
    if not isinstance(models, list):
        models = []
    has_glm52 = False
    for m in models:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("id") or m.get("name") or "").strip().lower()
        if mid in ("glm-5.2", DEFAULT_MODEL_ID, "glm-5.2-instruct"):
            has_glm52 = True
            break
    return "listening", models, has_glm52, ""


def _bin_exists(bin_path: str) -> str | None:
    """Return None if binary exists, error message otherwise."""
    p = Path(bin_path)
    if not p.is_file():
        return f"binary missing at {bin_path}"
    return None


def _model_exists(model_path: str) -> str | None:
    p = Path(model_path)
    if not p.is_file():
        return f"model file missing at {model_path} (download glm-5.2 Q4_K_M to that path)"
    return None


def _run_powershell(script: str, args: list[str], *, timeout: float = 30.0) -> tuple[int, str]:
    """Run a PowerShell script with arguments. Returns (rc, combined_output)."""
    cmd = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", script, *args,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, output[:8192]
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"
    except FileNotFoundError:
        return 127, "powershell.exe not on PATH"
    except Exception as exc:
        return 1, f"{exc.__class__.__name__}: {exc}"


def _start_local_server() -> tuple[bool, str]:
    """Launch the local llama-server (via PowerShell shim). Returns (ok, msg)."""
    bin_path = os.environ.get("LOCAL_BRAIN_BIN", DEFAULT_BIN_WINDOWS).strip()
    model_path = os.environ.get("LOCAL_BRAIN_MODEL_PATH", DEFAULT_MODEL_WINDOWS).strip()
    start_script = os.environ.get(
        "LOCAL_BRAIN_START_SCRIPT", DEFAULT_START_SCRIPT_WINDOWS
    ).strip()
    port = _env_int("LOCAL_BRAIN_HTTP_PORT", DEFAULT_HTTP_PORT)
    ctx = _env_int("LOCAL_BRAIN_CTX", DEFAULT_CTX)
    threads = _env_int("LOCAL_BRAIN_THREADS", DEFAULT_THREADS)
    gpu_layers = _env_int("LOCAL_BRAIN_GPU_LAYERS", DEFAULT_GPU_LAYERS)
    model_id = os.environ.get("LOCAL_BRAIN_MODEL_ID", DEFAULT_MODEL_ID).strip()

    if not Path(start_script).is_file():
        return False, f"start script missing: {start_script}"
    if (err := _bin_exists(bin_path)):
        return False, err
    if (err := _model_exists(model_path)):
        return False, err

    _log(f"start_local_server: invoking {start_script} on port {port} with model_id={model_id}")
    rc, output = _run_powershell(
        start_script,
        [
            "-BinaryPath", bin_path,
            "-ModelPath", model_path,
            "-Port", str(port),
            "-ModelId", model_id,
            "-ContextSize", str(ctx),
            "-Threads", str(threads),
            "-GpuLayers", str(gpu_layers),
        ],
        timeout=45.0,
    )
    if rc != 0:
        return False, f"start script exited {rc}: {output[:500]}"
    # PowerShell may exit 0 even when the underlying llama-server failed to
    # bind. Confirm pidfile got written.
    pid = _read_pid_file()
    if not pid or not _pid_alive(pid):
        return False, f"start script exited 0 but pidfile {DEFAULT_PID_FILE_WINDOWS} is missing or stale"
    return True, f"started pid={pid} port={port}"


def _stop_local_server() -> tuple[bool, str]:
    stop_script = os.environ.get(
        "LOCAL_BRAIN_STOP_SCRIPT", DEFAULT_STOP_SCRIPT_WINDOWS
    ).strip()
    if not Path(stop_script).is_file():
        # Fallback: kill the PID directly so the operator can still flip the toggle off.
        pid = _read_pid_file()
        if pid and _pid_alive(pid):
            try:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], timeout=15.0)
                else:
                    os.kill(pid, 9)
            except Exception as exc:
                return False, f"taskkill failed: {exc}"
        return True, "stopped via PID fallback (stop script absent)"
    rc, output = _run_powershell(stop_script, [], timeout=30.0)
    if rc != 0:
        return False, f"stop script exited {rc}: {output[:500]}"
    return True, "stopped"


# Reserved for a future adaptive-timeout restart variant; delete if no caller
# ships within 30 days.
def _wait_for_listening(base_url: str, *, timeout: float) -> tuple[str, list[dict], bool, str]:
    deadline = time.monotonic() + timeout
    last_err = ""
    while time.monotonic() < deadline:
        port_state, models, has_glm52, err = _probe_v1_models(base_url)
        if port_state == "listening":
            return port_state, models, has_glm52, err
        last_err = err
        time.sleep(2.0)
    return "dead", [], False, last_err or "timeout"


def run_once(
    machine_id: str,
    agency_url: str,
    token: str,
    http_port: int,
    start_timeout: int,
) -> int:
    """Run a single tick. Returns 0 on success (heartbeat sent), else 1/2.

    Exit codes:
      0  executed a tick and posted a heartbeat
      1  generic failure
      2  network/auth error posting heartbeat
    """
    # 1. Read desired state from the cloud first so the local probe sequence
    # below matches the historical (state, probe, heartbeat) urlopen contract.
    headers = {"X-Service-Token": token} if token else {}
    url = f"{agency_url.rstrip('/')}/api/local-brain/state"
    status, raw = _http_json(url, headers=headers, timeout=15.0)
    if status != 200:
        err = f"GET {url} -> {status}: {raw[:200]}"
        _log(f"poll failed: {err}")
        return 2
    try:
        cloud_state = json.loads(raw)
    except json.JSONDecodeError:
        _log("poll failed: cloud returned non-json")
        return 2
    desired = (cloud_state.get("desired") or {}).get("state", "off")
    _log(f"desired={desired} agency={agency_url} machine={machine_id}")

    # 2. Probe candidate local-brain ports in order; first listener wins.
    ports = _parse_http_ports(http_port)
    _, port_state, models, has_glm52, err = _choose_local_brain(ports)
    currently_running = port_state == "listening"

    # Reviewer fix: split cold start from readiness probe so the loop never
    # blocks for >2s regardless of how slow llama-server is. We POST a
    # status=starting heartbeat immediately after launching (so the admin UI
    # sees liveness), then probe /v1/models in a loop and keep posting
    # status=ok the moment glm-5.2 is reported. Any error from the start
    # script is captured into the heartbeat so the operator sees it on the
    # toggle card immediately.
    if desired == "on" and not currently_running:
        ok, msg = _start_local_server()
        if not ok:
            _log(f"start_local_server: FAIL ({msg})")
            port_state, models, has_glm52 = "dead", [], False
            err = msg
        else:
            _log(f"start_local_server: OK ({msg})")
            # Lock the readiness loop to http_port: we just launched
            # llama-server.exe there, so swapping ports mid-load (via the
            # multi-port _choose_local_brain) would only ping-pong between
            # :8081 (colibri slow) and :8072 (engine we just started) for
            # ~1200 unnecessary probes during a 40-min cold-load.
            deadline = time.monotonic() + float(start_timeout)
            while time.monotonic() < deadline:
                port_state, models, has_glm52, err = _probe_v1_models(
                    f"http://127.0.0.1:{http_port}"
                )
                if port_state == "listening" and has_glm52:
                    _log(f"ready: glm-5.2 present in /v1_models ({len(models)} model(s))")
                    break
                # Post a starting heartbeat immediately so the UI sees liveness
                # during the cold start, NOT a 4-minute silence.
                hb_url = f"{agency_url.rstrip('/')}/api/local-brain/heartbeat"
                _http_json(
                    hb_url,
                    method="POST",
                    body={
                        "machine_id": machine_id,
                        "status": "starting",
                        "port_state": port_state,
                        "v1_models": models,
                        "models_has_glm52": has_glm52,
                        "error": err or "",
                    },
                    headers={"X-Service-Token": token} if token else {},
                    timeout=10.0,
                )
                time.sleep(2.0)
            else:
                # Loop exhausted start_timeout without reaching "ready"
                _log(f"timed out waiting for glm-5.2 after {start_timeout}s")
                port_state, models, has_glm52 = port_state or "dead", models, has_glm52
    elif desired == "off" and currently_running:
        ok, msg = _stop_local_server()
        _log(f"stop_local_server: {'OK' if ok else 'FAIL'} ({msg})")
        if ok:
            port_state, models, has_glm52 = "dead", [], False
            err = ""
        else:
            err = msg
    elif desired == "on" and currently_running:
        # Already up — re-probe (the model may have died without killing the process)
        if not has_glm52:
            _log("still listening but glm-5.2 not in /v1/models; restarting")
            _stop_local_server()
            ok, msg = _start_local_server()
            if ok:
                port_state, models, has_glm52, err = _probe_v1_models(
                    f"http://127.0.0.1:{http_port}"
                )
                if not (port_state == "listening" and has_glm52):
                    err = err or "restart pending — check next heartbeat"
            else:
                port_state, models, has_glm52 = "dead", [], False
                err = msg

    # 3. Compute status string sent to cloud.
    if port_state != "listening":
        status_str = "error"
    elif desired == "off":
        status_str = "ok"
    elif not has_glm52:
        status_str = "starting"
    else:
        status_str = "ok"

    # 4. POST heartheat to cloud.
    hb_url = f"{agency_url.rstrip('/')}/api/local-brain/heartbeat"
    hb_body = {
        "machine_id": machine_id,
        "status": status_str,
        "port_state": port_state,
        "v1_models": models,
        "models_has_glm52": has_glm52,
        "error": err or "",
    }
    hb_status, hb_raw = _http_json(
        hb_url, method="POST", body=hb_body, headers=headers, timeout=15.0,
    )
    if hb_status != 200:
        _log(f"heartbeat FAILED: HTTP {hb_status}: {hb_raw[:200]}")
        return 2
    _log(
        f"heartbeat OK status={status_str} port={port_state} "
        f"models={len(models)} has_glm52={has_glm52}"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local GLM-5.2 controller daemon (pulls from cloud agency toggle).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--once", action="store_true", help="Single tick and exit (always 0).")
    group.add_argument("--daemon", action="store_true", help="Foreground loop. Default.")
    group.add_argument("--diagnose", action="store_true", help="One-shot health check (binary? model? lease?).")
    parser.add_argument("--interval", type=int, default=None, help="Tick interval seconds (env override).")
    parser.add_argument("--start-timeout", type=int, default=None, help="Max seconds waiting for llama-server (env override).")
    parser.add_argument("--agency-url", default=None, help="Override AGENCY_URL.")
    parser.add_argument("--http-port", type=int, default=None, help="Local llama-server port (env override).")
    parser.add_argument("--machine-id", default=None, help="Override machine_id (otherwise auto-generated).")
    args = parser.parse_args()

    machine_id = (args.machine_id or _get_or_create_machine_id())[:80]
    agency_url = (args.agency_url or _default_agency_url()).rstrip("/")
    token = os.environ.get("LOCAL_BRAIN_TOKEN") or os.environ.get("SERVICE_TOKEN", "").strip()
    http_port = args.http_port or _env_int("LOCAL_BRAIN_HTTP_PORT", DEFAULT_HTTP_PORT)
    interval = args.interval or _env_int("LOCAL_BRAIN_INTERVAL", DEFAULT_INTERVAL)
    start_timeout = args.start_timeout or _env_int("LOCAL_BRAIN_START_TIMEOUT", DEFAULT_START_TIMEOUT)

    if args.diagnose:
        # Health snapshot (does not post to the cloud).
        port_state, models, has_glm52, err = _probe_v1_models(f"http://127.0.0.1:{http_port}")
        bin_err = _bin_exists(os.environ.get("LOCAL_BRAIN_BIN", DEFAULT_BIN_WINDOWS))
        mod_err = _model_exists(os.environ.get("LOCAL_BRAIN_MODEL_PATH", DEFAULT_MODEL_WINDOWS))
        out = {
            "machine_id": machine_id,
            "agency_url": agency_url,
            "http_port": http_port,
            "binary": os.environ.get("LOCAL_BRAIN_BIN", DEFAULT_BIN_WINDOWS),
            "binary_ok": bin_err is None,
            "binary_err": bin_err,
            "model": os.environ.get("LOCAL_BRAIN_MODEL_PATH", DEFAULT_MODEL_WINDOWS),
            "model_ok": mod_err is None,
            "model_err": mod_err,
            "port_state": port_state,
            "models_count": len(models),
            "has_glm52": has_glm52,
            "error": err,
        }
        print(json.dumps(out, indent=2))
        sys.exit(0 if (bin_err is None and mod_err is None) else 1)

    if args.once:
        rc = run_once(machine_id, agency_url, token, http_port, start_timeout)
        sys.exit(rc)

    # daemon mode (default)
    _log(
        f"daemon started: machine={machine_id} agency={agency_url} "
        f"http_port={http_port} interval={interval}s token={'set' if token else 'MISSING'}"
    )
    if not token:
        _log("FATAL: LOCAL_BRAIN_TOKEN / SERVICE_TOKEN unset — heartbeats will be rejected. Exiting.")
        sys.exit(2)

    try:
        while True:
            try:
                run_once(machine_id, agency_url, token, http_port, start_timeout)
            except Exception as exc:
                _log(f"tick raised exception (non-fatal): {exc.__class__.__name__}: {exc}")
            time.sleep(max(interval, 5))
    except KeyboardInterrupt:
        _log("daemon stopped (Ctrl+C)")
        sys.exit(0)


if __name__ == "__main__":
    main()

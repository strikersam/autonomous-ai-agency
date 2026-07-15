#!/usr/bin/env python3
"""Windows-friendly Render + Ollama keepalive cron.

Render free-tier web services sleep after ~15 min without inbound HTTP. The repo
already has two keepalive mechanisms:
  - backend/server.py:_keepalive_self_ping (in-process, every 10 min, gated on
    TELEGRAM_BOT_TOKEN being set).
  - .github/workflows/keepalive.yml (GitHub Actions cron, every 5 min).

This script is a third, **local** keepalive that runs on the operator's
Windows box (the same box that runs Ollama + the ngrok tunnel). It adds:
  1. Belt-and-suspenders Render /api/health ping from the Windows box, so
     even if both existing mechanisms fail the service stays awake.
  2. Periodic Ollama model warm-up with ``keep_alive=-1``. If Ollama restarts
     and models unload, this script reloads them so the agency's first
     inference call is fast instead of a 2-3 min cold-load.

Modes:
    --diagnose   One-shot check of Render + Ollama health + warm-up. Exit 0/1.
    --once       Run a single tick and exit (always 0). Use from cron / Task Scheduler.
    --daemon     Foreground loop. Default when neither of the above is passed.

Environment:
    KEEPALIVE_URL           Override Render URL (default: https://local-llm-server.onrender.com)
    OLLAMA_BASE             Override local Ollama URL (default: http://localhost:11434)
    KEEPALIVE_INTERVAL_SEC  Tick interval for --daemon (default: 600 = 10 min)
    KEEPALIVE_LOG           Log file path (default: logs/keepalive.log)
    KEEPALIVE_MODELS        Comma-separated models to warm each tick (default: qwen3-coder:30b,deepseek-r1:32b)
    KEEPALIVE_WARM          "1"/"true" to also warm models (default: "1"); "0" to skip
    KEEPALIVE_HEALTH_ONLY   "1"/"true" to skip Ollama entirely (default: "0")
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx


MAX_LOG_BYTES = 1_048_576  # 1 MiB — rotate the keepalive.log at this size


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


def _default_render_url() -> str:
    return os.environ.get(
        "KEEPALIVE_URL", "https://local-llm-server.onrender.com"
    ).rstrip("/")


def _default_ollama_base() -> str:
    return os.environ.get("OLLAMA_BASE", "http://localhost:11434").rstrip("/")


_LOG_PATH_CACHE: Path | None = None


def _log_path() -> Path:
    """Resolve the log path once and reuse it on every tick.

    Resolves ``$repo/logs/keepalive.log`` (or whatever ``KEEPALIVE_LOG`` points
    at) and ensures the parent directory exists. The result is cached at
    module level so the daemon loop doesn't stat() / mkdir() per line.
    \"\"\"
    global _LOG_PATH_CACHE
    if _LOG_PATH_CACHE is not None:
        return _LOG_PATH_CACHE
    raw = os.environ.get("KEEPALIVE_LOG", "logs/keepalive.log").strip()
    p = Path(raw)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent / p
    p.parent.mkdir(parents=True, exist_ok=True)
    _LOG_PATH_CACHE = p
    return p


def _rotate_log_if_needed(path: Path) -> None:
    """Truncate ``keepalive.log`` to the last ~25% once it crosses 1 MiB.

    Keeps the daemon alive across months without a separate logrotate dep.
    Idempotent and low-cost — runs on every log write but only does I/O when
    the file is over the cap.
    """
    try:
        if not path.exists() or path.stat().st_size <= MAX_LOG_BYTES:
            return
        keep_bytes = MAX_LOG_BYTES // 4
        with path.open("rb") as fh:
            fh.seek(-keep_bytes, 2)
            tail = fh.read()
        with path.open("wb") as fh:
            fh.write(b"...[rotated]...\n")
            fh.write(tail)
    except Exception:
        # Rotation is best-effort — never let it break the tick.
        pass


def _log(line: str) -> None:
    """Write a timestamped line to both stdout and the log file.

    ASCII-only because Windows console codecs (cp1252) can't render the
    Unicode chars used elsewhere in this repo (e.g. help text arrows).
    """
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{stamp}] {line}"
    p = _log_path()
    _rotate_log_if_needed(p)
    try:
        with p.open("a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except Exception:
        pass
    print(msg, flush=True)


def _safe_get(client: httpx.Client, url: str, *, timeout: float = 15.0) -> tuple[bool, str]:
    """Plain GET. Returns (ok, status_text)."""
    try:
        resp = client.get(url, timeout=timeout)
        return (resp.status_code == 200, str(resp.status_code))
    except httpx.RequestError as exc:
        return (False, f"error: {exc.__class__.__name__}")


def _check_render(client: httpx.Client, base: str) -> tuple[bool, str]:
    """Ping /api/health first; fall back to /api/ping when /api/health stalls.

    Render returns /api/ping faster while /api/health can take a few seconds
    when waking from sleep, so the fallback shortens the cold-start dead air.
    """
    health_url = f"{base}/api/health"
    ping_url = f"{base}/api/ping"
    ok, status = _safe_get(client, health_url, timeout=20.0)
    if ok:
        return True, f"{status} via /api/health"
    ok, status = _safe_get(client, ping_url, timeout=10.0)
    if ok:
        return True, f"{status} via /api/ping"
    return False, status


def _check_ollama(client: httpx.Client, base: str) -> tuple[bool, list[str]]:
    try:
        resp = client.get(f"{base}/api/tags", timeout=10.0)
    except httpx.RequestError as exc:
        return (False, [f"ollama unreachable: {exc.__class__.__name__}: {exc}"])
    if resp.status_code != 200:
        return (False, [f"ollama /api/tags -> HTTP {resp.status_code}"])
    names = sorted(
        m["name"] for m in resp.json().get("models", [])
        if isinstance(m, dict) and m.get("name")
    )
    return (True, names)


def _loaded_ollama_prefixes(client: httpx.Client, base: str) -> set[str]:
    """Return the set of model prefixes (tag-stripped name) currently in Ollama VRAM.

    Single GET per tick — the previous per-model loop issued N requests which
    would also stall N×5s when Ollama was hung or slow.
    """
    try:
        resp = client.get(f"{base}/api/ps", timeout=5.0)
        if resp.status_code != 200:
            return set()
        loaded = resp.json().get("models", []) or []
    except httpx.RequestError:
        return set()
    return {m.get("name", "").split(":")[0] for m in loaded if m.get("name")}


def _warm_model(client: httpx.Client, base: str, model: str, *, timeout: float = 220.0) -> tuple[bool, str]:
    """Trigger a 1-token inference so Ollama loads the model into VRAM.

    Uses ``keep_alive=-1`` so once loaded it stays loaded for this process
    lifetime. The operator should also set ``OLLAMA_KEEP_ALIVE=-1`` as a
    user/system env var so the setting survives new shells.
    """
    payload = {"model": model, "prompt": "ok", "stream": False, "keep_alive": -1}
    try:
        resp = client.post(f"{base}/api/generate", json=payload, timeout=timeout)
    except httpx.RequestError as exc:
        return (False, f"warm failed: {exc.__class__.__name__}: {exc}")
    if resp.status_code != 200:
        return (False, f"warm HTTP {resp.status_code}")
    try:
        data = resp.json()
    except json.JSONDecodeError:
        return (False, "warm returned non-JSON")
    if not data.get("done"):
        return (False, "warm response missing done=true")
    eval_count = data.get("eval_count", "?")
    elapsed = resp.elapsed.total_seconds()
    return (True, f"loaded -> {eval_count} eval in {elapsed:.1f}s")


def _parse_models() -> list[str]:
    raw = os.environ.get("KEEPALIVE_MODELS", "qwen3-coder:30b,deepseek-r1:32b").strip()
    return [m.strip() for m in raw.split(",") if m.strip()]


def _short_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


WarmResult = tuple[str, bool, str]


def run_once(render_url: str, ollama_base: str) -> int:
    """Run a single keepalive tick. Returns 0 if Render+models healthy, else 1."""
    health_only = _env_bool("KEEPALIVE_HEALTH_ONLY", False)
    should_warm = _env_bool("KEEPALIVE_WARM", True) and not health_only
    models = _parse_models() if should_warm else []

    warm_results: list[WarmResult] = []

    with httpx.Client() as client:
        _log(
            f"tick: render={_short_url(render_url)} "
            f"ollama={_short_url(ollama_base)} "
            f"warm={should_warm} models={models or '<none>'}"
        )

        ok_render, render_status = _check_render(client, render_url)
        _log(
            f"render health: ok ({render_status})"
            if ok_render
            else f"render health FAILED: {render_status}"
        )

        ok_ollama, ollama_status_list = (True, [])
        if not health_only:
            ok_ollama, ollama_status_list = _check_ollama(client, ollama_base)
            if ok_ollama:
                _log(f"ollama tags: {len(ollama_status_list)} model(s) installed")
            else:
                _log(
                    f"ollama tags FAILED: "
                    f"{ollama_status_list[0] if ollama_status_list else 'unknown'} "
                    f"-- skipping warm pass to avoid stacked timeouts"
                )

        if should_warm and ok_ollama:
            # Single GET keeps the tick fast even with many KEEPALIVE_MODELS.
            loaded_prefixes = _loaded_ollama_prefixes(client, ollama_base)
            installed_prefixes = {m.split(":")[0] for m in ollama_status_list}
            for model in models:
                prefix = model.split(":")[0]
                if prefix not in installed_prefixes:
                    warm_results.append((model, True, "skipped (not installed)"))
                    _log(f"warm {model}: skipped (not installed)")
                    continue
                if prefix in loaded_prefixes:
                    warm_results.append((model, True, "already loaded"))
                    _log(f"warm {model}: already loaded, skipping inference")
                    continue
                ok, msg = _warm_model(client, ollama_base, model)
                warm_results.append((model, ok, msg))
                _log(f"warm {model}: {'ok' if ok else 'FAIL'} ({msg})")
        elif should_warm and not ok_ollama:
            warm_results.append(("", False, "warm skipped (ollama unreachable)"))

    overall = ok_render and ok_ollama
    if any(not ok for _, ok, _ in warm_results):
        overall = False

    def _fmt(item: WarmResult) -> str:
        model, ok, msg = item
        label = "ok" if ok else "FAIL"
        return f"{model} -> {label} ({msg})" if model else f"({msg})"

    summary = "+".join(_fmt(w) for w in warm_results) or "n/a"

    if overall:
        _log(f"tick OK: render={render_status} warm={summary}")
        return 0
    _log(f"tick FAIL: render={ok_render} ollama={ok_ollama} warm={[(_fmt(w)) for w in warm_results]}")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render + Ollama keepalive (Windows-friendly cron).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--diagnose",
        action="store_true",
        help="Run a single tick and exit 0 if Render+models healthy, else 1.",
    )
    mode.add_argument(
        "--once",
        action="store_true",
        help="Run a single tick and exit (always 0). Use this from cron / Task Scheduler.",
    )
    mode.add_argument(
        "--daemon",
        action="store_true",
        help="Run in a foreground loop, sleeping between ticks. Default mode.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Tick interval in seconds (overrides KEEPALIVE_INTERVAL_SEC; default 600).",
    )
    parser.add_argument(
        "--render-url",
        default=None,
        help="Render URL (overrides KEEPALIVE_URL).",
    )
    parser.add_argument(
        "--ollama-base",
        default=None,
        help="Ollama URL (overrides OLLAMA_BASE).",
    )
    args = parser.parse_args()

    render_url = (args.render_url or _default_render_url()).rstrip("/")
    ollama_base = (args.ollama_base or _default_ollama_base()).rstrip("/")
    interval = args.interval or int(os.environ.get("KEEPALIVE_INTERVAL_SEC", "600"))

    if args.diagnose or args.once:
        rc = run_once(render_url, ollama_base)
        sys.exit(rc if args.diagnose else 0)

    # daemon mode (default)
    _log(
        f"daemon started (interval={interval}s "
        f"render={_short_url(render_url)} "
        f"ollama={_short_url(ollama_base)} "
        f"warm={_env_bool('KEEPALIVE_WARM', True)} "
        f"models={_parse_models()})"
    )
    try:
        while True:
            try:
                run_once(render_url, ollama_base)
            except Exception as exc:
                # never let a tick exception kill the loop
                _log(f"tick raised exception (non-fatal): {exc.__class__.__name__}: {exc}")
            time.sleep(max(interval, 30))
    except KeyboardInterrupt:
        _log("daemon stopped (Ctrl+C)")
        sys.exit(0)


if __name__ == "__main__":
    main()

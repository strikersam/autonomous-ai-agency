#!/usr/bin/env python3
"""Capture README screenshots of every v5 screen from a locally-running server.

Usage:
    # 1. build frontend:           (cd frontend && CI=false npm run build)
    # 2. run backend:              ADMIN_PASSWORD=... uvicorn backend.server:app --port 8001
    # 3. capture:                  python scripts/capture_screens.py

Logs in via /api/auth/login, injects the token into localStorage, then navigates
to each route and writes a PNG to docs/screenshots/v5/. Console errors and HTTP
5xx responses per page are collected and printed as a bug report at the end.

Env: SHOT_BASE_URL (default http://127.0.0.1:8001), SHOT_EMAIL, SHOT_PASSWORD,
     SHOT_CHROME (path to a chromium binary).
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import secrets
import subprocess  # nosec B404 - launches the local uvicorn server for capture
import sys
import time
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

log = logging.getLogger("qwen-proxy")

BASE = os.environ.get("SHOT_BASE_URL", "http://127.0.0.1:8001")
EMAIL = os.environ.get("SHOT_EMAIL", "admin@llmrelay.local")
PASSWORD = os.environ.get("SHOT_PASSWORD", "")
CHROME = os.environ.get("SHOT_CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
OUT = pathlib.Path(os.environ.get("SHOT_OUT", "docs/screenshots/v5"))

# (filename-stem, route) — every authenticated v5 screen. v5 is URL-addressable
# at /v5/<id> (see frontend/src/v5/V5App.jsx::screenFromPath); /v5 == chat.
DESKTOP = [
    ("chat", "/v5/chat"),
    ("dashboard", "/v5/dashboard"),
    ("tasks", "/v5/tasks"),
    ("agents", "/v5/agents"),
    ("schedules", "/v5/schedules"),
    ("skills", "/v5/skills"),
    ("portfolio", "/v5/portfolio"),
    ("intelligence", "/v5/intelligence"),
    ("knowledge", "/v5/knowledge"),
    ("providers", "/v5/providers"),
    ("github", "/v5/github"),
    ("logs", "/v5/logs"),
    ("company", "/v5/company"),
    ("onboarding", "/v5/onboarding"),
    ("doctor", "/v5/doctor"),
    ("admin", "/v5/admin"),
]
MOBILE = [
    ("dashboard", "/v5/dashboard"),
    ("tasks", "/v5/tasks"),
    ("agents", "/v5/agents"),
]


def _wait_up(timeout_s: int = 60) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE}/api/activation/status", timeout=3):  # nosec B310
                return True
        except (urllib.error.URLError, OSError):
            time.sleep(2)
    return False


def _start_server() -> subprocess.Popen | None:
    """Launch the local uvicorn server (activated, sqlite, loops off) for capture."""
    if not os.environ.get("SHOT_START_SERVER"):
        return None
    env = {
        **os.environ,
        "ADMIN_EMAIL": EMAIL,
        "ADMIN_PASSWORD": PASSWORD,
        "STORAGE_BACKEND": "sqlite",
        "RUN_BACKGROUND_IN_WEB": "false",
        "AGENCY_CEO_ENABLED": "false",
        "ACTIVATION_REQUIRED": "false",
        # Throwaway per-run signing secret — never a hardcoded value in source.
        "V3_JWT_SECRET": os.environ.get("V3_JWT_SECRET") or secrets.token_hex(16),
        "LLM_PROVIDER": "nvidia-nim",
    }
    log_path = os.environ.get("SHOT_SERVER_LOG", "/tmp/backend.log")  # nosec B108 - dev capture log
    log_file = open(log_path, "w")  # noqa: SIM115 - kept open for the subprocess lifetime; closed in main()
    proc = subprocess.Popen(  # nosec B603 - fixed argv, local server
        [sys.executable, "-m", "uvicorn", "backend.server:app", "--host", "127.0.0.1",
         "--port", "8001", "--log-level", "warning"],
        env=env, stdout=log_file, stderr=subprocess.STDOUT,
    )
    proc._shot_log_file = log_file  # type: ignore[attr-defined]  # closed by main()
    if not _wait_up(70):
        proc.terminate()
        log_file.close()
        raise RuntimeError(f"backend did not come up — see {log_path}")
    log.info("backend up (managed by capture script)")
    return proc


def _login() -> tuple[str, str]:
    req = urllib.request.Request(
        f"{BASE}/api/auth/login",
        data=json.dumps({"email": EMAIL, "password": PASSWORD}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:  # nosec B310 - local fixed URL
        data = json.load(r)
    return data["access_token"], data.get("refresh_token", "")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    server = _start_server()
    try:
        _capture()
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except Exception:  # noqa: BLE001
                server.kill()
            log_file = getattr(server, "_shot_log_file", None)
            if log_file is not None:
                log_file.close()


def _capture() -> None:
    access, refresh = _login()
    bugs: list[tuple[str, str, list[str]]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )

        def run(items, width, height, prefix, authed):
            ctx = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=2)
            page = ctx.new_page()
            errs: list[str] = []
            page.on("console", lambda m: errs.append(f"console.error: {m.text}") if m.type == "error" else None)
            page.on("response", lambda r: errs.append(f"HTTP {r.status} {r.url}") if r.status >= 500 else None)
            page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))

            page.goto(f"{BASE}/login", wait_until="domcontentloaded")
            if authed:
                page.evaluate(
                    "([a, r, b]) => { localStorage.setItem('access_token', a);"
                    " if (r) localStorage.setItem('refresh_token', r);"
                    " localStorage.setItem('backend_url', b); }",
                    [access, refresh, BASE],
                )
            for name, route in items:
                errs.clear()
                try:
                    # domcontentloaded (not networkidle): authed pages poll/stream,
                    # so the network never goes idle. Fixed settle wait instead.
                    page.goto(f"{BASE}{route}", wait_until="domcontentloaded", timeout=20000)
                except Exception as exc:  # noqa: BLE001
                    errs.append(f"navigation: {exc}")
                page.wait_for_timeout(2600)
                fn = OUT / f"{prefix}{name}.png"
                page.screenshot(path=str(fn))
                if errs:
                    bugs.append((f"{prefix}{name}", route, list(dict.fromkeys(errs))[:6]))
                log.info("captured %s  (errors: %d)", fn, len(errs))
            ctx.close()

        run([("login", "/login")], 1440, 900, "", authed=False)
        run(DESKTOP, 1440, 900, "", authed=True)
        run([("login", "/login")], 390, 844, "mobile-", authed=False)
        run(MOBILE, 390, 844, "mobile-", authed=True)
        browser.close()

    log.info("=== PER-PAGE ERRORS (bug report) ===")
    if not bugs:
        log.info("none — all screens rendered without console errors or 5xx")
    for name, route, errs in bugs:
        log.info("[%s]  %s", name, route)
        for e in errs:
            log.info("   %s", e[:200])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()

"""E2E UI smoke test: every v5 screen renders without errors.

This is the assertion form of the README screenshot-capture flow
(`scripts/capture_screens.py`): it logs in, visits each `/v5/<screen>` route, and
asserts the screen renders the app shell with **no page errors, no HTTP 5xx, and
no console errors** (other than the cosmetic Google-Fonts cert failure seen in
sandboxes that MITM HTTPS).

Opt-in — skipped unless a built frontend is being served by a running backend:
    SHOT_BASE_URL=http://127.0.0.1:8011  (a server with the SPA built + activated)
    SHOT_PASSWORD=...                    (admin password)
and a Chromium binary is available (SHOT_CHROME or the default playwright path).
"""
from __future__ import annotations

import json
import os
import urllib.request

import pytest

BASE = os.environ.get("SHOT_BASE_URL")
PASSWORD = os.environ.get("SHOT_PASSWORD")
EMAIL = os.environ.get("SHOT_EMAIL", "admin@llmrelay.local")
CHROME = os.environ.get("SHOT_CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")

V5_SCREENS = [
    "chat", "dashboard", "tasks", "agents", "schedules", "skills", "portfolio",
    "intelligence", "knowledge", "providers", "github", "logs", "company",
    "onboarding", "doctor", "admin",
]

# Console errors that are environment artifacts, not app bugs (sandbox HTTPS
# proxy intercepts Google Fonts → cert failure; favicon noise).
_IGNORABLE = ("ERR_CERT_AUTHORITY_INVALID", "favicon.ico")


def _server_up() -> bool:
    if not (BASE and PASSWORD):
        return False
    try:
        with urllib.request.urlopen(f"{BASE}/api/health", timeout=3):  # nosec B310
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _server_up() or not os.path.exists(CHROME),
    reason="needs SHOT_BASE_URL+SHOT_PASSWORD server with a built SPA and a Chromium binary",
)


def _login() -> str:
    req = urllib.request.Request(
        f"{BASE}/api/auth/login",
        data=json.dumps({"email": EMAIL, "password": PASSWORD}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:  # nosec B310
        return json.load(r)["access_token"]


def test_every_v5_screen_renders_without_errors():
    from playwright.sync_api import sync_playwright

    token = _login()
    failures: dict[str, list[str]] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        errs: list[str] = []
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
        page.on("response", lambda r: errs.append(f"HTTP {r.status} {r.url}") if r.status >= 500 else None)

        page.goto(f"{BASE}/login", wait_until="domcontentloaded")
        page.evaluate("t => localStorage.setItem('access_token', t)", token)

        for screen in V5_SCREENS:
            errs.clear()
            page.goto(f"{BASE}/v5/{screen}", wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2000)
            body = page.inner_text("body")
            real = [e for e in errs if not any(ig in e for ig in _IGNORABLE)]
            if "AUTONOMOUS AI AGENCY" not in body.upper():
                real.append("app shell did not render")
            if real:
                failures[screen] = list(dict.fromkeys(real))[:5]
        browser.close()

    assert not failures, "v5 screens with errors:\n" + json.dumps(failures, indent=2)

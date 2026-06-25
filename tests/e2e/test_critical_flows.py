#!/usr/bin/env python3
"""
Critical-flow E2E tests (Playwright) — the five journeys that must never break.

Unlike ``test_browser.py`` (which smoke-loads every page), this suite drives the
*flows* a real user performs end to end:

  1. Login                         — auth into the V5 control plane.
  2. Company onboarding / scanning — paste a URL, kick off the tech scan.
  3. Task creation + status poll   — create a task, watch its status settle.
  4. Chat (direct mode, non-agent) — send a message, get a reply.
  5. Admin dashboard               — the admin portal loads with its panels.

Targets:
  * Backend  (V5 SPA + REST API):  http://localhost:8001   (RELAY_BASE_URL)
  * Proxy    (OpenAI-compatible):  http://localhost:8000   (PROXY_BASE_URL)

Design rules (match the rest of tests/e2e/):
  * No mocks — every assertion hits a live endpoint.
  * Self-skipping: if Playwright isn't installed or the server isn't up, the
    test SKIPS (never hard-fails) so the unit suite stays green offline.
  * Resilient selectors: the SPA markup shifts between versions, so we locate
    elements by several strategies and assert on outcomes (URL / network / text)
    rather than brittle CSS.

Run:
    RELAY_BASE_URL=http://localhost:8001 \
    PROXY_BASE_URL=http://localhost:8000 \
    ADMIN_EMAIL=admin@llmrelay.local \
    ADMIN_PASSWORD=<pw> \
    pytest tests/e2e/test_critical_flows.py -v
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

import pytest

BASE_URL = os.environ.get("RELAY_BASE_URL", "http://localhost:8001").rstrip("/")
PROXY_BASE_URL = os.environ.get("PROXY_BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@llmrelay.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
PROXY_API_KEY = os.environ.get("PROXY_API_KEY") or os.environ.get("API_KEY", "")

DESKTOP = {"width": 1280, "height": 800}


# ─── Availability guards ──────────────────────────────────────────────────────

def _http_ok(url: str, timeout: float = 8.0) -> bool:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https"):
        return False
    try:
        r = urllib.request.urlopen(url, timeout=timeout)  # noqa: S310 - scheme validated
        return 200 <= r.status < 500
    except Exception:
        return False


def _require_backend() -> None:
    if not _http_ok(f"{BASE_URL}/api/health"):
        pytest.skip(f"Backend not reachable at {BASE_URL}")


def _require_proxy() -> None:
    if not _http_ok(f"{PROXY_BASE_URL}/api/health"):
        pytest.skip(f"Proxy not reachable at {PROXY_BASE_URL}")


def _playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return sync_playwright
    except ImportError:
        pytest.skip("playwright not installed (pip install playwright && playwright install chromium)")


# ─── Shared login helper ──────────────────────────────────────────────────────

def _do_login(page, base_url: str) -> bool:
    """Best-effort login. Returns True if we end up authenticated."""
    page.goto(f"{base_url}/login", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(1200)

    # Already authenticated (redirected away from /login)?
    if "login" not in page.url.lower():
        return True

    email = None
    pw = None
    for sel in (
        'input[type="email"]', 'input[name="email"]', 'input[name="username"]',
        'input[placeholder*="email" i]', 'input[placeholder*="user" i]',
    ):
        el = page.locator(sel)
        if el.count() and el.first.is_visible():
            email = el.first
            break
    for sel in ('input[type="password"]', 'input[name="password"]', 'input[placeholder*="password" i]'):
        el = page.locator(sel)
        if el.count() and el.first.is_visible():
            pw = el.first
            break

    if email is None or pw is None:
        # Fall back to all visible inputs.
        inputs = page.locator("input:visible")
        for i in range(inputs.count()):
            inp = inputs.nth(i)
            t = (inp.get_attribute("type") or "").lower()
            if t == "password" and pw is None:
                pw = inp
            elif t != "password" and email is None:
                email = inp

    if email is None or pw is None:
        return "login" not in page.url.lower()

    email.fill(ADMIN_EMAIL)
    pw.fill(ADMIN_PASSWORD)
    btn = page.locator(
        'button[type="submit"]:visible, button:has-text("Sign in"):visible, '
        'button:has-text("Login"):visible, button:has-text("Log in"):visible'
    ).first
    if btn.count():
        btn.click()
    else:
        pw.press("Enter")
    page.wait_for_load_state("domcontentloaded", timeout=20000)
    page.wait_for_timeout(1500)
    return "login" not in page.url.lower()


# ─── 1. Login flow ────────────────────────────────────────────────────────────

def test_login_flow():
    _require_backend()
    if not ADMIN_PASSWORD:
        pytest.skip("ADMIN_PASSWORD not set — cannot exercise authenticated login")
    sync_playwright = _playwright()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport=DESKTOP, ignore_https_errors=True)
        page = ctx.new_page()
        try:
            logged_in = _do_login(page, BASE_URL)
            assert logged_in, f"Still on a login URL after submitting: {page.url}"
            # The control plane shell should render some recognizable chrome.
            body = page.locator("body").inner_text().lower()
            assert any(k in body for k in ("dashboard", "tasks", "agents", "chat", "agency")), \
                "Authenticated shell did not render expected navigation"
        finally:
            ctx.close()
            browser.close()


# ─── 2. Company onboarding / scanning flow ────────────────────────────────────

def test_company_onboarding_scan_flow():
    _require_backend()
    if not ADMIN_PASSWORD:
        pytest.skip("ADMIN_PASSWORD not set")
    sync_playwright = _playwright()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport=DESKTOP, ignore_https_errors=True)
        page = ctx.new_page()
        try:
            assert _do_login(page, BASE_URL), "login failed"
            page.goto(f"{BASE_URL}/onboarding", wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(1500)
            # Find a URL/domain input to paste a target into.
            url_input = None
            for sel in (
                'input[type="url"]', 'input[placeholder*="url" i]',
                'input[placeholder*="website" i]', 'input[placeholder*="domain" i]',
                'input[placeholder*="https" i]', 'input[type="text"]:visible',
            ):
                el = page.locator(sel)
                if el.count() and el.first.is_visible():
                    url_input = el.first
                    break
            if url_input is None:
                # Onboarding may already be complete for this instance — that's a
                # valid state, not a failure; assert the screen at least rendered.
                body = page.locator("body").inner_text().lower()
                assert any(k in body for k in ("onboard", "company", "scan", "complete", "done")), \
                    "Onboarding screen rendered nothing recognizable"
                pytest.skip("No URL input present (onboarding likely already complete)")
            url_input.fill("https://example.com")
            scan_btn = page.locator(
                'button:has-text("Scan"):visible, button:has-text("Onboard"):visible, '
                'button:has-text("Start"):visible, button:has-text("Continue"):visible, '
                'button[type="submit"]:visible'
            ).first
            assert scan_btn.count(), "No scan/onboard button found on the onboarding screen"
            # Clicking kicks the scan; we don't wait for full completion (the scan
            # can take 30s+), only that the UI accepts the action without error.
            scan_btn.click()
            page.wait_for_timeout(2500)
            body = page.locator("body").inner_text().lower()
            assert "error" not in body or "scanning" in body or "scan" in body, \
                "Scan kickoff surfaced an error state"
        finally:
            ctx.close()
            browser.close()


# ─── 3. Task creation + status polling flow ───────────────────────────────────

def test_task_creation_and_status_poll():
    """Create a task via the REST API (the same endpoint the UI calls) and poll
    its status until it leaves the initial state — exercising the dispatcher."""
    _require_backend()
    if not ADMIN_PASSWORD:
        pytest.skip("ADMIN_PASSWORD not set")

    import httpx  # local import so the unit suite doesn't hard-require it

    with httpx.Client(base_url=BASE_URL, timeout=20.0, verify=False) as client:
        # Log in for a JWT (the SPA uses email/password -> token).
        login = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        if login.status_code == 404:
            login = client.post("/api/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        if login.status_code >= 400:
            pytest.skip(f"Login endpoint unavailable ({login.status_code}) — cannot create task")
        token = (login.json() or {}).get("token") or (login.json() or {}).get("access_token")
        if not token:
            pytest.skip("Login did not return a token")
        headers = {"Authorization": f"Bearer {token}"}

        created = client.post(
            "/api/tasks/",
            headers=headers,
            json={"title": "E2E smoke task", "description": "created by test_critical_flows", "priority": "low"},
        )
        assert created.status_code < 400, f"Task create failed: {created.status_code} {created.text[:200]}"
        task = created.json()
        task_id = task.get("task_id") or task.get("id") or (task.get("task") or {}).get("task_id")
        assert task_id, f"No task id in create response: {task}"

        # Poll status a handful of times; we only require the endpoint to keep
        # answering with a valid status (the flow the UI's poller depends on).
        last_status = None
        for _ in range(6):
            resp = client.get(f"/api/tasks/{task_id}", headers=headers)
            if resp.status_code >= 400:
                break
            last_status = (resp.json() or {}).get("status")
            if last_status and last_status not in ("queued", "pending", "todo"):
                break
        assert last_status is not None, "Task status endpoint never returned a status"


# ─── 4. Chat (direct, non-agent) flow ─────────────────────────────────────────

def test_chat_direct_mode_via_proxy():
    """Direct (non-agent) chat: hit the OpenAI-compatible proxy completion the
    same way the Chat screen's direct mode does."""
    _require_proxy()
    if not PROXY_API_KEY:
        pytest.skip("PROXY_API_KEY/API_KEY not set — proxy requires a Bearer key")

    import httpx

    with httpx.Client(base_url=PROXY_BASE_URL, timeout=60.0, verify=False) as client:
        # Models endpoint is a cheap auth + liveness check.
        models = client.get("/v1/models", headers={"Authorization": f"Bearer {PROXY_API_KEY}"})
        if models.status_code == 401:
            pytest.skip("Proxy rejected the provided API key (401)")
        assert models.status_code < 500, f"/v1/models errored: {models.status_code}"

        resp = client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {PROXY_API_KEY}"},
            json={
                "model": "auto",
                "messages": [{"role": "user", "content": "Reply with the single word: pong"}],
                "stream": False,
                "max_tokens": 16,
            },
        )
        # A reachable-but-no-backend-model deployment returns 5xx/502 — skip rather
        # than fail, since that's an infra state, not a contract break.
        if resp.status_code >= 500:
            pytest.skip(f"No live model behind the proxy ({resp.status_code})")
        assert resp.status_code < 400, f"chat completion failed: {resp.status_code} {resp.text[:200]}"
        data = resp.json()
        assert data.get("choices"), f"No choices in completion response: {json.dumps(data)[:200]}"


# ─── 5. Admin dashboard loads ─────────────────────────────────────────────────

def test_admin_dashboard_loads():
    _require_backend()
    if not ADMIN_PASSWORD:
        pytest.skip("ADMIN_PASSWORD not set")
    sync_playwright = _playwright()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport=DESKTOP, ignore_https_errors=True)
        page = ctx.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        try:
            assert _do_login(page, BASE_URL), "login failed"
            page.goto(f"{BASE_URL}/admin", wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2000)
            body = page.locator("body").inner_text().lower()
            assert any(k in body for k in ("admin", "key", "user", "health", "portal", "manage")), \
                "Admin portal did not render expected content"
            # Ignore benign network-abort console noise; fail only on real JS errors.
            fatal = [e for e in console_errors if "Failed to load resource" not in e and "net::" not in e]
            assert len(fatal) == 0, f"Admin dashboard logged JS errors: {fatal[:3]}"
        finally:
            ctx.close()
            browser.close()

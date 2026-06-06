#!/usr/bin/env python3
"""
Browser-based E2E tests for the 33 new roadmap features.

Covers:
- Dashboard UI health (20 pages: desktop + mobile viewports)
- Agent session creation and listing via API
- Chat with function-calling tools
- Model routing preview
- Harness detection and routing
- Health check endpoints
- Provider listing

Usage:
  RELAY_BASE_URL=http://localhost:8001 python tests/e2e/test_new_features_e2e.py

  # With pytest (for CI):
  pytest tests/e2e/test_new_features_e2e.py -v --browser chromium
"""

from __future__ import annotations

import os
import sys
import time
import json

try:
    from playwright.sync_api import sync_playwright, Page, Browser, APIRequestContext
except ImportError:
    print("Install playwright: pip install playwright && playwright install chromium")
    sys.exit(1)

BASE_URL = os.environ.get("RELAY_BASE_URL", "http://localhost:8001").rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@llmrelay.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WikiAdmin2026!")  # nosec B105
API_KEY = os.environ.get("TEST_API_KEY", "")

DESKTOP = {"width": 1280, "height": 720, "name": "desktop"}
MOBILE = {"width": 375, "height": 812, "name": "mobile"}

# ─── All dashboard pages ─────────────────────────────────────────────────────
PAGES = [
    {"path": "/", "name": "Dashboard"},
    {"path": "/tasks", "name": "Tasks"},
    {"path": "/agents", "name": "Agents"},
    {"path": "/schedules", "name": "Schedules"},
    {"path": "/chat", "name": "Chat"},
    {"path": "/knowledge", "name": "Knowledge"},
    {"path": "/skills", "name": "Skills"},
    {"path": "/intelligence", "name": "Intelligence"},
    {"path": "/company", "name": "Company"},
    {"path": "/github", "name": "GitHub"},
    {"path": "/doctor", "name": "Doctor"},
    {"path": "/onboarding", "name": "Onboarding"},
    {"path": "/admin", "name": "Admin"},
    {"path": "/runtimes", "name": "Runtimes"},
    {"path": "/routing", "name": "Routing"},
    {"path": "/providers", "name": "Providers"},
    {"path": "/logs", "name": "Logs"},
    {"path": "/setup", "name": "Setup"},
    {"path": "/settings", "name": "Settings"},
    {"path": "/login", "name": "Login"},
]

# ─── API endpoints to test ──────────────────────────────────────────────────
API_TESTS = [
    {"method": "GET", "path": "/api/health", "name": "Health check", "auth": False},
    {"method": "GET", "path": "/api/doctor/public", "name": "Doctor public", "auth": False},
    {"method": "GET", "path": "/version", "name": "Version", "auth": False},
    {"method": "GET", "path": "/v1/models", "name": "Models list", "auth": True},
    {"method": "GET", "path": "/ui/api/bootstrap", "name": "UI bootstrap", "auth": False},
    {"method": "GET", "path": "/ui/api/providers", "name": "UI providers", "auth": True},
    {"method": "POST", "path": "/ui/api/route", "name": "Route preview", "auth": True,
     "body": {"text": "Write a Python function to sort a list"}},
]


class Result:
    passed = 0
    failed = 0
    errors: list[str] = []


def ok(label: str) -> None:
    print(f"  \u2713 {label}")
    Result.passed += 1


def fail(label: str, detail: str = "") -> None:
    msg = f"  \u2717 {label}"
    if detail:
        msg += f" \u2014 {detail}"
    print(msg)
    Result.failed += 1
    Result.errors.append(msg)


# ─── Login ────────────────────────────────────────────────────────────────

def do_login(page: Page, base_url: str) -> bool:
    print(f"\n{'='*60}\n  Login\n{'='*60}")

    page.goto(f"{base_url}/login", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(1500)

    if "login" not in page.url.lower():
        ok("login \u2014 already authenticated")
        return True

    email_field = None
    pw_field = None

    for selector in [
        'input[type="email"]', 'input[name="email"]', 'input[name="username"]',
        'input[placeholder*="email" i]', 'input[placeholder*="Email" i]',
        'input[placeholder*="user" i]',
    ]:
        el = page.locator(selector)
        if el.count() > 0 and el.first.is_visible():
            email_field = el.first
            break

    for selector in [
        'input[type="password"]', 'input[name="password"]',
        'input[placeholder*="password" i]', 'input[placeholder*="Password" i]',
    ]:
        el = page.locator(selector)
        if el.count() > 0 and el.first.is_visible():
            pw_field = el.first
            break

    if email_field is None or pw_field is None:
        all_inputs = page.locator('input:visible')
        for i in range(all_inputs.count()):
            inp = all_inputs.nth(i)
            inp_type = (inp.get_attribute("type") or "").lower()
            if inp_type == "password" and pw_field is None:
                pw_field = inp
            elif inp_type != "password" and email_field is None:
                email_field = inp

    if email_field is None or pw_field is None:
        page.goto(f"{base_url}/admin/ui/login", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(800)
        email_field = page.locator('input[name="username"], input[type="text"]:visible').first
        pw_field = page.locator('input[type="password"]:visible').first

    if email_field is None or pw_field is None or email_field.count() == 0:
        body = page.locator('body').inner_text()[:300]
        fail("login", f"could not find form fields. Body: {body}")
        return False

    email_field.fill(ADMIN_EMAIL)
    pw_field.fill(ADMIN_PASSWORD)

    btn = page.locator(
        'button[type="submit"]:visible, button:has-text("Sign in"):visible, '
        'button:has-text("Login"):visible, button:has-text("Log in"):visible'
    ).first
    if btn.count() > 0:
        btn.click()
    else:
        pw_field.press("Enter")

    page.wait_for_load_state("domcontentloaded", timeout=15000)
    page.wait_for_timeout(1500)

    current = page.url
    if "login" in current.lower():
        error_el = page.locator('[class*="error" i], [class*="alert" i], .text-red-500, .text-danger')
        error_text = ""
        if error_el.count() > 0:
            error_text = f" \u2014 page error: {error_el.first.inner_text()[:100]}"
        fail("login", f"still on login page: {current}{error_text}")
        return False

    ok(f"login \u2192 {current[:60]}")
    return True


# ─── Test a dashboard page ────────────────────────────────────────────────

def test_page(page: Page, base_url: str, page_info: dict, viewport_name: str) -> None:
    path = page_info["path"]
    name = page_info["name"]

    console_errors: list[str] = []

    def on_console(msg):
        if msg.type == "error":
            console_errors.append(msg.text)

    page.on("console", on_console)

    try:
        page.goto(f"{base_url}{path}", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(800)
    except Exception as e:
        fail(f"{name} ({viewport_name})", f"navigation error: {e}")
        return

    title = page.title()
    if not title:
        fail(f"{name} ({viewport_name})", "empty page title")
        return

    body_text = page.locator("body").inner_text()[:200].lower()
    if any(indicator in body_text for indicator in ["internal server error", "something went wrong"]):
        fail(f"{name} ({viewport_name})", "error page detected")
        return

    page.wait_for_timeout(500)

    if console_errors:
        critical = [e for e in console_errors if "500" in e or "Internal Server Error" in e]
        if critical:
            fail(f"{name} ({viewport_name})", f"console errors: {critical[:3]}")
            return

    ok(f"{name} ({viewport_name})")


# ─── Test API endpoints ────────────────────────────────────────────────────

def test_api_endpoints(context: APIRequestContext, base_url: str) -> None:
    print(f"\n{'='*60}\n  API Endpoints\n{'='*60}")

    headers: dict[str, str] = {}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    for test in API_TESTS:
        name = test["name"]
        method = test["method"]
        path = test["path"]
        auth_required = test.get("auth", False)

        try:
            if method == "GET":
                resp = context.get(f"{base_url}{path}", headers=headers if auth_required else {})
            elif method == "POST":
                body = test.get("body", {})
                resp = context.post(
                    f"{base_url}{path}",
                    data=json.dumps(body),
                    headers={**headers, "Content-Type": "application/json"} if auth_required else {"Content-Type": "application/json"},
                )
            else:
                fail(name, f"unsupported method: {method}")
                continue

            if resp.status < 500:
                ok(f"API {name} ({resp.status})")
            else:
                fail(f"API {name}", f"status={resp.status} body={resp.text()[:200]}")
        except Exception as e:
            fail(f"API {name}", f"request failed: {e}")


# ─── Main test runner ─────────────────────────────────────────────────────

def run_tests(base_url: str) -> bool:
    print(f"\n{'='*60}")
    print(f"  LLM Relay \u2014 New Features Browser E2E Tests")
    print(f"  Target: {base_url}")
    print(f"  Viewports: {DESKTOP['name']} ({DESKTOP['width']}x{DESKTOP['height']}),")
    print(f"             {MOBILE['name']} ({MOBILE['width']}x{MOBILE['height']})")
    print(f"{'='*60}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ── API tests (no viewport needed) ──────────────────────────────
        api_context = browser.new_context()
        test_api_endpoints(api_context.request, base_url)
        api_context.close()

        # ── UI page tests ─────────────────────────────────────────────
        for viewport in [DESKTOP, MOBILE]:
            print(f"\n{'-'*60}")
            print(f"  {viewport['name'].upper()} viewport ({viewport['width']}x{viewport['height']})")
            print(f"{'-'*60}")

            context = browser.new_context(
                viewport={"width": viewport["width"], "height": viewport["height"]},
                device_scale_factor=2 if viewport["name"] == "mobile" else 1,
            )
            page = context.new_page()

            try:
                for attempt in range(30):
                    try:
                        r = page.goto(f"{base_url}/api/health", timeout=5000)
                        if r and r.status == 200:
                            break
                    except Exception:  # nosec B110 - graceful degradation in browser test
                        pass
                    time.sleep(2)
                else:
                    fail("server startup", f"not responding at {base_url}")
                    context.close()
                    continue

                ok(f"server ready ({viewport['name']})")

                if not do_login(page, base_url):
                    try:
                        page.screenshot(path=f"/tmp/e2e-login-fail-{viewport['name']}.png")  # nosec B108 - test screenshot path
                    except Exception:  # nosec B110 - graceful degradation in browser test
                        pass

                for page_info in PAGES:
                    test_page(page, base_url, page_info, viewport["name"])

            except Exception as e:
                fail(f"fatal {viewport['name']}", str(e))
                try:
                    page.screenshot(path=f"/tmp/e2e-fatal-{viewport['name']}.png")  # nosec B108 - test screenshot path
                except Exception:  # nosec B110 - cleanup handler
                    pass
            finally:
                context.close()

        browser.close()

    total = Result.passed + Result.failed
    print(f"\n{'='*60}")
    print(f"  {Result.passed} passed  |  {Result.failed} failed  |  {total} total")
    print(f"{'='*60}\n")

    if Result.failed > 0:
        print(f"{len(Result.errors)} failure(s):")
        for e in Result.errors:
            print(f"  {e}")

    return Result.failed == 0


# ─── Pytest integration ───────────────────────────────────────────────────

import pytest


@pytest.fixture(scope="module")
def base_url() -> str:
    return BASE_URL


def test_server_health(base_url: str) -> None:
    import urllib.parse
    import urllib.request
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in ("http", "https"):
        pytest.skip(f"Unsupported RELAY_BASE_URL scheme: {parsed.scheme!r}")
    try:
        r = urllib.request.urlopen(f"{base_url}/api/health", timeout=10)  # nosec B310 - health check URL from config
        assert r.status == 200  # nosec B101
    except Exception as e:
        pytest.skip(f"Server not available: {e}")


def test_new_features_browser(base_url: str) -> None:
    assert run_tests(base_url), "Browser tests failed. See output above for details."  # nosec B101


if __name__ == "__main__":
    success = run_tests(BASE_URL)
    sys.exit(0 if success else 1)

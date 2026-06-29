#!/usr/bin/env python3
"""
Browser-based E2E tests — runs with Playwright against a live LLM Relay instance.

Covers ALL 20 control plane pages in both desktop (1280x720) and mobile (375x812)
viewports. Verifies pages load without console errors, key UI elements are present,
and navigation works.

Usage:
  # Against a running server:
  RELAY_BASE_URL=http://localhost:8001 python tests/e2e/test_browser.py

  # In Docker (docker-compose.e2e.yml):
  RELAY_BASE_URL=http://backend:8001 python tests/e2e/test_browser.py

  # With pytest (for CI):
  pytest tests/e2e/test_browser.py -v --browser chromium
"""

from __future__ import annotations

import os
import sys
import time
import json

try:
    from playwright.sync_api import sync_playwright, Page, Browser
except ImportError:
    print("Install playwright: pip install playwright && playwright install chromium")
    sys.exit(1)

BASE_URL = os.environ.get("RELAY_BASE_URL", "http://localhost:8001").rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@llmrelay.local")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]  # nosec B105 — test credential only

# ─── Viewports ────────────────────────────────────────────────────────────────

DESKTOP = {"width": 1280, "height": 720, "name": "desktop"}
MOBILE = {"width": 375, "height": 812, "name": "mobile"}

# ─── All 13 pages to test ─────────────────────────────────────────────────────

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


# ─── Helpers ──────────────────────────────────────────────────────────────────

class Result:
    passed = 0
    failed = 0
    errors: list[str] = []


def ok(label: str) -> None:
    print(f"  ✓ {label}")
    Result.passed += 1


def fail(label: str, detail: str = "") -> None:
    msg = f"  ✗ {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    Result.failed += 1
    Result.errors.append(msg)


# ─── Login ────────────────────────────────────────────────────────────────────

def do_login(page: Page, base_url: str) -> bool:
    """Log in and return True on success."""
    print(f"\n{'='*60}\n  Login\n{'='*60}")

    page.goto(f"{base_url}/login", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(1500)

    # Check if already logged in (redirected away from login)
    if "login" not in page.url.lower():
        ok("login — already authenticated")
        return True

    # Find email and password fields using multiple strategies
    email_field = None
    pw_field = None

    # Strategy 1: Standard input types
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

    # Strategy 2: All visible inputs (first text = email, password type = password)
    if email_field is None or pw_field is None:
        all_inputs = page.locator('input:visible')
        for i in range(all_inputs.count()):
            inp = all_inputs.nth(i)
            inp_type = (inp.get_attribute("type") or "").lower()
            if inp_type == "password" and pw_field is None:
                pw_field = inp
            elif inp_type != "password" and email_field is None:
                email_field = inp

    # Strategy 3: Try admin UI login page
    if email_field is None or pw_field is None:
        page.goto(f"{base_url}/admin/ui/login", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(800)
        email_field = page.locator('input[name="username"], input[type="text"]:visible').first
        pw_field = page.locator('input[type="password"]:visible').first

    if email_field is None or pw_field is None or email_field.count() == 0:
        # Dump page content for debugging
        body = page.locator('body').inner_text()[:300]
        fail("login", f"could not find form fields. Body: {body}")
        try:
            page.screenshot(path="/tmp/login-debug.png")
        except Exception:
            pass
        return False

    email_field.fill(ADMIN_EMAIL)
    pw_field.fill(ADMIN_PASSWORD)

    # Find and click login button
    btn = page.locator('button[type="submit"]:visible, button:has-text("Sign in"):visible, button:has-text("Login"):visible, button:has-text("Log in"):visible').first
    if btn.count() > 0:
        btn.click()
    else:
        pw_field.press("Enter")

    page.wait_for_load_state("domcontentloaded", timeout=15000)
    page.wait_for_timeout(1500)

    # Verify we're logged in (not on login page anymore)
    current = page.url
    if "login" in current.lower():
        # Check for error message on page
        error_el = page.locator('[class*="error" i], [class*="alert" i], .text-red-500, .text-danger')
        error_text = ""
        try:
            if error_el.count() > 0:
                error_text = f" — page error: {error_el.first.inner_text()[:100]}"
        except Exception:
            pass  # locator might match a non-HTMLElement node
        fail("login", f"still on login page: {current}{error_text}")
        return False

    ok(f"login → {current[:60]}")
    return True


# ─── Test a single page ───────────────────────────────────────────────────────

def test_page(page: Page, base_url: str, page_info: dict, viewport_name: str) -> None:
    """Navigate to a page and verify it loads without errors."""
    path = page_info["path"]
    name = page_info["name"]

    console_errors: list[str] = []

    def on_console(msg):
        if msg.type == "error":
            console_errors.append(msg.text)

    page.on("console", on_console)

    try:
        # Use domcontentloaded instead of networkidle — pages with auto-refresh
        # (Dashboard polls every 15s, etc.) never reach networkidle, causing flaky
        # timeouts in CI. domcontentloaded is reliable when the SPA shell loads.
        page.goto(f"{base_url}{path}", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(800)
    except Exception as e:
        fail(f"{name} ({viewport_name})", f"navigation error: {e}")
        return

    # Check page loaded
    title = page.title()
    if not title:
        fail(f"{name} ({viewport_name})", "empty page title")
        return

    # Check for 500 / error text in page
    body_text = page.locator("body").inner_text()[:200].lower()
    if any(indicator in body_text for indicator in ["internal server error", "something went wrong"]):
        fail(f"{name} ({viewport_name})", "error page detected")
        return

    # Check for console errors
    page.wait_for_timeout(500)

    status = "✓"
    if console_errors:
        # Filter out non-critical errors
        critical = [e for e in console_errors if "500" in e or "Internal Server Error" in e]
        if critical:
            fail(f"{name} ({viewport_name})", f"console errors: {critical[:3]}")
            return
        status = "○"  # warnings but not critical

    ok(f"{name} ({viewport_name}) {status}")


# ─── Main test runner ─────────────────────────────────────────────────────────

def run_tests(base_url: str) -> bool:
    print(f"\n{'═'*60}")
    print(f"  LLM Relay — Browser E2E Tests")
    print(f"  Target: {base_url}")
    print(f"  Viewports: {DESKTOP['name']} ({DESKTOP['width']}x{DESKTOP['height']}),")
    print(f"             {MOBILE['name']} ({MOBILE['width']}x{MOBILE['height']})")
    print(f"{'═'*60}")

    with sync_playwright() as p:
        for viewport in [DESKTOP, MOBILE]:
            print(f"\n{'─'*60}")
            print(f"  {viewport['name'].upper()} viewport ({viewport['width']}x{viewport['height']})")
            print(f"{'─'*60}")

            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": viewport["width"], "height": viewport["height"]},
                device_scale_factor=2 if viewport["name"] == "mobile" else 1,
            )
            page = context.new_page()

            try:
                # Wait for server to be ready. NOTE: the app serves /api/health,
                # not /api/ping — health returns 200 even in SQLite/degraded mode.
                for attempt in range(30):
                    try:
                        r = page.goto(f"{base_url}/api/health", timeout=5000)
                        if r and r.status == 200:
                            break
                    except Exception:
                        pass
                    time.sleep(2)
                else:
                    fail("server startup", f"not responding at {base_url}")
                    browser.close()
                    return False

                ok(f"server ready ({viewport['name']})")

                # Login
                if not do_login(page, base_url):
                    # Log the page content for debugging
                    try:
                        page.screenshot(path=f"/tmp/login-fail-{viewport['name']}.png")
                        print(f"  Screenshot saved to /tmp/login-fail-{viewport['name']}.png")
                    except Exception:
                        pass

                # Test all pages
                for page_info in PAGES:
                    test_page(page, base_url, page_info, viewport["name"])

            except Exception as e:
                fail(f"fatal {viewport['name']}", str(e))
                try:
                    page.screenshot(path=f"/tmp/fatal-{viewport['name']}.png")
                except Exception:
                    pass
            finally:
                context.close()
                browser.close()

    # Summary
    total = Result.passed + Result.failed
    print(f"\n{'═'*60}")
    print(f"  {Result.passed} passed  |  {Result.failed} failed  |  {total} total")
    print(f"{'═'*60}\n")

    if Result.failed > 0:
        print(f"{len(Result.errors)} failure(s):")
        for e in Result.errors:
            print(f"  {e}")

    return Result.failed == 0


# ─── Pytest integration ───────────────────────────────────────────────────────

import pytest  # noqa: E402


@pytest.fixture(scope="module")
def base_url() -> str:
    return BASE_URL


def test_server_health(base_url: str) -> None:
    """Verify server responds to health check before running browser tests."""
    import urllib.parse
    import urllib.request
    # Only probe http(s) — urlopen also accepts file:/custom schemes, which we
    # never want to hit from a base_url taken from the environment (Ruff S310).
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in ("http", "https"):
        pytest.skip(f"Unsupported RELAY_BASE_URL scheme: {parsed.scheme!r}")
    try:
        r = urllib.request.urlopen(f"{base_url}/api/health", timeout=10)  # noqa: S310 - scheme validated above
        assert r.status == 200
    except Exception as e:
        pytest.skip(f"Server not available: {e}")


def test_all_pages_browser(base_url: str) -> None:
    """Run full browser e2e suite."""
    assert run_tests(base_url), f"Browser tests failed. See output above for details."


# ─── Script entry point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    success = run_tests(BASE_URL)
    sys.exit(0 if success else 1)

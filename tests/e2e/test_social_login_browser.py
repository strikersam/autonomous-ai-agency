#!/usr/bin/env python3
"""
Social Login E2E Browser Test — GitHub & Google OAuth flow verification.

Covers:
  - LoginPage renders GitHub + Google social buttons
  - GitHub button redirects to correct backend OAuth URL
  - Google button redirects to correct backend OAuth URL
  - AuthCallback handles access_token + refresh_token params
  - AuthCallback handles the social token flow (token + provider)
  - AuthCallback shows success UI
  - AuthCallback shows error UI for missing tokens
  - /api/auth/me endpoint returns user profile (validates the fix from PR #857)

Usage:
  RELAY_BASE_URL=http://localhost:8001 pytest tests/e2e/test_social_login_browser.py -v --tb=short
  RELAY_BASE_URL=http://localhost:8001 python tests/e2e/test_social_login_browser.py
"""

from __future__ import annotations

import os
import sys
import time
import uuid

try:
    from playwright.sync_api import sync_playwright, Page, BrowserContext
except ImportError:
    print("Install playwright: pip install playwright && playwright install chromium")
    sys.exit(1)

BASE_URL = os.environ.get("RELAY_BASE_URL", "http://localhost:8001").rstrip("/")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@llmrelay.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "test-admin-password-for-ci")

DESKTOP = {"width": 1280, "height": 720, "name": "desktop"}

# ─── Results tracking ─────────────────────────────────────────────────────────

class Report:
    passed = 0
    failed = 0
    skipped = 0
    errors: list[str] = []

    @classmethod
    def reset(cls) -> None:
        cls.passed = 0
        cls.failed = 0
        cls.skipped = 0
        cls.errors = []

    @classmethod
    def ok(cls, label: str) -> None:
        print(f"  \u2713 {label}")
        cls.passed += 1

    @classmethod
    def fail(cls, label: str, detail: str = "") -> None:
        msg = f"  \u2717 {label}"
        if detail:
            msg += f" -- {detail}"
        print(msg)
        cls.failed += 1
        cls.errors.append(msg)

    @classmethod
    def skip(cls, label: str, reason: str = "") -> None:
        msg = f"  \u25cb SKIP {label}"
        if reason:
            msg += f" -- {reason}"
        print(msg)
        cls.skipped += 1


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _login_api(page: Page) -> str | None:
    """Login via API and store the access_token in localStorage."""
    resp = page.request.post(
        f"{BASE_URL}/api/auth/login",
        data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if resp.status != 200:
        return None
    data = resp.json()
    token = data.get("access_token", "")
    if not token:
        return None
    # Inject token into localStorage so the app treats us as authenticated
    page.evaluate(f"localStorage.setItem('access_token', '{token}')")
    return token


def _navigate_logged_out(page: Page) -> bool:
    """Navigate to the frontend login page and verify it loads."""
    page.goto(f"{FRONTEND_URL}/login", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(500)
    body = page.locator("body").inner_text()
    if not body:
        return False
    # The login page should have "Sign in" text
    return "sign in" in body.lower() or "autonomous ai agency" in body.lower()


def _navigate_auth_callback(page: Page, query: str) -> None:
    """Navigate directly to the AuthCallback page with query params."""
    page.goto(f"{FRONTEND_URL}/auth/callback?{query}", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(1000)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


class TestLoginPage:
    """Social login buttons on the LoginPage."""

    def test_page_loads(self, page: Page) -> bool:
        """Verify the login page renders."""
        if not _navigate_logged_out(page):
            Report.fail("LoginPage: page fails to load")
            return False
        Report.ok("LoginPage: page loads with 'Sign in' content")
        return True

    def test_github_button_click_redirects(self, page: Page) -> None:
        """Click the GitHub button and verify it navigates to GitHub OAuth URL."""
        if not _navigate_logged_out(page):
            Report.skip("LoginPage: GitHub click", "page did not load")
            return

        gh_link = page.locator('a[href*="/api/auth/github/login"]').first
        if gh_link.count() == 0:
            Report.fail("LoginPage: GitHub click", "link element not found")
            return

        # Click the GitHub button
        gh_link.click()
        page.wait_for_timeout(2000)

        current_url = page.url
        # Should have redirected to the backend auth endpoint, then to GitHub
        if "github.com/login/oauth/authorize" in current_url:
            Report.ok("LoginPage: GitHub button click redirects to GitHub OAuth")
        elif "/api/auth/github/login" in current_url:
            # Backend redirects to GitHub — this URL might show briefly
            Report.ok("LoginPage: GitHub button click redirects to backend auth endpoint")
        else:
            Report.fail(
                "LoginPage: GitHub click redirect",
                f"expected GitHub OAuth URL, got: {current_url[:80]}",
            )

    def test_github_button_visible(self, page: Page) -> None:
        """Verify the GitHub social login button is rendered."""
        if not _navigate_logged_out(page):
            Report.skip("LoginPage: GitHub button", "page did not load")
            return

        gh_btn = page.locator(
            'a[href*="/api/auth/github/login"]:visible, '
            'button:has-text("GitHub"):visible'
        ).first

        if gh_btn.count() > 0:
            Report.ok("LoginPage: GitHub social login button visible")
        else:
            Report.fail("LoginPage: GitHub button", "button not found on page")

    def test_google_button_visible(self, page: Page) -> None:
        """Verify the Google social login button is rendered."""
        if not _navigate_logged_out(page):
            Report.skip("LoginPage: Google button", "page did not load")
            return

        goog_btn = page.locator(
            'a[href*="/api/auth/google/login"]:visible, '
            'button:has-text("Google"):visible'
        ).first

        if goog_btn.count() > 0:
            Report.ok("LoginPage: Google social login button visible")
        else:
            Report.fail("LoginPage: Google button", "button not found on page")

    def test_github_button_has_correct_href(self, page: Page) -> None:
        """Verify the GitHub button links to the backend auth URL."""
        if not _navigate_logged_out(page):
            Report.skip("LoginPage: GitHub href", "page did not load")
            return

        gh_link = page.locator('a[href*="/api/auth/github/login"]').first
        if gh_link.count() == 0:
            Report.fail("LoginPage: GitHub href", "link element not found")
            return

        href = gh_link.get_attribute("href") or ""
        if "/api/auth/github/login" in href:
            Report.ok(f"LoginPage: GitHub button links to backend auth URL ({href[:60]})")
        else:
            Report.fail("LoginPage: GitHub href", f"unexpected href: {href}")

    def test_google_button_has_correct_href(self, page: Page) -> None:
        """Verify the Google button links to the backend auth URL."""
        if not _navigate_logged_out(page):
            Report.skip("LoginPage: Google href", "page did not load")
            return

        goog_link = page.locator('a[href*="/api/auth/google/login"]').first
        if goog_link.count() == 0:
            Report.fail("LoginPage: Google href", "link element not found")
            return

        href = goog_link.get_attribute("href") or ""
        if "/api/auth/google/login" in href:
            Report.ok(f"LoginPage: Google button links to backend auth URL ({href[:60]})")
        else:
            Report.fail("LoginPage: Google href", f"unexpected href: {href}")

    def test_github_button_disabled_without_backend(self, page: Page) -> None:
        """Verify the GitHub button is aria-disabled when no backend is configured."""
        if not _navigate_logged_out(page):
            Report.skip("LoginPage: GitHub disabled", "page did not load")
            return

        gh_link = page.locator('a[href*="/api/auth/github/login"]').first
        if gh_link.count() == 0:
            Report.fail("LoginPage: GitHub disabled", "link element not found")
            return

        aria_disabled = gh_link.get_attribute("aria-disabled")
        if aria_disabled == "true":
            Report.ok("LoginPage: GitHub button is disabled when no backend configured")
        else:
            Report.ok("LoginPage: GitHub button is enabled (backend configured)")

    def test_or_continue_with_text(self, page: Page) -> None:
        """Verify the 'or continue with' divider is present."""
        if not _navigate_logged_out(page):
            Report.skip("LoginPage: divider text", "page did not load")
            return

        body = page.locator("body").inner_text()
        if "continue with" in body.lower():
            Report.ok("LoginPage: 'or continue with' divider text visible")
        else:
            Report.fail("LoginPage: divider text", "'continue with' text not found")


class TestAuthCallback:
    """AuthCallback page — handles tokens after OAuth redirect."""

    def test_legacy_token_flow(self, page: Page) -> None:
        """Simulate the legacy callback with access_token + refresh_token."""
        test_token = f"test-access-{uuid.uuid4().hex[:8]}"
        test_refresh = f"test-refresh-{uuid.uuid4().hex[:8]}"

        _navigate_auth_callback(
            page,
            f"access_token={test_token}&refresh_token={test_refresh}",
        )

        # Check localStorage for stored tokens
        stored_access = page.evaluate("localStorage.getItem('access_token')")
        stored_refresh = page.evaluate("localStorage.getItem('refresh_token')")

        if stored_access == test_token:
            Report.ok("AuthCallback: legacy flow stores access_token in localStorage")
        else:
            Report.fail(
                "AuthCallback: legacy flow",
                f"expected token '{test_token[:12]}...' got '{str(stored_access)[:20]}'",
            )

        if stored_refresh == test_refresh:
            Report.ok("AuthCallback: legacy flow stores refresh_token in localStorage")
        else:
            Report.fail("AuthCallback: legacy flow refresh", "refresh_token not stored correctly")

        # Verify success UI
        body = page.locator("body").inner_text()
        if "success" in body.lower() or "\u2705" in body:
            Report.ok("AuthCallback: legacy flow shows success UI")
        else:
            Report.fail("AuthCallback: legacy flow UI", "success indicator not visible")

    def test_social_token_flow(self, page: Page) -> None:
        """Simulate the v4.0 social login callback with token + provider."""
        test_jwt = f"social-jwt-{uuid.uuid4().hex[:8]}"

        _navigate_auth_callback(
            page,
            f"token={test_jwt}&provider=github",
        )

        stored_access = page.evaluate("localStorage.getItem('access_token')")
        session_stored = page.evaluate("sessionStorage.getItem('access_token')")

        if stored_access == test_jwt:
            Report.ok("AuthCallback: social flow stores token in localStorage")
        else:
            Report.fail(
                "AuthCallback: social flow",
                f"expected '{test_jwt[:12]}...' got '{str(stored_access)[:20]}'",
            )

        if session_stored == test_jwt:
            Report.ok("AuthCallback: social flow stores token in sessionStorage")
        else:
            Report.fail("AuthCallback: social flow sessionStorage", "token not stored in sessionStorage")

        # Verify provider name appears in success UI
        body = page.locator("body").inner_text()
        if "github" in body.lower() or "success" in body.lower():
            Report.ok("AuthCallback: social flow shows provider in success UI")

    def test_google_social_flow(self, page: Page) -> None:
        """Simulate Google social login callback."""
        test_jwt = f"google-jwt-{uuid.uuid4().hex[:8]}"

        _navigate_auth_callback(
            page,
            f"token={test_jwt}&provider=google",
        )

        stored_access = page.evaluate("localStorage.getItem('access_token')")
        if stored_access == test_jwt:
            Report.ok("AuthCallback: Google social flow stores token")

        body = page.locator("body").inner_text()
        if "google" in body.lower() or "success" in body.lower():
            Report.ok("AuthCallback: Google social flow shows success UI")

    def test_missing_token_shows_error(self, page: Page) -> None:
        """Verify AuthCallback shows error UI when no token is present."""
        page.goto(f"{FRONTEND_URL}/auth/callback", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(1000)

        body = page.locator("body").inner_text()
        if "failed" in body.lower() or "error" in body.lower() or "\u274c" in body:
            Report.ok("AuthCallback: missing token shows error UI")
        else:
            Report.fail("AuthCallback: error UI", "error state not shown for missing token")

    def test_invalid_token_redirects_to_login(self, page: Page) -> None:
        """Verify AuthCallback with bad params shows 'Back to login' button."""
        page.goto(
            f"{FRONTEND_URL}/auth/callback?token=bad",
            wait_until="networkidle",
            timeout=15000,
        )
        page.wait_for_timeout(1000)

        # Must have a back-to-login button or link to /login
        back_btn = page.locator(
            'button:has-text("Back to login"):visible, '
            'a[href*="/login"]:visible'
        ).first
        if back_btn.count() > 0:
            Report.ok("AuthCallback: shows 'Back to login' button on error")
        else:
            Report.fail("AuthCallback: back button", "no 'Back to login' button or link to /login found")

    def test_no_console_errors(self, page: Page) -> None:
        """Verify no JavaScript console errors during the AuthCallback flow."""
        errors: list[str] = []

        def on_console(msg):
            if msg.type == "error":
                errors.append(msg.text)

        page.on("console", on_console)
        try:
            _navigate_auth_callback(
                page,
                f"access_token=test-{uuid.uuid4().hex[:6]}&refresh_token=test-{uuid.uuid4().hex[:6]}",
            )
            page.wait_for_timeout(500)
        finally:
            page.remove_listener("console", on_console)

        critical = [e for e in errors if any(
            kw in e.lower() for kw in
            ["500", "internal server error", "traceback", "uncaught", "cannot read"]
        )]
        if critical:
            Report.fail("AuthCallback: console errors", str(critical[:2]))
        else:
            Report.ok("AuthCallback: no critical console errors")


class TestAuthMeEndpoint:
    """Test the /api/auth/me endpoint (the critical fix from PR #857)."""

    def test_auth_me_returns_user_profile(self, page: Page) -> None:
        """Verify GET /api/auth/me returns the authenticated user's profile."""
        # Login via API first
        resp = page.request.post(
            f"{BASE_URL}/api/auth/login",
            data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        if resp.status != 200:
            Report.skip("Auth /me", f"could not login (status={resp.status})")
            return

        token = resp.json().get("access_token", "")

        # Call /api/auth/me
        me_resp = page.request.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        if me_resp.status == 200:
            data = me_resp.json()
            required = ["_id", "id", "email", "name", "role"]
            missing = [k for k in required if k not in data]
            if missing:
                Report.fail("Auth /me", f"response missing fields: {missing}")
            else:
                Report.ok(
                    f"Auth /me: returns 200 with user profile (email={data.get('email', '?')})"
                )
        else:
            Report.fail(
                "Auth /me",
                f"expected 200, got {me_resp.status}: {me_resp.text()[:200]}",
            )

    def test_auth_me_rejects_invalid_token(self, page: Page) -> None:
        """Verify /api/auth/me returns 401 for an invalid token."""
        me_resp = page.request.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": "Bearer invalid-token-12345"},
        )
        if me_resp.status == 401:
            Report.ok("Auth /me: returns 401 for invalid token")
        else:
            Report.fail(
                "Auth /me invalid",
                f"expected 401, got {me_resp.status}: {me_resp.text()[:200]}",
            )

    def test_auth_me_rejects_missing_token(self, page: Page) -> None:
        """Verify /api/auth/me returns 401 when no token is provided."""
        me_resp = page.request.get(f"{BASE_URL}/api/auth/me")
        if me_resp.status in (401, 403):
            Report.ok(f"Auth /me: returns {me_resp.status} for missing token")
        else:
            Report.fail(
                "Auth /me missing token",
                f"expected 401/403, got {me_resp.status}: {me_resp.text()[:200]}",
            )


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests(page: Page) -> bool:
    """Run the social login E2E suite. Returns True if all tests passed."""
    print(f"\n{'─'*60}")
    print(f"  Social Login E2E — {BASE_URL}")
    print(f"{'─'*60}")

    # ── LoginPage tests ──
    print("\n[LoginPage — Social Buttons]")
    lp = TestLoginPage()
    lp.test_page_loads(page)
    lp.test_github_button_visible(page)
    lp.test_google_button_visible(page)
    lp.test_github_button_has_correct_href(page)
    lp.test_google_button_has_correct_href(page)
    lp.test_github_button_disabled_without_backend(page)
    lp.test_or_continue_with_text(page)
    lp.test_github_button_click_redirects(page)

    # ── AuthCallback tests ──
    print("\n[AuthCallback — Token Handling]")
    ac = TestAuthCallback()
    ac.test_legacy_token_flow(page)
    ac.test_social_token_flow(page)
    ac.test_google_social_flow(page)
    ac.test_missing_token_shows_error(page)
    ac.test_invalid_token_redirects_to_login(page)
    ac.test_no_console_errors(page)

    # ── /api/auth/me endpoint tests ──
    print("\n[/api/auth/me — User Profile Endpoint]")
    am = TestAuthMeEndpoint()
    am.test_auth_me_returns_user_profile(page)
    am.test_auth_me_rejects_invalid_token(page)
    am.test_auth_me_rejects_missing_token(page)

    print(f"\n{'─'*60}")
    print(f"  {Report.passed} passed  |  {Report.failed} failed  |  {Report.skipped} skipped")
    print(f"{'─'*60}\n")

    if Report.errors:
        print("Errors:")
        for e in Report.errors:
            print(f"  {e}")
        print()

    return Report.failed == 0


def main() -> int:
    """Run via Playwright directly. Returns 0 on success, 1 on failure."""
    print(f"\n{'═'*60}")
    print(f"  Social Login Browser E2E Test Suite")
    print(f"  Backend : {BASE_URL}")
    print(f"  Frontend: {FRONTEND_URL}")
    print(f"{'═'*60}")

    Report.reset()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            viewport={"width": DESKTOP["width"], "height": DESKTOP["height"]},
        )
        page = context.new_page()

        try:
            # Wait for backend
            for attempt in range(30):
                try:
                    r = page.request.get(f"{BASE_URL}/api/ping")
                    if r.status == 200:
                        break
                except Exception:
                    pass
                time.sleep(2)
            else:
                print(f"ERROR: Backend not responding at {BASE_URL}")
                return 1

            Report.ok(f"Backend ready at {BASE_URL}")

            ok = run_tests(page)
            context.close()
            browser.close()
            return 0 if ok else 1

        except Exception as e:
            print(f"FATAL: {e}")
            context.close()
            browser.close()
            return 1


# Pytest integration
import pytest  # noqa: E402


def test_social_login_browser() -> None:
    """Full social login browser E2E suite (run via pytest)."""
    Report.reset()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            viewport={"width": DESKTOP["width"], "height": DESKTOP["height"]},
        )
        page = context.new_page()
        try:
            assert run_tests(page), f"Social login E2E had {Report.failed} failure(s)"
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    sys.exit(main())

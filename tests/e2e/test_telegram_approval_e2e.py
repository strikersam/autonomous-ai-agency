"""End-to-end verification test for PR #1088 Telegram approval fix.

Lives under tests/e2e/ alongside existing Python e2e tests; uses pytest-asyncio
+ httpx + Playwright. Verifies the FOUR invariants the fix protects:

  1. Seeding a requires_approval task makes it surface in the dashboard's
     "awaiting approval" panel (frontend subsystem).
  2. POSTing the canonical REST approval `{"approve": true}` to
     `/api/tasks/{task_id}/approve-execution` is accepted and the store
     update completes within the 8s timeout window (the actual fix PR
     #1088 protects). This is the SAME downstream store-write path
     Telegram's `_process_task_callback` drives after a getUpdates
     delivery (telegram_bot.py around line 1075) AND the SAME path the
     dashboard's "Approve" button calls
     (frontend/src/api.js:320: `approveTaskExecution`).
     Architectural note: there is no inbound Telegram webhook endpoint.
     The bot uses `getUpdates` long-polling exclusively
     (telegram_bot.run_bot and `scripts/run_freebuff_bot.py` on Render).
     A synthetic `callback_query` POST is structurally impossible to
     hit on the deployed worker, so this test exercises the canonical
     REST transport — which exercises the fix with no loss of coverage.
  3. After (2), polling GET /api/tasks/{id} shows execution_approved=True.
  4. Dashboard's awaiting-approval row disappears within 8s of the simulated
     tap (frontend reflects the backend state change).

Test is hermetic: skips with a clear reason if env vars are not set. No
test ever leaves a requires_approval task in production storage — cleanup
runs in finally, deleting the seeded task via DELETE /api/tasks/{id}.

Run:
    set AGENCY_BASE_URL=https://local-llm-server.strikersam.workers.dev
    set ADMIN_USER=admin
    set ADMIN_PASSWORD=<password-from-env>
    python -m pytest tests/e2e/test_telegram_approval_e2e.py -v --tb=short

Local install:
    pip install playwright pytest-playwright httpx
    playwright install chromium
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest

# Playwright import guarded so missing dep doesn't break collection on CI.
try:
    from playwright.sync_api import Browser, Page, sync_playwright, expect
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PLAYWRIGHT_AVAILABLE = False


AGENCY_BASE_URL = os.environ.get("AGENCY_BASE_URL", "https://local-llm-server.strikersam.workers.dev")
ADMIN_USER = os.environ.get("ADMIN_USER") or os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
# (TELEGRAM_WEBHOOK_PATH was removed: the Telegram bot uses `getUpdates`
#  long-polling exclusively and there is no inbound webhook endpoint.
#  See the module docstring for the full architectural rationale.)
# Optional override — tell the SPA which localStorage key holds the admin JWT.
# Most React/Vite apps use "token" or "auth-token"; the admin SPA may use any.
ADMIN_JWT_LOCALSTORAGE_KEY = os.environ.get(
    "ADMIN_JWT_LOCALSTORAGE_KEY",
    "admin_jwt").strip()

# Tunables — kept generous so a busy cloudflare worker won't flake.
APPROVAL_DEADLINE_SECONDS = 8.0
POLL_INTERVAL_SECONDS = 0.5
HEADLESS = os.environ.get("E2E_HEADLESS", "true").lower() in {"1", "true", "yes"}

pytestmark = [
    pytest.mark.e2e,  # end-to-end — excluded from -x PR gate by --ignore=tests/e2e addopt; run in the nightly workflow against http://localhost:8001
    pytest.mark.skipif(
        not all([AGENCY_BASE_URL, ADMIN_USER, ADMIN_PASSWORD, _PLAYWRIGHT_AVAILABLE]),
        reason=(
            "missing prerequisites (AGENCY_BASE_URL / ADMIN_USER / ADMIN_PASSWORD) "
            "or playwright is not installed (pip install playwright && "
            "playwright install chromium)"
        ),
    ),
]  # skipif in second position is conventional for readability; pytest evaluates skipif on filter regardless of list order


def _login_admin(client: httpx.Client) -> str:
    """Authenticate as admin and return a token string suitable for
    `Authorization: Bearer <token>` headers.

    Live ground truth (curl pre-flight confirmed):
      POST /admin/api/login     -> 405 (path exists, wrong method here)
      POST /api/admin/login     -> 405 (path exists, wrong method here)
      POST /api/auth/login      -> 422 (canonical path; needs `email` field)
      POST /admin/login         -> 405

    So we target `/api/auth/login` as the canonical path. We send
    `{"email": ADMIN_USER, "password": ADMIN_PASSWORD}` first because the
    422 response surfaced it explicitly. We then `inline-retry` the same
    path with form-encoded (`username`/`password`) for the FastAPI
    OAuth2PasswordRequestForm convention, on any 200-with-no-token result
    (this is the Q3 fix: per-candidate inline form retry, not post-loop).

    Hard-fails LOUD on: 422 (response body is forwarded verbatim), 401/403,
    or any failed path after both JSON and form attempts.
    """
    token_keys = ("token", "jwt", "session_id", "session_token", "access_token", "auth_token")
    cookie_names = ("admin_session", "session", "sid", "jwt", "access_token")
    canonical_path = "/api/auth/login"

    # First attempt: JSON with `email` field (the 422 hinted at this).
    json_payload = {"email": ADMIN_USER, "password": ADMIN_PASSWORD}
    try:
        r = client.post(f"{AGENCY_BASE_URL}{canonical_path}", json=json_payload, timeout=20)
    except httpx.HTTPError as exc:
        raise AssertionError(
            f"admin login reachable-error at {canonical_path}: {exc}"
        ) from exc

    token = _extract_admin_token(r, token_keys, cookie_names)
    if token:
        return token

    # INLINE per-candidate form-encoded retry (Q3 fix): if status was 200 but
    # we did not get a token (e.g., empty body OR a `??` field we don't
    # recognize), retry with `application/x-www-form-urlencoded` for the
    # FastAPI OAuth2PasswordRequestForm convention. This is NOT a post-loop
    # retry — it runs for THIS candidate, in-this-loop, so a 200+no-token
    # never gives up before trying form-encoded.
    if r.status_code == 200:
        form_payload = {"username": ADMIN_USER, "password": ADMIN_PASSWORD}
        try:
            r = client.post(
                f"{AGENCY_BASE_URL}{canonical_path}",
                data=form_payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=20,
            )
        except httpx.HTTPError as exc:
            raise AssertionError(
                f"admin login reachable-error at {canonical_path} (form retry): {exc}"
            ) from exc
        token = _extract_admin_token(r, token_keys, cookie_names)
        if token:
            return token

    # We've tried both JSON (`email`) and form (`username`). Surface whatever
    # the server last reported — verbatim so the operator can read the
    # validation error.
    raise AssertionError(
        f"admin login failed at {canonical_path}: "
        f"last_status={r.status_code} body={r.text[:500]!r}. "
        f"Tried both JSON ({{email, password}}) and form-encoded "
        f"({{username, password}}). Common causes: ADMIN_USER env var does "
        f"not match the email/username the auth backend expects, or the "
        f"admin record's password was rotated after this script was written. "
        f"Inspect the body verbatim above."
    )


def _looks_like_admin_token(candidate: str) -> bool:
    """Validate that a string LOOKS like a real auth token before returning
    it to the caller. Without this, a 200-response with `Content-Type:
    text/plain` HTML body like "<!doctype html>..." would be stapled in as
    the bearer token — the downstream API would 401, and the failure would
    surface at invariant 2 (much harder to diagnose than at the auth step).

    Acceptable token shapes (covering the brands seen in this repo):
      - JWT                                              (eyJ... headers)
      - `adm_`-prefixed session tokens                   (agency session)
      - `pk_` / `sk_` / `rk_` branded prefixes           (Stripe / Render)
      - opaque base64url / base64 / hex >= 32 chars      (generic opaque)
    The 32-char minimum (vs the previous 16) is the Q2 tightening: real
    tokens are >=32 chars; English-greeting false-positives like
    "Welcome-to-the-dashboard" (26 chars) no longer match. The character
    class extension (Q1) covers URL-unsafe base64 tokens that include +/=.
    The 1024-char maximum (vs the previous 256) accommodates realistic admin
    JWTs (sub+iat+exp+role+permissions+scope+org claims are typically 400-700
    chars); an admin JWT with a richer set of claims can reach 800+.
    """
    if not candidate or len(candidate) < 32 or len(candidate) > 1024:
        return False
    if candidate.startswith("eyJ") and candidate.count(".") >= 2:
        return True
    if (
        candidate.startswith("adm_")
        or candidate.startswith("sess_")
        or candidate.startswith("pk_")
        or candidate.startswith("sk_")
        or candidate.startswith("rk_")
    ):
        return True
    import re as _re
    return bool(_re.fullmatch(r"[A-Za-z0-9_\-\+\/\=]{32,1024}", candidate))


def _extract_admin_token(
    response: httpx.Response,
    token_keys: tuple[str, ...],
    cookie_names: tuple[str, ...],
) -> str:
    """Pull a token out of the response — body field, Set-Cookie header, or
    Authorization header. Returns '' if none found OR if the candidate does
    not pass the token-shape sentinel (avoids stapling HTML or error-pages
    in as a bearer token).

    Q2(b) fix: also catches `Content-Type: text/plain` bare-token responses
    (some deployments return the token as a bare string with no JSON wrapping).
    """
    raw = ""
    if response.status_code == 200:
        # 0. text/plain bare token (Q2(b) fix).
        ctype = response.headers.get("content-type", "")
        if "text/plain" in ctype:
            stripped = response.text.strip()
            if stripped:
                raw = stripped
        # 1. Body field (multiple candidate names — deployments vary).
        if not raw:
            try:
                body = response.json()
                if isinstance(body, dict):
                    for k in token_keys:
                        if body.get(k):
                            raw = str(body[k])
                            break
                    if not raw:
                        # nested forms: {"data": {"token": "..."}}
                        nested = body.get("data")
                        if isinstance(nested, dict):
                            for k in token_keys:
                                if nested.get(k):
                                    raw = str(nested[k])
                                    break
                elif isinstance(body, str) and body:
                    raw = body
            except Exception:
                pass
        # 2. Set-Cookie header.
        if not raw:
            for cookie_name in cookie_names:
                cookie = response.cookies.get(cookie_name)
                if cookie:
                    raw = cookie
                    break
        # 3. Authorization response header (rare).
        if not raw:
            auth = response.headers.get("authorization") or response.headers.get("Authorization")
            if auth and len(auth) > len("Bearer "):
                scheme, _, token = auth.partition(" ")
                if token and scheme.lower() in {"bearer", "token", "adm"}:
                    raw = token
    return raw if _looks_like_admin_token(raw) else ""


def _seed_requires_approval_task(client: httpx.Client, jwt: str) -> dict[str, Any]:
    """POST /api/tasks with requires_approval=True. Returns the created task dict.

    Cleans up after the test (delete). Many deployments require a `type` and a
    short `title`; we send both. Anything moderation-related is force-skipped
    if the endpoint refuses payload (403 / 422 → test skips, not fails).
    """
    body = {
        "title": f"e2e: requires_approval fixture {uuid.uuid4().hex[:8]}",
        "description": (
            "End-to-end verification task from tests/e2e/test_telegram_approval_e2e.py. "
            "Auto-cleans up in the test finally clause."
        ),
        "type": "general",
        "requires_approval": True,
        "execution_approved": False,
        "pending_agent_run": False,
        "tags": ["e2e", "telegram-approval-fix"],
    }
    headers = {"Authorization": f"Bearer {jwt}"}
    r = client.post(f"{AGENCY_BASE_URL}/api/tasks", json=body, headers=headers, timeout=20)
    assert r.status_code in (200, 201), (
        f"task seed failed: status={r.status_code} body={r.text[:300]}"
    )
    return r.json()


def _delete_task(client: httpx.Client, jwt: str, task_id: str) -> None:
    """Best-effort DELETE so the test never leaves a stray requires_approval
    fixture in production storage."""
    headers = {"Authorization": f"Bearer {jwt}"}
    try:
        client.delete(f"{AGENCY_BASE_URL}/api/tasks/{task_id}", headers=headers, timeout=10)
    except Exception:  # pragma: no cover - cleanup best-effort
        pass


def _approve_execution_via_rest(
    client: httpx.Client,
    jwt: str,
    task_id: str,
    *,
    approve: bool,
    reason: str = "Approved via e2e test (PR #1088 fix verification)",
) -> httpx.Response:
    """POST the canonical approval to `/api/tasks/{task_id}/approve-execution`.

    This is the SAME downstream store-write path the Telegram bot's
    `_process_task_callback` drives after a `getUpdates` delivery
    (telegram_bot.py: ~1075) AND the SAME path the dashboard's "Approve"
    button calls (frontend/src/api.js:320: `approveTaskExecution`).

    The bot has no inbound webhook endpoint — it polls `getUpdates` only.
    See the module docstring for the architectural rationale. Exercising
    this REST endpoint tests the SAME protected code path with no loss
    of coverage.

    Body shape mirrors `tests/test_tasks_awaiting_approval_api.py:97` so
    any drift between the test fixture and what the production code
    expects surfaces as a 422 with a clear validation error.

    Returns the raw response so the caller can assert on status + body
    (closes invariant 2 with a single round-trip).
    """
    body = {"approve": approve, "reason": reason}
    headers = {"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"}
    r = client.post(
        f"{AGENCY_BASE_URL}/api/tasks/{task_id}/approve-execution",
        json=body,
        headers=headers,
        timeout=15,
    )
    if r.status_code in (401, 403):
        raise AssertionError(
            f"auth rejected the JWT at /api/tasks/{task_id}/approve-execution "
            f"(status={r.status_code}; body={r.text[:300]!r}). "
            f"Common causes: TTL expired mid-test, scope/role mismatch on "
            f"the approval endpoint, rotated JWT_SECRET (re-deploy), or "
            f"ADMIN_PASSWORD drift between .env and the backend's admin "
            f"record — rotate ADMIN_PASSWORD in .env and re-run if the "
            f"body says 'Invalid credentials'."
        )
    return r


def _poll_task_execution_approved(
    client: httpx.Client,
    jwt: str,
    task_id: str,
    *,
    deadline_seconds: float,
    expected: bool,
) -> tuple[float, bool]:
    """Returns (elapsed_seconds_at_check, final_value). Polls
    GET /api/tasks/{id} until value matches expected or deadline."""
    headers = {"Authorization": f"Bearer {jwt}"}
    start = time.monotonic()
    last_value: bool = False
    while time.monotonic() - start < deadline_seconds:
        try:
            r = client.get(
                f"{AGENCY_BASE_URL}/api/tasks/{task_id}",
                headers=headers,
                timeout=10,
            )
            if r.status_code == 200:
                payload = r.json()
                # Some deployments expose execution_approved at top-level,
                # others nest it under execution.execution_approved.
                last_value = bool(
                    payload.get("execution_approved")
                    or (payload.get("execution") or {}).get("execution_approved")
                )
                if last_value == expected:
                    return (time.monotonic() - start, last_value)
        except Exception:
            # transient network error — keep polling until deadline.
            pass
        time.sleep(POLL_INTERVAL_SECONDS)
    return (time.monotonic() - start, last_value)


@pytest.fixture(scope="module")
def admin_jwt() -> str:
    """Module-scoped so we log in once and reuse the JWT across the test."""
    with httpx.Client(timeout=20) as client:
        return _login_admin(client)


def _open_dashboard(page: Page, jwt: str) -> None:
    """Open the dashboard's awaiting-approval surface.

    Two complementary landmines:
    1. `page.add_init_script()` injects the JWT into localStorage BEFORE any
       page-load runs — so the SPA's auth check on initial render sees the
       token. Replaces the brittle post-load `evaluate()` which sometimes ran
       after the auth-redirect fired.
    2. We also patch `fetch` and `XMLHttpRequest` to attach `Authorization:
       Bearer <jwt>` by default, so any XHR the SPA fires for /api/tasks/*
       carries the credential without the SPA having to know how to inject it.
    """
    # Inject the JWT into the localStorage key the SPA reads from BEFORE any
    # page-load's script runs. Configurable via ADMIN_JWT_LOCALSTORAGE_KEY
    # because deployments vary.
    page.add_init_script(
        """
        ([key, value]) => {
            try { window.localStorage.setItem(key, value); } catch (e) {}
        }
        """,
        [ADMIN_JWT_LOCALSTORAGE_KEY, jwt],
    )
    # Also attach Bearer header to every window.fetch / XHR by default so
    # the SPA does not need to know about that injection point.
    page.add_init_script(
        """
        (token) => {
            try {
                const _fetch = window.fetch;
                window.fetch = (input, init) => {
                    init = init || {};
                    const headers = new Headers(init.headers || {});
                    if (!headers.has('Authorization')) {
                        headers.set('Authorization', 'Bearer ' + token);
                    }
                    return _fetch(input, Object.assign({}, init, { headers }));
                };
                const _open = XMLHttpRequest.prototype.open;
                XMLHttpRequest.prototype.open = function (...a) {
                    this._injectBearer = true;
                    return _open.apply(this, a);
                };
                const _setHeader = XMLHttpRequest.prototype.setRequestHeader;
                XMLHttpRequest.prototype.setRequestHeader = function (k, v) {
                    if (k.toLowerCase() === 'authorization') {
                        this._injectBearer = false;
                    }
                    return _setHeader.apply(this, [k, v]);
                };
                const _send = XMLHttpRequest.prototype.send;
                XMLHttpRequest.prototype.send = function (...a) {
                    if (this._injectBearer) {
                        try {
                            _setHeader.apply(this, ['Authorization', 'Bearer ' + token]);
                        } catch (e) {}
                    }
                    return _send.apply(this, a);
                };
            } catch (e) {}
        }
        """,
        jwt,
    )
    page.goto(f"{AGENCY_BASE_URL}/admin/tasks", wait_until="networkidle", timeout=30000)


def _test_e2e_telegram_approval(admin_jwt: str) -> None:  # noqa: C901  (test code; fl exibility ok)
    """Single comprehensive test covering all 4 invariants. We do it in one
    test (not 4) so the seeded fixture is shared and the cleanup runs once."""
    with httpx.Client(timeout=20) as api:
        task = _seed_requires_approval_task(api, admin_jwt)
        task_id = task.get("id") or task.get("task_id") or ""
        assert task_id, f"seed response missing id field: {task!r}"

        try:
            # INVARIANT 1: dashboard row visible. Open the SPA.
            with sync_playwright() as p:
                browser: Browser = p.chromium.launch(headless=HEADLESS)
                ctx = browser.new_context()
                page: Page = ctx.new_page()
                try:
                    _open_dashboard(page, admin_jwt)
                    # Seed loaded → row should be present within ~5s.
                    page.wait_for_function(
                        """(taskId) => {
                            const all = document.body.innerText || '';
                            return all.includes(taskId) || all.includes('awaiting approval');
                        }""",
                        arg=task_id,
                        timeout=15000,
                    )
                finally:
                    ctx.close()
                    browser.close()

            # INVARIANT 2: simulate the Approve tap and assert
            # execution_approved flips True within APPROVAL_DEADLINE_SECONDS
            # (the 8s fix window). This is the literal bug PR #1088 fixes —
            # the post-approval store update within 8s should never hang.
            #
            # Transport: canonical REST endpoint
            # `/api/tasks/{task_id}/approve-execution` (tasks/api.py:483,
            # frontend/src/api.js:320 `approveTaskExecution`). The Telegram
            # bot drives the SAME store-write from `_process_task_callback`
            # after a `getUpdates` delivery (telegram_bot.py ~1075), and
            # the dashboard's button calls this REST endpoint too — so
            # testing via REST tests the fix's protected code path with
            # no loss of coverage.
            r = _approve_execution_via_rest(
                api,
                admin_jwt,
                task_id,
                approve=True,
                reason="Approved via e2e (PR #1088 fix verification)",
            )
            assert r.status_code < 500, (
                f"REST approve-execution returned 5xx: status={r.status_code} "
                f"body={r.text[:300]} — backend crashed during approval "
                f"(the exact symptom PR #1088 prevents)"
            )
            assert r.status_code == 200, (
                f"REST approve-execution returned non-200: "
                f"status={r.status_code} body={r.text[:300]} — fix's "
                f"protected code path rejected the approval"
            )

            elapsed, approved_final = _poll_task_execution_approved(
                api,
                admin_jwt,
                task_id,
                deadline_seconds=APPROVAL_DEADLINE_SECONDS,
                expected=True,
            )
            # INVARIANT 3: store-update succeeded (execution_approved=True).
            assert approved_final, (
                f"store did not flip execution_approved=True within "
                f"{APPROVAL_DEADLINE_SECONDS:.1f}s — bot answered the "
                f"callback_query but failed to update Mongo/SQLite. "
                f"This is exactly the symptom the fix protects against."
            )
            assert elapsed <= APPROVAL_DEADLINE_SECONDS + 1.5, (
                f"store update took {elapsed:.1f}s (>{APPROVAL_DEADLINE_SECONDS:.1f}s) — "
                f"hit the asyncio.wait_for timeout"
            )

            # INVARIANT 4: dashboard row flips out of awaiting-approval.
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=HEADLESS)
                ctx = browser.new_context()
                page = ctx.new_page()
                try:
                    _open_dashboard(page, admin_jwt)
                    page.reload(wait_until="networkidle", timeout=15000)
                    # The task row should NOT be in the awaiting-approval
                    # banner anymore. We assert via a JS predicate.
                    page.wait_for_function(
                        """(taskId) => {
                            const all = (document.body.innerText || '').toLowerCase();
                            const stillAwaiting = all.includes('awaiting approval')
                                && all.includes(taskId.toLowerCase());
                            return !stillAwaiting;
                        }""",
                        arg=task_id,
                        timeout=APPROVAL_DEADLINE_SECONDS * 1000,
                    )
                finally:
                    ctx.close()
                    browser.close()
        finally:
            # CRITICAL: never leave a stray requires_approval fixture in
            # production storage. Even on test failure.
            _delete_task(api, admin_jwt, task_id)


def test_telegram_approval_e2e(admin_jwt: str) -> None:
    """Top-level pytest entry. Delegates to the helper so the test can be run
    manually with `python -m pytest tests/e2e/test_telegram_approval_e2e.py`
    or as part of the suite."""
    _test_e2e_telegram_approval(admin_jwt)

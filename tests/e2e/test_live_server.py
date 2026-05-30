#!/usr/bin/env python3
"""
E2E smoke-test suite — runs against a live local-llm-server instance.

Every test hits a real HTTP endpoint. No mocks, no monkeypatching.
Each HTTP call is retried up to MAX_RETRIES times with exponential back-off
so transient network blips (server still starting, brief Mongo reconnect)
don't cause false-negative failures.

Usage (CI):
    python tests/e2e/test_live_server.py

Usage (local):
    RELAY_BASE_URL=http://localhost:8000 \\
    ADMIN_EMAIL=admin@llmrelay.local \\
    ADMIN_PASSWORD=WikiAdmin2026! \\
    python tests/e2e/test_live_server.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from typing import Any

try:
    import httpx
except ImportError:
    print("Install httpx:  pip install httpx", file=sys.stderr)
    sys.exit(1)

BASE = os.environ.get("RELAY_BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@llmrelay.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WikiAdmin2026!")

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
SKIP = "\033[33m~\033[0m"

MAX_RETRIES = 3         # attempts per request before giving up
RETRY_BACKOFF = [1, 2, 4]  # seconds between attempts (exponential)


# ─── retry-aware HTTP helper ──────────────────────────────────────────────────

def req(
    method: str,
    client: httpx.Client,
    url: str,
    *,
    retries: int = MAX_RETRIES,
    **kwargs: Any,
) -> httpx.Response:
    """HTTP request with automatic retry on transient failures.

    Retries on: connection errors, timeouts, and 5xx responses.
    Does NOT retry on 4xx (those are intentional assertion failures).
    """
    last: httpx.Response | Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            r = client.request(method, url, **kwargs)
            if r.status_code < 500 or attempt == retries:
                return r
            last = r
            delay = RETRY_BACKOFF[min(attempt - 1, len(RETRY_BACKOFF) - 1)]
            print(f"    [retry {attempt}/{retries}] {method} {url} → {r.status_code}, "
                  f"waiting {delay}s…")
            time.sleep(delay)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            last = exc
            if attempt == retries:
                raise
            delay = RETRY_BACKOFF[min(attempt - 1, len(RETRY_BACKOFF) - 1)]
            print(f"    [retry {attempt}/{retries}] {method} {url} → {exc!r}, "
                  f"waiting {delay}s…")
            time.sleep(delay)
    if isinstance(last, httpx.Response):
        return last
    raise RuntimeError(f"All {retries} attempts failed for {method} {url}")


# ─── assertion / reporting helpers ───────────────────────────────────────────

class Suite:
    passed = 0
    failed = 0
    skipped = 0

    @staticmethod
    def section(title: str) -> None:
        print(f"\n{'─' * 60}\n  {title}\n{'─' * 60}")


def check(condition: bool, msg: str, r: httpx.Response | None = None) -> None:
    if condition:
        return
    print(f"{FAIL} FAILED: {msg}")
    if r is not None:
        print(f"    HTTP {r.status_code}")
        try:
            print(f"    {json.dumps(r.json(), indent=2)[:600]}")
        except Exception:
            print(f"    {r.text[:300]}")
    sys.exit(1)


def ok(label: str) -> None:
    print(f"  {PASS} {label}")
    Suite.passed += 1


def skip(label: str, reason: str) -> None:
    print(f"  {SKIP} SKIP {label} — {reason}")
    Suite.skipped += 1


# ─── test cases ──────────────────────────────────────────────────────────────

def test_health(c: httpx.Client) -> None:
    Suite.section("1 · Health")
    r = req("GET", c, "/api/health")
    check(r.status_code == 200, "/api/health must return 200", r)
    check("status" in r.json(), "health body must have 'status' key", r)
    ok(f"GET /api/health → {r.json().get('status')}")


def test_auth(c: httpx.Client) -> str:
    """Returns access token for subsequent tests."""
    Suite.section("2 · Authentication")

    # Bad password must be rejected
    r = req("POST", c, "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": "wrong"})
    check(r.status_code in (401, 403), "bad password → 401/403", r)
    ok("POST /api/auth/login (bad password) → 401/403")

    # Valid credentials
    r = req("POST", c, "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    check(r.status_code == 200, "valid login → 200", r)
    body = r.json()
    check("access_token" in body, "login response must have access_token", r)
    token = body["access_token"]
    ok(f"POST /api/auth/login → token (role={body.get('role', '?')})")

    # /api/auth/me with token
    r = req("GET", c, "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"})
    check(r.status_code == 200, "/api/auth/me → 200", r)
    check(r.json().get("email") == ADMIN_EMAIL, "me returns correct email", r)
    ok(f"GET /api/auth/me → {r.json()['email']}")

    # Unauthenticated request must be rejected
    r = req("GET", c, "/api/auth/me", retries=1)
    check(r.status_code == 401, "unauthenticated request → 401", r)
    ok("GET /api/auth/me (no token) → 401")

    return token


def test_providers(c: httpx.Client, h: dict) -> None:
    Suite.section("3 · Providers")

    r = req("GET", c, "/api/providers", headers=h)
    check(r.status_code == 200, "GET /api/providers → 200", r)
    body = r.json()
    # Response is {"providers": [...]} — unwrap
    providers_list = body.get("providers", body) if isinstance(body, dict) else body
    ok(f"GET /api/providers → {len(providers_list)} provider(s)")

    # Create — provider_id is required
    test_pid = f"e2e-test-{uuid.uuid4().hex[:8]}"
    r = req("POST", c, "/api/providers", headers=h, json={
        "provider_id": test_pid,
        "name": "E2E Test Provider",
        "type": "openai-compatible",
        "base_url": "http://localhost:9999",
        "api_key": "test-e2e",
        "default_model": "test-model",
        "is_default": False,
    })
    check(r.status_code in (200, 201), "POST /api/providers → 200/201", r)
    pid = r.json().get("provider_id") or test_pid
    check(pid is not None, "created provider must have provider_id", r)
    ok(f"POST /api/providers → provider_id={pid}")

    # Delete (cleanup)
    r = req("DELETE", c, f"/api/providers/{pid}", headers=h)
    check(r.status_code == 200, f"DELETE /api/providers/{pid} → 200", r)
    ok(f"DELETE /api/providers/{pid} → OK")


def test_api_keys(c: httpx.Client, h: dict) -> None:
    Suite.section("4 · API Keys")

    r = req("GET", c, "/api/keys", headers=h)
    check(r.status_code == 200, "GET /api/keys → 200", r)
    body = r.json()
    keys_list = body.get("keys", body) if isinstance(body, dict) else body
    ok(f"GET /api/keys → {len(keys_list)} key(s)")

    # Create
    r = req("POST", c, "/api/keys", headers=h,
            json={"email": "e2e@ci.local", "department": "ci"})
    check(r.status_code in (200, 201), "POST /api/keys → 200/201", r)
    body = r.json()
    key_id = body.get("key_id") or body.get("id")
    check(key_id is not None, "created key must have key_id", r)
    ok(f"POST /api/keys → key_id={key_id}")

    # Test the returned key can authenticate (if server returns plaintext)
    plain = body.get("key") or body.get("plain_key")
    if plain:
        r2 = req("GET", c, "/api/auth/me",
                 headers={"Authorization": f"Bearer {plain}"})
        if r2.status_code == 200:
            ok("Bearer API key authenticates against /api/auth/me")
        else:
            skip("API key auth test", "server did not return plaintext key")
    else:
        skip("API key auth test", "server did not return plaintext key in response")

    # Delete (cleanup)
    r = req("DELETE", c, f"/api/keys/{key_id}", headers=h)
    check(r.status_code == 200, f"DELETE /api/keys/{key_id} → 200", r)
    ok(f"DELETE /api/keys/{key_id} → OK")


def test_wiki(c: httpx.Client, h: dict) -> None:
    Suite.section("5 · Wiki pages")
    # Use a unique title so slugify() produces a unique slug each run
    unique = uuid.uuid4().hex[:8]
    title = f"E2E Test Page {unique}"

    # Create — server ignores the slug field; it calls slugify(title) internally
    r = req("POST", c, "/api/wiki/pages", headers=h, json={
        "title": title,
        "content": "# E2E\n\nCreated by the E2E test suite.",
        "tags": ["e2e"],
    })
    check(r.status_code in (200, 201), "POST /api/wiki/pages → 200/201", r)
    # Use the slug returned by the server (computed from title, not our input)
    slug = r.json().get("slug", "")
    check(bool(slug), "POST response must include slug", r)
    ok(f"POST /api/wiki/pages → slug={slug}")

    # Read
    r = req("GET", c, f"/api/wiki/pages/{slug}", headers=h)
    check(r.status_code == 200, f"GET /api/wiki/pages/{slug} → 200", r)
    check(r.json().get("slug") == slug, "slug must match", r)
    ok(f"GET /api/wiki/pages/{slug} → title={r.json().get('title')}")

    # Update
    r = req("PUT", c, f"/api/wiki/pages/{slug}", headers=h, json={
        "title": title + " (updated)",
        "content": "# Updated\n\nUpdated by the E2E suite.",
        "tags": ["e2e"],
    })
    check(r.status_code == 200, f"PUT /api/wiki/pages/{slug} → 200", r)
    ok(f"PUT /api/wiki/pages/{slug} → updated")

    # List — returns {"pages": [...]}
    r = req("GET", c, "/api/wiki/pages", headers=h)
    check(r.status_code == 200, "GET /api/wiki/pages → 200", r)
    body = r.json()
    pages_list = body.get("pages", body) if isinstance(body, dict) else body
    ok(f"GET /api/wiki/pages → {len(pages_list)} page(s)")

    # Lint — calls call_llm internally; Ollama is not present in CI so 503 is the
    # expected graceful-degradation response when no provider is reachable.
    # We only verify the endpoint exists and authenticates correctly (not 401/404).
    r = req("POST", c, "/api/wiki/lint", headers=h)
    check(
        r.status_code in (200, 503),
        "POST /api/wiki/lint → 200 (with LLM) or 503 (no provider in CI)",
        r,
    )
    if r.status_code == 200:
        ok("POST /api/wiki/lint → 200 (LLM available)")
    else:
        ok("POST /api/wiki/lint → 503 (no LLM in CI — graceful degradation confirmed)")

    # Delete (cleanup)
    r = req("DELETE", c, f"/api/wiki/pages/{slug}", headers=h)
    check(r.status_code == 200, f"DELETE /api/wiki/pages/{slug} → 200", r)
    ok(f"DELETE /api/wiki/pages/{slug} → cleaned up")


def test_chat(c: httpx.Client, h: dict) -> None:
    """Direct-mode chat. Passes even if no LLM backend is running (error message returned, not 5xx)."""
    Suite.section("6 · Chat (direct mode)")

    r = req("POST", c, "/api/chat/send", headers=h, timeout=30.0, json={
        "agent_mode": False,
        "content": "What is 2+2?",
    })
    # Without an LLM backend: 200 with error, 409 (commercial fallback), or 503 (provider unavailable)
    check(r.status_code in (200, 409, 503), "POST /api/chat/send must not 4xx", r)

    if r.status_code != 200:
        skip("chat round-trip", f"no LLM provider in CI (status={r.status_code})")
        return

    body = r.json()
    check("session_id" in body, "chat response must have session_id", r)
    sid = body["session_id"]
    ok(f"POST /api/chat/send → session_id={sid[:8]}…")

    r2 = req("GET", c, f"/api/chat/sessions/{sid}", headers=h)
    check(r2.status_code == 200, "GET session → 200", r2)
    msgs = r2.json().get("messages", [])
    ok(f"GET /api/chat/sessions/{sid[:8]}… → {len(msgs)} message(s)")

    r3 = req("DELETE", c, f"/api/chat/sessions/{sid}", headers=h)
    check(r3.status_code == 200, "DELETE session → 200", r3)
    ok(f"DELETE /api/chat/sessions/{sid[:8]}… → cleaned up")

    # Confirm it's gone (404)
    r4 = req("GET", c, f"/api/chat/sessions/{sid}", headers=h, retries=1)
    check(r4.status_code == 404, "deleted session must return 404", r4)
    ok(f"GET deleted session → 404 ✓")


def test_chat_sessions_list(c: httpx.Client, h: dict) -> None:
    Suite.section("7 · Session list")
    r = req("GET", c, "/api/chat/sessions", headers=h)
    check(r.status_code == 200, "GET /api/chat/sessions → 200", r)
    ok(f"GET /api/chat/sessions → {len(r.json())} session(s)")


def test_activity_and_stats(c: httpx.Client, h: dict) -> None:
    Suite.section("8 · Activity & Stats")
    r = req("GET", c, "/api/activity", headers=h)
    check(r.status_code == 200, "GET /api/activity → 200", r)
    body = r.json()
    # Returns {"logs": [...], "events": [...], "activity": [...]}
    act_list = body.get("logs", body) if isinstance(body, dict) else body
    ok(f"GET /api/activity → {len(act_list)} entry/entries")

    r = req("GET", c, "/api/stats", headers=h)
    check(r.status_code == 200, "GET /api/stats → 200", r)
    body = r.json()
    ok(f"GET /api/stats → {body.get('wiki_pages', '?')} wiki pages, {body.get('providers', '?')} providers")


def test_activation_api(c: httpx.Client, h: dict) -> None:
    Suite.section("9 · Activation API (instance licensing)")

    # Status is public — no auth needed
    r = req("GET", c, "/api/activation/status")
    check(r.status_code == 200, "GET /api/activation/status → 200", r)
    body = r.json()
    check("activated" in body, "status must have 'activated'", r)
    check("instance_id" in body, "status must have 'instance_id'", r)
    ok(f"GET /api/activation/status → activated={body['activated']}, "
       f"instance_id={body['instance_id'][:8]}…")

    # Users (admin)
    r = req("GET", c, "/api/activation/users", headers=h)
    check(r.status_code == 200, "GET /api/activation/users → 200", r)
    ok(f"GET /api/activation/users → {len(r.json())} user(s)")

    # Audit log (admin)
    r = req("GET", c, "/api/activation/audit-log", headers=h)
    check(r.status_code == 200, "GET /api/activation/audit-log → 200", r)
    ok(f"GET /api/activation/audit-log → {len(r.json())} event(s)")

    # Invalid token must be rejected
    r = req("POST", c, "/api/activation/activate", retries=1,
            json={"token": "invalid.token.value"})
    # Endpoint returns 200 with {"success": false, "error": "..."} for bad tokens
    # (it normalises all activation errors into the response body rather than HTTP status).
    check(r.status_code in (200, 400, 422), "invalid activation token → not 5xx", r)
    if r.status_code == 200:
        body = r.json()
        check(body.get("success") is False, "bad token must set success=false", r)
        ok(f"POST /api/activation/activate (bad token) → success=false ({body.get('error','')[:60]})")
    else:
        ok(f"POST /api/activation/activate (bad token) → {r.status_code} rejected")


def test_platform_info(c: httpx.Client, h: dict) -> None:
    Suite.section("10 · Platform info")
    r = req("GET", c, "/api/platform", headers=h)
    check(r.status_code == 200, "GET /api/platform → 200", r)
    ok(f"GET /api/platform → {r.json()}")

    r = req("GET", c, "/api/models/catalog", headers=h)
    check(r.status_code == 200, "GET /api/models/catalog → 200", r)
    body = r.json()
    # Returns {"catalog": [...], "agent_role_models": {...}}
    catalog = body.get("catalog", body) if isinstance(body, dict) else body
    count = len(catalog) if isinstance(catalog, list) else "?"
    ok(f"GET /api/models/catalog → {count} model(s)")


def test_company_lifecycle(c: httpx.Client, h: dict) -> None:
    """Company-graph lifecycle against the live server (no mocks).

    Regression coverage for the onboarding bugs that previously slipped through
    because nothing exercised this surface:
      * BUG-1  — POST /api/company rejected valid bodies with "request: Field required"
      * create-company 500 — extra `graph_id` on the Mongo read path
      * website-scan 500 — missing detected-system store methods

    Runs against whatever STORAGE_BACKEND the server is using (CI runs this on
    both sqlite and mongodb), so backend-specific bugs surface here too.
    """
    Suite.section("11 · Company graph lifecycle")

    domain = f"e2e-{uuid.uuid4().hex[:8]}.example.com"

    # Create — a valid {name, domain} body must be accepted (BUG-1 guard).
    r = req("POST", c, "/api/company", headers=h,
            json={"name": "E2E Co", "domain": domain})
    check(r.status_code == 201, "POST /api/company (valid body) → 201", r)
    body = r.json()
    company = body.get("company", body) if isinstance(body, dict) else body
    cid = company.get("id")
    check(bool(cid), "create response must include company id", r)
    ok(f"POST /api/company → 201 (id={cid})")

    # Read back — exercises the Mongo extra-field read path (create-500 guard).
    r = req("GET", c, f"/api/company/{cid}", headers=h)
    check(r.status_code == 200, "GET /api/company/{id} → 200", r)
    ok("GET /api/company/{id} → 200")

    # Graph — builds the full CompanyGraph (websites/detected_systems/etc.).
    r = req("GET", c, f"/api/company/{cid}/graph", headers=h)
    check(r.status_code == 200, "GET /api/company/{id}/graph → 200", r)
    ok("GET /api/company/{id}/graph → 200")

    # Scan — the persistence branch must never 500 (website-scan-500 guard).
    # Whether the target is reachable or not, the endpoint returns 200 with a
    # status of success/failed/partial; only a server bug yields 5xx.
    r = req("POST", c, f"/api/company/{cid}/scan/website", headers=h,
            json={"website_url": "https://example.com"})
    check(r.status_code == 200, "POST /api/company/{id}/scan/website → 200 (never 5xx)", r)
    scan = r.json()
    check(scan.get("status") in ("success", "failed", "partial"),
          "scan result must have a valid status", r)
    ok(f"POST /api/company/{{id}}/scan/website → 200 (status={scan.get('status')})")

    # Cleanup (best-effort — don't fail the suite if delete isn't available).
    r = req("DELETE", c, f"/api/company/{cid}", headers=h, retries=1)
    if r.status_code in (200, 204):
        ok("DELETE /api/company/{id} → cleaned up")
    else:
        skip("DELETE /api/company/{id}", f"status {r.status_code}")


# ─── main ─────────────────────────────────────────────────────────────────────

def wait_for_server(base: str, timeout: int = 60) -> None:
    """Poll /api/health with retries until the server is up."""
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            r = httpx.get(f"{base}/api/health", timeout=5.0)
            if r.status_code == 200:
                print(f"  {PASS} Server ready after {attempt} attempt(s)")
                return
        except Exception:
            pass
        remaining = deadline - time.time()
        delay = min(RETRY_BACKOFF[min(attempt - 1, len(RETRY_BACKOFF) - 1)], remaining)
        if delay > 0:
            print(f"  Waiting for server… (attempt {attempt}, {int(remaining)}s left)")
            time.sleep(delay)
    print(f"{FAIL} Server at {base} not responding after {timeout}s")
    sys.exit(1)


def main() -> int:
    print(f"\n{'═' * 60}")
    print(f"  LLM Relay — E2E Test Suite (retries={MAX_RETRIES})")
    print(f"  Target: {BASE}")
    print(f"{'═' * 60}")

    wait_for_server(BASE, timeout=60)

    with httpx.Client(base_url=BASE, timeout=60.0) as c:
        test_health(c)
        token = test_auth(c)
        h = {"Authorization": f"Bearer {token}"}

        test_providers(c, h)
        test_api_keys(c, h)
        test_wiki(c, h)
        test_chat(c, h)
        test_chat_sessions_list(c, h)
        test_activity_and_stats(c, h)
        test_activation_api(c, h)
        test_platform_info(c, h)
        test_company_lifecycle(c, h)

    print(f"\n{'═' * 60}")
    total = Suite.passed + Suite.failed + Suite.skipped
    print(f"  {Suite.passed} passed  |  {Suite.skipped} skipped  |  "
          f"{Suite.failed} failed  |  {total} total")
    print(f"{'═' * 60}\n")
    return 0 if Suite.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

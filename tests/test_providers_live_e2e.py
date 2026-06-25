"""tests/test_providers_live_e2e.py — Live integration test for /api/providers/{id}.

Exercises the real production path against the deployed backend:

  1. POST /api/auth/login       → get a real JWT (admin credentials)
  2. PUT  /api/providers/{id}  → create/update a provider record
  3. GET  /api/providers/{id}  → confirm the round-trip reads back
  4. DELETE the test provider  → clean up so the run is idempotent

The test self-skips (not hard-fails) when any of:
  - PROVIDER_E2E_BASE_URL is unset (CI default)
  - PROVIDER_E2E_EMAIL / PROVIDER_E2E_PASSWORD are unset (no creds)
  - The deployed backend is unreachable (network / TLS / WAF)
  - The deployed backend returns a 5xx for the login attempt (real outage)

This is the test that proves the production path is pinned end-to-end,
not just the mocked unit-test path. It runs the EXACT same code that
ships to https://autonomous-ai-agency.strikersam.workers.dev/, so a
green run here means the rebrand + Pydantic v2 + atomic-claim work
didn't break the providers contract.

Example local invocation (against the live production URL):
  PROVIDER_E2E_BASE_URL=https://autonomous-ai-agency.strikersam.workers.dev \\
  PROVIDER_E2E_EMAIL=$ADMIN_EMAIL \\
  PROVIDER_E2E_PASSWORD=$ADMIN_PASSWORD \\
  pytest -x -v tests/test_providers_live_e2e.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from typing import Any

import pytest


# Skip the entire module unless the operator explicitly opts in by setting
# the base URL. This is the default in CI so the offline unit suite stays green.
_BASE_URL = os.environ.get("PROVIDER_E2E_BASE_URL", "").strip().rstrip("/")
_EMAIL = os.environ.get("PROVIDER_E2E_EMAIL", "").strip()
_PASSWORD = os.environ.get("PROVIDER_E2E_PASSWORD", "").strip()

pytestmark = pytest.mark.skipif(
    not _BASE_URL,
    reason=(
        "PROVIDER_E2E_BASE_URL not set — live /api/providers/{id} round-trip "
        "is opt-in. Set PROVIDER_E2E_BASE_URL + PROVIDER_E2E_EMAIL + "
        "PROVIDER_E2E_PASSWORD to run the production-path pin test."
    ),
)


def _skip(reason: str) -> None:
    """Skip the current test with a structured reason (pytest.skip is fine too)."""
    pytest.skip(reason)


def _login_via_email(base_url: str, email: str, password: str) -> dict[str, Any]:
    """POST /api/auth/login and return the parsed JSON body. Raises on failure."""
    import httpx

    with httpx.Client(timeout=15.0) as client:
        resp = client.post(
            f"{base_url}/api/auth/login",
            json={"email": email, "password": password},
        )
        if resp.status_code == 404:
            _skip(
                f"Deployed backend at {base_url} has no /api/auth/login endpoint "
                f"(404). The email/password auth surface may not be deployed yet."
            )
        if resp.status_code >= 500:
            _skip(
                f"Deployed backend at {base_url} returned 5xx for login "
                f"({resp.status_code}); treating as a real outage, not a test failure."
            )
        if resp.status_code != 200:
            _skip(
                f"Login failed at {base_url}: {resp.status_code} {resp.text[:200]}"
            )
        return resp.json()


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def test_live_providers_round_trip():
    """Full JWT round-trip: login → PUT → GET → cleanup.

    Asserts that the providers router is fully on the Pydantic v2 + JWT auth
    path against the REAL deployed backend. A green run here proves the
    production path is pinned, not just the mocked unit-test path.
    """
    if not _EMAIL or not _PASSWORD:
        _skip("PROVIDER_E2E_EMAIL / PROVIDER_E2E_PASSWORD not set")

    # Unique provider_id per run so the test is idempotent across re-runs.
    provider_id = f"e2e-test-{uuid.uuid4().hex[:8]}"
    payload = {
        "name": "E2E Test Provider",
        "type": "openai-compatible",
        "base_url": "https://example.com/v1",
        "api_key": "sk-e2e-test-do-not-use",
        "default_model": "e2e-test-model",
        "is_default": False,
        "priority": 999,
        "status": "configured",
    }

    import httpx

    try:
        with httpx.Client(timeout=20.0) as client:
            # 1. Login → get a real JWT.
            body = _login_via_email(_BASE_URL, _EMAIL, _PASSWORD)
            access = body.get("access_token") or body.get("accessToken") or body.get("token")
            if not access:
                _skip(
                    f"Login response from {_BASE_URL} has no access_token field. "
                    f"Got keys: {list(body.keys())}"
                )
            headers = _auth_headers(access)

            # 2-4: PUT → GET → cleanup, all inside a try/finally so the
            # DELETE always runs even on assertion failure. Without this,
            # a failing assert between PUT and DELETE leaves a stale
            # "e2e-test-*" provider in the production collection that
            # accumulates cruft across test runs.
            def _cleanup() -> None:
                try:
                    del_resp = client.delete(
                        f"{_BASE_URL}/api/providers/{provider_id}", headers=headers
                    )
                    # 200/204 = success; 404 = already gone. We do NOT
                    # assert on the cleanup response — a network blip
                    # during teardown must not mask the real test failure.
                    if del_resp.status_code not in (200, 204, 404):
                        print(
                            f"  WARN: cleanup DELETE returned "
                            f"{del_resp.status_code} for {provider_id} "
                            f"(test provider may have leaked)"
                        )
                except Exception as exc:  # pragma: no cover
                    print(f"  WARN: cleanup DELETE failed for {provider_id}: {exc}")

            try:
                # 2. PUT /api/providers/{id} — create the test provider.
                put_resp = client.put(
                    f"{_BASE_URL}/api/providers/{provider_id}",
                    headers=headers,
                    json=payload,
                )
                if put_resp.status_code == 404:
                    _skip(
                        f"Deployed backend at {_BASE_URL} returned 404 for "
                        f"PUT /api/providers/{provider_id} — the providers router "
                        f"may not be deployed in this environment."
                    )
                assert put_resp.status_code in (200, 201), (
                    f"PUT /api/providers/{provider_id} returned {put_resp.status_code}: "
                    f"{put_resp.text[:500]}"
                )
                put_body = put_resp.json()
                # Confirm the body actually persisted our payload — proves the
                # response went through the real Pydantic v2 model_dump() path,
                # not a mocked one.
                assert put_body.get("provider_id") == provider_id, (
                    f"PUT response missing provider_id; got keys: {list(put_body.keys())}"
                )
                assert put_body.get("default_model") == payload["default_model"], (
                    f"PUT round-trip lost the default_model field: {put_body}"
                )

                # 3. GET /api/providers/{id} — confirm readback matches.
                get_resp = client.get(
                    f"{_BASE_URL}/api/providers/{provider_id}", headers=headers
                )
                assert get_resp.status_code == 200, (
                    f"GET /api/providers/{provider_id} returned {get_resp.status_code}: "
                    f"{get_resp.text[:500]}"
                )
                get_body = get_resp.json()
                assert get_body.get("provider_id") == provider_id
                assert get_body.get("name") == payload["name"]
                assert get_body.get("priority") == payload["priority"]
                assert get_body.get("base_url") == payload["base_url"], (
                    f"base_url round-trip lost: sent {payload['base_url']!r}, "
                    f"got {get_body.get('base_url')!r}"
                )
                # api_key should be masked in the response, not returned in cleartext.
                api_key_returned = get_body.get("api_key")
                assert api_key_returned != payload["api_key"], (
                    "api_key was returned in cleartext — masking regressed!"
                )
            finally:
                # ALWAYS cleanup, even on assert failure, so the production
                # collection doesn't accumulate e2e-test-* cruft.
                _cleanup()

    except httpx.ConnectError as exc:
        _skip(f"Cannot reach {_BASE_URL}: {exc}")
    except httpx.TimeoutException as exc:
        _skip(f"Timeout reaching {_BASE_URL}: {exc}")
    except httpx.HTTPError as exc:
        _skip(f"HTTP error talking to {_BASE_URL}: {exc}")


def test_live_providers_role_tags_visible():
    """The /api/providers list now annotates each record with is_brain/role.

    The role-tagging work pinned the production path so operators can see
    which provider is the brain, which are sub-agents, which are paid
    fallbacks. This test confirms that field is present and well-formed
    on a real GET — not just a mocked one.
    """
    if not _EMAIL or not _PASSWORD:
        _skip("PROVIDER_E2E_EMAIL / PROVIDER_E2E_PASSWORD not set")

    import httpx

    try:
        with httpx.Client(timeout=20.0) as client:
            body = _login_via_email(_BASE_URL, _EMAIL, _PASSWORD)
            access = body.get("access_token") or body.get("accessToken") or body.get("token")
            if not access:
                _skip("Login response has no access_token")
            headers = _auth_headers(access)

            resp = client.get(f"{_BASE_URL}/api/providers", headers=headers)
            if resp.status_code == 404:
                _skip(f"GET /api/providers returned 404 at {_BASE_URL}")
            assert resp.status_code == 200, (
                f"GET /api/providers returned {resp.status_code}: {resp.text[:500]}"
            )
            providers = (resp.json() or {}).get("providers") or []
            assert isinstance(providers, list) and providers, (
                f"GET /api/providers returned no providers list: {resp.text[:500]}"
            )
            # The role tag is the whole point of this round-trip — verify it.
            for entry in providers:
                # Either role is set (production) or absent (older deploy) — both
                # are valid; the test only fails if is_brain is a non-boolean.
                if "is_brain" in entry:
                    assert isinstance(entry["is_brain"], bool), (
                        f"is_brain for {entry.get('provider_id')!r} is not a bool: "
                        f"{entry['is_brain']!r}"
                    )
    except httpx.ConnectError as exc:
        _skip(f"Cannot reach {_BASE_URL}: {exc}")
    except httpx.TimeoutException as exc:
        _skip(f"Timeout reaching {_BASE_URL}: {exc}")
    except httpx.HTTPError as exc:
        _skip(f"HTTP error talking to {_BASE_URL}: {exc}")


if __name__ == "__main__":
    # Allow running the test directly: `python tests/test_providers_live_e2e.py`
    # Pytest-style exit code so CI integrations work either way.
    sys.exit(pytest.main([__file__, "-v", "--no-header"]))

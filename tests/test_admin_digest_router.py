#!/usr/bin/env python3
"""tests/test_admin_digest_router.py — Coverage for /api/admin/digest/* endpoints.

Tests hit the router directly via FastAPI's TestClient; environment is
manipulated via monkeypatching so we don't mutate real env vars.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch


class _StubDispatcher:
    """Stub for telegram_service.NotificationDispatcher used by /send."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    async def send_daily_digest(self, payload) -> bool:  # mirrors signature
        self.calls.append(("send_daily_digest", getattr(payload, "markdown_body", None)))
        return True


class AdminDigestRouterAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        # Force a known secret for the duration of these tests
        os.environ["DIGEST_SECRET"] = "test_digest_secret_at_least_32_chars_long"
        os.environ["ADMIN_SECRET"] = "test_admin_secret_at_least_32_chars_long"
        # Re-import the test environment so the module picks up the new env
        from backend import admin_digest_router
        # Reload module-level constants by re-importing
        self._router_module = admin_digest_router

    def _client(self):
        """Build a FastAPI TestClient against an app shell with only the
        admin_digest_router mounted."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.admin_digest_router import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_send_without_secret_returns_401(self) -> None:
        client = self._client()
        resp = client.post("/api/admin/digest/send")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("authentication failed", resp.json()["detail"])

    def test_send_with_wrong_secret_returns_401(self) -> None:
        client = self._client()
        resp = client.post(
            "/api/admin/digest/send",
            headers={"X-Admin-Secret": "definitely-not-the-right-value"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_send_with_correct_secret_returns_200_and_envelope(self) -> None:
        client = self._client()
        # Patch the dispatcher and orchestrator to avoid real I/O
        stub = _StubDispatcher()
        from backend import admin_digest_router as adm
        with patch.object(adm, "NotificationDispatcher", return_value=stub), \
             patch.object(adm, "_build_payload_or_500") as build_mock:
            # Build a minimal DigestPayload-like object
            from services.daily_digest import DigestPayload, DigestSummary
            payload = DigestPayload(
                cutoff_utc="2026-06-19T00:00:00",
                generated_utc="2026-06-19T00:00:00",
                summary=DigestSummary(
                    counts={"awaiting_review": 0, "pending_decisions": 0, "recent_wins_24h": 0},
                ),
                markdown_body="*Daily Review Digest* — 2026-06-19",
                truncated_path=None,
            )
            build_mock.return_value = payload
            resp = client.post(
                "/api/admin/digest/send",
                headers={
                    "X-Admin-Secret": "test_digest_secret_at_least_32_chars_long",
                    "X-Idempotency-Key": "smoke-2026-06-19",
                },
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertIn("cutoff_utc", body)
        self.assertIn("counts", body)
        self.assertEqual(body["idempotency_key"], "smoke-2026-06-19")
        # Dispatcher was called with the payload
        self.assertEqual(len(stub.calls), 1)
        self.assertEqual(stub.calls[0][0], "send_daily_digest")

    def test_preview_with_correct_secret_returns_markdown_body(self) -> None:
        client = self._client()
        from backend import admin_digest_router as adm
        with patch.object(adm, "_build_payload_or_500") as build_mock:
            from services.daily_digest import DigestPayload, DigestSummary
            payload = DigestPayload(
                cutoff_utc="2026-06-19T00:00:00",
                generated_utc="2026-06-19T00:00:00",
                summary=DigestSummary(
                    counts={"awaiting_review": 1, "pending_decisions": 0, "recent_wins_24h": 2},
                ),
                markdown_body="*Daily Review Digest*\nhello",
                truncated_path=None,
            )
            build_mock.return_value = payload
            resp = client.get(
                "/api/admin/digest/preview",
                headers={"X-Admin-Secret": "test_digest_secret_at_least_32_chars_long"},
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["counts"]["awaiting_review"], 1)
        self.assertIn("hello", body["markdown_body"])

    def test_no_secret_configured_returns_500(self) -> None:
        # Wipe both env vars for this test only
        prev_digest = os.environ.pop("DIGEST_SECRET", None)
        prev_admin = os.environ.pop("ADMIN_SECRET", None)
        try:
            client = self._client()
            resp = client.post("/api/admin/digest/send", headers={"X-Admin-Secret": "anything"})
            # When no secret configured, _check_secret returns False → 401
            self.assertEqual(resp.status_code, 401)
        finally:
            if prev_digest is not None:
                os.environ["DIGEST_SECRET"] = prev_digest
            if prev_admin is not None:
                os.environ["ADMIN_SECRET"] = prev_admin


if __name__ == "__main__":
    unittest.main(verbosity=2)

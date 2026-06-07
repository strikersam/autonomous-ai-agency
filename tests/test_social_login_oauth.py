"""Regression tests for social-login (GitHub & Google) OAuth state handling.

Bug #7 (2026-06-06): "Invalid OAuth state" on Google login. Root cause: the
login flows stored the CSRF state in a session cookie, which does not survive
the OAuth round-trip in the split Cloudflare-frontend / Render-backend
deployment (cross-domain redirect + cold-start SESSION_SECRET rotation).
Fix: store login state server-side in the shared ``oauth_states`` collection,
exactly like the GitHub repo-connect flow. These tests lock in that the
state-validation logic is provider-scoped, expiry-aware, and rejects forged or
mismatched states.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

# Ensure backend.server imports without a live MongoDB.
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test-secret-for-tests-only")
os.environ.setdefault("ADMIN_EMAIL", "admin@test.local")

from backend.server import _valid_login_state  # noqa: E402


def _doc(provider="google", flow_type="login", age_seconds=0):
    return {
        "state": "abc123",
        "flow_type": flow_type,
        "provider": provider,
        "created_at": datetime.now(timezone.utc) - timedelta(seconds=age_seconds),
    }


def test_valid_google_login_state_accepted():
    assert _valid_login_state(_doc(provider="google"), provider="google") is True


def test_valid_github_login_state_accepted():
    assert _valid_login_state(_doc(provider="github"), provider="github") is True


def test_missing_state_doc_rejected():
    # A None doc means the state was never issued by us (or already consumed).
    assert _valid_login_state(None, provider="google") is False


def test_wrong_provider_rejected():
    # A GitHub-issued state must not validate a Google callback and vice versa.
    assert _valid_login_state(_doc(provider="github"), provider="google") is False
    assert _valid_login_state(_doc(provider="google"), provider="github") is False


def test_repo_flow_state_not_usable_for_login():
    # Repo-connect states (flow_type="repo") must never authenticate a login.
    assert _valid_login_state(_doc(flow_type="repo"), provider="github") is False


def test_expired_state_rejected():
    # Older than the 10-minute TTL window — defends backends without TTL indexes.
    assert _valid_login_state(_doc(age_seconds=601), provider="google") is False


def test_just_within_window_accepted():
    assert _valid_login_state(_doc(age_seconds=599), provider="google") is True


def test_naive_created_at_does_not_raise():
    """MongoDB/motor returns naive UTC datetimes. Subtracting a naive datetime
    from an aware now() raised TypeError -> 500 *after* the state check passed
    (the production "Internal server error" on Google login). The validator must
    normalise naive timestamps instead of crashing."""
    naive_recent = {
        "state": "abc123",
        "flow_type": "login",
        "provider": "google",
        "created_at": datetime.utcnow(),  # naive, like PyMongo returns
    }
    assert _valid_login_state(naive_recent, provider="google") is True

    naive_expired = {
        "state": "abc123",
        "flow_type": "login",
        "provider": "google",
        "created_at": datetime.utcnow() - timedelta(seconds=601),
    }
    assert _valid_login_state(naive_expired, provider="google") is False


def test_login_endpoints_do_not_depend_on_session_cookie():
    """The login handlers must persist state via _store_login_state, not the
    session cookie (the source of the original bug)."""
    import inspect

    from backend import server

    gh_src = inspect.getsource(server.github_login)
    goog_src = inspect.getsource(server.google_login)

    for src in (gh_src, goog_src):
        assert "_store_login_state" in src
        assert "request.session[" not in src

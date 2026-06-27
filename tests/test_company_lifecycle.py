"""Tests for company lifecycle gating — who gets ephemeral vs persistent agencies.

Policy (confirmed product decision): every non-admin account is a social
(GitHub/Google) login; the only persistent local account is the admin. So
ephemeral == non-admin AND social provider.
"""
from __future__ import annotations

from backend.company_api import _is_ephemeral_user, _resolve_provider


def test_admin_local_is_persistent():
    user = {"email": "admin@llmrelay.local", "role": "admin", "provider": "local"}
    assert _is_ephemeral_user(user) is False


def test_github_non_admin_is_ephemeral():
    user = {"user_id": "gh_123", "role": "user", "provider": "github"}
    assert _is_ephemeral_user(user) is True


def test_google_non_admin_is_ephemeral():
    user = {"user_id": "goog_456", "role": "user", "provider": "google"}
    assert _is_ephemeral_user(user) is True


def test_social_admin_is_persistent():
    # A social user promoted to admin keeps persistent companies.
    user = {"user_id": "gh_789", "role": "admin", "provider": "github"}
    assert _is_ephemeral_user(user) is False


def test_non_social_non_admin_is_persistent():
    # Defensive: a hypothetical non-admin local account is NOT ephemeral.
    user = {"email": "someone@llmrelay.local", "role": "user", "provider": "local"}
    assert _is_ephemeral_user(user) is False


def test_provider_inferred_from_user_id_prefix():
    assert _resolve_provider({"user_id": "gh_1"}) == "github"
    assert _resolve_provider({"user_id": "goog_1"}) == "google"
    assert _resolve_provider({"email": "x@y.com"}) == "local"

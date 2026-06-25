"""tests/test_orchestrator_push_token.py — #506 push/PR token resolution.

workflow_orchestrator only fell back to the server token for internal runs
(user_id is None), so user/admin-initiated runs executed but could never push a
branch or open a PR. _resolve_push_token now lets the operator opt in for user
runs while keeping the per-user token as the winner and the multi-tenant guard
on by default.
"""
from __future__ import annotations

import pytest

from services.workflow_orchestrator import _resolve_push_token

_ENV_KEYS = ("GH_TOKEN", "GH_PAT", "GITHUB_TOKEN", "ORCHESTRATOR_ALLOW_SERVER_TOKEN_FOR_USER_RUNS")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in _ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    yield


def test_per_user_token_always_wins(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "server-tok")
    assert _resolve_push_token("user-tok", "user@example.com") == "user-tok"


def test_internal_run_uses_server_token(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "server-tok")
    # No user_id => internal/system run => server token fallback applies.
    assert _resolve_push_token(None, None) == "server-tok"


def test_user_run_without_optin_gets_no_server_token(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "server-tok")
    # Multi-tenant guard: a user run must not silently borrow the service account.
    assert _resolve_push_token(None, "user@example.com") is None


def test_user_run_with_optin_uses_server_token(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "server-tok")
    monkeypatch.setenv("ORCHESTRATOR_ALLOW_SERVER_TOKEN_FOR_USER_RUNS", "true")
    # #506: operator opts in so user-initiated runs can finally open PRs.
    assert _resolve_push_token(None, "user@example.com") == "server-tok"


def test_falls_through_gh_pat_and_github_token(monkeypatch):
    monkeypatch.setenv("GH_PAT", "pat-tok")
    assert _resolve_push_token(None, None) == "pat-tok"

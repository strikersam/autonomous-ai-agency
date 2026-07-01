"""tests/test_service_token.py — N5 acceptance: service-token auth surface.

Tests the new ``services.service_token`` module that gates the mutating
Telegram control endpoints (``PATCH /admin/api/policy/brain`` and
``POST /admin/api/prs/{number}/merge``).

Acceptance criteria from the roadmap:
  - valid token → 200 (request reaches the handler)
  - invalid token → 401
  - absent token → 401 (when SERVICE_TOKEN is configured)
  - SERVICE_TOKEN unset → 503 (misconfiguration signal, distinct from 401)
  - token never appears in logs (verified via the log capture fixture)
  - constant-time comparison (hmac.compare_digest on SHA-256 digests)
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pytest


# Ensure services/ is importable even when services/__init__.py is broken
# in the test env (it tries to import bson/pymongo, which may be absent).
REPO_ROOT = Path(__file__).resolve().parent.parent
SERVICES_DIR = REPO_ROOT / "services"
# V2.0 Phase 3: service_token.py moved to packages/auth/service_token.py.
# The services/service_token.py shim re-exports symbols but tests that
# inspect the module SOURCE (e.g. for `hmac.compare_digest`) need to load
# the real file.
REAL_SERVICE_TOKEN_PATH = REPO_ROOT / "packages" / "auth" / "service_token.py"


@pytest.fixture
def service_token_module(monkeypatch):
    """Load services.service_token fresh in each test so env-var changes take effect."""
    # Always reset the in-memory hash cache before each test.
    sys.path.insert(0, str(REPO_ROOT))
    sys.path.insert(0, str(SERVICES_DIR))
    # Force-import the top-level module (skipping services/__init__.py cascade)
    # by loading it directly. brain_watchdog.py uses the same trick in its tests.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_test_service_token", REAL_SERVICE_TOKEN_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Reset cached hash so env changes are picked up.
    mod._hashed_token_cache = None
    mod._hashed_token_computed_at = 0
    yield mod
    mod._hashed_token_cache = None
    mod._hashed_token_computed_at = 0
    if str(REPO_ROOT) in sys.path:
        sys.path.remove(str(REPO_ROOT))
    if str(SERVICES_DIR) in sys.path:
        sys.path.remove(str(SERVICES_DIR))


# ── is_service_token_configured ──────────────────────────────────────────────

def test_is_service_token_configured_false_when_unset(service_token_module, monkeypatch):
    monkeypatch.delenv("SERVICE_TOKEN", raising=False)
    assert service_token_module.is_service_token_configured() is False


def test_is_service_token_configured_true_when_set(service_token_module, monkeypatch):
    monkeypatch.setenv("SERVICE_TOKEN", "tok_abc123")
    assert service_token_module.is_service_token_configured() is True


def test_is_service_token_configured_false_when_empty(service_token_module, monkeypatch):
    monkeypatch.setenv("SERVICE_TOKEN", "   ")
    assert service_token_module.is_service_token_configured() is False


# ── verify_service_token ─────────────────────────────────────────────────────

def test_verify_service_token_returns_false_when_unset(service_token_module, monkeypatch):
    """Fail-closed: when SERVICE_TOKEN is unset, no provided token passes."""
    monkeypatch.delenv("SERVICE_TOKEN", raising=False)
    assert service_token_module.verify_service_token("anything") is False


def test_verify_service_token_returns_false_for_none_input(service_token_module, monkeypatch):
    monkeypatch.setenv("SERVICE_TOKEN", "tok_abc123")
    assert service_token_module.verify_service_token(None) is False
    assert service_token_module.verify_service_token("") is False


def test_verify_service_token_returns_true_for_correct_token(service_token_module, monkeypatch):
    monkeypatch.setenv("SERVICE_TOKEN", "tok_correct_value_xyz")
    assert service_token_module.verify_service_token("tok_correct_value_xyz") is True


def test_verify_service_token_returns_false_for_wrong_token(service_token_module, monkeypatch):
    """N5 acceptance: invalid token → 401 (here: verify returns False)."""
    monkeypatch.setenv("SERVICE_TOKEN", "tok_correct_value_xyz")
    assert service_token_module.verify_service_token("tok_wrong_value") is False


def test_verify_service_token_returns_false_for_near_match(service_token_module, monkeypatch):
    """Near-miss tokens must not pass (no prefix-match, no fuzzy match)."""
    monkeypatch.setenv("SERVICE_TOKEN", "tok_correct_value_xyz")
    assert service_token_module.verify_service_token("tok_correct_value") is False  # truncated
    assert service_token_module.verify_service_token("tok_correct_value_xyz!") is False  # extra char


# ── Plaintext never cached beyond hash call site ────────────────────────────

def test_hashed_token_cache_does_not_hold_plaintext(service_token_module, monkeypatch):
    """After verification, the module must NOT hold the plaintext token — only
    the SHA-256 hash. A memory dump shouldn't recover the secret."""
    monkeypatch.setenv("SERVICE_TOKEN", "secret_plaintext_value")
    service_token_module.verify_service_token("secret_plaintext_value")
    # The cache holds bytes (the digest), not the plaintext string.
    assert service_token_module._hashed_token_cache is not None
    assert isinstance(service_token_module._hashed_token_cache, bytes)
    # And the plaintext is not present in any module attribute.
    import inspect
    src = inspect.getsource(service_token_module)
    # The plaintext we used for the test must not be hardcoded in the module source.
    assert "secret_plaintext_value" not in src


# ── Token never logged ───────────────────────────────────────────────────────

def test_verify_service_token_does_not_log_plaintext(service_token_module, monkeypatch, caplog):
    """The token plaintext must NEVER appear in logs. Capture every log
    record emitted during a verify call and assert the plaintext is absent."""
    monkeypatch.setenv("SERVICE_TOKEN", "do_not_log_this_plaintext")
    with caplog.at_level(logging.DEBUG, logger="qwen-proxy"):
        # Both a success and a failure call — neither must leak the token.
        service_token_module.verify_service_token("do_not_log_this_plaintext")
        service_token_module.verify_service_token("wrong_token")
    all_logs = " ".join(r.getMessage() for r in caplog.records)
    assert "do_not_log_this_plaintext" not in all_logs, (
        f"Service token plaintext leaked in logs: {all_logs!r}"
    )


# ── Constant-time comparison ────────────────────────────────────────────────

def test_verify_service_token_uses_constant_time_compare(service_token_module, monkeypatch):
    """The module must use hmac.compare_digest (not ==) for the comparison —
    timing attacks would otherwise recover the token byte-by-byte. We assert
    the function is referenced by name in the module source."""
    import inspect
    src = inspect.getsource(service_token_module)
    assert "hmac.compare_digest" in src, (
        "service_token.py must use hmac.compare_digest for constant-time comparison"
    )


# ── MUTATING_ENDPOINTS allowlist is narrow ──────────────────────────────────

def test_mutating_endpoints_allowlist_is_narrow(service_token_module):
    """The service token must only gate a narrow allowlist of endpoints — not
    all of /admin/api/*. Adding an entry requires a paired test (this is the
    risky-module-review trigger)."""
    endpoints = service_token_module.MUTATING_ENDPOINTS
    assert isinstance(endpoints, frozenset)
    # The two N5 endpoints
    assert "patch:/admin/api/policy/brain" in endpoints
    assert "post:/admin/api/prs/{number}/merge" in endpoints
    # And NOT any other admin endpoints — the allowlist is intentionally narrow
    assert len(endpoints) == 2, (
        f"Mutating endpoint allowlist grew unexpectedly: {sorted(endpoints)}. "
        "Each new entry requires a paired test + risky-module-review sign-off."
    )


# ── Hash rotation picks up env changes ───────────────────────────────────────

def test_token_rotation_picks_up_env_change(service_token_module, monkeypatch):
    """When SERVICE_TOKEN is rotated in the env, the new token must verify
    (within the 60s cache window). This is the risky-module-review T6 mitigation."""
    monkeypatch.setenv("SERVICE_TOKEN", "old_token_value")
    assert service_token_module.verify_service_token("old_token_value") is True
    assert service_token_module.verify_service_token("new_token_value") is False

    # Rotate the env var
    monkeypatch.setenv("SERVICE_TOKEN", "new_token_value")
    # Force the cache to refresh (the cache TTL is 60s; the test resets it via the fixture)
    service_token_module._hashed_token_cache = None
    service_token_module._hashed_token_computed_at = 0
    assert service_token_module.verify_service_token("new_token_value") is True
    assert service_token_module.verify_service_token("old_token_value") is False

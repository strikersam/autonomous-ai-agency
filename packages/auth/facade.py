"""packages/auth/facade.py — unified auth facade.

This module provides a single import point for all authentication.
During the migration, it re-exports functions from their current locations.
As each auth module is moved to packages/auth/, the re-exports will
be replaced with direct imports.

Usage:
    from packages.auth import get_current_user, get_optional_user, require_admin
"""
from __future__ import annotations

# Re-export existing auth functions (migration bridge)
# These will be replaced with direct imports as modules are moved

def get_current_user(request):
    """Get the authenticated user or raise 401."""
    from backend.server import get_current_user as _impl
    return _impl(request)


def get_optional_user(request):
    """Get the authenticated user or return None."""
    from backend.server import get_optional_user as _impl
    return _impl(request)


def require_admin(user: dict) -> None:
    """Raise 403 if user is not admin."""
    from backend.server import _require_admin as _impl
    _impl(user)


def verify_api_key(request):
    """Verify API key for proxy endpoints."""
    from proxy import verify_api_key as _impl
    return _impl(request)


def verify_service_token(provided: str | None) -> bool:
    """Verify a service token (for Telegram bot → backend)."""
    from packages.auth.service_token import verify_service_token as _impl
    return _impl(provided)


# OAuth helpers (re-export from social_auth.py)
def github_exchange_code(code: str):
    from packages.auth.oauth import github_exchange_code as _impl
    return _impl(code)


def github_fetch_user(access_token: str):
    from packages.auth.oauth import github_fetch_user as _impl
    return _impl(access_token)


def google_exchange_code(code: str, redirect_uri: str | None = None):
    from packages.auth.oauth import google_exchange_code as _impl
    return _impl(code, redirect_uri)


def google_fetch_user(access_token: str):
    from packages.auth.oauth import google_fetch_user as _impl
    return _impl(access_token)


# JWT helpers
def create_access_token(user_id: str, email: str) -> str:
    from backend.server import create_access_token as _impl
    return _impl(user_id, email)


def create_refresh_token(user_id: str) -> str:
    from backend.server import create_refresh_token as _impl
    return _impl(user_id)

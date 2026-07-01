"""social_auth.py — GitHub and Google OAuth social login (CANONICAL MODULE).

Provides reusable OAuth exchange and user-fetch helpers used by backend/server.py
and any other module that needs to authenticate via GitHub/Google OAuth.

The live OAuth endpoints live in backend/server.py and import the helper
functions from here — there is one canonical implementation for token exchange
and profile fetch.

Flow:
  1. Frontend redirects user to  GET /api/auth/{provider}/login
     → server redirects to GitHub/Google consent screen

  2. Provider redirects back to  GET /api/auth/{provider}/callback?code=...
     → server exchanges code for access token
     → server fetches user profile (email, name, avatar)
     → server upserts user in MongoDB
     → server issues a signed JWT (PyJWT library)
     → server redirects to frontend /auth/callback?access_token=...&refresh_token=...

  3. Frontend stores tokens in localStorage, calls /api/auth/me to verify,
     and sends "Authorization: Bearer <jwt>" on every API request.

Environment variables:
  GITHUB_CLIENT_ID        GitHub OAuth app client ID
  GITHUB_CLIENT_SECRET    GitHub OAuth app client secret
  GOOGLE_CLIENT_ID        Google OAuth 2.0 client ID
  GOOGLE_CLIENT_SECRET    Google OAuth 2.0 client secret
  OAUTH_REDIRECT_BASE     Base URL of this server (e.g. https://myserver.com)
  JWT_SECRET              Secret for signing session JWTs
  FRONTEND_URL            Frontend base URL for post-auth redirect
"""

from __future__ import annotations

import logging
import os
import secrets
import time

import httpx

log = logging.getLogger("qwen-proxy")


# ── Configuration ──────────────────────────────────────────────────────────────

def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


GITHUB_CLIENT_ID     = _env("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = _env("GITHUB_CLIENT_SECRET")
GOOGLE_CLIENT_ID     = _env("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = _env("GOOGLE_CLIENT_SECRET")
OAUTH_REDIRECT_BASE  = _env("OAUTH_REDIRECT_BASE", "http://localhost:9999")
FRONTEND_URL         = _env("FRONTEND_URL", "http://localhost:3000")
JWT_SECRET           = _env("JWT_SECRET") or secrets.token_hex(32)

if not _env("JWT_SECRET"):
    log.warning(
        "JWT_SECRET not set — using a randomly generated secret. "
        "Sessions will be invalidated on every server restart. "
        "Set JWT_SECRET in production."
    )


# ── CSRF state helpers ─────────────────────────────────────────────────────────

_oauth_states: dict[str, float] = {}
_STATE_TTL = 600  # 10 minutes


def _new_state() -> str:
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = time.time() + _STATE_TTL
    return state


def _validate_state(state: str) -> bool:
    expiry = _oauth_states.pop(state, None)
    if expiry is None:
        return False
    if time.time() > expiry:
        return False
    return True


# ── URL builders (dormant reference) ───────────────────────────────────────────

def _github_login_url() -> str:
    """Utility: return the GitHub OAuth authorize URL."""
    if not GITHUB_CLIENT_ID:
        return ""
    state = _new_state()
    return (
        "https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={OAUTH_REDIRECT_BASE}/api/auth/github/callback"
        f"&scope=user:email"
        f"&state={state}"
    )


def _google_login_url() -> str:
    """Utility: return the Google OAuth authorize URL."""
    if not GOOGLE_CLIENT_ID:
        return ""
    state = _new_state()
    return (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={OAUTH_REDIRECT_BASE}/api/auth/google/callback"
        f"&response_type=code"
        f"&scope=openid+email+profile"
        f"&state={state}"
    )


# ── GitHub OAuth helpers (canonical) ─────────────────────────────────────────

async def github_exchange_code(code: str) -> str | None:
    """Exchange GitHub OAuth code for access token."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
        resp = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id":     GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code":          code,
            },
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            return None
        return resp.json().get("access_token")


async def github_fetch_user(access_token: str) -> dict | None:
    """Fetch GitHub user profile using an access token.

    Makes the user + email requests CONCURRENTLY (was sequential — 2x slower).
    Also only fetches /user/emails when the user profile doesn't already have
    a public email (saves one API call in the common case).
    """
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
        }
        user_resp = await client.get("https://api.github.com/user", headers=headers)

        if user_resp.status_code != 200:
            return None

        ud = user_resp.json()
        email = ud.get("email") or ""

        # Only fetch /user/emails if the user profile doesn't have a public email.
        # This saves one API round-trip in the common case (most users have a
        # public email).
        if not email:
            email_resp = await client.get("https://api.github.com/user/emails", headers=headers)
            if email_resp.status_code == 200:
                for e in email_resp.json():
                    if e.get("primary") and e.get("verified"):
                        email = e["email"]
                        break

        if not email:
            log.warning("GitHub OAuth: no verified email for user %s", ud.get("login"))
            email = f"{ud['login']}@users.noreply.github.com"

        return {
            "user_id": f"gh_{ud['id']}",
            "email": email.lower(),
            "name": ud.get("name") or ud.get("login") or email,
            "avatar_url": ud.get("avatar_url", ""),
            "login": ud.get("login", ""),
            "provider": "github",
        }


# ── Google OAuth helpers (canonical) ─────────────────────────────────────────

async def google_exchange_code(code: str, redirect_uri: str | None = None) -> str | None:
    if redirect_uri is None:
        redirect_uri = f"{OAUTH_REDIRECT_BASE}/api/auth/google/callback"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code":          code,
                "grant_type":    "authorization_code",
                "redirect_uri":  redirect_uri,
            },
        )
        if resp.status_code != 200:
            return None
        return resp.json().get("access_token")


async def google_fetch_user(access_token: str) -> dict | None:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code != 200:
            return None
        ud = resp.json()
        return {
            "user_id": f"goog_{ud['id']}",
            "email": ud.get("email", "").lower(),
            "name": ud.get("name", ud.get("email", "")),
            "avatar_url": ud.get("picture", ""),
            "provider": "google",
        }

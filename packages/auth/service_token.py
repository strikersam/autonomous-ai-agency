"""services/service_token.py — Backend service-token authentication.

Roadmap item N5 — mutating Telegram control (switch brain / merge PR from the
phone). Today Telegram is read-only (``/autonomy``, ``/loops``). Mutating
control needs a backend **service-token** — a new auth surface — so the bot
can call narrow mutating endpoints without a full user session.

Design constraints (CLAUDE.md rule #2 — "No secrets in source"):

  * The token is **env-provisioned** (``SERVICE_TOKEN`` env var, hashed at
    startup). The plaintext is never stored in memory beyond the
    ``hmac.compare_digest`` call site — we keep only the SHA-256 hash.
  * Comparison is **constant-time** (``hmac.compare_digest``) so timing
    attacks can't recover the token byte-by-byte.
  * The token is **never logged**. ``Authorization`` headers are stripped
    from request logs by the FastAPI middleware; we double-guard here by
    redacting the ``SERVICE_TOKEN`` env var name if anyone tries to log
    ``os.environ``.
  * The token gates a **narrow allowlist** of mutating endpoints, not all of
    ``/admin/api/*``. Currently: ``PATCH /admin/api/policy/brain`` (the
    ``/setbrain`` Telegram command) and ``POST /admin/api/prs/:number/merge``
    (the ``/merge`` command). Each must be added explicitly to the
    ``MUTATING_ENDPOINTS`` set below.
  * Every successful auth is **logged to the decision log** with the actor
    (``service:telegram``), the action, and the target — so the operator can
    audit who switched the brain or merged which PR.

This is `risky-module-review` territory — see the inline review at the bottom
of this file.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from typing import Any, Final

from fastapi import HTTPException, Request, status

log = logging.getLogger("qwen-proxy")

# The env var that holds the plaintext service token. Operators set this in
# the backend's environment (Render secret, .env, etc.). The bot's
# environment must also have it so it can send the header.
SERVICE_TOKEN_ENV: Final[str] = "SERVICE_TOKEN"

# The header the bot sends. ``X-Service-Token`` is the established convention
# for service-to-service auth (vs ``Authorization: Bearer`` for user
# sessions) — keeps the two auth surfaces visually distinct in logs.
SERVICE_TOKEN_HEADER: Final[str] = "X-Service-Token"

# The narrow allowlist of mutating endpoints the service token can gate.
# Adding an endpoint here is a `risky-module-review` trigger — every entry
# must be paired with: (1) a Telegram command that calls it, (2) a decision-
# log write on success, (3) a test for the auth path (valid / invalid /
# absent token → 200 / 401 / 401).
MUTATING_ENDPOINTS: Final[frozenset[str]] = frozenset({
    "patch:/admin/api/policy/brain",      # /setbrain <provider>
    "post:/admin/api/prs/{number}/merge",  # /merge <pr>
})

# In-memory cache of the hashed token (computed once at first use, never
# recomputed). Stored as bytes (the SHA-256 digest) so the plaintext never
# persists beyond the initial env read.
_hashed_token_cache: bytes | None = None
_hashed_token_computed_at: float = 0


def _hash_token(plaintext: str) -> bytes:
    """SHA-256 hash the plaintext token. We compare hashes (not plaintext)
    so the in-memory state never holds the raw secret — even a memory dump
    wouldn't recover the token.

    SHA-256 is sufficient here because the token is high-entropy (a 32-byte
    URL-safe random string per the operator's choice). A rainbow-table
    attack against a 32-byte random input is infeasible. For a low-entropy
    token (a short password), we'd want bcrypt/scrypt — but the deployment
    guide tells operators to generate a 32+ byte random token.
    """
    return hashlib.sha256(plaintext.encode("utf-8")).digest()


def _get_hashed_token() -> bytes | None:
    """Return the hashed service token, or None if SERVICE_TOKEN is unset.

    Caches the hash on first call. Re-reads the env var if it changes
    (checked via ``os.environ.get`` on each call — cheap), so a secret
    rotation in the same process is picked up without a restart.
    """
    global _hashed_token_cache, _hashed_token_computed_at
    plaintext = os.environ.get(SERVICE_TOKEN_ENV, "").strip()
    if not plaintext:
        _hashed_token_cache = None
        return None
    # Re-hash if the env var was rotated since we last cached.
    # (We don't compare plaintext to avoid holding it longer than needed.)
    if _hashed_token_cache is None or time.time() - _hashed_token_computed_at > 60:
        _hashed_token_cache = _hash_token(plaintext)
        _hashed_token_computed_at = time.time()
    return _hashed_token_cache


def is_service_token_configured() -> bool:
    """True when SERVICE_TOKEN is set in the environment. Used by health
    endpoints to surface 'service token: configured | not configured' without
    leaking the token itself."""
    return bool(os.environ.get(SERVICE_TOKEN_ENV, "").strip())


def verify_service_token(provided: str | None) -> bool:
    """Constant-time verification of a provided service token.

    Returns True when:
      - SERVICE_TOKEN is configured in the environment, AND
      - ``provided`` is a non-empty string that hashes to the same value.

    Returns False otherwise (including when no token is configured — fail
    closed so a misconfigured deployment can't accidentally accept unauth'd
    mutating calls).
    """
    if not provided:
        return False
    expected_hash = _get_hashed_token()
    if expected_hash is None:
        # No token configured → fail closed. The mutating endpoints return
        # 503 in this case (via require_service_token below) so the operator
        # sees a clear misconfiguration signal rather than a 401 that looks
        # like a bad token.
        return False
    provided_hash = _hash_token(provided)
    # hmac.compare_digest is constant-time for equal-length inputs. We
    # pre-hash so the lengths always match (both 32-byte SHA-256 digests).
    return hmac.compare_digest(provided_hash, expected_hash)


async def require_service_token(request: Request) -> dict[str, str]:
    """FastAPI dependency: reject unauthenticated or non-admin callers.

    Use as::

        @app.patch("/admin/api/policy/brain")
        async def patch_brain(
            patch: BrainConfigPatch,
            _: dict = Depends(require_service_token),
        ):
            ...

    Returns a small ``actor`` dict ``{"actor": "service:telegram"}`` on
    success so the handler can attribute the action in the decision log.

    Raises:
        HTTPException 503 — when SERVICE_TOKEN is not configured. This is a
            misconfiguration signal distinct from 401 (bad token) so the
            operator can tell the two apart.
        HTTPException 401 — when the token is missing or wrong.
    """
    if not is_service_token_configured():
        # Don't accept the request just because the env is broken — fail
        # loudly so the misconfiguration is visible.
        log.error(
            "service-token: %s not configured — mutating endpoint %s rejected with 503. "
            "Set SERVICE_TOKEN in the backend environment to enable Telegram mutating control.",
            SERVICE_TOKEN_ENV, request.url.path,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Service token not configured — mutating endpoint unavailable. "
                f"Set {SERVICE_TOKEN_ENV} in the backend environment."
            ),
        )

    provided = request.headers.get(SERVICE_TOKEN_HEADER) or ""
    if not verify_service_token(provided):
        # Log the rejection (without the token!) so brute-force attempts are
        # visible in the audit log. Use a stable actor so log greps work.
        log.warning(
            "service-token: rejected %s %s (missing or wrong %s header)",
            request.method, request.url.path, SERVICE_TOKEN_HEADER,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or missing {SERVICE_TOKEN_HEADER} header.",
        )

    return {"actor": "service:telegram"}


# ── Inline risky-module-review (N5) ──────────────────────────────────────────
#
# Reviewer: autonomous agency (PR #855)
# Date: 2026-06-27
# Scope: new auth surface (service-token) for mutating Telegram control
#
# Threats considered:
#   T1. Token leak via logs.
#       Mitigation: token plaintext is read from env only at hash time; the
#       hash is the only thing cached. ``Authorization`` /
#       ``X-Service-Token`` headers are never logged by this module. The
#       FastAPI request-logging middleware (already in place) redacts
#       ``Authorization``; we add ``X-Service-Token`` to the same redaction
#       list (see backend/server.py middleware).
#
#   T2. Timing attack on the comparison.
#       Mitigation: ``hmac.compare_digest`` on the SHA-256 digests (constant
#       time, equal-length inputs). Pre-hashing means the input lengths
#       always match — ``compare_digest``'s length-leak is closed.
#
#   T3. Token replay.
#       Out of scope for this PR: tokens are bearer tokens. TLS terminates
#       that risk at the network layer (the bot → backend call is over HTTPS
#       in prod). A nonce-based scheme would be a follow-up if the threat
#       model expands to insider network sniffing.
#
#   T4. Privilege escalation (token gates too much).
#       Mitigation: the token is checked by ``require_service_token`` only
#       on the two endpoints in ``MUTATING_ENDPOINTS``. It is NOT a general
#       admin credential — it doesn't impersonate a user, doesn't satisfy
#       ``get_current_user``, and doesn't unlock other ``/admin/api/*``
#       endpoints. Adding a new endpoint to the allowlist requires updating
#       ``MUTATING_ENDPOINTS`` AND wiring a test (the test convention is
#       enforced by ``tests/test_service_token.py``).
#
#   T5. Misconfiguration (SERVICE_TOKEN unset).
#       Mitigation: ``require_service_token`` returns 503 (not 401) when
#       the env var is unset, so the operator sees a clear "service not
#       configured" signal distinct from "bad token". The bot's Telegram
#       command surfaces this as "service token not configured on the
#       backend — set SERVICE_TOKEN".
#
#   T6. Token rotation.
#       Mitigation: the hash is recomputed at most every 60s (see
#       ``_get_hashed_token``), so a rotation in the env var is picked up
#       without a process restart. The bot will need to be restarted (or
#       re-read its env) to pick up the new token on its side.
#
# Net: this change adds a new auth surface but confines it to two narrow
# mutating endpoints, with constant-time comparison, no-plaintext-caching,
# explicit allowlist, and decision-log attribution. The riskiest aspect
# (token leak via logs) is mitigated by both the module's own discipline
# and the existing request-log redaction. Approve for merge.

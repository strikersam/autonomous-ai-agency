"""
.github/scripts/provider_policy.py — Read the durable provider policy from the
backend API with a hard failsafe: allow_paid=False when the API is unreachable.

CI scripts (generate_context, apply_review, review_agent, ci-failure-autofix)
import this to decide whether paid LLM providers (Anthropic) may be used.

Usage:
    from provider_policy import allow_paid
    if not allow_paid():
        print("Paid providers are disabled by policy — using free models only")

Failsafe hierarchy:
  1. Call GET /api/providers/policy on the backend (respects env: BACKEND_URL)
  2. Check PROVIDER_POLICY_ALLOW_PAID env var
  3. Default: False (never allow paid)
"""
from __future__ import annotations

import json
import logging
import os
import sys
import urllib.request

log = logging.getLogger("provider_policy")

BACKEND_URL = os.environ.get(
    "BACKEND_URL",
    os.environ.get("API_BASE_URL", "http://localhost:8001"),
).rstrip("/")

POLICY_CACHE: dict | None = None


def _fetch_policy() -> dict:
    """Fetch the provider policy from the backend API. Never raises."""
    global POLICY_CACHE
    if POLICY_CACHE is not None:
        return POLICY_CACHE

    url = f"{BACKEND_URL}/api/providers/policy"
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            allow = bool(data.get("allow_paid", False))
            POLICY_CACHE = {"allow_paid": allow}
            log.info("Provider policy fetched from %s: allow_paid=%s", url, allow)
            return POLICY_CACHE
    except Exception:
        # Failsafe: check env var, default to False
        env_val = os.environ.get("PROVIDER_POLICY_ALLOW_PAID", "").strip().lower()
        allow = env_val in ("1", "true", "yes", "on")
        POLICY_CACHE = {"allow_paid": allow}
        log.info(
            "Provider policy API unreachable — using env fallback: allow_paid=%s",
            allow,
        )
        return POLICY_CACHE


def allow_paid() -> bool:
    """Return True if paid providers (Anthropic) are allowed by policy."""
    return bool(_fetch_policy().get("allow_paid", False))


def reset_cache() -> None:
    """Reset the cached policy (test helper)."""
    global POLICY_CACHE
    POLICY_CACHE = None

"""Tests for standard rate-limit response headers on 429 responses.

Verifies that when check_rate_limit raises a 429 it includes the headers
that clients like Claude Code, Cursor, and Aider use for automatic backoff:
  - X-RateLimit-Limit
  - X-RateLimit-Remaining
  - X-RateLimit-Reset
  - Retry-After
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

import proxy


@pytest.fixture(autouse=True)
def _clear_rate_buckets():
    """Isolate rate-limit state between tests."""
    with proxy._rate_lock:
        proxy._rate_buckets.clear()
        proxy._rate_bucket_keys.clear()
    yield
    with proxy._rate_lock:
        proxy._rate_buckets.clear()
        proxy._rate_bucket_keys.clear()


def test_rate_limit_success_does_not_raise():
    old_limit = proxy.RATE_LIMIT_RPM
    proxy.RATE_LIMIT_RPM = 5
    try:
        proxy.check_rate_limit("key-ok")
        proxy.check_rate_limit("key-ok")
        proxy.check_rate_limit("key-ok")
    finally:
        proxy.RATE_LIMIT_RPM = old_limit


def test_rate_limit_exceeded_raises_429_with_standard_headers():
    old_limit = proxy.RATE_LIMIT_RPM
    proxy.RATE_LIMIT_RPM = 2
    try:
        proxy.check_rate_limit("key-limited")
        proxy.check_rate_limit("key-limited")

        with pytest.raises(HTTPException) as exc_info:
            proxy.check_rate_limit("key-limited")

        exc = exc_info.value
        assert exc.status_code == 429
        assert exc.headers is not None

        # Standard headers required by RFC 6585 and used by client SDKs
        assert exc.headers["X-RateLimit-Limit"] == "2"
        assert exc.headers["X-RateLimit-Remaining"] == "0"
        assert "X-RateLimit-Reset" in exc.headers
        assert "Retry-After" in exc.headers

        retry_after = int(exc.headers["Retry-After"])
        assert 1 <= retry_after <= 61

        reset_at = int(exc.headers["X-RateLimit-Reset"])
        assert reset_at > 0
    finally:
        proxy.RATE_LIMIT_RPM = old_limit


def test_rate_limit_retry_after_is_positive():
    old_limit = proxy.RATE_LIMIT_RPM
    proxy.RATE_LIMIT_RPM = 1
    try:
        proxy.check_rate_limit("key-one")

        with pytest.raises(HTTPException) as exc_info:
            proxy.check_rate_limit("key-one")

        assert int(exc_info.value.headers["Retry-After"]) >= 1
    finally:
        proxy.RATE_LIMIT_RPM = old_limit


def test_rate_limit_detail_mentions_retry():
    old_limit = proxy.RATE_LIMIT_RPM
    proxy.RATE_LIMIT_RPM = 1
    try:
        proxy.check_rate_limit("key-detail")

        with pytest.raises(HTTPException) as exc_info:
            proxy.check_rate_limit("key-detail")

        detail = exc_info.value.detail
        assert "Retry after" in detail or "retry" in detail.lower()
    finally:
        proxy.RATE_LIMIT_RPM = old_limit


def test_different_keys_have_independent_buckets():
    old_limit = proxy.RATE_LIMIT_RPM
    proxy.RATE_LIMIT_RPM = 1
    try:
        proxy.check_rate_limit("key-alpha")

        # key-beta should succeed even though key-alpha is exhausted
        proxy.check_rate_limit("key-beta")

        with pytest.raises(HTTPException) as exc_info:
            proxy.check_rate_limit("key-alpha")
        assert exc_info.value.status_code == 429
    finally:
        proxy.RATE_LIMIT_RPM = old_limit

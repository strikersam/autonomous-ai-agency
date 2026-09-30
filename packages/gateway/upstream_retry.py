"""packages/gateway/upstream_retry.py — retry transient upstream failures.

Runs *before* the model-swap fallback in ``chat_handlers._post_with_fallback``:
a momentary 429/502/503/504 or a refused connection is retried against the same
model first, because swapping models for a blip loses the caller's routing
choice. Backoff, jitter, ``Retry-After`` and the shared attempt/time budget come
from :mod:`packages.llm.retry`.

Only the non-streaming POST is retried. A stream that has begun cannot be
replayed, and this module is deliberately not wired into the streaming path.

``GATEWAY_UPSTREAM_RETRIES=0`` (the default) makes :func:`post_with_retries`
exactly one attempt with no wrapper behaviour, i.e. what the proxy did before.
"""

from __future__ import annotations

import logging

import httpx

from packages.llm.config import RetryConfig
from packages.llm.retry import RetryBudget, sleep_before_retry

log = logging.getLogger("qwen-proxy")

RETRYABLE_STATUSES = frozenset({429, 502, 503, 504})
_CONNECT_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout)
_TIMEOUT = httpx.Timeout(300.0, connect=10.0)


def default_retry_config(retries: int) -> RetryConfig:
    """Backoff policy for *retries* extra attempts."""
    return RetryConfig(
        max_attempts=retries + 1,
        base_delay_sec=0.5,
        max_delay_sec=10.0,
        multiplier=2.0,
        jitter=0.3,
        respect_retry_after=True,
        budget_sec=60.0,
    )


def _retry_after_seconds(resp: httpx.Response) -> float | None:
    raw = resp.headers.get("retry-after", "").strip()
    try:
        return float(raw) if raw else None
    except ValueError:
        return None  # an HTTP-date; the computed backoff is used instead


async def _post_once(url: str, body: bytes, headers: dict[str, str]) -> httpx.Response:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        return await client.post(url, content=body, headers=headers)


async def post_with_retries(
    url: str,
    body: bytes,
    headers: dict[str, str],
    retries: int,
    config: RetryConfig | None = None,
) -> httpx.Response:
    """POST *body* to *url*, retrying transient failures up to *retries* times.

    Returns the last response (whatever its status). A connect error that
    survives every attempt is re-raised so the caller's existing handling of it
    is unchanged.
    """
    if retries <= 0:
        return await _post_once(url, body, headers)
    policy = config or default_retry_config(retries)
    budget = RetryBudget(max_attempts=retries + 1, deadline_sec=policy.budget_sec)
    attempt = 0
    while True:
        attempt += 1
        budget.charge()
        try:
            resp = await _post_once(url, body, headers)
        except _CONNECT_ERRORS as exc:
            if budget.exhausted() or not await sleep_before_retry(attempt, policy, budget):
                raise
            log.warning("Upstream connect error (%s); retrying, attempt %d", type(exc).__name__, attempt + 1)
            continue
        if resp.status_code not in RETRYABLE_STATUSES or budget.exhausted():
            return resp
        wait_hint = _retry_after_seconds(resp)
        if not await sleep_before_retry(attempt, policy, budget, retry_after=wait_hint):
            return resp
        log.warning("Upstream returned %d; retrying, attempt %d", resp.status_code, attempt + 1)

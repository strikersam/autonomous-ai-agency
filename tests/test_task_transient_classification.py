"""Regression: transient provider/sandbox errors must re-queue a task, not fail it.

Production showed 349 of 468 tasks FAILED. Any exception that was not a brain
connection error was marked permanently FAILED, including rate limits (HTTP 429),
upstream 5xx responses and sandbox-provider API errors that are retryable.
"""
from __future__ import annotations

import httpx
import pytest

import tasks.service as svc
from services.freestyle_sandbox import FreestyleApiError


@pytest.mark.parametrize(
    "exc",
    [
        FreestyleApiError(429, "rate_limited", "slow down"),
        FreestyleApiError(503, "unavailable", "try later"),
        FreestyleApiError(500, "internal", "boom"),
        RuntimeError("Sandbox provider freestyle failed to open: upstream 502"),
        Exception("429 Too Many Requests"),
        Exception("Rate limit reached for model"),
        Exception("Service Unavailable"),
        Exception("model is overloaded, please retry"),
        httpx.HTTPStatusError(
            "server error",
            request=httpx.Request("POST", "https://example.invalid"),
            response=httpx.Response(503, request=httpx.Request("POST", "https://example.invalid")),
        ),
    ],
)
def test_transient_errors_are_requeued(exc: BaseException) -> None:
    assert svc._is_transient_error(exc), f"should be transient: {exc!r}"


@pytest.mark.parametrize(
    "exc",
    [
        ValueError("bad plan output"),
        FreestyleApiError(400, "bad_request", "invalid payload"),
        FreestyleApiError(404, "not_found", "no such vm"),
        Exception("ValueError: bad plan output"),
        KeyError("missing"),
        RuntimeError("failed to open file foo.py"),
        RuntimeError("task 4290 failed"),
        RuntimeError("Task abc429 KeyError"),
        RuntimeError("port 8429 bad"),
    ],
)
def test_permanent_errors_still_fail(exc: BaseException) -> None:
    assert not svc._is_transient_error(exc), f"should be permanent: {exc!r}"


def test_brain_connection_errors_remain_transient() -> None:
    assert svc._is_transient_error(httpx.ConnectError("x"))
    assert svc._is_transient_error(Exception("Connection refused"))

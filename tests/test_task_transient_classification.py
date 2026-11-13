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


class _StatusError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def test_any_5xx_status_is_transient_without_a_message_match() -> None:
    assert svc._is_transient_error(_StatusError(529, "capacity exhausted"))
    assert svc._is_transient_error(_StatusError(507, "x"))


def test_a_permanent_status_wins_over_transient_wording() -> None:
    assert not svc._is_transient_error(
        FreestyleApiError(400, "bad_request", "sandbox provider configuration is invalid")
    )
    assert not svc._is_transient_error(_StatusError(403, "rate limit plan does not include this"))


def test_failed_result_text_is_capacity_only_for_failover_phrases() -> None:
    assert svc._is_capacity_result(
        "Tool selection failed after 3 attempts: All brain providers exhausted. Last error: x"
    )
    assert svc._is_capacity_result("All 1 brain provider attempt(s) failed: nvidia: nvidia HTTP 429")
    assert not svc._is_capacity_result("the README mentions a rate limit of 5 requests")
    assert not svc._is_capacity_result("tests failed: 2 assertions")
    assert not svc._is_capacity_result(None)


async def test_failed_result_from_brain_capacity_is_requeued_not_failed() -> None:
    from types import SimpleNamespace

    calls: list[str] = []
    transitions: list[object] = []
    coordinator = SimpleNamespace(
        workflow=SimpleNamespace(
            transition=lambda task, status, **kw: transitions.append(status),
            add_comment=lambda *a, **kw: None,
        ),
        _requeue_or_block_unavailable=lambda task, exc, *, what: calls.append(what),
    )
    from unittest.mock import MagicMock

    task = MagicMock()
    result = MagicMock()
    result.success = False
    result.metadata = {}
    result.output = "planning: All brain providers exhausted. Last error: all candidates failed"
    await svc.TaskExecutionCoordinator._apply_result(coordinator, task, None, result)
    assert calls == ["Brain capacity exhausted"]
    assert transitions == [], "a capacity failure must not mark the task FAILED"

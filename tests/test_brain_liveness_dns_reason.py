"""A dead provider hostname must be reported as a DNS failure, not a raw errno.

Production symptom (Aerolink, whose configured host ``capi.aerolink.lat`` no
longer resolves)::

    ✗ Probe error: [Errno -2] Name

The probe surfaced the bare OS error, which the Brain card then truncates. The
operator learns neither which host failed nor which knob fixes it, and the
message reads like a key or model problem when it is neither.
"""
from __future__ import annotations

import socket

import httpx
import pytest

from services.brain_liveness import _is_dns_failure, _probe_failure_reason


class TestIsDnsFailure:
    def test_bare_gaierror(self) -> None:
        assert _is_dns_failure(socket.gaierror(-2, "Name or service not known"))

    def test_gaierror_wrapped_in_connect_error(self) -> None:
        """httpx wraps the resolver error — the cause chain must be walked."""
        root = socket.gaierror(-2, "Name or service not known")
        wrapped = httpx.ConnectError("[Errno -2] Name or service not known")
        wrapped.__cause__ = root

        assert _is_dns_failure(wrapped)

    def test_connect_error_message_only(self) -> None:
        """Some stacks lose the cause and keep only the resolver text."""
        assert _is_dns_failure(
            httpx.ConnectError("[Errno -2] Name or service not known")
        )

    @pytest.mark.parametrize(
        "exc",
        [
            httpx.ConnectError("[Errno 111] Connection refused"),
            httpx.ReadTimeout("timed out"),
            ValueError("something else entirely"),
        ],
    )
    def test_non_dns_errors_are_not_matched(self, exc: Exception) -> None:
        assert not _is_dns_failure(exc)

    def test_self_referential_cause_chain_terminates(self) -> None:
        """A cyclic __cause__ must not hang the probe."""
        exc = ValueError("loop")
        exc.__cause__ = exc

        assert _is_dns_failure(exc) is False


class TestProbeFailureReason:
    def test_dns_failure_names_the_host_and_the_env_override(self) -> None:
        exc = httpx.ConnectError("[Errno -2] Name or service not known")
        exc.__cause__ = socket.gaierror(-2, "Name or service not known")

        reason = _probe_failure_reason(
            exc, "https://capi.aerolink.lat/v1", "aerolink"
        )

        assert "capi.aerolink.lat" in reason
        assert "AEROLINK_BASE_URL" in reason
        assert "DNS" in reason
        # The raw errno alone was the whole problem.
        assert reason != "Probe error: [Errno -2] Name or service not known"

    def test_non_dns_failure_keeps_the_original_message(self) -> None:
        reason = _probe_failure_reason(
            ValueError("boom"), "https://api.example.test/v1", "example"
        )

        assert reason == "Probe error: boom"

    def test_unknown_provider_falls_back_to_a_derived_env_var(self) -> None:
        exc = socket.gaierror(-2, "Name or service not known")

        reason = _probe_failure_reason(exc, "https://x.invalid/v1", "someprovider")

        assert "SOMEPROVIDER_BASE_URL" in reason


@pytest.mark.asyncio
async def test_probe_reports_dns_failure_end_to_end(monkeypatch) -> None:
    """The reason must survive the real probe entry point, not just the helper."""
    import services.brain_liveness as bl

    monkeypatch.setenv("AEROLINK_API_KEY", "test-key-not-real")

    async def _raise_dns_error(*args, **kwargs):
        exc = httpx.ConnectError("[Errno -2] Name or service not known")
        exc.__cause__ = socket.gaierror(-2, "Name or service not known")
        raise exc

    monkeypatch.setattr(bl, "_probe_openai_compat", _raise_dns_error)

    result = await bl.probe_model_liveness(
        "aerolink", "claude-sonnet-5", timeout=5
    )

    assert result.live is False
    assert "capi.aerolink.lat" in result.reason
    assert "AEROLINK_BASE_URL" in result.reason
    # The truncated, uninformative original must not come back.
    assert not result.reason.startswith("Probe error: [Errno -2]")


def test_configured_aerolink_host_is_the_one_that_fails() -> None:
    """Documents the actual defect: the shipped Aerolink host does not resolve.

    This asserts on configuration, not on live DNS — the test must not depend on
    network access. It pins the fact that the failing host is what the catalog
    ships, so if someone corrects the hostname this test tells them to re-verify
    rather than silently passing.
    """
    from packages.ai.brain_config import PROVIDER_DEFAULT_BASE_URL

    assert "aerolink" in PROVIDER_DEFAULT_BASE_URL
    # If this changes, the operator has updated the endpoint — re-run a live
    # probe to confirm the new host resolves before shipping.
    assert PROVIDER_DEFAULT_BASE_URL["aerolink"] == "https://capi.aerolink.lat/v1"

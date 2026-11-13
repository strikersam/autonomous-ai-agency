"""Tests for the outbound identity guard (#1892 item 3).

``agent/web_reach.py`` sends model-chosen URLs and search queries to third parties.
When an operator turns ``WEB_REACH_EGRESS_IDENTITY_GUARD`` on *and* lists an address in
``OPERATOR_EMAILS``, a request carrying that address is refused before it leaves the
process — with a generic reason and a ``safety_event`` that never contain it.
"""
from __future__ import annotations

import logging

import pytest

import services.otel_tracing as ot
from agent.web_reach import get_web_reach, unsafe_target_reason
from packages.config import settings
from packages.security.egress import GENERIC_REASON, egress_identity_reason

EMAIL = "operator@agency.example"
PUBLIC_URL = f"https://93.184.216.34/?contact={EMAIL}"


@pytest.fixture
def guard(monkeypatch):
    """Configure the guard: on/off, and which addresses are protected."""

    def _configure(enabled: bool, emails: str = EMAIL) -> None:
        monkeypatch.setattr(
            settings, "web_reach_egress_identity_guard_raw", "true" if enabled else "false"
        )
        monkeypatch.setattr(settings, "operator_emails_raw", emails)

    return _configure


@pytest.fixture
def no_dns(monkeypatch):
    """Fail the test if a name is resolved: the refusal must precede any lookup."""
    import socket

    def _boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("DNS lookup happened before the guard refused")

    monkeypatch.setattr(socket, "getaddrinfo", _boom)


@pytest.fixture
def stub_backends(monkeypatch):
    """Replace the search backends with one that records being called."""
    called: list[tuple] = []

    def _backend(query, limit, timeout):  # noqa: ANN001, ANN202
        called.append((query, limit, timeout))
        return [{"title": "match", "url": "https://example.com/match"}]

    monkeypatch.setattr("agent.web_reach._SEARCH_BACKENDS", (("stub", _backend),))
    return called


@pytest.fixture
def safety_events(monkeypatch):
    """Record ``emit_safety_event`` calls without touching sys.modules.

    ``agent/web_reach.py`` imports the emitter inside the function, so patching the
    attribute on its module is enough — and unlike installing a fake ``opentelemetry``
    package, it cannot leak into the next test module.
    """
    events: list[tuple[str, str, str]] = []

    def _record(kind, subject, reason):  # noqa: ANN001
        events.append((kind, subject, reason))

    monkeypatch.setattr(ot, "emit_safety_event", _record)
    return events


def test_guard_off_changes_nothing(guard, stub_backends):
    # The shipped default: with the guard off, neither a URL nor a query is inspected.
    guard(False)
    assert egress_identity_reason(PUBLIC_URL) is None
    assert unsafe_target_reason(PUBLIC_URL) is None
    assert get_web_reach().search_web(f"who is {EMAIL}")["ok"] is True
    assert len(stub_backends) == 1


def test_guard_on_refuses_a_url_before_any_dns_lookup(guard, no_dns):
    guard(True)
    assert unsafe_target_reason(PUBLIC_URL) == GENERIC_REASON


@pytest.mark.parametrize(
    "encoded",
    ["operator%40agency.example", "operator%2540agency.example"],
)
def test_encoding_cannot_hide_the_address(guard, encoded):
    # %40 is a one-line bypass; a doubly-encoded value is one more round.
    guard(True)
    assert egress_identity_reason(f"https://93.184.216.34/?contact={encoded}") == GENERIC_REASON


def test_matching_is_case_insensitive(guard):
    guard(True)
    assert egress_identity_reason(PUBLIC_URL.replace(EMAIL, EMAIL.upper())) == GENERIC_REASON


def test_guard_on_lets_other_requests_through(guard):
    guard(True)
    assert unsafe_target_reason("https://93.184.216.34/plain") is None


def test_guard_on_without_configured_addresses_is_inert(guard, stub_backends):
    # A guard with nothing to protect must not become a blanket refusal.
    guard(True, emails="")
    assert egress_identity_reason(PUBLIC_URL) is None
    assert get_web_reach().search_web(f"who is {EMAIL}")["ok"] is True


def test_search_refusal_never_calls_a_backend(guard, stub_backends):
    guard(True)
    result = get_web_reach().search_web(f"who is {EMAIL}")
    assert result["ok"] is False
    assert GENERIC_REASON in result["error"]
    # Neither the address nor its domain may come back to the model in the refusal.
    assert EMAIL not in str(result)
    assert "agency.example" not in str(result)
    assert stub_backends == []


def test_url_block_emits_a_safety_event_without_the_identity(guard, safety_events):
    guard(True)
    assert unsafe_target_reason(PUBLIC_URL) == GENERIC_REASON
    assert len(safety_events) == 1
    kind, subject, reason = safety_events[0]
    assert kind == "web_reach_block"
    assert reason == GENERIC_REASON
    assert EMAIL not in str(safety_events)
    assert "agency.example" not in str(safety_events)


def test_search_refusal_emits_a_safety_event(guard, safety_events, stub_backends):
    guard(True)
    get_web_reach().search_web(f"contact {EMAIL}")
    assert safety_events
    kind, subject, reason = safety_events[0]
    assert kind == "web_reach_block"
    assert subject == ""  # a query has no host to digest, and the text is the identity
    assert EMAIL not in str(safety_events)
    assert "agency.example" not in str(safety_events)


def test_nothing_logs_the_address(guard, stub_backends, caplog):
    guard(True)
    with caplog.at_level(logging.DEBUG):
        unsafe_target_reason(PUBLIC_URL)
        get_web_reach().search_web(f"contact {EMAIL}")
    assert EMAIL not in caplog.text
    assert "agency.example" not in caplog.text

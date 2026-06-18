"""Unit tests for router/circuit_breaker.py."""

from __future__ import annotations

import os
import time

import pytest

from router.circuit_breaker import OllamaCircuitBreaker, get_circuit_breaker, reset_circuit_breaker


@pytest.fixture(autouse=True)
def clean_breaker(monkeypatch):
    """Reset the singleton and env vars before every test."""
    reset_circuit_breaker()
    monkeypatch.setenv("CIRCUIT_BREAKER_ENABLED", "true")
    monkeypatch.setenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "3")
    monkeypatch.setenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "60")
    yield
    reset_circuit_breaker()


# ── Basic state machine ──────────────────────────────────────────────────────────────────────────────

def test_fresh_circuit_is_closed():
    b = OllamaCircuitBreaker()
    assert not b.is_open("qwen3-coder:30b")
    assert b.state_for("qwen3-coder:30b") == "CLOSED"


def test_single_failure_does_not_open():
    b = OllamaCircuitBreaker()
    b.record_failure("model-a")
    assert not b.is_open("model-a")
    assert b.state_for("model-a") == "CLOSED"


def test_circuit_opens_at_threshold(monkeypatch):
    monkeypatch.setenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "3")
    b = OllamaCircuitBreaker()
    b.record_failure("model-a")
    b.record_failure("model-a")
    assert not b.is_open("model-a")
    b.record_failure("model-a")
    assert b.is_open("model-a")
    assert b.state_for("model-a") == "OPEN"


def test_success_resets_failure_count():
    b = OllamaCircuitBreaker()
    b.record_failure("model-a")
    b.record_failure("model-a")
    b.record_success("model-a")
    assert not b.is_open("model-a")
    assert b.state_for("model-a") == "CLOSED"


def test_success_after_open_closes_circuit(monkeypatch):
    monkeypatch.setenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "1")
    b = OllamaCircuitBreaker()
    b.record_failure("model-a")
    assert b.state_for("model-a") == "OPEN"
    b.record_success("model-a")
    assert b.state_for("model-a") == "CLOSED"
    assert not b.is_open("model-a")


# ── Recovery / HALF_OPEN ─────────────────────────────────────────────────────────────────────────────\n
def _trip_and_expire(b: OllamaCircuitBreaker, model: str) -> None:
    """Trip the circuit for *model* and backdate opened_at so it expires immediately."""
    b.record_failure(model)
    # Backdate opened_at by 1000s so the recovery timeout has long since elapsed
    b._circuits[model].opened_at = 0.0


def test_circuit_transitions_to_half_open_after_timeout(monkeypatch):
    monkeypatch.setenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "1")
    b = OllamaCircuitBreaker()
    b.record_failure("model-b")
    assert b.state_for("model-b") == "OPEN"
    # Backdate opened_at so recovery timeout has elapsed
    b._circuits["model-b"].opened_at = 0.0
    result = b.is_open("model-b")
    assert not result  # allowed through for probe
    assert b.state_for("model-b") == "HALF_OPEN"


def test_half_open_allows_only_one_probe(monkeypatch):
    monkeypatch.setenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "1")
    b = OllamaCircuitBreaker()
    _trip_and_expire(b, "model-b")
    first = b.is_open("model-b")   # transitions to HALF_OPEN, probe starts
    second = b.is_open("model-b")  # second caller — probe in flight, block this
    assert not first
    assert second  # second request is blocked


def test_failed_probe_reopens_circuit(monkeypatch):
    monkeypatch.setenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "1")
    b = OllamaCircuitBreaker()
    _trip_and_expire(b, "model-b")
    b.is_open("model-b")  # probe — HALF_OPEN
    b.record_failure("model-b")  # probe failed
    assert b.state_for("model-b") == "OPEN"


def test_successful_probe_closes_circuit(monkeypatch):
    monkeypatch.setenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "1")
    b = OllamaCircuitBreaker()
    _trip_and_expire(b, "model-b")
    b.is_open("model-b")  # probe
    b.record_success("model-b")
    assert b.state_for("model-b") == "CLOSED"


# ── Isolation between models ────────────────────────────────────────────────────────────────────────────\n
def test_independent_circuits_per_model(monkeypatch):
    monkeypatch.setenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "1")
    b = OllamaCircuitBreaker()
    b.record_failure("model-x")
    assert b.is_open("model-x")
    assert not b.is_open("model-y")  # different model unaffected


# ── Disabled mode ──────────────────────────────────────────────────────────────────────────────────

def test_disabled_never_opens(monkeypatch):
    monkeypatch.setenv("CIRCUIT_BREAKER_ENABLED", "false")
    monkeypatch.setenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "1")
    b = OllamaCircuitBreaker()
    for _ in range(10):
        b.record_failure("model-z")
    assert not b.is_open("model-z")


# ── Reset ─────────────────────────────────────────────────────────────────────────────────────────\n
def test_reset_single_model(monkeypatch):
    monkeypatch.setenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "1")
    b = OllamaCircuitBreaker()
    b.record_failure("model-a")
    assert b.is_open("model-a")
    b.reset("model-a")
    assert not b.is_open("model-a")


def test_reset_all_models(monkeypatch):
    monkeypatch.setenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "1")
    b = OllamaCircuitBreaker()
    b.record_failure("m1")
    b.record_failure("m2")
    assert b.is_open("m1") and b.is_open("m2")
    b.reset()
    assert not b.is_open("m1") and not b.is_open("m2")


# ── Stats ──────────────────────────────────────────────────────────────────────────────────────────\n
def test_stats_returns_snapshot(monkeypatch):
    monkeypatch.setenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")
    b = OllamaCircuitBreaker()
    b.record_failure("alpha")
    b.record_failure("alpha")
    stats = b.stats()
    assert "alpha" in stats
    assert stats["alpha"]["failures"] == 2
    assert stats["alpha"]["state"] == "CLOSED"


# ── Singleton ──────────────────────────────────────────────────────────────────────────────────────\n
def test_singleton_returns_same_instance():
    b1 = get_circuit_breaker()
    b2 = get_circuit_breaker()
    assert b1 is b2


def test_reset_singleton_creates_fresh():
    b1 = get_circuit_breaker()
    reset_circuit_breaker()
    b2 = get_circuit_breaker()
    assert b1 is not b2

"""tests/test_provider_max_rpm.py — packages/ai/brain_config.provider_max_rpm().

Config-boundary rule: env vars are read here, in the approved config module,
not in packages/ai/rate_limiter.py's business logic (which calls this).
"""
from __future__ import annotations

from packages.ai.brain_config import provider_max_rpm


def test_unset_returns_none(monkeypatch):
    monkeypatch.delenv("CEREBRAS_MAX_RPM", raising=False)
    assert provider_max_rpm("cerebras") is None


def test_valid_value_returned(monkeypatch):
    monkeypatch.setenv("CEREBRAS_MAX_RPM", "28")
    assert provider_max_rpm("cerebras") == 28.0


def test_non_numeric_returns_none(monkeypatch):
    monkeypatch.setenv("CEREBRAS_MAX_RPM", "not-a-number")
    assert provider_max_rpm("cerebras") is None


def test_zero_and_negative_return_none(monkeypatch):
    monkeypatch.setenv("CEREBRAS_MAX_RPM", "0")
    assert provider_max_rpm("cerebras") is None
    monkeypatch.setenv("CEREBRAS_MAX_RPM", "-5")
    assert provider_max_rpm("cerebras") is None


def test_infinite_and_nan_return_none(monkeypatch):
    """inf previously parsed successfully and passed a bare `> 0` check,
    producing a zero pacing interval in the caller (i.e. no pacing at all,
    silently) instead of being rejected like other invalid input."""
    monkeypatch.setenv("CEREBRAS_MAX_RPM", "inf")
    assert provider_max_rpm("cerebras") is None
    monkeypatch.setenv("CEREBRAS_MAX_RPM", "nan")
    assert provider_max_rpm("cerebras") is None


def test_provider_id_uppercased_for_lookup(monkeypatch):
    monkeypatch.setenv("GROQ_MAX_RPM", "30")
    assert provider_max_rpm("groq") == 30.0
    assert provider_max_rpm("GROQ") == 30.0

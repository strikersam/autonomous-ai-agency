"""Bedrock registers only when the operator opts into paid brains.

Regression for the "Bedrock keeps coming back" defect: ``ProviderRouter.from_env``
appended a ``bedrock`` provider whenever ``AWS_ACCESS_KEY_ID``+``AWS_SECRET_ACCESS_KEY``
(or the ``BEDROCK_*`` aliases) were both set, independent of ``ALLOW_PAID_BRAIN``.
Removing it in the UI never stuck: the record was rebuilt from the environment on
every restart. Bedrock now follows the same paid-brain opt-in the agent loop and
model router already honour.
"""
from __future__ import annotations

import pytest

from packages.ai.router import ProviderRouter


@pytest.fixture(autouse=True)
def _bedrock_kill_switch_off(monkeypatch):
    """These tests cover Bedrock once the operator has turned the kill switch off."""
    monkeypatch.setenv("BEDROCK_DISABLED", "false")


@pytest.fixture(autouse=True)
def _aws_creds_present(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIATEST1234567890AB")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test_secret")
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVidiaApiKey", raising=False)
    yield


def _bedrock_registered() -> bool:
    return any(p.provider_id == "bedrock" for p in ProviderRouter.from_env().providers)


def test_bedrock_absent_when_paid_brain_off(monkeypatch):
    monkeypatch.setenv("ALLOW_PAID_BRAIN", "false")
    assert _bedrock_registered() is False


def test_bedrock_absent_when_paid_brain_unset(monkeypatch):
    monkeypatch.delenv("ALLOW_PAID_BRAIN", raising=False)
    assert _bedrock_registered() is False


def test_bedrock_present_when_paid_brain_on(monkeypatch):
    monkeypatch.setenv("ALLOW_PAID_BRAIN", "true")
    assert _bedrock_registered() is True

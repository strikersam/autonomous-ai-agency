"""tests/test_hermes_base_url.py — resolve_hermes_base_url precedence."""
from __future__ import annotations

from packages.ai.brain_config import resolve_hermes_base_url


def test_env_wins(monkeypatch):
    monkeypatch.setenv("HERMES_BASE_URL", "http://hermes:8100/")
    assert resolve_hermes_base_url() == "http://hermes:8100"  # trailing slash stripped


def test_default_when_unset(monkeypatch):
    monkeypatch.delenv("HERMES_BASE_URL", raising=False)
    assert resolve_hermes_base_url() == "http://localhost:8100"

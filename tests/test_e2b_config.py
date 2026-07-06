"""tests/test_e2b_config.py — Config-module behaviour for E2B sandbox.

Constitution §1: this is the ONLY module that reads ``os.environ.get`` for E2B
keys. Tests cover the activation matrix and the kill-switch, plus the
never-leak-the-key invariant on the frozen E2BConfig dataclass.

Post-data-flow-fix guardrail: E2B requires explicit opt-in via
``E2B_ENABLED=true`` / ``RUNTIME_E2B_ENABLED=true`` / ``AGENT_SANDBOX_MODE=e2b``.
A bare ``E2B_API_KEY`` no longer auto-enables.
"""
from __future__ import annotations

import pytest

from services import e2b_config
from services.e2b_config import E2BConfig, e2b_enabled, is_e2b_sdk_importable, resolve_e2b_config


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Strip every E2B-related env var before each test."""
    for k in ("E2B_API_KEY", "E2B_ENABLED", "RUNTIME_E2B_ENABLED",
              "E2B_TEMPLATE", "E2B_TIMEOUT_SEC", "E2B_SANDBOX_METADATA",
              "AGENT_SANDBOX_MODE"):
        monkeypatch.delenv(k, raising=False)
    yield


# ── Activation matrix (post-guardrail: explicit opt-in required) ──────────


def test_e2b_disabled_when_no_key(monkeypatch):
    """No key → e2b_enabled() is False and resolve_e2b_config() returns None."""
    assert e2b_enabled() is False
    assert resolve_e2b_config() is None


def test_e2b_disabled_when_key_only_no_opt_in(monkeypatch):
    """GUARDRAIL: bare E2B_API_KEY without E2B_ENABLED=true → NOT enabled.

    This is the critical guardrail: adding the key alone must NOT silently
    activate E2B (the execution data flow was broken before the fixes).
    """
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    # No E2B_ENABLED, no RUNTIME_E2B_ENABLED, no AGENT_SANDBOX_MODE
    assert e2b_enabled() is False
    assert resolve_e2b_config() is None


def test_e2b_enabled_with_explicit_opt_in(monkeypatch):
    """E2B_ENABLED=true + key → enabled, config resolves."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")
    assert e2b_enabled() is True
    cfg = resolve_e2b_config()
    assert cfg is not None
    assert cfg.api_key == "e2b_test_key_abc123"
    assert cfg.template == "base"
    assert cfg.timeout_sec == 300


def test_e2b_enabled_with_runtime_flag(monkeypatch):
    """RUNTIME_E2B_ENABLED=true + key → enabled (alt opt-in path)."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("RUNTIME_E2B_ENABLED", "true")
    assert e2b_enabled() is True
    cfg = resolve_e2b_config()
    assert cfg is not None


def test_e2b_enabled_with_sandbox_mode(monkeypatch):
    """AGENT_SANDBOX_MODE=e2b + key → enabled (roadmap ★5 kill-switch)."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("AGENT_SANDBOX_MODE", "e2b")
    assert e2b_enabled() is True
    cfg = resolve_e2b_config()
    assert cfg is not None


def test_e2b_enabled_opt_in_without_key_returns_false(monkeypatch):
    """E2B_ENABLED=true but no key → False (key is still required)."""
    monkeypatch.setenv("E2B_ENABLED", "true")
    monkeypatch.delenv("E2B_API_KEY", raising=False)
    assert e2b_enabled() is False
    assert resolve_e2b_config() is None


# ── Kill-switch ───────────────────────────────────────────────────────────


def test_e2b_kill_switch_explicit_false(monkeypatch):
    """E2B_ENABLED=false wins over key + opt-in (operator kill-switch)."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "false")
    assert e2b_enabled() is False
    assert resolve_e2b_config() is None


def test_e2b_kill_switch_case_insensitive(monkeypatch):
    """E2B_ENABLED=FALSE / False / NO all count as opt-out."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    for falsy in ("FALSE", "False", "no", "off", "0"):
        monkeypatch.setenv("E2B_ENABLED", falsy)
        assert e2b_enabled() is False, f"E2B_ENABLED={falsy!r} should disable"
        assert resolve_e2b_config() is None


# ── Config resolution ────────────────────────────────────────────────────


def test_e2b_template_override(monkeypatch):
    """E2B_TEMPLATE overrides the default 'base'."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")
    monkeypatch.setenv("E2B_TEMPLATE", "python-pytest")
    cfg = resolve_e2b_config()
    assert cfg is not None
    assert cfg.template == "python-pytest"


def test_e2b_timeout_clamped_low(monkeypatch):
    """E2B_TIMEOUT_SEC below 30 is clamped to 30."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")
    monkeypatch.setenv("E2B_TIMEOUT_SEC", "5")
    cfg = resolve_e2b_config()
    assert cfg is not None
    assert cfg.timeout_sec == 30


def test_e2b_timeout_clamped_high(monkeypatch):
    """E2B_TIMEOUT_SEC above 1800 is clamped to 1800."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")
    monkeypatch.setenv("E2B_TIMEOUT_SEC", "9999")
    cfg = resolve_e2b_config()
    assert cfg is not None
    assert cfg.timeout_sec == 1800


def test_e2b_timeout_invalid_falls_back_to_default(monkeypatch):
    """A non-int E2B_TIMEOUT_SEC falls back to 300 (default)."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")
    monkeypatch.setenv("E2B_TIMEOUT_SEC", "not-a-number")
    cfg = resolve_e2b_config()
    assert cfg is not None
    assert cfg.timeout_sec == 300


def test_e2b_metadata_parsed(monkeypatch):
    """E2B_SANDBOX_METADATA 'key=value,key=value' is parsed into a dict."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")
    monkeypatch.setenv("E2B_SANDBOX_METADATA", "team=platform,env=test")
    cfg = resolve_e2b_config()
    assert cfg is not None
    assert cfg.metadata == {"team": "platform", "env": "test"}


def test_e2b_metadata_none_when_unset(monkeypatch):
    """metadata is None when E2B_SANDBOX_METADATA is unset."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")
    cfg = resolve_e2b_config()
    assert cfg is not None
    assert cfg.metadata is None


# ── Security invariants ──────────────────────────────────────────────────


def test_e2b_config_does_not_leak_key_in_repr(monkeypatch):
    """The frozen dataclass __repr__ must not include the actual key."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_super_secret_key_xyz_12345")
    monkeypatch.setenv("E2B_ENABLED", "true")
    cfg = resolve_e2b_config()
    assert cfg is not None
    r = repr(cfg)
    s = str(cfg)
    assert "e2b_super_secret_key_xyz_12345" not in r
    assert "e2b_super_secret_key_xyz_12345" not in s
    assert "***" in r


def test_e2b_config_is_frozen(monkeypatch):
    """E2BConfig is frozen — assignment must raise FrozenInstanceError."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")
    cfg = resolve_e2b_config()
    assert cfg is not None
    with pytest.raises(Exception):  # FrozenInstanceError
        cfg.api_key = "tampered"  # type: ignore[misc]


def test_e2b_sdk_importable_returns_bool():
    """is_e2b_sdk_importable() returns a bool (True in test env with SDK)."""
    result = is_e2b_sdk_importable()
    assert isinstance(result, bool)


def test_e2b_enabled_idempotent(monkeypatch):
    """Calling e2b_enabled() twice returns the same value (no side effects)."""
    monkeypatch.setenv("E2B_API_KEY", "e2b_test_key_abc123")
    monkeypatch.setenv("E2B_ENABLED", "true")
    first = e2b_enabled()
    second = e2b_enabled()
    assert first == second


def test_e2b_config_module_is_sole_env_reader():
    """Constitution §1: no other module in services/ may read E2B_API_KEY directly."""
    import re
    from pathlib import Path
    services_dir = Path(__file__).parent.parent / "services"
    pattern = re.compile(r'os\.environ\.get\s*\(\s*["\']E2B_API_KEY["\']')
    violators = []
    for p in services_dir.glob("*.py"):
        if p.name == "e2b_config.py":
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if pattern.search(text):
            violators.append(p.name)
    assert not violators, (
        f"Constitution §1 violation — these files read E2B_API_KEY directly "
        f"instead of going through services.e2b_config: {violators}"
    )

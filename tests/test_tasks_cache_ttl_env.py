"""Round-trip tests for TASKS_LIST_ALL_CACHE_TTL_SEC env-var override in tasks/api.py.

Covers seven operator-mistake classes:
1. Default behaviour (env unset → 8.0s).
2. Valid numeric override is honored.
3. Non-numeric value falls back to default (no ValueError at import).
4. Zero / negative falls back to default (cache must always be > 0).
5. NaN falls back to default (`float("nan")` parses but the TTL comparison
   would silently disable caching).
6. Infinity falls back to default (`float("inf")` parses positive but would
   cause the dict to grow unbounded).
"""
from __future__ import annotations

import importlib

import pytest


def _reload_tasks_api_with_env(value: str | None) -> object:
    """Reload tasks.api after injecting TASKS_LIST_ALL_CACHE_TTL_SEC=value (or unset)."""
    import tasks.api as api_mod

    if value is None:
        api_mod.__dict__.pop("TASKS_LIST_ALL_CACHE_TTL_SEC", None)
        import os

        os.environ.pop("TASKS_LIST_ALL_CACHE_TTL_SEC", None)
    else:
        import os

        os.environ["TASKS_LIST_ALL_CACHE_TTL_SEC"] = value
    return importlib.reload(api_mod)


def test_default_ttl_is_eight_seconds_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TASKS_LIST_ALL_CACHE_TTL_SEC", raising=False)
    api = _reload_tasks_api_with_env(None)
    assert api._LIST_ALL_CACHE_TTL == 8.0


def test_valid_numeric_override_is_honored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TASKS_LIST_ALL_CACHE_TTL_SEC", "0.5")
    api = _reload_tasks_api_with_env("0.5")
    assert api._LIST_ALL_CACHE_TTL == 0.5


def test_non_numeric_value_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TASKS_LIST_ALL_CACHE_TTL_SEC", "not-a-number")
    api = _reload_tasks_api_with_env("not-a-number")
    assert api._LIST_ALL_CACHE_TTL == 8.0


def test_zero_value_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TASKS_LIST_ALL_CACHE_TTL_SEC", "0")
    api = _reload_tasks_api_with_env("0")
    assert api._LIST_ALL_CACHE_TTL == 8.0


def test_negative_value_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TASKS_LIST_ALL_CACHE_TTL_SEC", "-5")
    api = _reload_tasks_api_with_env("-5")
    assert api._LIST_ALL_CACHE_TTL == 8.0


def test_nan_value_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TASKS_LIST_ALL_CACHE_TTL_SEC", "nan")
    api = _reload_tasks_api_with_env("nan")
    assert api._LIST_ALL_CACHE_TTL == 8.0


def test_infinity_value_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TASKS_LIST_ALL_CACHE_TTL_SEC", "inf")
    api = _reload_tasks_api_with_env("inf")
    assert api._LIST_ALL_CACHE_TTL == 8.0


def test_above_cap_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Values above the 1h upper bound in _safe_ttl fall back to default.

    Guards the memory-leak footgun: ``TASKS_LIST_ALL_CACHE_TTL_SEC=999999`` would
    silently let ``_LIST_ALL_CACHE`` grow unbounded.
    """
    monkeypatch.setenv("TASKS_LIST_ALL_CACHE_TTL_SEC", "99999")
    api = _reload_tasks_api_with_env("99999")
    assert api._LIST_ALL_CACHE_TTL == 8.0


def test_at_cap_is_honored(monkeypatch: pytest.MonkeyPatch) -> None:
    """Value equal to the 1h upper bound is honored (boundary case)."""
    monkeypatch.setenv("TASKS_LIST_ALL_CACHE_TTL_SEC", "3600")
    api = _reload_tasks_api_with_env("3600")
    assert api._LIST_ALL_CACHE_TTL == 3600.0


def test_cap_value_env_override_changes_module_constant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``TASKS_MAX_CACHE_TTL_SEC`` env var overrides the cap module-level constant."""
    monkeypatch.setenv("TASKS_MAX_CACHE_TTL_SEC", "120.0")
    api = _reload_tasks_api_with_env(None)
    assert api._MAX_CACHE_TTL_SEC == 120.0
    assert api._LIST_ALL_CACHE_TTL == 8.0  # default, unchanged


def test_lower_cap_rejects_value_above_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With a lowered cap, a value above the new cap falls back to default."""
    monkeypatch.setenv("TASKS_MAX_CACHE_TTL_SEC", "120")
    monkeypatch.setenv("TASKS_LIST_ALL_CACHE_TTL_SEC", "200")
    api = _reload_tasks_api_with_env("200")
    assert api._MAX_CACHE_TTL_SEC == 120.0
    assert api._LIST_ALL_CACHE_TTL == 8.0

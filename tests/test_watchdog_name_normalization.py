"""tests/test_watchdog_name_normalization.py — PR #963

Verifies the watchdog normalizes provider names so "nvidia-nim" and "nvidia"
map to the same failure counter. This was the root cause of self-healing
not kicking in: agent/loop.py recorded failures under "nvidia-nim" but
self_heal checked "nvidia" — they never matched.
"""
from __future__ import annotations

import inspect


def test_normalize_provider_strips_suffixes():
    """_normalize_provider must strip -nim, -local, -cloud suffixes."""
    from packages.ai.watchdog import BrainWatchdog
    assert BrainWatchdog._normalize_provider("nvidia-nim") == "nvidia"
    assert BrainWatchdog._normalize_provider("ollama-local") == "ollama"
    assert BrainWatchdog._normalize_provider("nvidia") == "nvidia"
    assert BrainWatchdog._normalize_provider("ollama") == "ollama"
    assert BrainWatchdog._normalize_provider("") == ""
    assert BrainWatchdog._normalize_provider("NVIDIA-NIM") == "nvidia"


def test_record_failure_normalizes_name():
    """record_failure must store counts under the normalized name."""
    from packages.ai.watchdog import BrainWatchdog
    wd = BrainWatchdog(max_failures=10)  # high threshold so no failover
    # Record under long name
    wd.record_failure("nvidia-nim")
    # Check under short name
    assert wd._failure_counts.get("nvidia", 0) == 1
    # Check under long name should NOT exist (it was normalized)
    assert "nvidia-nim" not in wd._failure_counts


def test_record_success_normalizes_name():
    """record_success must reset counts under the normalized name."""
    from packages.ai.watchdog import BrainWatchdog
    wd = BrainWatchdog(max_failures=10)
    wd.record_failure("nvidia-nim")
    wd.record_failure("nvidia-nim")
    assert wd._failure_counts.get("nvidia", 0) == 2
    # Success under short name should reset the count
    wd.record_success("nvidia")
    assert wd._failure_counts.get("nvidia", 0) == 0


def test_is_provider_actually_available_checks_ollama_url():
    """_is_provider_actually_available must return False for ollama without URL."""
    import os
    from packages.ai.watchdog import _is_provider_actually_available
    # Temporarily clear ollama env vars
    old_base = os.environ.pop("OLLAMA_BASE_URL", None)
    old_base2 = os.environ.pop("OLLAMA_BASE", None)
    try:
        assert _is_provider_actually_available("ollama") is False
    finally:
        if old_base:
            os.environ["OLLAMA_BASE_URL"] = old_base
        if old_base2:
            os.environ["OLLAMA_BASE"] = old_base2


def test_is_provider_actually_available_true_for_ollama_with_url():
    """_is_provider_actually_available must return True for ollama with URL."""
    import os
    from packages.ai.watchdog import _is_provider_actually_available
    os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
    try:
        assert _is_provider_actually_available("ollama") is True
    finally:
        os.environ.pop("OLLAMA_BASE_URL", None)


def test_self_heal_uses_normalized_names():
    """self_heal must normalize active_provider before checking failure counts."""
    from packages.ai import self_heal
    src = inspect.getsource(self_heal)
    assert "_normalize_provider" in src
    assert "normalized_active" in src

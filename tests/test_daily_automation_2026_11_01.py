"""tests/test_daily_automation_2026_11_01.py — Daily automation 2026-11-01.

Changes shipped today:
- **Fix Sonnet 5.5 cache-read fraction** (2026-11-01). When Anthropic launched
  Haiku 5.5 on 2026-10-07 it simultaneously halved the Sonnet 5.5 cache-read
  price (SiliconANGLE 2026-10-07; 9to5Mac 2026-10-07). The per-model override
  was never added to ``_CACHE_READ_FRACTIONS``, so ``claude-sonnet-5-5`` was
  falling through to the generic ``claude-`` 10 % fallback and over-billing
  cache-heavy agentic work by 2×.

  The fix adds ``("claude-sonnet-5-5", 0.05)`` to ``_CACHE_READ_FRACTIONS``
  immediately after the existing ``("claude-opus-5-5", 0.05)`` entry. The
  prefix match covers both ``claude-sonnet-5-5`` and its versioned sibling
  ``claude-sonnet-5-5-20260929``. The generic ``("claude-", 0.10)`` fallback
  is unchanged and still applies to every other Claude model.

  After the fix, a 1 M-token fully-cached Sonnet 5.5 prompt costs $0.10
  (= 5 % × $2.00/MTok) instead of the erroneous $0.20 (= 10 % × $2.00/MTok).

  Sources:
  - SiliconANGLE 2026-10-07 — "Anthropic releases Claude Haiku 5.5 small
    model and halves Sonnet 5.5 cache read prices."
    https://siliconangle.com/2026/10/07/anthropic-releases-claude-haiku-5-5-small-model-and-halves-sonnet-5-5-cache-read-prices/
  - 9to5Mac 2026-10-07 — "Anthropic upgrades Claude with new Haiku 5.5
    model, details here."
    https://9to5mac.com/2026/10/07/anthropic-upgrades-claude-with-new-haiku-5-5-model-details-here/

Files changed:
  ``packages/ai/cost_tracker.py``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_11_01.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

SONNET_5_5_ID = "claude-sonnet-5-5"
SONNET_5_5_VERSIONED_ID = "claude-sonnet-5-5-20260929"
SONNET_5_5_INPUT_COST = 2.0    # $2.00/MTok (unchanged)
SONNET_5_5_OUTPUT_COST = 10.0  # $10.00/MTok (unchanged)
SONNET_5_5_CACHE_FRACTION = 0.05  # 5 % — halved from 10 % on 2026-10-07
SONNET_5_5_CACHED_COST_PER_MTOKEN = 0.10  # $0.10/MTok = 5 % × $2.00/MTok


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_11_01",
        REPO_ROOT / "packages" / "ai" / "cost_tracker.py",
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Base costs are unchanged
# ---------------------------------------------------------------------------

class TestSonnet55BaseCost:
    def test_input_cost_unchanged(self, ct):
        cost = ct.cost_for_tokens(SONNET_5_5_ID, 1_000_000, 0)
        assert cost == pytest.approx(SONNET_5_5_INPUT_COST), (
            f"{SONNET_5_5_ID} input cost must remain ${SONNET_5_5_INPUT_COST}/MTok"
        )

    def test_output_cost_unchanged(self, ct):
        cost = ct.cost_for_tokens(SONNET_5_5_ID, 0, 1_000_000)
        assert cost == pytest.approx(SONNET_5_5_OUTPUT_COST), (
            f"{SONNET_5_5_ID} output cost must remain ${SONNET_5_5_OUTPUT_COST}/MTok"
        )

    def test_versioned_id_input_cost(self, ct):
        cost = ct.cost_for_tokens(SONNET_5_5_VERSIONED_ID, 1_000_000, 0)
        assert cost == pytest.approx(SONNET_5_5_INPUT_COST)

    def test_versioned_id_output_cost(self, ct):
        cost = ct.cost_for_tokens(SONNET_5_5_VERSIONED_ID, 0, 1_000_000)
        assert cost == pytest.approx(SONNET_5_5_OUTPUT_COST)


# ---------------------------------------------------------------------------
# Cache-read fraction fix — the core change
# ---------------------------------------------------------------------------

class TestSonnet55CacheFraction:
    def test_explicit_override_exists(self, ct):
        """claude-sonnet-5-5 must have an explicit 5 % override, not the 10 % generic."""
        fractions = {prefix: frac for prefix, frac in ct._CACHE_READ_FRACTIONS}
        assert SONNET_5_5_ID in fractions, (
            f"{SONNET_5_5_ID} must have an explicit cache-read fraction entry; "
            "without it the generic 'claude-' 10 % fallback over-bills by 2×."
        )

    def test_cache_fraction_is_five_percent(self, ct):
        fractions = {prefix: frac for prefix, frac in ct._CACHE_READ_FRACTIONS}
        assert fractions[SONNET_5_5_ID] == pytest.approx(SONNET_5_5_CACHE_FRACTION), (
            f"Cache fraction must be 0.05 (5 %), got {fractions[SONNET_5_5_ID]}"
        )

    def test_override_precedes_generic_claude_prefix(self, ct):
        """The claude-sonnet-5-5 entry must appear before 'claude-' in the tuple."""
        prefixes = [prefix for prefix, _ in ct._CACHE_READ_FRACTIONS]
        assert SONNET_5_5_ID in prefixes
        assert "claude-" in prefixes
        sonnet_pos = prefixes.index(SONNET_5_5_ID)
        generic_pos = prefixes.index("claude-")
        assert sonnet_pos < generic_pos, (
            "claude-sonnet-5-5 override must appear before the generic 'claude-' fallback"
        )

    def test_cache_read_reduces_cost(self, ct):
        full_input = ct.cost_for_tokens(SONNET_5_5_ID, 1_000_000, 0)
        with_cache = ct.cost_for_tokens(
            SONNET_5_5_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert with_cache < full_input

    def test_cached_cost_is_five_percent_of_input(self, ct):
        """A fully-cached 1M-token Sonnet 5.5 prompt must cost $0.10, not $0.20."""
        full_input = ct.cost_for_tokens(SONNET_5_5_ID, 1_000_000, 0)
        cached = ct.cost_for_tokens(
            SONNET_5_5_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert cached == pytest.approx(full_input * SONNET_5_5_CACHE_FRACTION), (
            f"Expected {full_input * SONNET_5_5_CACHE_FRACTION} (5 % of full input), "
            f"got {cached}"
        )

    def test_cached_cost_absolute_value(self, ct):
        """Fully-cached 1M tokens should cost exactly $0.10."""
        cached = ct.cost_for_tokens(
            SONNET_5_5_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert cached == pytest.approx(SONNET_5_5_CACHED_COST_PER_MTOKEN), (
            f"Expected $0.10/MTok cache-read cost, got ${cached}"
        )

    def test_not_ten_percent(self, ct):
        """Regression: before the fix this was erroneously 10 % ($0.20/MTok)."""
        old_wrong_cost = SONNET_5_5_INPUT_COST * 0.10  # 10 % of $2.00
        cached = ct.cost_for_tokens(
            SONNET_5_5_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert cached != pytest.approx(old_wrong_cost), (
            "Cache cost must NOT be 10 % of input; that was the pre-fix erroneous rate."
        )


# ---------------------------------------------------------------------------
# Versioned ID inherits the override via prefix match
# ---------------------------------------------------------------------------

class TestSonnet55VersionedCacheFraction:
    def test_versioned_id_uses_five_percent(self, ct):
        """claude-sonnet-5-5-20260929 must pick up the 5 % rate via prefix match."""
        full_input = ct.cost_for_tokens(SONNET_5_5_VERSIONED_ID, 1_000_000, 0)
        cached = ct.cost_for_tokens(
            SONNET_5_5_VERSIONED_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert cached == pytest.approx(full_input * SONNET_5_5_CACHE_FRACTION), (
            "Versioned ID must also use 5 % cache fraction via prefix match on "
            "'claude-sonnet-5-5'"
        )

    def test_versioned_id_cache_cost_absolute(self, ct):
        cached = ct.cost_for_tokens(
            SONNET_5_5_VERSIONED_ID, 1_000_000, 0, cached_tokens=1_000_000
        )
        assert cached == pytest.approx(SONNET_5_5_CACHED_COST_PER_MTOKEN)


# ---------------------------------------------------------------------------
# Generic fallback still applies to other Claude models (no regression)
# ---------------------------------------------------------------------------

class TestGenericClaudeFallbackUnchanged:
    def test_claude_sonnet_5_still_ten_percent(self, ct):
        """claude-sonnet-5 (not 5.5) still uses the 10 % generic Claude rate."""
        full_input = ct.cost_for_tokens("claude-sonnet-5", 1_000_000, 0)
        cached = ct.cost_for_tokens("claude-sonnet-5", 1_000_000, 0, cached_tokens=1_000_000)
        if full_input > 0:
            assert cached == pytest.approx(full_input * 0.10), (
                "claude-sonnet-5 (not 5.5) must still use the generic 10 % rate"
            )

    def test_claude_haiku_5_5_still_ten_percent(self, ct):
        """claude-haiku-5-5 uses the generic 10 % rate (no halving announced)."""
        full_input = ct.cost_for_tokens("claude-haiku-5-5", 1_000_000, 0)
        cached = ct.cost_for_tokens("claude-haiku-5-5", 1_000_000, 0, cached_tokens=1_000_000)
        if full_input > 0:
            assert cached == pytest.approx(full_input * 0.10), (
                "claude-haiku-5-5 must use the generic 10 % rate (no halving for Haiku)"
            )

    def test_opus_5_5_still_five_percent(self, ct):
        """claude-opus-5-5 override must be unchanged (5 %)."""
        full_input = ct.cost_for_tokens("claude-opus-5-5", 1_000_000, 0)
        cached = ct.cost_for_tokens("claude-opus-5-5", 1_000_000, 0, cached_tokens=1_000_000)
        assert cached == pytest.approx(full_input * 0.05), (
            "claude-opus-5-5 must retain its 5 % cache fraction"
        )

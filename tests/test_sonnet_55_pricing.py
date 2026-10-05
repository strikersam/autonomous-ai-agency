"""Regression: Sonnet 5.5 is priced $2/$10 per MTok (same as Sonnet 5), not $1.6/$8."""
from __future__ import annotations

import pytest

from packages.ai import cost_tracker as ct


@pytest.mark.parametrize("model", ["claude-sonnet-5-5", "claude-sonnet-5-5-20260929"])
def test_sonnet_55_one_million_in_out_costs_twelve_dollars(model: str) -> None:
    assert ct.cost_for_tokens(model, 1_000_000, 1_000_000, 0) == pytest.approx(12.0)


def test_sonnet_55_matches_sonnet_5() -> None:
    assert ct._DEFAULT_COST_TABLE["claude-sonnet-5-5"] == ct._DEFAULT_COST_TABLE["claude-sonnet-5"]

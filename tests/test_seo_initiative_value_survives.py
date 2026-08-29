"""A number that goes in must come out, or nothing should claim it did.

`b368f9e7` shipped three SEO endpoints that reported `"estimated_monthly_value":
0` for every initiative, and a roadmap whose value column read `$0` on every
row. The figure was not missing — `SeoDelegationTask` carried it. The conversion
to `Initiative` read it, interpolated it into a free-text `rationale` string,
and dropped the field.

`Initiative` had no such attribute, so every consumer reached it through
`getattr(init, 'estimated_monthly_value', 0)`. That default is the whole defect:
without it the first call would have raised `AttributeError` and the loss would
have been found in minutes. With it, a missing field and a genuine zero are the
same value, and the API reported a fabricated measurement.

The 2026-08-28 council review flagged this class of thing — *"unsure if
`agents.portfolio.Initiative` supports these fields"* — as a WARN, and the
merge gate treated WARN as mergeable.
"""
from __future__ import annotations

import pytest

from agents.portfolio import Initiative
from agents.seo_portfolio_bridge import (
    SeoDelegationTask,
    delegation_task_to_initiative,
)

VALUE = 12345.0


def _task(**overrides) -> SeoDelegationTask:
    """A delegation task shaped like the real generator's output."""
    kwargs = {}
    for name, field in SeoDelegationTask.model_fields.items():
        if not field.is_required():
            continue
        annotation = str(field.annotation)
        kwargs[name] = (
            3 if "int" in annotation
            else 3.0 if "float" in annotation
            else [] if "ist[" in annotation
            else "x" if "str" in annotation
            else False
        )
    kwargs.update(
        priority="high",
        effort="M",
        task_key="k1",
        title="Fix canonical tags",
        estimated_monthly_value=VALUE,
        business_value=8,
        time_criticality=5,
        risk_reduction=3,
        job_size=2,
        wsjf_score=8.0,
    )
    kwargs.update(overrides)
    return SeoDelegationTask(**kwargs)


class TestTheFieldExists:
    """`getattr(..., 0)` cannot distinguish "absent" from "zero"."""

    def test_initiative_declares_it(self) -> None:
        assert "estimated_monthly_value" in Initiative.__dataclass_fields__

    def test_it_defaults_to_zero_for_sources_that_cannot_estimate(self) -> None:
        """Zero must mean "not estimated", not "estimation was lost"."""
        assert Initiative(initiative_id="i1", title="T").estimated_monthly_value == 0.0

    def test_reading_it_needs_no_getattr_default(self) -> None:
        initiative = Initiative(initiative_id="i1", title="T")
        assert initiative.estimated_monthly_value == 0.0  # no AttributeError


class TestTheValueSurvivesConversion:
    def test_the_number_goes_in_and_comes_out(self) -> None:
        initiative = delegation_task_to_initiative(
            _task(), audit_id="a1", website_url="https://example.test"
        )
        assert initiative.estimated_monthly_value == VALUE, (
            "the conversion dropped the figure; every consumer then read 0"
        )

    def test_it_is_not_only_in_the_rationale_prose(self) -> None:
        """It was there, and prose is not a field anyone can read back."""
        initiative = delegation_task_to_initiative(
            _task(), audit_id="a1", website_url="https://example.test"
        )
        assert "12,345" in initiative.rationale  # the human-readable copy stays
        assert initiative.estimated_monthly_value == VALUE  # and the machine one exists

    @pytest.mark.parametrize("value", [0.0, 1.0, 999999.0])
    def test_any_value_survives(self, value: float) -> None:
        initiative = delegation_task_to_initiative(
            _task(estimated_monthly_value=value),
            audit_id="a1",
            website_url="https://example.test",
        )
        assert initiative.estimated_monthly_value == value


class TestNoConsumerHidesAMissingField:
    """The `getattr` default is what made a dropped field look like a real zero.

    Asserted on the source rather than by calling every endpoint: the point is
    that the pattern is gone, so re-introducing it anywhere fails here.
    """

    def test_no_getattr_default_remains(self) -> None:
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[1]
        offenders = []
        for relative in ("backend/seo_api.py", "agents/seo_portfolio_bridge.py"):
            text = (repo_root / relative).read_text(encoding="utf-8")
            if "getattr(" in text and "estimated_monthly_value'" in text:
                for number, line in enumerate(text.splitlines(), 1):
                    if "getattr(" in line and "estimated_monthly_value" in line:
                        offenders.append(f"{relative}:{number}")
        assert not offenders, (
            "a getattr default makes an absent field indistinguishable from a "
            f"real zero — the defect this file exists for: {offenders}"
        )

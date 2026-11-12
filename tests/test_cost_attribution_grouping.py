"""Tests for mod.group_cost_snapshot() — item 2 of the 2026-W46 routine backlog (#1892).

The endpoint serves `cost_tracker.get_stats()`; these tests pin the grouping
helper that reshapes it, including the two groupings it must refuse.
"""
from __future__ import annotations

import copy
import importlib.util
import pathlib
import sys

import pytest

import packages.ai.cost_tracker as ct

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def mod():
    """Load services/cost_attribution.py by path.

    Importing it as ``services.cost_attribution`` runs ``services/__init__.py``,
    which pulls the whole company-graph stack (pydantic, motor) into these unit
    tests. The module itself only needs the stdlib, so load the file directly —
    the same pattern ``tests/test_daily_automation_2026_11_08.py`` uses for
    ``packages/ai/cost_tracker.py``.
    """
    spec = importlib.util.spec_from_file_location(
        "cost_attribution_under_test", REPO_ROOT / "services" / "cost_attribution.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve ``from __future__ import annotations`` strings through
    # sys.modules[cls.__module__], so the module must be registered first.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _reset():
    ct.clear_stats()
    yield
    ct.clear_stats()


def _snapshot() -> dict:
    ct.record_usage(
        "claude-sonnet-4-6", provider_id="anthropic",
        prompt_tokens=1_000_000, completion_tokens=0, tag="reasoning",
    )
    ct.record_usage(
        "claude-haiku-4-5-20251001", provider_id="anthropic",
        prompt_tokens=1_000_000, completion_tokens=0, tag="code_generation",
    )
    return ct.get_stats()


class TestGroupCostSnapshot:
    def test_group_by_model_ranks_by_spend(self, mod):
        rows = mod.group_cost_snapshot(_snapshot(), "model")
        assert [r["key"] for r in rows] == ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"]
        assert rows[0]["estimated_cost_usd"] >= rows[1]["estimated_cost_usd"]

    def test_group_by_tag_uses_the_tag_breakdown(self, mod):
        snapshot = _snapshot()
        rows = mod.group_cost_snapshot(snapshot, "tag")
        assert {r["key"] for r in rows} == set(snapshot["by_tag"])
        assert {r["key"]: r["estimated_cost_usd"] for r in rows} == {
            tag: entry["estimated_cost_usd"] for tag, entry in snapshot["by_tag"].items()
        }

    def test_grouping_reconciles_with_the_totals(self, mod):
        snapshot = _snapshot()
        for group_by in mod.GROUP_BY_CHOICES:
            rows = mod.group_cost_snapshot(snapshot, group_by)
            assert sum(r["calls"] for r in rows) == snapshot["totals"]["calls"]
            assert sum(r["estimated_cost_usd"] for r in rows) == pytest.approx(
                snapshot["totals"]["estimated_cost_usd"]
            )

    def test_helper_does_not_mutate_the_snapshot(self, mod):
        snapshot = _snapshot()
        before = copy.deepcopy(snapshot)
        mod.group_cost_snapshot(snapshot, "model")
        mod.group_cost_snapshot(snapshot, "tag")
        assert snapshot == before

    def test_empty_snapshot_groups_to_nothing(self, mod):
        assert mod.group_cost_snapshot(ct.get_stats(), "model") == []
        assert mod.group_cost_snapshot(ct.get_stats(), "tag") == []

    def test_provider_grouping_is_refused_with_the_reason(self, mod):
        with pytest.raises(ValueError, match="provider"):
            mod.group_cost_snapshot(_snapshot(), "provider")

    def test_unknown_grouping_is_refused(self, mod):
        with pytest.raises(ValueError, match="unsupported group_by"):
            mod.group_cost_snapshot(_snapshot(), "phase")

"""Tests for agents/portfolio.py — Agentic Portfolio Management.

Uses importlib to load the module directly, bypassing agents/__init__.py deps.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module():
    path = Path(__file__).parent.parent / "agents" / "portfolio.py"
    spec = importlib.util.spec_from_file_location("portfolio", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["portfolio"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_agile():
    path = Path(__file__).parent.parent / "agents" / "agile_sprints.py"
    spec = importlib.util.spec_from_file_location("agile_sprints", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["agile_sprints"] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load_module()
Initiative = mod.Initiative
InitiativeStatus = mod.InitiativeStatus
RoadmapHorizon = mod.RoadmapHorizon
CapacityAllocation = mod.CapacityAllocation
PortfolioMetrics = mod.PortfolioMetrics
PortfolioManager = mod.PortfolioManager
InitiativeProgress = mod.InitiativeProgress

agile = _load_agile()
AgileManager = agile.AgileManager
UserStory = agile.UserStory
StoryStatus = agile.StoryStatus


class TestInitiative:
    """Tests for the Initiative dataclass and WSJF maths."""

    def test_create(self):
        i = Initiative(initiative_id="i1", title="Payments")
        assert i.initiative_id == "i1"
        assert i.status == InitiativeStatus.PROPOSED
        assert i.horizon == RoadmapHorizon.UNSCHEDULED

    def test_cost_of_delay(self):
        i = Initiative(
            initiative_id="i1", title="x",
            business_value=8, time_criticality=5, risk_reduction=3,
        )
        assert i.cost_of_delay == 16

    def test_wsjf(self):
        i = Initiative(
            initiative_id="i1", title="x",
            business_value=8, time_criticality=5, risk_reduction=3, job_size=4,
        )
        assert i.wsjf == pytest.approx(16 / 4)

    def test_job_size_must_be_positive(self):
        with pytest.raises(ValueError):
            Initiative(initiative_id="i1", title="x", job_size=0)

    def test_negative_component_raises(self):
        with pytest.raises(ValueError):
            Initiative(initiative_id="i1", title="x", business_value=-1)

    def test_link_sprint_dedupes(self):
        i = Initiative(initiative_id="i1", title="x")
        i.link_sprint("sp1")
        i.link_sprint("sp1")
        assert i.sprint_ids == ["sp1"]


class TestPortfolioManagerCrud:
    """CRUD behaviour for PortfolioManager."""

    def test_add_and_count(self):
        mgr = PortfolioManager()
        i = mgr.add_initiative("Search", business_value=5, job_size=2)
        assert mgr.initiative_count == 1
        assert mgr.get_initiative(i.initiative_id) is i

    def test_remove(self):
        mgr = PortfolioManager()
        i = mgr.add_initiative("Search")
        mgr.remove_initiative(i.initiative_id)
        assert mgr.initiative_count == 0

    def test_remove_missing_raises(self):
        mgr = PortfolioManager()
        with pytest.raises(KeyError):
            mgr.remove_initiative("nope")

    def test_get_missing_returns_none(self):
        assert PortfolioManager().get_initiative("nope") is None


class TestPrioritization:
    """WSJF ranking is the heart of portfolio management."""

    def test_prioritized_orders_by_wsjf(self):
        mgr = PortfolioManager()
        low = mgr.add_initiative("Low", business_value=2, time_criticality=1, risk_reduction=1, job_size=8)   # 0.5
        high = mgr.add_initiative("High", business_value=8, time_criticality=8, risk_reduction=4, job_size=4)  # 5.0
        mid = mgr.add_initiative("Mid", business_value=5, time_criticality=3, risk_reduction=2, job_size=5)    # 2.0
        ranked = mgr.prioritized()
        assert [i.title for i in ranked] == ["High", "Mid", "Low"]
        assert ranked[0] is high and ranked[-1] is low

    def test_prioritized_excludes_cancelled(self):
        mgr = PortfolioManager()
        keep = mgr.add_initiative("Keep", business_value=5, job_size=1)
        drop = mgr.add_initiative("Drop", business_value=9, job_size=1)
        drop.status = InitiativeStatus.CANCELLED
        assert [i.title for i in mgr.prioritized()] == ["Keep"]

    def test_prioritized_excludes_done_by_default(self):
        mgr = PortfolioManager()
        done = mgr.add_initiative("Done", business_value=9, job_size=1)
        done.status = InitiativeStatus.DONE
        active = mgr.add_initiative("Active", business_value=2, job_size=1)
        assert [i.title for i in mgr.prioritized()] == ["Active"]
        assert len(mgr.prioritized(include_done=True)) == 2


class TestCapacityAllocation:
    """Greedy capacity allocation by WSJF."""

    def test_allocate_fits_by_priority(self):
        mgr = PortfolioManager()
        mgr.add_initiative("A", business_value=9, time_criticality=9, risk_reduction=9, job_size=5)  # wsjf 5.4
        mgr.add_initiative("B", business_value=4, time_criticality=2, risk_reduction=2, job_size=4)  # wsjf 2.0
        mgr.add_initiative("C", business_value=2, time_criticality=1, risk_reduction=1, job_size=3)  # wsjf 1.33
        alloc = mgr.allocate_capacity(8)
        assert [i.title for i in alloc.committed] == ["A", "C"]  # 5 + 3 fits; B (size 4) deferred
        assert [i.title for i in alloc.deferred] == ["B"]
        assert alloc.committed_job_size == 8
        assert alloc.remaining_capacity == 0
        assert alloc.utilization == pytest.approx(1.0)

    def test_allocate_zero_capacity(self):
        mgr = PortfolioManager()
        mgr.add_initiative("A", job_size=3)
        alloc = mgr.allocate_capacity(0)
        assert alloc.committed == []
        assert alloc.utilization == 0.0


class TestRoadmap:
    """Now/Next/Later roadmap placement."""

    def test_plan_roadmap_distributes(self):
        mgr = PortfolioManager()
        mgr.add_initiative("Top", business_value=9, time_criticality=9, risk_reduction=9, job_size=5)
        mgr.add_initiative("Second", business_value=6, time_criticality=4, risk_reduction=2, job_size=5)
        mgr.add_initiative("Third", business_value=3, time_criticality=2, risk_reduction=1, job_size=5)
        roadmap = mgr.plan_roadmap(capacity_per_horizon=5)
        assert roadmap[RoadmapHorizon.NOW.value][0].title == "Top"
        assert roadmap[RoadmapHorizon.NEXT.value][0].title == "Second"
        assert roadmap[RoadmapHorizon.LATER.value][0].title == "Third"

    def test_roadmap_overflow_goes_unscheduled(self):
        mgr = PortfolioManager()
        for n in range(4):
            mgr.add_initiative(f"I{n}", business_value=5, job_size=5)
        roadmap = mgr.plan_roadmap(capacity_per_horizon=5)
        assert len(roadmap[RoadmapHorizon.UNSCHEDULED.value]) == 1


class TestRollup:
    """Progress roll-up from linked agile sprints."""

    def test_rollup_progress(self):
        pf = PortfolioManager()
        am = AgileManager()
        sprint = am.create_sprint("S1")
        sprint.add_story(UserStory(story_id="s1", title="A", story_points=5))
        sprint.add_story(UserStory(story_id="s2", title="B", story_points=3))
        sprint.get_story("s1").status = StoryStatus.DONE

        init = pf.add_initiative("Checkout", business_value=8, job_size=4)
        pf.link_sprint(init.initiative_id, sprint.sprint_id)

        progress = pf.rollup_progress(am)
        assert len(progress) == 1
        assert progress[0].total_points == 8
        assert progress[0].completed_points == 5
        assert progress[0].completion_percentage == pytest.approx(62.5)

    def test_rollup_ignores_unknown_sprint(self):
        pf = PortfolioManager()
        am = AgileManager()
        init = pf.add_initiative("X")
        pf.link_sprint(init.initiative_id, "missing-sprint")
        progress = pf.rollup_progress(am)
        assert progress[0].sprint_count == 0
        assert progress[0].completion_percentage == 0.0

    def test_link_sprint_missing_initiative_raises(self):
        with pytest.raises(KeyError):
            PortfolioManager().link_sprint("nope", "sp1")


class TestMetrics:
    """Aggregate portfolio metrics."""

    def test_metrics(self):
        mgr = PortfolioManager()
        a = mgr.add_initiative("A", business_value=8, time_criticality=4, risk_reduction=4, job_size=4)  # wsjf 4
        b = mgr.add_initiative("B", business_value=2, time_criticality=1, risk_reduction=1, job_size=4)  # wsjf 1
        a.status = InitiativeStatus.IN_PROGRESS
        b.status = InitiativeStatus.APPROVED
        m = mgr.metrics()
        assert m.total_initiatives == 2
        assert m.active_initiatives == 2
        assert m.total_cost_of_delay == 16 + 4
        assert m.average_wsjf == pytest.approx(2.5)
        assert m.status_counts == {"in_progress": 1, "approved": 1}

    def test_metrics_empty(self):
        m = PortfolioManager().metrics()
        assert m.total_initiatives == 0
        assert m.average_wsjf == 0.0

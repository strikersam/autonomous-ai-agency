"""Tests for agents/agile_ceremonies.py — autonomous agile ceremonies.

Loads modules with a stubbed ``agents`` package so the heavy ``agents/__init__``
chain is bypassed, matching tests/test_portfolio_intelligence.py.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


if "agents" not in sys.modules or not hasattr(sys.modules.get("agents"), "__path__"):
    pkg = types.ModuleType("agents")
    pkg.__path__ = [str(ROOT / "agents")]
    sys.modules["agents"] = pkg

agile_sprints = _load("agents.agile_sprints", "agents/agile_sprints.py")
_load("agents.portfolio", "agents/portfolio.py")
_load("agents.portfolio_intelligence", "agents/portfolio_intelligence.py")
ac = _load("agents.agile_ceremonies", "agents/agile_ceremonies.py")

AgileManager = agile_sprints.AgileManager
AgileSprint = agile_sprints.AgileSprint
SprintStatus = agile_sprints.SprintStatus
StoryStatus = agile_sprints.StoryStatus
UserStory = agile_sprints.UserStory
Retrospective = agile_sprints.Retrospective

PortfolioManager = sys.modules["agents.portfolio"].PortfolioManager


SAMPLE_TASKS = """# Active Task Tracker

## Current Sprint Tasks

| # | Task | Status | PR / Branch | Notes | Updated |
|---|------|--------|-------------|-------|---------|
| 1 | Ship the widget | `DONE` | [#1](http://x) | shipped | 2026-06-01 |
| 2 | Build the dashboard | `IN_PROGRESS` | — | wip | 2026-06-02 |
| 3 | Write onboarding docs | `TODO` | — | — | 2026-06-03 |
| 4 | Migrate to v2 schema | `BLOCKED` | — | waiting on infra | 2026-06-04 |
| 5 | Nice-to-have polish | `DEFERRED` | — | low priority | 2026-06-05 |

## Bug Log

| # | Bug Description | Found | Fixed | PR | Status |
|---|----------------|-------|-------|----|--------|
| 1 | Memory leak in worker | 2026-06-01 | 2026-06-02 | #2 | `BUG_FIXED` |
| 2 | Crash on empty payload | 2026-06-03 | — | — | `BUG_FOUND` |
"""


class TestGenerateStandup:
    def test_buckets_current_sprint_tasks_by_status(self):
        report = ac.generate_standup(SAMPLE_TASKS)
        assert report.completed == ["Ship the widget", "Bug fixed: Memory leak in worker"]
        assert report.in_progress == ["Build the dashboard"]
        assert report.planned == ["Write onboarding docs"]
        assert report.blockers == [
            "Migrate to v2 schema",
            "Nice-to-have polish",
            "Open bug: Crash on empty payload",
        ]

    def test_no_active_sprint_means_no_sprint_health(self):
        report = ac.generate_standup(SAMPLE_TASKS, agile_mgr=AgileManager())
        assert report.sprint_health == []

    def test_active_sprint_health_is_folded_in(self):
        mgr = AgileManager()
        sprint = mgr.create_sprint("Sprint 7", goal="Ship it")
        sprint.add_story(UserStory(story_id="s1", title="A", story_points=5, status=StoryStatus.DONE))
        sprint.add_story(UserStory(story_id="s2", title="B", story_points=5))
        sprint.start(duration_days=14)

        report = ac.generate_standup(SAMPLE_TASKS, agile_mgr=mgr)
        assert len(report.sprint_health) == 1
        assert "Sprint 7" in report.sprint_health[0]
        assert "50%" in report.sprint_health[0]

    def test_to_markdown_renders_all_sections(self):
        report = ac.generate_standup(SAMPLE_TASKS)
        md = report.to_markdown()
        assert "## Daily Standup" in md
        assert "### Completed" in md
        assert "- Ship the widget" in md
        assert "### Blockers" in md
        assert "- Migrate to v2 schema" in md

    def test_to_markdown_handles_empty_buckets(self):
        report = ac.generate_standup("# Active Task Tracker\n\n## Current Sprint Tasks\n")
        md = report.to_markdown()
        assert "- _none_" in md


class TestGenerateBacklogRetro:
    def test_done_rows_go_to_went_well(self):
        retro = ac.generate_backlog_retro(SAMPLE_TASKS)
        assert "Ship the widget" in retro.went_well
        assert "Bug fixed: Memory leak in worker" in retro.went_well

    def test_blocked_and_deferred_go_to_went_poorly_with_action_items(self):
        retro = ac.generate_backlog_retro(SAMPLE_TASKS)
        assert "Migrate to v2 schema" in retro.went_poorly
        assert "Nice-to-have polish" in retro.went_poorly
        assert "Open bug: Crash on empty payload" in retro.went_poorly
        assert "Unblock / re-prioritise: Migrate to v2 schema" in retro.action_items
        assert "Triage and fix: Crash on empty payload" in retro.action_items

    def test_in_progress_and_todo_are_not_categorised(self):
        retro = ac.generate_backlog_retro(SAMPLE_TASKS)
        joined = retro.went_well + retro.went_poorly
        assert "Build the dashboard" not in joined
        assert "Write onboarding docs" not in joined


class TestRetrospectiveToMarkdown:
    def test_renders_all_sections(self):
        retro = Retrospective(
            went_well=["Good pairing"],
            went_poorly=["Flaky CI"],
            action_items=["Stabilise CI"],
        )
        md = ac.retrospective_to_markdown(retro, "Sprint 7 Retro")
        assert "## Sprint 7 Retro" in md
        assert "- Good pairing" in md
        assert "- Flaky CI" in md
        assert "- Stabilise CI" in md

    def test_renders_placeholders_when_empty(self):
        md = ac.retrospective_to_markdown(Retrospective(), "Empty Retro")
        assert md.count("- _none_") == 3


class TestGenerateSprintRetro:
    def _sprint(self, *, total: int, completed: int, historical_velocity, span_days: int) -> AgileSprint:
        now = datetime.now(timezone.utc)
        sprint = AgileSprint(
            sprint_id="sp1",
            name="Sprint X",
            status=SprintStatus.ACTIVE,
            start_date=now,
            end_date=now + timedelta(days=span_days),
            _historical_velocity=list(historical_velocity),
        )
        if completed:
            sprint.add_story(UserStory(story_id="done", title="Done work", story_points=completed, status=StoryStatus.DONE))
        remaining = total - completed
        if remaining:
            sprint.add_story(UserStory(story_id="todo", title="Remaining work", story_points=remaining, status=StoryStatus.TODO))
        return sprint

    def test_complete_sprint(self):
        sprint = self._sprint(total=10, completed=10, historical_velocity=[], span_days=5)
        retro = ac.generate_sprint_retro(sprint)
        assert any("completed all 10" in note for note in retro.went_well)
        assert retro.went_poorly == []
        assert retro.action_items == []

    def test_on_track_sprint(self):
        # remaining=5, days_remaining~5 -> burndown_rate~1.0; avg_vel=(100/1)/5=20 -> on track
        sprint = self._sprint(total=10, completed=5, historical_velocity=[100], span_days=5)
        retro = ac.generate_sprint_retro(sprint)
        assert any("on track" in note for note in retro.went_well)
        assert retro.went_poorly == []

    def test_at_risk_sprint(self):
        # remaining=9, days_remaining~2 -> burndown_rate~4.5; avg_vel=(8/1)/2=4 -> at risk (<=4*1.25)
        sprint = self._sprint(total=10, completed=1, historical_velocity=[8], span_days=2)
        retro = ac.generate_sprint_retro(sprint)
        assert any("at risk" in note for note in retro.went_poorly)
        assert any("Re-baseline" in item for item in retro.action_items)

    def test_off_track_sprint(self):
        # remaining=10, days_remaining~1 -> burndown_rate~10; avg_vel=(2/1)/1=2 -> off track (10 > 2*1.25)
        sprint = self._sprint(total=10, completed=0, historical_velocity=[2], span_days=1)
        retro = ac.generate_sprint_retro(sprint)
        assert any("off track" in note for note in retro.went_poorly)
        assert any("Descope or re-plan" in item for item in retro.action_items)

    def test_scope_creep_adds_note_and_action_item(self):
        sprint = self._sprint(total=10, completed=5, historical_velocity=[100], span_days=5)
        sprint.committed_points = 8  # 2 points of creep beyond what was committed
        retro = ac.generate_sprint_retro(sprint)
        assert any("Scope crept by 2 points" in note for note in retro.went_poorly)
        assert any("Protect sprint scope" in item for item in retro.action_items)

    def test_mutates_sprint_retrospective_in_place(self):
        sprint = self._sprint(total=10, completed=10, historical_velocity=[], span_days=5)
        retro = ac.generate_sprint_retro(sprint)
        assert retro is sprint.retrospective


class TestPlanNextSprint:
    def _portfolio(self) -> PortfolioManager:
        mgr = PortfolioManager()
        mgr.add_initiative("High value, small", business_value=13, time_criticality=8, risk_reduction=3, job_size=3)
        mgr.add_initiative("Medium value, medium", business_value=5, time_criticality=3, risk_reduction=2, job_size=5)
        mgr.add_initiative("Low value, large", business_value=2, time_criticality=1, risk_reduction=1, job_size=8)
        return mgr

    def test_allocates_capacity_and_creates_stories(self):
        portfolio = self._portfolio()
        agile = AgileManager()

        plan = ac.plan_next_sprint(portfolio, agile, name="Sprint 8", goal="Ship MVP", capacity=8)

        assert plan.sprint.name == "Sprint 8"
        assert plan.sprint.goal == "Ship MVP"
        assert plan.sprint.status == SprintStatus.PLANNING  # left for a human to start
        assert plan.capacity == 8

        # WSJF order: High (8.0), Medium (2.0), Low (0.5). Greedy fill of
        # capacity=8: High (3) fits, Medium (5) fits exactly -> remaining 0;
        # Low (8) no longer fits and is deferred.
        committed_titles = {i.title for i in plan.committed}
        assert committed_titles == {"High value, small", "Medium value, medium"}
        assert {i.title for i in plan.deferred} == {"Low value, large"}

        story_titles = {s.title for s in plan.sprint.stories}
        assert committed_titles == story_titles

    def test_links_sprint_back_to_committed_initiatives(self):
        portfolio = self._portfolio()
        agile = AgileManager()

        plan = ac.plan_next_sprint(portfolio, agile, name="Sprint 8", capacity=8)

        for initiative in plan.committed:
            assert plan.sprint.sprint_id in initiative.sprint_ids
        for initiative in plan.deferred:
            assert plan.sprint.sprint_id not in initiative.sprint_ids

    def test_to_markdown_lists_committed_and_deferred(self):
        portfolio = self._portfolio()
        agile = AgileManager()

        plan = ac.plan_next_sprint(portfolio, agile, name="Sprint 8", capacity=8)
        md = plan.to_markdown()

        assert "## Sprint Plan — Sprint 8" in md
        assert "High value, small" in md
        assert "### Deferred" in md
        assert "Low value, large" in md

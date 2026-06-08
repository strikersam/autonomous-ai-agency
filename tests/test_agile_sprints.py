"""Tests for agents/agile_sprints.py — Agentic Agile.

Uses importlib to load the module directly, bypassing agents/__init__.py deps.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module():
    path = Path(__file__).parent.parent / "agents" / "agile_sprints.py"
    spec = importlib.util.spec_from_file_location("agile_sprints", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["agile_sprints"] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load_module()
UserStory = mod.UserStory
SprintMetrics = mod.SprintMetrics
SprintStatus = mod.SprintStatus
StoryStatus = mod.StoryStatus
SprintHealth = mod.SprintHealth
AgileSprint = mod.AgileSprint
AgileManager = mod.AgileManager
Retrospective = mod.Retrospective


class TestUserStory:
    """Tests for UserStory dataclass."""

    def test_create(self):
        s = UserStory(story_id="s1", title="Login", story_points=3)
        assert s.story_id == "s1"
        assert s.title == "Login"
        assert s.story_points == 3
        assert s.status == StoryStatus.BACKLOG

    def test_default_points(self):
        s = UserStory(story_id="s1", title="x")
        assert s.story_points == 1

    def test_negative_points_raises(self):
        try:
            UserStory(story_id="s1", title="x", story_points=-1)
            assert False, "Expected ValueError"
        except ValueError:
            pass

    def test_assignee(self):
        s = UserStory(story_id="s1", title="x", assignee="alice")
        assert s.assignee == "alice"


class TestSprintMetrics:
    """Tests for SprintMetrics."""

    def test_completion_percentage_zero_total(self):
        m = SprintMetrics(total_points=0, completed_points=0)
        assert m.completion_percentage == 100.0

    def test_completion_percentage(self):
        m = SprintMetrics(total_points=10, completed_points=5)
        assert m.completion_percentage == 50.0

    def test_burndown_rate(self):
        m = SprintMetrics(
            total_points=20, completed_points=10,
            days_remaining=5, average_velocity=2.0,
        )
        assert m.burndown_rate == 2.0  # 10 remaining / 5 days

    def test_is_on_track(self):
        m = SprintMetrics(
            total_points=20, completed_points=15,
            days_remaining=5, average_velocity=2.0,
        )
        assert m.is_on_track is True  # 1.0 needed vs 2.0 velocity

    def test_is_off_track(self):
        m = SprintMetrics(
            total_points=20, completed_points=5,
            days_remaining=5, average_velocity=2.0,
        )
        assert m.is_on_track is False  # 3.0 needed vs 2.0 velocity


class TestAgileSprint:
    """Tests for AgileSprint."""

    def test_create(self):
        s = AgileSprint(sprint_id="sp1", name="Sprint 1")
        assert s.sprint_id == "sp1"
        assert s.status == SprintStatus.PLANNING

    def test_add_story(self):
        s = AgileSprint(sprint_id="sp1", name="S1")
        s.add_story(UserStory(story_id="s1", title="Login"))
        assert s.story_count == 1
        assert s.total_points == 1

    def test_add_duplicate_raises(self):
        s = AgileSprint(sprint_id="sp1", name="S1")
        s.add_story(UserStory(story_id="s1", title="x"))
        try:
            s.add_story(UserStory(story_id="s1", title="y"))
            assert False, "Expected ValueError"
        except ValueError:
            pass

    def test_remove_story(self):
        s = AgileSprint(sprint_id="sp1", name="S1")
        s.add_story(UserStory(story_id="s1", title="x"))
        s.remove_story("s1")
        assert s.story_count == 0

    def test_start_sprint(self):
        s = AgileSprint(sprint_id="sp1", name="S1")
        s.add_story(UserStory(story_id="s1", title="Login"))
        s.start(duration_days=7)
        assert s.status == SprintStatus.ACTIVE
        assert s.start_date is not None
        assert s.end_date is not None

    def test_start_non_planning_raises(self):
        s = AgileSprint(sprint_id="sp1", name="S1")
        s.status = SprintStatus.ACTIVE
        try:
            s.start()
            assert False, "Expected ValueError"
        except ValueError:
            pass

    def test_complete_sprint(self):
        s = AgileSprint(sprint_id="sp1", name="S1")
        s.add_story(UserStory(story_id="s1", title="Login", story_points=5))
        s.start()
        s.get_story("s1").status = StoryStatus.DONE
        metrics = s.complete()
        assert s.status == SprintStatus.COMPLETED
        assert metrics.completed_points == 5

    def test_cancel(self):
        s = AgileSprint(sprint_id="sp1", name="S1")
        s.cancel()
        assert s.status == SprintStatus.CANCELLED

    def test_get_metrics(self):
        s = AgileSprint(sprint_id="sp1", name="S1")
        s.add_story(UserStory(story_id="s1", title="A", story_points=5))
        s.add_story(UserStory(story_id="s2", title="B", story_points=3))
        s.get_story("s1").status = StoryStatus.DONE
        m = s.get_metrics()
        assert m.total_points == 8
        assert m.completed_points == 5

    def test_completed_points_property(self):
        s = AgileSprint(sprint_id="sp1", name="S1")
        s.add_story(UserStory(story_id="s1", title="A", story_points=3))
        s.add_story(UserStory(story_id="s2", title="B", story_points=2))
        s.get_story("s1").status = StoryStatus.DONE
        assert s.completed_points == 3

    def test_burndown_data(self):
        s = AgileSprint(sprint_id="sp1", name="S1")
        assert s.burndown_data == []


class TestAgileManager:
    """Tests for AgileManager."""

    def test_create_sprint(self):
        mgr = AgileManager()
        sprint = mgr.create_sprint("Sprint 1", goal="Finish MVP")
        assert sprint.name == "Sprint 1"
        assert sprint.goal == "Finish MVP"
        assert mgr.sprint_count == 1

    def test_remove_sprint(self):
        mgr = AgileManager()
        s = mgr.create_sprint("S1")
        mgr.remove_sprint(s.sprint_id)
        assert mgr.sprint_count == 0

    def test_get_sprint(self):
        mgr = AgileManager()
        s = mgr.create_sprint("S1")
        assert mgr.get_sprint(s.sprint_id) is s
        assert mgr.get_sprint("nope") is None

    def test_active_sprints(self):
        mgr = AgileManager()
        s1 = mgr.create_sprint("S1")
        s1.status = SprintStatus.ACTIVE
        s2 = mgr.create_sprint("S2")
        s2.status = SprintStatus.PLANNING
        assert len(mgr.active_sprints()) == 1

    def test_predicted_velocity_no_history(self):
        mgr = AgileManager()
        assert mgr.predicted_velocity() == 0.0

    def test_predicted_velocity_with_history(self):
        mgr = AgileManager()
        s1 = mgr.create_sprint("S1")
        s1._historical_velocity = [10, 14]
        s2 = mgr.create_sprint("S2")
        s2._historical_velocity = [8]
        assert mgr.predicted_velocity() == pytest.approx(32 / 3)


class TestSprintHealth:
    """Tests for SprintMetrics.health signal."""

    def test_complete(self):
        m = SprintMetrics(total_points=10, completed_points=10, days_remaining=3, average_velocity=2.0)
        assert m.health == SprintHealth.COMPLETE

    def test_on_track(self):
        m = SprintMetrics(total_points=20, completed_points=15, days_remaining=5, average_velocity=2.0)
        assert m.health == SprintHealth.ON_TRACK

    def test_at_risk(self):
        # 12 remaining / 5 days = 2.4 needed; velocity 2.0; within 25% (2.5) → at risk
        m = SprintMetrics(total_points=20, completed_points=8, days_remaining=5, average_velocity=2.0)
        assert m.health == SprintHealth.AT_RISK

    def test_off_track(self):
        # 18 remaining / 5 days = 3.6 needed; velocity 2.0; > 25% over → off track
        m = SprintMetrics(total_points=20, completed_points=2, days_remaining=5, average_velocity=2.0)
        assert m.health == SprintHealth.OFF_TRACK


class TestScopeChange:
    """Tests for committed-scope snapshot and scope_added."""

    def test_scope_added_zero_before_start(self):
        s = AgileSprint(sprint_id="sp1", name="S1")
        s.add_story(UserStory(story_id="s1", title="A", story_points=5))
        assert s.scope_added == 0

    def test_scope_added_after_start(self):
        s = AgileSprint(sprint_id="sp1", name="S1")
        s.add_story(UserStory(story_id="s1", title="A", story_points=5))
        s.start()
        assert s.committed_points == 5
        s.add_story(UserStory(story_id="s2", title="B", story_points=3))
        assert s.scope_added == 3


class TestRetrospective:
    """Tests for sprint retrospective capture."""

    def test_starts_empty(self):
        s = AgileSprint(sprint_id="sp1", name="S1")
        assert s.retrospective.is_empty is True

    def test_add_notes_and_actions(self):
        s = AgileSprint(sprint_id="sp1", name="S1")
        s.add_retro_note(went_well="Good pairing", went_poorly="Flaky CI")
        s.add_action_item("Stabilise CI")
        assert s.retrospective.went_well == ["Good pairing"]
        assert s.retrospective.went_poorly == ["Flaky CI"]
        assert s.retrospective.action_items == ["Stabilise CI"]
        assert s.retrospective.is_empty is False


import pytest

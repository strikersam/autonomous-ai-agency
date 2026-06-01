"""Agentic Agile — Sprint management with velocity tracking and burndown.

Issue: #233
Branch: fix/quick-note-233-agile
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4


class SprintStatus(Enum):
    """Lifecycle status of a sprint."""

    PLANNING = "planning"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StoryStatus(Enum):
    """Status of a user story within a sprint."""

    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


@dataclass
class UserStory:
    """A user story with story points and status."""

    story_id: str
    title: str
    description: str = ""
    story_points: int = 1
    status: StoryStatus = StoryStatus.BACKLOG
    assignee: Optional[str] = None

    def __post_init__(self) -> None:
        if self.story_points < 0:
            raise ValueError("story_points must be non-negative")


@dataclass
class SprintMetrics:
    """Velocity and burndown metrics for a sprint."""

    total_points: int = 0
    completed_points: int = 0
    average_velocity: float = 0.0
    days_remaining: int = 0

    @property
    def completion_percentage(self) -> float:
        """Percentage of story points completed."""
        if self.total_points == 0:
            return 100.0
        return (self.completed_points / self.total_points) * 100.0

    @property
    def burndown_rate(self) -> float:
        """Points per day needed to complete on time."""
        if self.days_remaining <= 0:
            return 0.0
        remaining = self.total_points - self.completed_points
        return remaining / self.days_remaining

    @property
    def is_on_track(self) -> bool:
        """Whether the sprint is on track to complete."""
        if self.days_remaining <= 0:
            return self.completed_points >= self.total_points
        return self.burndown_rate <= self.average_velocity


@dataclass
class AgileSprint:
    """An agile sprint containing user stories."""

    sprint_id: str
    name: str
    goal: str = ""
    status: SprintStatus = SprintStatus.PLANNING
    _stories: Dict[str, UserStory] = field(default_factory=dict)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    _historical_velocity: List[int] = field(default_factory=list)

    def add_story(self, story: UserStory) -> None:
        """Add a user story to the sprint."""
        if story.story_id in self._stories:
            raise ValueError(f"Story '{story.story_id}' already in sprint.")
        self._stories[story.story_id] = story

    def remove_story(self, story_id: str) -> None:
        """Remove a user story from the sprint."""
        if story_id not in self._stories:
            raise KeyError(f"Story '{story_id}' not found.")
        self._stories.pop(story_id)

    def get_story(self, story_id: str) -> Optional[UserStory]:
        """Get a story by ID."""
        return self._stories.get(story_id)

    def start(self, duration_days: int = 14) -> None:
        """Activate the sprint."""
        if self.status != SprintStatus.PLANNING:
            raise ValueError(f"Cannot start sprint in '{self.status.value}' state.")
        self.status = SprintStatus.ACTIVE
        self.start_date = datetime.now(timezone.utc)
        from datetime import timedelta
        self.end_date = self.start_date + timedelta(days=duration_days)
        for story in self._stories.values():
            if story.status == StoryStatus.BACKLOG:
                story.status = StoryStatus.TODO

    def complete(self) -> SprintMetrics:
        """Complete the sprint and record velocity."""
        if self.status != SprintStatus.ACTIVE:
            raise ValueError(f"Cannot complete sprint in '{self.status.value}' state.")
        self.status = SprintStatus.COMPLETED
        completed = self.completed_points
        self._historical_velocity.append(completed)
        return self.get_metrics()

    def cancel(self) -> None:
        """Cancel the sprint."""
        self.status = SprintStatus.CANCELLED

    def get_metrics(self) -> SprintMetrics:
        """Calculate current sprint metrics."""
        total = sum(s.story_points for s in self._stories.values())
        completed = sum(
            s.story_points for s in self._stories.values()
            if s.status == StoryStatus.DONE
        )
        avg_vel = (
            sum(self._historical_velocity) / len(self._historical_velocity)
            if self._historical_velocity else 0.0
        )
        days_remaining = 0
        if self.end_date is not None:
            delta = self.end_date - datetime.now(timezone.utc)
            days_remaining = max(0, delta.days)
        return SprintMetrics(
            total_points=total,
            completed_points=completed,
            average_velocity=avg_vel,
            days_remaining=days_remaining,
        )

    @property
    def total_points(self) -> int:
        """Total story points in the sprint."""
        return sum(s.story_points for s in self._stories.values())

    @property
    def completed_points(self) -> int:
        """Completed story points."""
        return sum(
            s.story_points for s in self._stories.values()
            if s.status == StoryStatus.DONE
        )

    @property
    def burndown_data(self) -> List[int]:
        """Return completed points history for burndown chart."""
        return list(self._historical_velocity)

    @property
    def story_count(self) -> int:
        """Number of stories in the sprint."""
        return len(self._stories)


@dataclass
class AgileManager:
    """Manages multiple agile sprints with velocity tracking."""

    _sprints: Dict[str, AgileSprint] = field(default_factory=dict)

    def create_sprint(self, name: str, goal: str = "") -> AgileSprint:
        """Create a new sprint."""
        sprint = AgileSprint(
            sprint_id=uuid4().hex[:12],
            name=name,
            goal=goal,
        )
        self._sprints[sprint.sprint_id] = sprint
        return sprint

    def remove_sprint(self, sprint_id: str) -> None:
        """Remove a sprint."""
        if sprint_id not in self._sprints:
            raise KeyError(f"Sprint '{sprint_id}' not found.")
        self._sprints.pop(sprint_id)

    def get_sprint(self, sprint_id: str) -> Optional[AgileSprint]:
        """Get a sprint by ID."""
        return self._sprints.get(sprint_id)

    def active_sprints(self) -> List[AgileSprint]:
        """List all active sprints."""
        return [s for s in self._sprints.values() if s.status == SprintStatus.ACTIVE]

    def predicted_velocity(self) -> float:
        """Predict next sprint velocity from historical data."""
        all_velocities = []
        for sprint in self._sprints.values():
            all_velocities.extend(sprint._historical_velocity)
        if not all_velocities:
            return 0.0
        return sum(all_velocities) / len(all_velocities)

    @property
    def sprint_count(self) -> int:
        """Number of managed sprints."""
        return len(self._sprints)

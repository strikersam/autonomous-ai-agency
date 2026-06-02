# Skill: Agentic Agile

## Purpose
Agile sprint management (`agents/agile_sprints.py`) with velocity tracking,
burndown metrics, and multi-sprint orchestration.

## Usage
```python
from agents.agile_sprints import AgileManager, AgileSprint, UserStory

mgr = AgileManager()
sprint = mgr.create_sprint("Sprint 5", goal="Ship MVP")
sprint.add_story(UserStory(story_id="s1", title="Login", story_points=5))
sprint.add_story(UserStory(story_id="s2", title="Dashboard", story_points=8))
sprint.start(duration_days=14)

metrics = sprint.get_metrics()
print(f"On track: {metrics.is_on_track}")
```

## Key Classes
- **UserStory** — story points, status, assignee
- **SprintMetrics** — velocity, burndown rate, completion percentage, track prediction
- **AgileSprint** — story management, start/complete/cancel, metrics
- **AgileManager** — multi-sprint registry, velocity prediction

## Testing
```bash
python -m pytest tests/test_agile_sprints.py -v
```

## Related Issues
- Issue #233: Agentic Agile

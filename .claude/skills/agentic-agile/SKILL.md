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
- **SprintMetrics** — velocity, burndown rate, completion percentage, track prediction, **health** signal
- **SprintHealth** — ON_TRACK / AT_RISK / OFF_TRACK / COMPLETE
- **Retrospective** — went_well / went_poorly / action_items
- **AgileSprint** — story management, start/complete/cancel, metrics, **scope_added** (creep), retrospective helpers
- **AgileManager** — multi-sprint registry, velocity prediction

## Retrospective & health
```python
m = sprint.get_metrics()
print(m.health)                        # SprintHealth.AT_RISK
print(sprint.scope_added)              # points added since start()
sprint.add_retro_note(went_well="Good pairing", went_poorly="Flaky CI")
sprint.add_action_item("Stabilise CI")
```

## Testing
```bash
python -m pytest tests/test_agile_sprints.py -v
```

## Related
- Skill: `agentic-portfolio` (initiative/epic level — the layer above)
- Issue #233: Agentic Agile

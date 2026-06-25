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

## Autonomous ceremonies (`agents/agile_ceremonies.py`)
Builds standups, retros, and sprint plans straight from
`.claude/state/active-tasks.md` and the WSJF portfolio — no human input needed.

```python
from agents.agile_ceremonies import (
    generate_standup, generate_sprint_retro, generate_backlog_retro,
    plan_next_sprint, retrospective_to_markdown,
)

tasks_md = open(".claude/state/active-tasks.md").read()

# Daily standup: Completed / In progress / Planned / Blockers + active sprint health
report = generate_standup(tasks_md, agile_mgr=mgr)
print(report.to_markdown())

# Sprint retro: derived from SprintMetrics.health (complete/on-track/at-risk/
# off-track) plus scope-creep detection; mutates sprint.retrospective in place
retro = generate_sprint_retro(sprint)

# Backlog retro: mines DONE/BLOCKED/DEFERRED rows + the bug log for retro material
retro = generate_backlog_retro(tasks_md)
print(retrospective_to_markdown(retro, "Weekly Backlog Retro"))

# Next-sprint plan: WSJF-allocate portfolio capacity, create the sprint
# (left in PLANNING for a human to start) and add one UserStory per commit
plan = plan_next_sprint(portfolio_mgr, agile_mgr, name="Sprint 9", goal="Ship MVP", capacity=20)
print(plan.to_markdown())
```

### Scheduled workflow
`.github/workflows/agile-ceremonies.yml` runs `.github/scripts/agile_ceremonies.py`
on a cron (weekday standup 08:00 UTC, Friday backlog retro 17:00 UTC, Monday
sprint plan 07:00 UTC) and writes the markdown digest to the job summary.
Trigger manually with `workflow_dispatch` and the `ceremony` input
(`standup` / `retro` / `plan`).

## Testing
```bash
python -m pytest tests/test_agile_sprints.py tests/test_agile_ceremonies.py -v
```

## Related
- Skill: `agentic-portfolio` (initiative/epic level — the layer above)
- Issue #233: Agentic Agile

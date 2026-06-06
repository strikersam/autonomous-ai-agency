# Implementation Prompt: Unified Task Board + Portfolio UI

## Context & Problem

The repo has three isolated work-management layers with no UI integration:

| Layer | Backend | Frontend | Status |
|-------|---------|----------|--------|
| Task | `tasks/api.py` + `tasks/models.py` | `TaskBoardScreen.jsx` | **Partial** — kanban exists, rich interactions absent |
| Agile | `agents/agile_sprints.py` | None | **Missing entirely** |
| Portfolio | `agents/portfolio.py` | None | **Missing entirely** |

The current `TaskBoardScreen` is a basic kanban. The backend already has comments
(threaded), approval checkpoints, execution logs, follow-up/escalate actions, and a
rich task model — none of it is surfaced in the UI.

The old v4 LLM relay had a multica-inspired task experience
(https://github.com/multica-ai/multica): right-side detail panel, agent comment thread,
"needs clarification" status with context threads, execution log, agent assignment with
availability. That richness needs to come back.

A naive approach would add `AgileScreen.jsx` and `PortfolioScreen.jsx` as separate
screens — but this creates duplicate kanban boards, duplicate status models, and no
linking between layers. Instead: **collapse the three layers into two unified screens.**

---

## Unified Architecture

```
Portfolio (strategic layer)          PortfolioScreen.jsx
  └── Initiative (WSJF-ranked)          WSJF table, Now/Next/Later roadmap,
        └── Sprint (linked)              capacity allocation, rollup from tasks
              └── Tasks (count/progress)

TaskBoard (execution layer)          TaskBoardScreen.jsx  ← UPGRADED
  └── Task / UserStory (unified)        Rich kanban + right-side detail panel
        sprint_id + story_points         Sprint-grouping view mode
        agent comments                   Agent comment thread
        execution_log                    Execution log accordion
        approval checkpoints             Clarification + approval UI
```

**Key decisions:**
- `UserStory` ≈ `Task` with `story_points` — **no separate story CRUD screen**.
  Add `story_points` and `sprint_id` to the Task model; one kanban surface.
- **No separate AgileScreen** — sprint management lives as a view-mode toggle in
  TaskBoard ("Board" vs "Sprint" view). Velocity chart is a collapsible widget.
- **PortfolioScreen** is the strategic layer only — it reads task/sprint data but
  does not have its own task CRUD.
- Add `needs_clarification` as a 7th task status alongside existing six.

---

## Implementation Prompt

You are upgrading the task management UI and adding portfolio management to the
local-llm-server dashboard. Follow the patterns in `DashboardScreen.jsx` (Widget,
useSafeData, skeleton loaders) and `TaskBoardScreen.jsx` (status columns, polling).

### What exists and must NOT be broken
- `TaskBoardScreen.jsx` — 6-column kanban with create-task modal, approve/retry buttons.
  Extend it; do not rewrite from scratch.
- `tasks/api.py` — 12 endpoints already wired. Use them; don't duplicate.
- `agents/agile_sprints.py` / `agents/portfolio.py` — in-process singletons via
  `_get_agile_manager()` / `_get_portfolio_manager()` in `services/skill_bindings.py`.

### Backend additions needed

**Task model extensions** (`tasks/models.py` + migration if needed):
- Add `story_points: Optional[int]` field (0 = not estimated)
- Add `sprint_id: Optional[str]` field (links task to an AgileSprint)
- Add `needs_clarification` to `TaskStatus` enum (between `blocked` and `in_review`)

**New task endpoint:**
- `PATCH /api/tasks/{id}/clarify` — set status to needs_clarification + set blocked_reason

**Agile REST endpoints** (add to `backend/server.py`):
- `GET  /api/agile/sprints` — list all sprints; for each sprint, include linked task IDs,
  total_points, completed_points, health, days_remaining from AgileManager
- `POST /api/agile/sprints` — create sprint `{name, goal}`
- `POST /api/agile/sprints/{sprint_id}/start` — `{duration_days?}`
- `POST /api/agile/sprints/{sprint_id}/complete` — returns SprintMetrics
- `GET  /api/agile/velocity` — `{predicted_velocity, sprint_count, history[]}`

**Portfolio REST endpoints** (add to `backend/server.py`):
- `GET  /api/portfolio/initiatives` — WSJF-ranked; include linked sprint summaries
- `POST /api/portfolio/initiatives` — `{title, business_value, time_criticality, risk_reduction, job_size, owner?}`
- `DELETE /api/portfolio/initiatives/{initiative_id}`
- `GET  /api/portfolio/roadmap` — Now/Next/Later lanes
- `POST /api/portfolio/allocate` — `{capacity}` → CapacityAllocation
- `GET  /api/portfolio/metrics` — PortfolioMetrics
- `POST /api/portfolio/initiatives/{initiative_id}/link-sprint` — `{sprint_id}`

### TaskBoardScreen upgrade

Extend `frontend/src/v5/screens/TaskBoardScreen.jsx`:

**1. Right-side detail panel** (slide in when a card is clicked, ~380px wide):
- Full task title (editable inline)
- Description (editable)
- Status dropdown (all 7 statuses including needs_clarification)
- Priority + task_type dropdowns
- Story points picker (0/1/2/3/5/8/13 Fibonacci)
- Sprint assignment dropdown (fetches `/api/agile/sprints`, shows sprint name + health)
- Agent assignment (current agent_id, reassign dropdown)
- **Comment thread** — renders `task.comments[]` as a conversation:
  - Agent comments (grey background, agent avatar icon)
  - Human comments (blue background, user avatar)
  - Reply threading (indent reply_to chains)
  - "Add comment" textarea + submit (POST `/api/tasks/{id}/comments`)
- **Execution log accordion** — collapsible list of `task.execution_log[]` entries
- **Approval checkpoints** — list of pending checkpoints with Approve/Reject buttons
- **Actions row**: Follow-up (re-open with new message), Escalate, Request Clarification
- Close panel with `Esc` or clicking outside

**2. New "Needs Clarification" column** in the kanban (purple `#b57bee`), between
Blocked and In Review. Shows tasks awaiting human input before agent resumes.

**3. Sprint view mode toggle** (Board | Sprint buttons top-right):
- **Board mode** (default): current status-column kanban
- **Sprint mode**: group cards by sprint instead of status; sprint header shows name,
  health badge (ON_TRACK/AT_RISK/OFF_TRACK), burndown %, days remaining;
  "No sprint" group at bottom for unassigned tasks
- Velocity widget: collapsible panel showing predicted velocity + last 5 sprints bar chart

**4. Create-task modal enhancements**:
- Add Story Points field (Fibonacci picker: ?, 1, 2, 3, 5, 8, 13)
- Add Sprint dropdown (optional)
- Add "Needs clarification" checkbox to create as clarification-needed immediately

### PortfolioScreen (new file)

Create `frontend/src/v5/screens/PortfolioScreen.jsx`:

**Sections:**
1. **Metrics strip** — total initiatives, in_progress count, avg WSJF, capacity utilisation %
2. **WSJF initiative table** — columns: Title, CoD score, Job size, WSJF, Horizon badge
   (NOW/NEXT/LATER/UNSCHEDULED), Status, Owner; click row to expand linked sprints with
   progress bars
3. **Roadmap swimlanes** — 3 horizontal lanes (Now / Next / Later); initiative cards with
   WSJF score, health dot from linked sprint, task count. Drag-to-reorder optional (P2).
4. **Capacity widget** — input: available capacity (SP); output: committed initiatives vs
   deferred, utilisation bar
5. **Add Initiative modal** — title, business_value, time_criticality, risk_reduction,
   job_size, owner
6. **Link Sprint** — inline dropdown on each initiative row to link an agile sprint

### Navigation

`AppShell.jsx` NAV_ITEMS additions:
- Portfolio: id `'portfolio'`, icon `Layers`, label `"Portfolio"` — after TaskBoard
- Remove any placeholder nav item for "Agile" — agile lives inside TaskBoard Sprint view

---

## Prioritised TODO

### P0 — Backend: Task model + status
- [ ] Add `story_points: Optional[int]` and `sprint_id: Optional[str]` to Task model
- [ ] Add `needs_clarification` to `TaskStatus` enum
- [ ] `PATCH /api/tasks/{id}/clarify` endpoint

### P0 — Backend: Agile REST
- [ ] `GET /api/agile/sprints` with linked task counts + metrics
- [ ] `POST /api/agile/sprints`
- [ ] `POST /api/agile/sprints/{id}/start`
- [ ] `POST /api/agile/sprints/{id}/complete`
- [ ] `GET /api/agile/velocity`

### P0 — Backend: Portfolio REST
- [ ] `GET /api/portfolio/initiatives`
- [ ] `POST /api/portfolio/initiatives`
- [ ] `DELETE /api/portfolio/initiatives/{id}`
- [ ] `GET /api/portfolio/roadmap`
- [ ] `POST /api/portfolio/allocate`
- [ ] `GET /api/portfolio/metrics`
- [ ] `POST /api/portfolio/initiatives/{id}/link-sprint`

### P1 — Frontend: TaskBoard — detail panel
- [ ] Slide-out detail panel component (click card → opens)
- [ ] Comment thread render + "Add comment" form
- [ ] Execution log accordion
- [ ] Approval checkpoint list with Approve/Reject buttons
- [ ] Inline status / priority / story_points / sprint_id / agent_id editing
- [ ] Follow-up, Escalate, Request Clarification actions

### P1 — Frontend: TaskBoard — sprint view
- [ ] "Needs Clarification" kanban column (7th column, purple)
- [ ] Board | Sprint toggle
- [ ] Sprint-grouped card view with health badge + burndown %
- [ ] Velocity widget (collapsible)
- [ ] Story points + sprint in create-task modal

### P1 — Frontend: PortfolioScreen
- [ ] Metrics strip
- [ ] WSJF initiative table (expandable rows showing linked sprints)
- [ ] Now / Next / Later swimlanes
- [ ] Capacity allocation widget
- [ ] Add Initiative modal
- [ ] Nav entry in AppShell (`'portfolio'`, Layers icon)

### P2 — Tests + Changelog
- [ ] `tests/test_agile_api.py`
- [ ] `tests/test_portfolio_api.py`
- [ ] `tests/test_task_clarification.py`
- [ ] `docs/changelog.md` entry

---

## Duplicate eliminations

| Was planned | Decision |
|-------------|----------|
| Separate `AgileScreen.jsx` | **Eliminated** — sprint management is a view-mode toggle inside TaskBoard |
| UserStory CRUD screen | **Eliminated** — UserStory ≈ Task with story_points; one surface |
| Separate story kanban | **Eliminated** — the upgraded TaskBoard IS the story board |
| `POST /api/agile/sprints/{id}/stories` | **Replaced** — tasks link to sprints via `sprint_id`; no separate story objects |
| Sprint retro endpoint | **Deferred** — retro is a P3 nice-to-have, not P0 |

---

## Key files

| File | Role |
|------|------|
| `frontend/src/v5/screens/TaskBoardScreen.jsx` | Extend (308 lines) — do not rewrite |
| `frontend/src/v5/screens/PortfolioScreen.jsx` | Create new |
| `frontend/src/v5/AppShell.jsx` | Add Portfolio nav entry |
| `frontend/src/v5/api.js` | Add agile/portfolio fetch helpers |
| `tasks/models.py` | Add story_points, sprint_id, needs_clarification status |
| `tasks/api.py` | Add /clarify endpoint |
| `backend/server.py` | Add all agile + portfolio endpoints |
| `agents/agile_sprints.py` | Read-only — backend already complete |
| `agents/portfolio.py` | Read-only — backend already complete |
| `services/skill_bindings.py` | `_get_agile_manager()` / `_get_portfolio_manager()` singletons |

## Risk flags

- **`needs_clarification` status** — adding a new enum value to `TaskStatus` may
  require a DB migration if tasks are persisted in MongoDB/SQLite with strict enum
  validation. Check `tasks/models.py` for how status is stored.
- **Singleton state** — agile/portfolio managers are in-process only; server restart
  wipes sprint/initiative data. Flag this clearly in the UI (banner: "Sprint data is
  in-memory — persisted tasks survive restart, sprint planning does not").
- **TaskBoard size** — adding a detail panel + sprint view to an existing 308-line
  file will push it past 700 lines. Consider extracting `TaskDetailPanel.jsx` as a
  sibling component to keep the main file manageable.
- **Auth** — `_get_agile_manager()` / `_get_portfolio_manager()` are process-wide
  singletons with no per-user isolation. All dashboard users see the same sprint/
  portfolio state. Acceptable for single-operator use; document this limitation.

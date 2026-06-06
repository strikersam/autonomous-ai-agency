# Implementation Prompt: Agentic Agile UI

## Context

`agents/agile_sprints.py` and `agents/portfolio.py` ship a fully-featured sprint/story
management engine (SprintManager, WSJF prioritisation, velocity tracking, burndown,
retrospectives) backed by the `agentic-agile` and `agentic-portfolio` skill bindings in
`services/skill_bindings.py`. However there are **zero HTTP endpoints and zero frontend
screens** — the only way to interact with these systems today is through the agent chat.

The portfolio layer also has no REST surface despite `docs/context/agentic-portfolio.md`
calling it out as an explicit "extension idea".

This task wires both layers into the existing dashboard by adding:
1. REST API endpoints in `backend/server.py`
2. `AgileScreen.jsx` — sprint board, story kanban, velocity
3. `PortfolioScreen.jsx` — WSJF roadmap, capacity, initiative list
4. Nav entries in `AppShell.jsx`

## Implementation Prompt

You are implementing the Agentic Agile + Portfolio UI for the local-llm-server dashboard.
The backend engine already exists — your job is to expose it via REST and build the React
screens that consume it, following the exact patterns established by the existing v5 screens
(see `DashboardScreen.jsx`, `TaskBoardScreen.jsx` for component conventions).

### Backend conventions to follow

- All routes go in `backend/server.py` under the `app` FastAPI instance
- Auth: `Depends(require_auth)` on all write endpoints; GET endpoints may be open
- Pydantic request/response models at the top of the file (or `backend/models/`)
- Use `_get_agile_manager()` / `_get_portfolio_manager()` from `services/skill_bindings.py`
  for the singleton managers (don't instantiate new ones)
- Return consistent `{"ok": true, "data": ...}` or raise `HTTPException`

### Frontend conventions to follow

- File: `frontend/src/v5/screens/AgileScreen.jsx` and `PortfolioScreen.jsx`
- Use the `Widget` / `useSafeData` / skeleton-loader pattern from `DashboardScreen.jsx`
- Error boundaries via `ErrorBoundary` component
- All fetch calls via `api.js` (`import api from '../api'`)
- Story status chips: BACKLOG (grey) → TODO (blue) → IN_PROGRESS (yellow) → DONE (green)
- Sprint health badge: ON_TRACK (green) / AT_RISK (amber) / OFF_TRACK (red) / COMPLETE (grey)
- Nav entry in `AppShell.jsx` NAV_ITEMS — use the `Zap` icon for Agile, `Layers` for Portfolio

### Key data relationships

```
PortfolioManager                     AgileManager
  └── Initiative (WSJF-ranked)         └── AgileSprint
        └── linked sprint_ids                └── UserStory
              └── progress rollup
```

## Prioritised TODO

- [ ] **P0 — Backend: Agile API endpoints**
  - [ ] `GET  /api/agile/sprints` → list all sprints with inline metrics
  - [ ] `POST /api/agile/sprints` body: `{name, goal}` → create sprint
  - [ ] `GET  /api/agile/sprints/{sprint_id}` → sprint detail + full story list + metrics
  - [ ] `POST /api/agile/sprints/{sprint_id}/stories` body: `{title, description, story_points, assignee?}`
  - [ ] `PATCH /api/agile/sprints/{sprint_id}/stories/{story_id}` body: `{status}` → update story status
  - [ ] `POST /api/agile/sprints/{sprint_id}/start` body: `{duration_days?}` → start sprint
  - [ ] `POST /api/agile/sprints/{sprint_id}/complete` → complete sprint, return SprintMetrics
  - [ ] `GET  /api/agile/velocity` → `{predicted_velocity, sprint_count}`
  - [ ] `POST /api/agile/sprints/{sprint_id}/retro` body: `{went_well, went_poorly, action_item?}`

- [ ] **P0 — Backend: Portfolio API endpoints**
  - [ ] `GET  /api/portfolio/initiatives` → WSJF-ranked initiative list
  - [ ] `POST /api/portfolio/initiatives` body: `{title, business_value, time_criticality, risk_reduction, job_size, owner?}`
  - [ ] `DELETE /api/portfolio/initiatives/{initiative_id}`
  - [ ] `GET  /api/portfolio/roadmap` → Now/Next/Later lanes (default capacity_per_horizon=5)
  - [ ] `POST /api/portfolio/allocate` body: `{capacity}` → CapacityAllocation
  - [ ] `GET  /api/portfolio/metrics` → PortfolioMetrics
  - [ ] `POST /api/portfolio/initiatives/{initiative_id}/link-sprint` body: `{sprint_id}`
  - [ ] `GET  /api/portfolio/rollup` → initiative progress with linked sprint data

- [ ] **P1 — Frontend: `AgileScreen.jsx`**
  - [ ] Active sprints grid — each card shows name, goal, health badge, burndown %, days remaining
  - [ ] Story kanban inside each sprint card (4 columns: BACKLOG / TODO / IN_PROGRESS / DONE)
  - [ ] Click story to update status (inline dropdown or drag)
  - [ ] "New Sprint" modal — name + goal inputs
  - [ ] "Add Story" modal — title, points, assignee
  - [ ] "Start Sprint" button (with duration selector) and "Complete Sprint" button
  - [ ] Velocity widget — predicted velocity + completed sprint history sparkline
  - [ ] Retrospective section (expandable) showing went_well / went_poorly / action items

- [ ] **P1 — Frontend: `PortfolioScreen.jsx`**
  - [ ] WSJF ranked initiative table — title, CoD, job_size, WSJF score, horizon badge, status
  - [ ] Now / Next / Later roadmap swimlanes (horizontal card rows per horizon)
  - [ ] Capacity allocation widget — committed vs deferred pie/bar
  - [ ] Metrics summary strip — total_initiatives, completed, in_progress, avg_wsjf
  - [ ] "Add Initiative" modal
  - [ ] Link sprint to initiative dropdown (if agile sprints exist)

- [ ] **P1 — Nav wiring**
  - [ ] Add `AgileScreen` to `NAV_ITEMS` in `AppShell.jsx` (id: `'agile'`, icon: Zap, label: "Agile")
  - [ ] Add `PortfolioScreen` to `NAV_ITEMS` (id: `'portfolio'`, icon: Layers, label: "Portfolio")
  - [ ] Register both screens in the screen router (wherever `TaskBoardScreen` is imported/switched)

- [ ] **P2 — Tests**
  - [ ] `tests/test_agile_api.py` — endpoint smoke tests for create/list/start/complete flow
  - [ ] `tests/test_portfolio_api.py` — add/prioritize/roadmap/allocate endpoint tests

- [ ] **P2 — Changelog** — update `docs/changelog.md` under `[Unreleased]`

## Relevant files

| File | Role |
|------|------|
| `agents/agile_sprints.py` | AgileManager, AgileSprint, UserStory, SprintMetrics models |
| `agents/portfolio.py` | PortfolioManager, Initiative, CapacityAllocation, PortfolioMetrics |
| `services/skill_bindings.py` | Singleton accessors `_get_agile_manager()` / `_get_portfolio_manager()` |
| `backend/server.py` | Add all new endpoints here |
| `frontend/src/v5/screens/DashboardScreen.jsx` | Widget/useSafeData/skeleton pattern to copy |
| `frontend/src/v5/screens/TaskBoardScreen.jsx` | Modal + status mutation pattern to copy |
| `frontend/src/v5/AppShell.jsx` | NAV_ITEMS + screen router |
| `frontend/src/v5/api.js` | axios instance — use for all fetch calls |
| `tests/test_agile_sprints.py` | Existing tests — extend with API tests |
| `tests/test_portfolio.py` | Existing tests — extend with API tests |

## Risk flags

- **Singleton state is in-process only** — server restart wipes all sprints/initiatives.
  Acceptable for now; persistence to DB is a follow-on (noted in `docs/context/agentic-portfolio.md`).
- **Auth on GET endpoints** — portfolio/agile data is not sensitive, so GET routes can be
  unauthenticated for dashboard convenience. Confirm this aligns with the project's auth model.
- **Frontend bundle size** — adding two screens adds ~20–30KB to the React build. No concern.
- **`require_auth` import** — verify the exact import path before adding to any new endpoint.

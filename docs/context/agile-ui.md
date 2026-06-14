# Implementation Prompt: Rich TaskBoard + Agile Sprint Integration

## What's already on master (do not re-implement)

| Feature | Status | Key files |
|---------|--------|-----------|
| PortfolioScreen.jsx — WSJF table, Now/Next/Later roadmap, capacity, source badges, refresh | **DONE** (#426, #427) | `frontend/src/v5/screens/PortfolioScreen.jsx` |
| Portfolio REST API — `/board`, `/refresh`, `/initiatives` CRUD | **DONE** (#427) | `agents/portfolio_api.py` |
| Portfolio intelligence — auto-discovers from roadmap, bugs, open PRs, research | **DONE** (#427) | `agents/portfolio_intelligence.py` |
| Portfolio nav entry — `id:'portfolio'`, icon:'Target', section:'AGENCY' | **DONE** | `frontend/src/v5/AppShell.jsx` |
| Agile backend — AgileManager, AgileSprint, UserStory, SprintMetrics, SprintHealth | **DONE** (#423) | `agents/agile_sprints.py` |
| Task backend — 12 REST endpoints, comments, approval checkpoints, follow-up, escalate | **DONE** | `tasks/api.py`, `tasks/models.py` |

## What is genuinely missing

The **TaskBoardScreen** has a working 6-column kanban but zero rich interaction —
no detail panel, no comment thread UI, no execution log, no approval checkpoint UI,
no clarification flow — despite the backend having all of it. The agile sprint layer
has no REST surface, so sprints can't be grouped in the TaskBoard.

The old v4 LLM relay had a multica-inspired experience
(https://github.com/multica-ai/multica): right-side detail panel, agent comment
thread, "needs clarification" status, execution log, contextual actions per task.
This gap needs to close.

---

## Architecture

```
PortfolioScreen (already done)
  └── Initiative (WSJF) ← reads sprint rollup from agile API

TaskBoardScreen (UPGRADE — extend, do not rewrite)
  ├── Board view: 7-column kanban (add "Needs Clarification")
  ├── Sprint view: cards grouped by sprint (toggle)
  └── Detail panel: slide-out on card click
        ├── Comment thread (agent + human, threaded)
        ├── Execution log accordion
        ├── Approval checkpoints
        └── Actions: Follow-up, Escalate, Clarify, Sprint assign
```

---

## Implementation Prompt

You are upgrading `TaskBoardScreen.jsx` and adding agile sprint REST endpoints.
**Extend the existing component** — it is 308 lines and solid. Do not rewrite it.

### 1. Task model extensions (`tasks/models.py`)

Add to the Task Pydantic model:
- `story_points: Optional[int] = None` — Fibonacci estimate (1/2/3/5/8/13)
- `sprint_id: Optional[str] = None` — links task to an AgileSprint ID

Add `needs_clarification` to the `TaskStatus` enum (value: `"needs_clarification"`).
Place it between `blocked` and `in_review` in the ordering.

Check how TaskStatus is stored in MongoDB/SQLite — if it's stored as a plain string
field (not validated by MongoDB), no migration is needed; just add the enum value.

### 2. New task endpoint (`tasks/api.py`)

```
PATCH /api/tasks/{task_id}/clarify
  body: {reason: str}
  action: set status = needs_clarification, set blocked_reason = reason
  auth: require_auth
```

Also extend the `PATCH /api/tasks/{task_id}` handler to accept `story_points`
and `sprint_id` in the update body.

### 3. Agile REST endpoints (`backend/server.py`)

Use `_get_agile_manager()` from `services/skill_bindings.py` for the singleton.

```
GET  /api/agile/sprints
  Returns list of sprints. For each sprint, include:
    sprint_id, name, goal, status, start_date, end_date,
    metrics (total_points, completed_points, health, days_remaining,
             completion_percentage, burndown_rate),
    story_count, scope_added

POST /api/agile/sprints
  body: {name: str, goal: str}
  Returns created AgileSprint

POST /api/agile/sprints/{sprint_id}/start
  body: {duration_days?: int}  (default 14)

POST /api/agile/sprints/{sprint_id}/complete
  Returns SprintMetrics

GET  /api/agile/velocity
  Returns: {predicted_velocity: float, sprint_count: int, history: [...]}
  history = list of {sprint_id, name, velocity} for completed sprints
```

No auth required on GET. POST/action routes require `Depends(require_auth)`.
Return `{"ok": true, "data": ...}` or raise `HTTPException`.

### 4. TaskBoardScreen upgrade (`frontend/src/v5/screens/TaskBoardScreen.jsx`)

#### 4a. "Needs Clarification" 7th column

Add a 7th column between Blocked and In Review:
```js
{ id: 'needs_clarification', label: 'Needs Clarification', color: '#b57bee' }
```
Show a "❓ Clarify" chip on card if `task.status === 'needs_clarification'`.

#### 4b. Right-side detail panel

Extract as a sibling component `TaskDetailPanel.jsx` to keep the main file manageable.

Open when a task card is clicked (add `onClick` to card — currently no handler exists).
Close with `Esc` key or clicking the overlay.

Panel sections (top to bottom):
1. **Header** — task title (editable `<input>`), status badge, close button
2. **Meta row** — Priority dropdown, Task type, Story points picker
   (buttons: ?, 1, 2, 3, 5, 8, 13), Sprint dropdown (fetches `/api/agile/sprints`),
   Agent assignment dropdown
3. **Description** — `<textarea>` editable, auto-save on blur via
   `PATCH /api/tasks/{id}` with `{description}`
4. **Comment thread** — renders `task.comments[]`:
   - Agent comments: grey background, `🤖` prefix with `comment.author`
   - Human comments: blue background, user avatar initial
   - Threaded replies: indent `reply_to` chains one level
   - "Add comment" `<textarea>` + Submit button →
     `POST /api/tasks/{id}/comments` `{body: str}`
   - Re-fetch task after submit to update thread
5. **Execution log** — collapsible `<details>` accordion:
   - Renders `task.execution_log[]` as timestamped lines
   - Collapsed by default; show entry count in summary
6. **Approval checkpoints** — only shown when `task.approval_checkpoints?.length > 0`:
   - List each checkpoint with its `reason` and Approve / Reject buttons
   - Approve: `POST /api/tasks/{id}/approve` `{checkpoint_id, approve: true, reason: ''}`
   - Reject: same with `approve: false` + reason input
7. **Actions footer** — three buttons:
   - **Follow-up**: open a small modal with textarea →
     `POST /api/tasks/{id}/follow-up` `{message: str}`
   - **Escalate**: confirm dialog → `POST /api/tasks/{id}/escalate`
     `{escalation_reason: str}`
   - **Request Clarification**: small modal with reason input →
     `PATCH /api/tasks/{id}/clarify` `{reason: str}`

All mutations re-fetch the task after completion to refresh the panel.

#### 4c. Sprint view mode toggle

Add "Board" | "Sprint" toggle buttons top-right (alongside the existing filter bar).
Default: Board mode (unchanged).

**Sprint mode:**
- Fetch `/api/agile/sprints` on mount
- Group task cards by `task.sprint_id`; sprints with matching tasks appear as
  labelled sections with their health badge:
  - ON_TRACK: green dot
  - AT_RISK: amber dot
  - OFF_TRACK: red dot
  - COMPLETE: grey dot
- Sprint section header shows: name, health dot, `completion_percentage`%,
  `days_remaining` days left
- Tasks without a sprint_id appear in "No Sprint" section at the bottom
- Velocity widget: collapsible `<details>` below the sprint list showing
  predicted_velocity from `/api/agile/velocity` and a simple bar chart
  of the last 5 sprints by velocity

#### 4d. Create-task modal enhancements

In the existing create-task modal, add:
- Story points picker (same Fibonacci buttons as panel)
- Sprint dropdown (`<select>`, populated from `/api/agile/sprints`)
- Both are optional fields

#### 4e. New "New Sprint" button (Sprint view only)

When in Sprint view, show a "New Sprint +" button above the sprint list.
Clicking opens a small modal: Sprint name + goal inputs →
`POST /api/agile/sprints` → refreshes sprint list.

### 5. Portfolio ↔ TaskBoard integration (bonus, do after core work)

The PortfolioScreen already shows `rollup` from linked sprints. Close the loop:
- In the TaskBoard sprint view, add a small "Link to initiative" dropdown on each
  sprint header, fetching `GET /api/portfolio/board` to get the initiative list.
  On select: `POST /api/portfolio/initiatives/{initiative_id}/link-sprint`
  `{sprint_id}` (add this endpoint to `agents/portfolio_api.py`).

---

## Prioritised TODO

### P0 — Backend
- [ ] `story_points` + `sprint_id` on Task model + PATCH support
- [ ] `needs_clarification` TaskStatus enum value
- [ ] `PATCH /api/tasks/{id}/clarify`
- [ ] `GET /api/agile/sprints` with inline metrics
- [ ] `POST /api/agile/sprints`
- [ ] `POST /api/agile/sprints/{id}/start`
- [ ] `POST /api/agile/sprints/{id}/complete`
- [ ] `GET /api/agile/velocity`

### P1 — TaskBoard: detail panel
- [ ] `TaskDetailPanel.jsx` component (extract / create)
- [ ] Card `onClick` → open panel
- [ ] Comment thread render + add-comment form
- [ ] Execution log accordion
- [ ] Approval checkpoint list with Approve/Reject
- [ ] Inline field editing (status, priority, story_points, sprint_id, agent)
- [ ] Follow-up / Escalate / Clarify action modals

### P1 — TaskBoard: sprint view + clarification column
- [ ] "Needs Clarification" 7th column
- [ ] Board | Sprint toggle
- [ ] Sprint-grouped view with health badge + burndown %
- [ ] Velocity widget (collapsible)
- [ ] story_points + sprint_id in create modal
- [ ] "New Sprint" button + modal (Sprint view only)

### P2 — Portfolio integration
- [ ] `POST /api/portfolio/initiatives/{id}/link-sprint` endpoint
- [ ] "Link to initiative" dropdown on sprint headers in TaskBoard

### P2 — Tests + Changelog
- [ ] `tests/test_agile_api.py` — sprint create/start/complete/velocity
- [ ] `tests/test_task_clarification.py` — needs_clarification status + /clarify
- [ ] `docs/changelog.md` under `[Unreleased]`

---

## Key files

| File | Role |
|------|------|
| `frontend/src/v5/screens/TaskBoardScreen.jsx` | Extend (308 lines) — do not rewrite |
| `frontend/src/v5/screens/TaskDetailPanel.jsx` | Create as sibling component |
| `frontend/src/v5/api.js` | Add `fetchSprints`, `createSprint`, `fetchVelocity` helpers |
| `tasks/models.py` | Add story_points, sprint_id, needs_clarification |
| `tasks/api.py` | Add /clarify endpoint; extend PATCH for new fields |
| `backend/server.py` | Add all /api/agile/* endpoints |
| `agents/agile_sprints.py` | Read-only — backend complete |
| `agents/portfolio_api.py` | Add link-sprint endpoint (P2) |
| `services/skill_bindings.py` | `_get_agile_manager()` singleton |

## Risk flags

- **`needs_clarification` enum** — adding a new TaskStatus value is safe if status
  is stored as a plain string (most likely). Verify `tasks/models.py` storage.
- **Singleton state** — agile sprint data is in-process only (no DB persistence).
  Show a subtle banner: "Sprint planning is in-memory — restarts reset sprint data."
- **TaskDetailPanel size** — extract as a sibling `TaskDetailPanel.jsx` rather than
  inlining into the already-308-line `TaskBoardScreen.jsx`.
- **Auth model for agile GET** — agile/sprint data is not user-specific; GET routes
  can be unauthenticated for dashboard convenience.

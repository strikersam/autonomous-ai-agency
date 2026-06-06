# Context: Agentic Agile + Portfolio Management

This document captures the design context and rationale for the agentic agile and
portfolio management capabilities, so future sessions can extend them without
re-deriving the model.

## Problem

The repo shipped `agents/agile_sprints.py` (sprint/story level) and a `portfolio`
specialist family (Portfolio Manager, capabilities: roadmapping, prioritization,
resource_allocation, strategy, planning) — but there was **no module backing the
portfolio family**, and the `agentic-agile` skill binding was a stub that reset
state on every call and hard-coded `get_metrics` to `sprint_count: 0`.

## The two layers

| Layer | Unit | Module | Skill |
|-------|------|--------|-------|
| Agile | Sprint / User Story | `agents/agile_sprints.py` | `agentic-agile` |
| Portfolio | Initiative (epic) | `agents/portfolio.py` | `agentic-portfolio` |

Portfolio sits **above** agile: initiatives are delivered by one or more sprints.
`PortfolioManager.rollup_progress(agile_manager)` reads each linked sprint's
total/completed points to report real delivery against each initiative.

## Prioritisation model — WSJF (SAFe)

`WSJF = Cost of Delay / Job Size`
`Cost of Delay = business_value + time_criticality + risk_reduction`

Higher WSJF schedules sooner. Components use a relative (modified Fibonacci) scale.
This is the standard Scaled Agile Framework economic-prioritisation model and is
deliberately the same maths a human portfolio manager uses, so agent decisions are
auditable. Ties break on cost of delay (higher) then job size (smaller).

## Capacity & roadmap

- `allocate_capacity(capacity)` — greedy fill by WSJF priority; returns committed
  vs deferred plus utilisation. Answers "what makes the next increment?".
- `plan_roadmap(capacity_per_horizon)` — distributes the ranked backlog across
  **Now / Next / Later** horizons, overflow → Unscheduled. Mutates each
  initiative's `horizon` so placement persists.

## Agile improvements shipped alongside

- **`SprintHealth`** signal on `SprintMetrics.health`: ON_TRACK / AT_RISK /
  OFF_TRACK / COMPLETE (AT_RISK = within ~25% of the required burndown pace).
- **Scope-change tracking**: `committed_points` is snapshotted at `start()`;
  `scope_added` reports mid-sprint creep.
- **Retrospective**: `Retrospective` (went_well / went_poorly / action_items) with
  `add_retro_note()` and `add_action_item()` helpers.

## Wiring

- `services/skill_bindings.py` registers `agentic-portfolio`, binds it to the
  `portfolio`/`product`/`operations`/`analytics` families, and exposes process-wide
  shared `AgileManager` / `PortfolioManager` singletons so stateful planning skills
  accumulate across calls instead of resetting.

## v5 UI surface

`frontend/src/v5/screens/PortfolioScreen.jsx` (nav id `portfolio`, AGENCY section)
renders the portfolio as a live board:

- **Metrics strip** — initiatives, active, avg WSJF, total Cost of Delay, increment capacity.
- **Now/Next/Later roadmap** — three capacity-bounded columns + a backlog overflow row.
- **WSJF priority table** — BV / TC / RR → CoD → Job Size → WSJF score bars.
- **Sprint health cards** — health pill, burndown %, scope-creep, days remaining.

It reads a single payload from `GET /api/portfolio/board` (`agents/portfolio_api.py`),
which composes `PortfolioManager` + `AgileManager`. The API holds an in-process
`PortfolioService` singleton seeded with illustrative demo data (`POST /api/portfolio/seed`
resets it), so the screen is populated immediately after deploy. This is a
presentation surface, **not** a system of record — persistence is a future step.

> Deploy note: the backend deploy (`deploy-backend.yml`) covers `agents/**`,
> `services/**`, `backend/**`; the frontend deploy (`deploy-frontend.yml`) covers
> `frontend/**`. This feature touches both, so both pipelines run on merge.

## Extension ideas (not yet built)

- Persist managers to disk / the company graph instead of in-process singletons.
- Expose REST endpoints in `agents/api.py` for portfolio CRUD + roadmap.
- Dependencies between initiatives (block/enable) feeding into roadmap ordering.
- Tie `financial-analyst` ROI/burn into Initiative economics for budget-aware WSJF.
- Confidence weighting / RICE as an alternative prioritisation model.

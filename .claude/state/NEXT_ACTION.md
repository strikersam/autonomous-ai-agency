# Agent State — agentic-agile-workflows-8ymf4d

**Session:** `agentic-agile-workflows-8ymf4d`
**Status:** planned — awaiting user confirmation to implement
**Last updated:** 2026-06-13T20:15:00Z

## Context / Task

User asked: "Does agentic agile work (sprints, standups, scrums, retros) happen
for the agents on its own? Is there agents for portfolio manager, delivery
manager, product manager etc., typical to an agency, with the right skills and
workflows? If not, make sure these exist and they all do their work properly."

## Findings (research complete — see PR description for full writeup)

- `agents/agile_sprints.py` — sprint/story/retro data structures exist and are
  tested, but are **not autonomous**. No standup/retro/sprint-planning scheduler
  anywhere.
- `agents/portfolio.py` + `agents/portfolio_intelligence.py` — WSJF portfolio
  management **is** autonomous: a 6h cron (`.github/workflows/portfolio-refresh.yml`)
  sweeps real signals and refreshes the v5 dashboard. This is the template to
  follow for the new ceremonies.
- `SpecialistFamily` (models/company_graph.py:47) has `agile` (Scrum Master),
  `portfolio` (Portfolio Manager), `product` — but these are capability/tool
  taxonomies, not ceremony-owning personas. **No `delivery` (Delivery Manager)
  role exists** — documented gap in
  `docs/architecture/tailored-onboarding-and-roles.md` (Phase 3 "Role Registry").

## Plan (NOT YET IMPLEMENTED — confirm before starting)

### Part A — Autonomous agile ceremonies

1. `agents/agile_ceremonies.py` (new):
   - Small addition to `agents/agile_sprints.py`: `AgileSprint.stories` property
     (public accessor for `_stories.values()` — ceremonies shouldn't reach into
     a private dict).
   - `StandupReport` dataclass + `generate_standup(tasks_md, agile_mgr=None)` —
     parses `.claude/state/active-tasks.md` "Current Sprint Tasks" + "Bug Log"
     tables (reuse `_table_rows`/`_clean` from `agents/portfolio_intelligence.py`)
     into completed / in_progress / planned / blockers; folds in active-sprint
     health if an `AgileManager` is supplied. `.to_markdown()`.
   - `generate_sprint_retro(sprint) -> Retrospective` — derives went_well /
     went_poorly / action_items from `SprintMetrics.health`, `scope_added`,
     `completion_percentage` via the existing `add_retro_note` /
     `add_action_item` helpers.
   - `generate_backlog_retro(tasks_md) -> Retrospective` — for the no-active-
     sprint case: DONE/BUG_FIXED rows -> went_well, BLOCKED/BUG_FOUND/DEFERRED ->
     went_poorly + action_items.
   - `SprintPlan` dataclass + `plan_next_sprint(portfolio_mgr, agile_mgr, *, name,
     goal, capacity)` — `allocate_capacity()` -> new sprint with one `UserStory`
     per committed initiative, linked back via `link_sprint`; left in PLANNING
     for a human to start. `.to_markdown()`.
   - `retrospective_to_markdown(retro, title)` shared renderer.

2. `tests/test_agile_ceremonies.py` (new) — cover standup parsing (all status
   buckets), sprint retro for COMPLETE / ON_TRACK / AT_RISK / OFF_TRACK + scope
   creep, backlog retro, and `plan_next_sprint` capacity allocation / story
   creation / linkage.

3. `.github/scripts/agile_ceremonies.py` (new) — CLI runner
   (`standup|retro|plan` subcommands), same importlib-stub-loading pattern as
   `.github/scripts/portfolio_refresh.py`. Posts a markdown digest to
   `GITHUB_STEP_SUMMARY`. No repo writes; sprint planning only proposes.

4. `.github/workflows/agile-ceremonies.yml` (new) — cron:
   - standup: weekdays 08:00 UTC
   - retro: Fridays 17:00 UTC
   - sprint planning: Mondays 07:00 UTC
   - `workflow_dispatch` with a `ceremony` choice input for manual runs
   - `permissions: contents: read` (matches `portfolio-refresh.yml`)

5. `.claude/skills/agentic-agile/SKILL.md` — document the new ceremony
   functions and the scheduled workflow.

### Part B — Delivery Manager role

6. `models/company_graph.py` — add `"delivery"` to `SpecialistFamily` Literal
   (35th family), placed next to `agile` / `portfolio`.

7. `services/specialist.py`:
   - `_generate_specialist_name`: `"delivery": "Delivery Manager"`
   - `_get_default_capabilities`: `"delivery": ["sprint_planning", "standups",
     "retrospectives", "release_coordination", "cross_team_unblocking"]`
   - `_get_default_tools`: `"delivery": ["jira", "github_api", "slack", "linear",
     "confluence"]`
   - **Verify** `services/company_agency.py`, `hardware/detector.py`,
     `admin_gui.py` for other per-`SpecialistFamily` maps (grep for
     `"platform":` as a marker — it's the last key in most of these dicts) and
     add a `"delivery"` entry to each so nothing is left inconsistent.

8. `services/skill_bindings.py` — add `"delivery"` to `specialist_families` for
   the `agentic-agile` and `agentic-portfolio` skills (gives Delivery Manager
   the ceremony + WSJF skills — satisfies the "every family has >=1 bound skill"
   CI gate).

9. `tests/test_specialist_skill_matrix.py` — bump 34 -> 35 family count
   (`test_matrix_has_thirty_four_families`); update docstring wording.

10. Regenerate `docs/specialists-skills-matrix.md`:
    `python scripts/generate_specialist_skill_matrix.py`

11. `README.md` — update "34 specialist families" references (around lines
    118, 127, 230, 538) to 35.

12. `docs/architecture/tailored-onboarding-and-roles.md` — note `delivery`
    added to the seed catalog as the 35th family (small step on Phase 3 "Role
    Registry"; the full open-registry/custom-roles work remains future). Do not
    overclaim Phase 3 as done.

### Part C — Bookkeeping

13. `docs/changelog.md` — `## [Unreleased]` entries:
    - Added: autonomous agile ceremonies (standup / retro / sprint-planning) +
      `agile-ceremonies.yml` cron
    - Added: `delivery` (Delivery Manager) specialist family, bound to
      agentic-agile + agentic-portfolio

14. `.claude/state/active-tasks.md` — mark task #10 `DONE` with the PR link
    when complete; log any bugs found in the Bug Log.

### Acceptance criteria

- `pytest -x` green (full suite — `requirements.txt` install was in progress
  when this session paused; re-run if needed)
- `python scripts/generate_specialist_skill_matrix.py --check` passes
- New ceremony module has unit tests covering all `SprintHealth` branches and
  the standup / retro / plan happy paths
- `agile-ceremonies.yml` is valid YAML and mirrors `portfolio-refresh.yml`'s
  permission / concurrency conventions

## Prompt for continuing agent

> Implement the plan above in full, in order (Part A, then Part B, then Part C).
> Read `agents/agile_sprints.py`, `agents/portfolio.py`,
> `agents/portfolio_intelligence.py`, `.github/scripts/portfolio_refresh.py`,
> `.github/workflows/portfolio-refresh.yml`, `services/specialist.py`,
> `services/skill_bindings.py`, and `tests/test_specialist_skill_matrix.py`
> first for exact conventions/signatures. Write tests alongside each new
> module. Run `pytest -x` before each commit. Update `docs/changelog.md` and
> `.claude/state/active-tasks.md` as you go (mark task #10 `IN_PROGRESS` ->
> `DONE`). For Part B, first grep for all per-`SpecialistFamily` dicts (search
> for `"platform":` as a marker key, which appears last in most family maps) so
> every map gets a `"delivery"` entry — don't leave the matrix generator or CI
> gate inconsistent. Commit incrementally and push to
> `claude/agentic-agile-workflows-8ymf4d`.

## Resume command

Just say "continue" in this session, or `python scripts/ai_runner.py resume`.

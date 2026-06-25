"""Agentic Agile — autonomous ceremonies (standup, retro, sprint planning).

Where ``agents/agile_sprints.py`` provides the sprint/story data model and
``agents/portfolio.py`` provides WSJF-ranked initiatives, this module turns
both into the day-to-day agile *ceremonies* a delivery team runs:

  • **Standup** — a daily digest of completed / in-progress / planned work and
    blockers, derived from ``.claude/state/active-tasks.md`` (reusing the
    markdown-table parsing helpers from ``agents/portfolio_intelligence.py``),
    optionally folding in the health of any active sprint.
  • **Retrospective** — derives went-well / went-poorly / action-items either
    from a completed/active ``AgileSprint`` (via its ``SprintMetrics.health``
    and ``scope_added``) or, when there is no active sprint, from the open
    backlog/bug-log rows in the task tracker.
  • **Sprint planning** — allocates portfolio capacity (WSJF order) into a new
    sprint, one ``UserStory`` per committed initiative, linked back to the
    portfolio via ``link_sprint``. The sprint is left in ``PLANNING`` for a
    human (or the Delivery Manager specialist) to start.

These functions are pure and dependency-light (stdlib only) so they can run in
``.github/scripts/agile_ceremonies.py`` on a cron without the full app
dependency tree — see ``.github/workflows/agile-ceremonies.yml``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from agents.agile_sprints import AgileManager, AgileSprint, Retrospective, SprintHealth
from agents.agile_sprints import UserStory
from agents.portfolio import Initiative, PortfolioManager
from agents.portfolio_intelligence import _clean, _table_rows

_STANDUP_DONE_STATUSES = {"DONE", "BUG_FIXED"}
_STANDUP_BLOCKED_STATUSES = {"BLOCKED", "BUG_FOUND", "DEFERRED"}


def _bullets(items: List[str]) -> List[str]:
    """Render a list of strings as markdown bullets (or a placeholder)."""
    return [f"- {item}" for item in items] if items else ["- _none_"]


# ── Standup ───────────────────────────────────────────────────────────────
@dataclass
class StandupReport:
    """A daily standup digest derived from the task tracker.

    ``sprint_health`` is populated only when an :class:`AgileManager` with an
    active sprint is supplied to :func:`generate_standup`.
    """

    completed: List[str] = field(default_factory=list)
    in_progress: List[str] = field(default_factory=list)
    planned: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    sprint_health: List[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Render the standup digest as markdown."""
        lines = ["## Daily Standup", ""]
        lines.append("### Completed")
        lines += _bullets(self.completed)
        lines.append("")
        lines.append("### In progress")
        lines += _bullets(self.in_progress)
        lines.append("")
        lines.append("### Planned")
        lines += _bullets(self.planned)
        lines.append("")
        lines.append("### Blockers")
        lines += _bullets(self.blockers)
        if self.sprint_health:
            lines.append("")
            lines.append("### Active sprint health")
            lines += _bullets(self.sprint_health)
        lines.append("")
        return "\n".join(lines)


def generate_standup(tasks_md: str, agile_mgr: Optional[AgileManager] = None) -> StandupReport:
    """Build a :class:`StandupReport` from ``.claude/state/active-tasks.md``.

    Reads the "Current Sprint Tasks" and "Bug Log" tables and buckets each
    row by status into completed / in-progress / planned / blockers. If
    ``agile_mgr`` has an active sprint, its health is appended too.
    """
    report = StandupReport()

    for cells in _table_rows(tasks_md, "Current Sprint Tasks"):
        if len(cells) < 3:
            continue
        task, status = _clean(cells[1]), _clean(cells[2]).upper()
        if not task:
            continue
        if status in _STANDUP_DONE_STATUSES:
            report.completed.append(task)
        elif status == "IN_PROGRESS":
            report.in_progress.append(task)
        elif status == "TODO":
            report.planned.append(task)
        elif status in _STANDUP_BLOCKED_STATUSES:
            report.blockers.append(task)

    for cells in _table_rows(tasks_md, "Bug Log"):
        if len(cells) < 6:
            continue
        desc, status = _clean(cells[1]), _clean(cells[5]).upper()
        if not desc:
            continue
        if status == "BUG_FIXED":
            report.completed.append(f"Bug fixed: {desc}")
        elif status == "BUG_FOUND":
            report.blockers.append(f"Open bug: {desc}")

    if agile_mgr is not None:
        for sprint in agile_mgr.active_sprints():
            metrics = sprint.get_metrics()
            report.sprint_health.append(
                f"{sprint.name}: {metrics.health.value} "
                f"({metrics.completion_percentage:.0f}% complete, "
                f"{metrics.completed_points}/{metrics.total_points} pts)"
            )

    return report


# ── Retrospective ─────────────────────────────────────────────────────────
def retrospective_to_markdown(retro: Retrospective, title: str) -> str:
    """Render a :class:`Retrospective` as a markdown section."""
    lines = [f"## {title}", ""]
    lines.append("### What went well")
    lines += _bullets(retro.went_well)
    lines.append("")
    lines.append("### What went poorly")
    lines += _bullets(retro.went_poorly)
    lines.append("")
    lines.append("### Action items")
    lines += _bullets(retro.action_items)
    lines.append("")
    return "\n".join(lines)


def generate_sprint_retro(sprint: AgileSprint) -> Retrospective:
    """Derive retro notes for ``sprint`` from its current metrics.

    Records observations via :meth:`AgileSprint.add_retro_note` and
    :meth:`AgileSprint.add_action_item` (mutating ``sprint.retrospective``)
    and returns it.
    """
    metrics = sprint.get_metrics()
    health = metrics.health

    if health == SprintHealth.COMPLETE:
        sprint.add_retro_note(
            went_well=f"Sprint '{sprint.name}' completed all {metrics.total_points} committed points."
        )
    elif health == SprintHealth.ON_TRACK:
        sprint.add_retro_note(
            went_well=f"Sprint '{sprint.name}' is on track at {metrics.completion_percentage:.0f}% complete."
        )
    elif health == SprintHealth.AT_RISK:
        sprint.add_retro_note(
            went_poorly=(
                f"Sprint '{sprint.name}' is at risk: burndown rate "
                f"{metrics.burndown_rate:.2f}/day exceeds average velocity "
                f"{metrics.average_velocity:.2f}/day."
            )
        )
        sprint.add_action_item("Re-baseline remaining scope or add capacity to recover pace.")
    elif health == SprintHealth.OFF_TRACK:
        sprint.add_retro_note(
            went_poorly=(
                f"Sprint '{sprint.name}' is off track at {metrics.completion_percentage:.0f}% "
                "complete — required pace far exceeds velocity."
            )
        )
        sprint.add_action_item("Descope or re-plan the sprint — current pace will not finish on time.")

    if sprint.scope_added > 0:
        sprint.add_retro_note(
            went_poorly=f"Scope crept by {sprint.scope_added} points after the sprint started."
        )
        sprint.add_action_item("Protect sprint scope — defer new work to the backlog mid-sprint.")

    return sprint.retrospective


def generate_backlog_retro(tasks_md: str) -> Retrospective:
    """Derive a retrospective from the task tracker when no sprint is active.

    DONE / BUG_FIXED rows become "went well"; BLOCKED / BUG_FOUND / DEFERRED
    rows become "went poorly" with a matching action item.
    """
    retro = Retrospective()

    for cells in _table_rows(tasks_md, "Current Sprint Tasks"):
        if len(cells) < 3:
            continue
        task, status = _clean(cells[1]), _clean(cells[2]).upper()
        if not task:
            continue
        if status in _STANDUP_DONE_STATUSES:
            retro.went_well.append(task)
        elif status in _STANDUP_BLOCKED_STATUSES:
            retro.went_poorly.append(task)
            retro.action_items.append(f"Unblock / re-prioritise: {task}")

    for cells in _table_rows(tasks_md, "Bug Log"):
        if len(cells) < 6:
            continue
        desc, status = _clean(cells[1]), _clean(cells[5]).upper()
        if not desc:
            continue
        if status == "BUG_FIXED":
            retro.went_well.append(f"Bug fixed: {desc}")
        elif status == "BUG_FOUND":
            retro.went_poorly.append(f"Open bug: {desc}")
            retro.action_items.append(f"Triage and fix: {desc}")

    return retro


# ── Sprint planning ──────────────────────────────────────────────────────
@dataclass
class SprintPlan:
    """The result of allocating portfolio capacity into a new sprint."""

    sprint: AgileSprint
    committed: List[Initiative] = field(default_factory=list)
    deferred: List[Initiative] = field(default_factory=list)
    capacity: int = 0

    def to_markdown(self) -> str:
        """Render the sprint plan as markdown."""
        committed_points = sum(i.job_size for i in self.committed)
        lines = [
            f"## Sprint Plan — {self.sprint.name}",
            "",
            f"**Goal:** {self.sprint.goal or '_none_'}",
            f"**Capacity:** {self.capacity} pts · **Committed:** {committed_points} pts "
            f"· **Deferred:** {len(self.deferred)} initiatives",
            "",
            "### Committed (WSJF order)",
            "| Initiative | WSJF | Points |",
            "|------------|------|--------|",
        ]
        for init in self.committed:
            lines.append(f"| {init.title} | {init.wsjf:.2f} | {init.job_size} |")
        if not self.committed:
            lines.append("| _none_ | — | — |")
        lines.append("")
        lines.append("### Deferred")
        lines += _bullets([f"{i.title} (WSJF {i.wsjf:.2f})" for i in self.deferred])
        lines.append("")
        return "\n".join(lines)


def plan_next_sprint(
    portfolio_mgr: PortfolioManager,
    agile_mgr: AgileManager,
    *,
    name: str,
    goal: str = "",
    capacity: int,
) -> SprintPlan:
    """Allocate ``capacity`` of WSJF-ranked initiatives into a new sprint.

    Creates one :class:`UserStory` per committed initiative (sized by
    ``job_size``), links the sprint back to each initiative via
    :meth:`PortfolioManager.link_sprint`, and leaves the sprint in
    ``PLANNING`` for a human to start.
    """
    allocation = portfolio_mgr.allocate_capacity(capacity)
    sprint = agile_mgr.create_sprint(name, goal=goal)

    for initiative in allocation.committed:
        sprint.add_story(UserStory(
            story_id=f"{initiative.initiative_id}-story",
            title=initiative.title,
            description=initiative.rationale,
            story_points=initiative.job_size,
        ))
        portfolio_mgr.link_sprint(initiative.initiative_id, sprint.sprint_id)

    return SprintPlan(
        sprint=sprint,
        committed=allocation.committed,
        deferred=allocation.deferred,
        capacity=allocation.capacity,
    )

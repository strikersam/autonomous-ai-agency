"""Agentic Portfolio Management — initiative prioritisation, capacity allocation,
and roadmap planning on top of agile sprints.

Where ``agents/agile_sprints.py`` operates at the sprint/story level, this module
operates one level up: it manages a *portfolio* of initiatives (epics), ranks them
with WSJF (Weighted Shortest Job First — the SAFe prioritisation model), allocates
finite team capacity across them, lays them onto a Now/Next/Later roadmap, and rolls
delivery progress up from the agile sprints that implement them.

Design notes live in ``docs/context/agentic-portfolio.md``.

Issue: #233 (Agentic Agile) — portfolio extension
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional
from uuid import uuid4

if TYPE_CHECKING:  # avoid importing agile_sprints (and its deps) at runtime
    from agents.agile_sprints import AgileManager


class InitiativeStatus(Enum):
    """Lifecycle status of a portfolio initiative."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class RoadmapHorizon(Enum):
    """Roadmap placement for an initiative (Now/Next/Later planning)."""

    NOW = "now"
    NEXT = "next"
    LATER = "later"
    UNSCHEDULED = "unscheduled"


@dataclass
class Initiative:
    """A portfolio initiative (epic) prioritised via WSJF.

    WSJF (Weighted Shortest Job First) = Cost of Delay / Job Size, where
    Cost of Delay = business_value + time_criticality + risk_reduction.
    Higher WSJF should be scheduled sooner. All component scores use a relative
    scale (commonly a modified Fibonacci sequence: 1, 2, 3, 5, 8, 13, 20).
    """

    initiative_id: str
    title: str
    description: str = ""
    business_value: int = 1
    time_criticality: int = 1
    risk_reduction: int = 1
    job_size: int = 1
    status: InitiativeStatus = InitiativeStatus.PROPOSED
    owner: Optional[str] = None
    horizon: RoadmapHorizon = RoadmapHorizon.UNSCHEDULED
    sprint_ids: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for name in ("business_value", "time_criticality", "risk_reduction"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.job_size <= 0:
            raise ValueError("job_size must be a positive integer")

    @property
    def cost_of_delay(self) -> int:
        """Aggregate cost of delay (CoD) used as the WSJF numerator."""
        return self.business_value + self.time_criticality + self.risk_reduction

    @property
    def wsjf(self) -> float:
        """Weighted Shortest Job First score — higher schedules sooner."""
        return self.cost_of_delay / self.job_size

    def link_sprint(self, sprint_id: str) -> None:
        """Associate an agile sprint that delivers part of this initiative."""
        if sprint_id not in self.sprint_ids:
            self.sprint_ids.append(sprint_id)


@dataclass
class InitiativeProgress:
    """Delivery roll-up for a single initiative across its linked sprints."""

    initiative_id: str
    title: str
    total_points: int = 0
    completed_points: int = 0
    sprint_count: int = 0

    @property
    def completion_percentage(self) -> float:
        """Percentage of linked sprint points completed."""
        if self.total_points == 0:
            return 0.0
        return (self.completed_points / self.total_points) * 100.0


@dataclass
class CapacityAllocation:
    """Result of fitting initiatives into a fixed capacity by WSJF priority."""

    capacity: int
    committed: List[Initiative] = field(default_factory=list)
    deferred: List[Initiative] = field(default_factory=list)

    @property
    def committed_job_size(self) -> int:
        """Total job size of initiatives that fit within capacity."""
        return sum(i.job_size for i in self.committed)

    @property
    def remaining_capacity(self) -> int:
        """Unused capacity after committing the selected initiatives."""
        return max(0, self.capacity - self.committed_job_size)

    @property
    def utilization(self) -> float:
        """Fraction of capacity consumed (0.0–1.0)."""
        if self.capacity <= 0:
            return 0.0
        return min(1.0, self.committed_job_size / self.capacity)


@dataclass
class PortfolioMetrics:
    """Aggregate metrics across the whole portfolio."""

    total_initiatives: int = 0
    active_initiatives: int = 0
    total_cost_of_delay: int = 0
    total_job_size: int = 0
    average_wsjf: float = 0.0
    status_counts: Dict[str, int] = field(default_factory=dict)


@dataclass
class PortfolioManager:
    """Manages a portfolio of initiatives with WSJF prioritisation and roadmapping."""

    _initiatives: Dict[str, Initiative] = field(default_factory=dict)

    # ── CRUD ────────────────────────────────────────────────────────────────
    def add_initiative(
        self,
        title: str,
        *,
        business_value: int = 1,
        time_criticality: int = 1,
        risk_reduction: int = 1,
        job_size: int = 1,
        description: str = "",
        owner: Optional[str] = None,
    ) -> Initiative:
        """Create and register a new initiative, returning it."""
        initiative = Initiative(
            initiative_id=uuid4().hex[:12],
            title=title,
            description=description,
            business_value=business_value,
            time_criticality=time_criticality,
            risk_reduction=risk_reduction,
            job_size=job_size,
            owner=owner,
        )
        self._initiatives[initiative.initiative_id] = initiative
        return initiative

    def remove_initiative(self, initiative_id: str) -> None:
        """Remove an initiative from the portfolio."""
        if initiative_id not in self._initiatives:
            raise KeyError(f"Initiative '{initiative_id}' not found.")
        self._initiatives.pop(initiative_id)

    def get_initiative(self, initiative_id: str) -> Optional[Initiative]:
        """Look up an initiative by ID."""
        return self._initiatives.get(initiative_id)

    @property
    def initiative_count(self) -> int:
        """Number of initiatives in the portfolio."""
        return len(self._initiatives)

    # ── Prioritisation ──────────────────────────────────────────────────────
    def prioritized(self, *, include_done: bool = False) -> List[Initiative]:
        """Return initiatives sorted by WSJF (highest first).

        Cancelled initiatives are always excluded; completed initiatives are
        excluded unless ``include_done`` is True. Ties break on cost of delay
        (higher first) then job size (smaller first) for stable, sensible order.
        """
        candidates = [
            i for i in self._initiatives.values()
            if i.status != InitiativeStatus.CANCELLED
            and (include_done or i.status != InitiativeStatus.DONE)
        ]
        return sorted(
            candidates,
            key=lambda i: (i.wsjf, i.cost_of_delay, -i.job_size),
            reverse=True,
        )

    def allocate_capacity(self, capacity: int) -> CapacityAllocation:
        """Greedily fill ``capacity`` (in job-size units) by WSJF priority.

        Walks the WSJF-ranked backlog and commits each initiative that still
        fits in the remaining capacity, deferring the rest. This is the
        "what makes the next increment" decision.
        """
        allocation = CapacityAllocation(capacity=max(0, capacity))
        remaining = allocation.capacity
        for initiative in self.prioritized():
            if initiative.job_size <= remaining:
                allocation.committed.append(initiative)
                remaining -= initiative.job_size
            else:
                allocation.deferred.append(initiative)
        return allocation

    def plan_roadmap(self, capacity_per_horizon: int) -> Dict[str, List[Initiative]]:
        """Lay the prioritised backlog onto a Now/Next/Later roadmap.

        Each horizon holds up to ``capacity_per_horizon`` job-size units. Mutates
        each scheduled initiative's ``horizon`` so the placement is persistent.
        """
        horizons = [RoadmapHorizon.NOW, RoadmapHorizon.NEXT, RoadmapHorizon.LATER]
        roadmap: Dict[str, List[Initiative]] = {h.value: [] for h in horizons}
        roadmap[RoadmapHorizon.UNSCHEDULED.value] = []

        cap = max(0, capacity_per_horizon)
        remaining = {h: cap for h in horizons}
        for initiative in self.prioritized():
            placed = False
            for horizon in horizons:
                if cap > 0 and initiative.job_size <= remaining[horizon]:
                    initiative.horizon = horizon
                    roadmap[horizon.value].append(initiative)
                    remaining[horizon] -= initiative.job_size
                    placed = True
                    break
            if not placed:
                initiative.horizon = RoadmapHorizon.UNSCHEDULED
                roadmap[RoadmapHorizon.UNSCHEDULED.value].append(initiative)
        return roadmap

    # ── Sprint linkage & roll-up ────────────────────────────────────────────
    def link_sprint(self, initiative_id: str, sprint_id: str) -> None:
        """Link an agile sprint to an initiative it helps deliver."""
        initiative = self._initiatives.get(initiative_id)
        if initiative is None:
            raise KeyError(f"Initiative '{initiative_id}' not found.")
        initiative.link_sprint(sprint_id)

    def rollup_progress(self, agile_manager: "AgileManager") -> List[InitiativeProgress]:
        """Aggregate delivery progress per initiative from its linked sprints.

        Reads each linked sprint's total/completed points out of the supplied
        ``AgileManager`` so the portfolio reflects real agile execution.
        """
        progress: List[InitiativeProgress] = []
        for initiative in self._initiatives.values():
            total = completed = sprints = 0
            for sprint_id in initiative.sprint_ids:
                sprint = agile_manager.get_sprint(sprint_id)
                if sprint is None:
                    continue
                sprints += 1
                total += sprint.total_points
                completed += sprint.completed_points
            progress.append(
                InitiativeProgress(
                    initiative_id=initiative.initiative_id,
                    title=initiative.title,
                    total_points=total,
                    completed_points=completed,
                    sprint_count=sprints,
                )
            )
        return progress

    # ── Metrics ─────────────────────────────────────────────────────────────
    def metrics(self) -> PortfolioMetrics:
        """Compute aggregate portfolio metrics."""
        initiatives = list(self._initiatives.values())
        status_counts: Dict[str, int] = {}
        for initiative in initiatives:
            key = initiative.status.value
            status_counts[key] = status_counts.get(key, 0) + 1

        active = [
            i for i in initiatives
            if i.status in (InitiativeStatus.APPROVED, InitiativeStatus.IN_PROGRESS)
        ]
        ranked = self.prioritized()
        avg_wsjf = sum(i.wsjf for i in ranked) / len(ranked) if ranked else 0.0
        return PortfolioMetrics(
            total_initiatives=len(initiatives),
            active_initiatives=len(active),
            total_cost_of_delay=sum(i.cost_of_delay for i in initiatives),
            total_job_size=sum(i.job_size for i in initiatives),
            average_wsjf=avg_wsjf,
            status_counts=status_counts,
        )

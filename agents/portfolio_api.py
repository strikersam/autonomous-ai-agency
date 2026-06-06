"""Portfolio + Agile read API for the v5 dashboard.

Serves a single rich "board" payload (WSJF ranking, Now/Next/Later roadmap,
capacity allocation, portfolio metrics, and sprint-health roll-up) that powers
the v5 PortfolioScreen, plus add/remove/seed mutations.

State is an in-process singleton seeded with illustrative demo data so the
screen renders immediately after deploy. This is a presentation surface over
``agents/portfolio.py`` and ``agents/agile_sprints.py`` — not a system of record.

Imports are kept minimal (no ``agents`` package __init__, no rbac) so the router
can be unit-tested in isolation.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from agents.agile_sprints import AgileManager, StoryStatus, UserStory
from agents.portfolio import InitiativeStatus, PortfolioManager

log = logging.getLogger("qwen-proxy")

portfolio_router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# Default per-horizon roadmap capacity (job-size units ≈ one increment of work).
DEFAULT_HORIZON_CAPACITY = 13


# ── API I/O models ───────────────────────────────────────────────────────────
class InitiativeIn(BaseModel):
    """Request body for creating an initiative."""

    title: str = Field(..., min_length=1, max_length=140)
    business_value: int = Field(1, ge=0, le=100)
    time_criticality: int = Field(1, ge=0, le=100)
    risk_reduction: int = Field(1, ge=0, le=100)
    job_size: int = Field(1, ge=1, le=100)
    owner: Optional[str] = None
    status: Optional[str] = None


class InitiativeOut(BaseModel):
    """An initiative as rendered in the WSJF table / roadmap."""

    initiative_id: str
    title: str
    business_value: int
    time_criticality: int
    risk_reduction: int
    job_size: int
    cost_of_delay: int
    wsjf: float
    status: str
    horizon: str
    owner: Optional[str] = None
    sprint_ids: List[str] = Field(default_factory=list)


class SprintHealthOut(BaseModel):
    """Per-sprint health roll-up for the agile panel."""

    sprint_id: str
    name: str
    status: str
    health: str
    total_points: int
    completed_points: int
    completion_percentage: float
    scope_added: int
    days_remaining: float


class MetricsOut(BaseModel):
    """Aggregate portfolio metrics for the header strip."""

    total_initiatives: int
    active_initiatives: int
    total_cost_of_delay: int
    total_job_size: int
    average_wsjf: float
    status_counts: dict


class AllocationOut(BaseModel):
    """Capacity allocation summary for the current increment."""

    capacity: int
    committed: List[str]
    deferred: List[str]
    committed_job_size: int
    utilization: float


class BoardOut(BaseModel):
    """The full payload that powers the PortfolioScreen."""

    metrics: MetricsOut
    ranked: List[InitiativeOut]
    roadmap: dict
    allocation: AllocationOut
    sprints: List[SprintHealthOut]
    horizon_capacity: int


# ── In-process state ─────────────────────────────────────────────────────────
class PortfolioService:
    """Holds the portfolio + agile managers and builds the board payload."""

    def __init__(self) -> None:
        self.portfolio = PortfolioManager()
        self.agile = AgileManager()
        self._seeded = False

    # -- demo seed ------------------------------------------------------------
    def seed(self, *, force: bool = False) -> None:
        """Populate illustrative initiatives + linked sprints (idempotent)."""
        if self._seeded and not force:
            return
        if force:
            self.portfolio = PortfolioManager()
            self.agile = AgileManager()

        specs = [
            ("Checkout v2 — one-page flow", 13, 8, 5, 8, "in_progress"),
            ("Search relevance overhaul", 8, 5, 3, 13, "approved"),
            ("Mobile app push notifications", 5, 8, 2, 5, "approved"),
            ("GDPR data-retention compliance", 5, 5, 13, 8, "in_progress"),
            ("Self-serve analytics dashboard", 8, 3, 2, 13, "proposed"),
            ("Loyalty / rewards programme", 13, 2, 1, 21, "proposed"),
            ("Internationalisation (i18n)", 3, 2, 2, 8, "proposed"),
        ]
        first_id: Optional[str] = None
        for title, bv, tc, rr, js, status in specs:
            init = self.portfolio.add_initiative(
                title, business_value=bv, time_criticality=tc,
                risk_reduction=rr, job_size=js,
            )
            try:
                init.status = InitiativeStatus(status)
            except ValueError:
                pass
            if first_id is None:
                first_id = init.initiative_id

        # A live sprint delivering the top initiative, with partial progress.
        sprint = self.agile.create_sprint("Sprint 24", goal="Ship checkout v2 beta")
        sprint.add_story(UserStory(story_id="s1", title="Address autofill", story_points=5))
        sprint.add_story(UserStory(story_id="s2", title="Guest checkout", story_points=3))
        sprint.add_story(UserStory(story_id="s3", title="Payment retry UX", story_points=5))
        sprint.start(duration_days=14)
        sprint.get_story("s1").status = StoryStatus.DONE
        sprint.get_story("s2").status = StoryStatus.DONE
        # Mid-sprint scope creep
        sprint.add_story(UserStory(story_id="s4", title="Apple Pay", story_points=3))
        if first_id:
            self.portfolio.link_sprint(first_id, sprint.sprint_id)

        self._seeded = True

    # -- board ----------------------------------------------------------------
    def board(self, *, horizon_capacity: int = DEFAULT_HORIZON_CAPACITY) -> BoardOut:
        """Assemble the full board payload."""
        cap = max(1, horizon_capacity)
        ranked = self.portfolio.prioritized()
        roadmap_raw = self.portfolio.plan_roadmap(cap)
        alloc = self.portfolio.allocate_capacity(cap)
        m = self.portfolio.metrics()

        ranked_out = [self._initiative_out(i) for i in ranked]
        roadmap_out = {
            horizon: [self._initiative_out(i) for i in items]
            for horizon, items in roadmap_raw.items()
        }

        sprints_out: List[SprintHealthOut] = []
        for sprint in self.agile._sprints.values():  # noqa: SLF001 — internal demo store
            metrics = sprint.get_metrics()
            sprints_out.append(SprintHealthOut(
                sprint_id=sprint.sprint_id,
                name=sprint.name,
                status=sprint.status.value,
                health=metrics.health.value,
                total_points=metrics.total_points,
                completed_points=metrics.completed_points,
                completion_percentage=round(metrics.completion_percentage, 1),
                scope_added=sprint.scope_added,
                days_remaining=round(metrics.days_remaining, 1),
            ))

        return BoardOut(
            metrics=MetricsOut(
                total_initiatives=m.total_initiatives,
                active_initiatives=m.active_initiatives,
                total_cost_of_delay=m.total_cost_of_delay,
                total_job_size=m.total_job_size,
                average_wsjf=round(m.average_wsjf, 2),
                status_counts=m.status_counts,
            ),
            ranked=ranked_out,
            roadmap=roadmap_out,
            allocation=AllocationOut(
                capacity=alloc.capacity,
                committed=[i.title for i in alloc.committed],
                deferred=[i.title for i in alloc.deferred],
                committed_job_size=alloc.committed_job_size,
                utilization=round(alloc.utilization, 3),
            ),
            sprints=sprints_out,
            horizon_capacity=cap,
        )

    @staticmethod
    def _initiative_out(i) -> InitiativeOut:
        return InitiativeOut(
            initiative_id=i.initiative_id,
            title=i.title,
            business_value=i.business_value,
            time_criticality=i.time_criticality,
            risk_reduction=i.risk_reduction,
            job_size=i.job_size,
            cost_of_delay=i.cost_of_delay,
            wsjf=round(i.wsjf, 3),
            status=i.status.value,
            horizon=i.horizon.value,
            owner=i.owner,
            sprint_ids=list(i.sprint_ids),
        )


_SERVICE: Optional[PortfolioService] = None


def get_service() -> PortfolioService:
    """Return the process-wide PortfolioService, seeding demo data on first use."""
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = PortfolioService()
        _SERVICE.seed()
    return _SERVICE


# ── Routes ───────────────────────────────────────────────────────────────────
@portfolio_router.get("/board", response_model=BoardOut)
async def get_board(horizon_capacity: int = DEFAULT_HORIZON_CAPACITY) -> BoardOut:
    """Return the full portfolio board (ranking, roadmap, allocation, sprints)."""
    return get_service().board(horizon_capacity=horizon_capacity)


@portfolio_router.post("/initiatives", response_model=InitiativeOut, status_code=201)
async def add_initiative(body: InitiativeIn) -> InitiativeOut:
    """Add an initiative to the portfolio."""
    svc = get_service()
    init = svc.portfolio.add_initiative(
        body.title,
        business_value=body.business_value,
        time_criticality=body.time_criticality,
        risk_reduction=body.risk_reduction,
        job_size=body.job_size,
        owner=body.owner,
    )
    if body.status:
        try:
            init.status = InitiativeStatus(body.status)
        except ValueError:
            pass
    return PortfolioService._initiative_out(init)


@portfolio_router.delete("/initiatives/{initiative_id}", status_code=204)
async def remove_initiative(initiative_id: str) -> None:
    """Remove an initiative from the portfolio (no-op if it is already gone)."""
    svc = get_service()
    try:
        svc.portfolio.remove_initiative(initiative_id)
    except KeyError:
        pass


@portfolio_router.post("/seed", response_model=BoardOut)
async def reseed() -> BoardOut:
    """Reset the portfolio to the illustrative demo data and return the board."""
    svc = get_service()
    svc.seed(force=True)
    return svc.board()

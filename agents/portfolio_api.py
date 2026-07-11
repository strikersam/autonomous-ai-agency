"""Portfolio + Agile read API for the v5 dashboard.

Serves a single rich "board" payload (WSJF ranking, Now/Next/Later roadmap,
capacity allocation, portfolio metrics, sprint-health roll-up, and signal
provenance) that powers the v5 PortfolioScreen, plus refresh + manual mutations.

The board is assembled **autonomously** by `agents/portfolio_intelligence.py`
from real signals (roadmap backlog, bug log, open GitHub PRs/issues, research
trends) — not demo data. Results are cached and rebuilt on a TTL or on demand;
a scheduled GitHub Action (`portfolio-refresh.yml`) drives the regular cadence.

Imports are kept minimal (no rbac) so the router can be unit-tested in isolation.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from agents.agile_sprints import AgileManager
from agents.portfolio import InitiativeStatus, PortfolioManager
from agents.portfolio_intelligence import PortfolioIntelligence

log = logging.getLogger("qwen-proxy")

portfolio_router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# Default per-horizon roadmap capacity (job-size units ≈ one increment of work).
DEFAULT_HORIZON_CAPACITY = 13
# How long a built board stays fresh before the next /board rebuilds it.
CACHE_TTL_SECONDS = 30 * 60


# ── API I/O models ───────────────────────────────────────────────────────────
class InitiativeIn(BaseModel):
    """Request body for creating an initiative manually."""

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
    source: str
    rationale: str
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
    sources: Dict[str, int] = Field(default_factory=dict)
    generated_at: float = 0.0
    materialized_task_ids: List[str] = Field(default_factory=list)


# ── In-process state ─────────────────────────────────────────────────────────
class PortfolioService:
    """Builds and caches the autonomous portfolio board from live signals."""

    def __init__(self) -> None:
        self.intelligence = PortfolioIntelligence()
        self.agile = AgileManager()
        self.portfolio: PortfolioManager = PortfolioManager()
        self._built_at: float = 0.0
        self._sources: Dict[str, int] = {}

    # -- intelligence build ---------------------------------------------------
    def refresh(self, **kwargs) -> None:
        """Re-sweep all signals and rebuild the portfolio."""
        self.portfolio = self.intelligence.build(**kwargs)
        self._sources = dict(self.intelligence.last_build)
        self._built_at = time.time()

    def ensure_fresh(self) -> None:
        """Build on first use or when the cached board has expired."""
        if self._built_at == 0.0 or (time.time() - self._built_at) > CACHE_TTL_SECONDS:
            self.refresh()

    # -- board ----------------------------------------------------------------
    def board(self, *, horizon_capacity: int = DEFAULT_HORIZON_CAPACITY) -> BoardOut:
        """Assemble the full board payload from the current portfolio."""
        self.ensure_fresh()
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
        for sprint in self.agile._sprints.values():  # noqa: SLF001 — internal store
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
            sources=dict(self._sources),
            generated_at=self._built_at,
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
            source=i.source,
            rationale=i.rationale,
            owner=i.owner,
            sprint_ids=list(i.sprint_ids),
        )


_SERVICE: Optional[PortfolioService] = None


def get_service() -> PortfolioService:
    """Return the process-wide PortfolioService (built lazily on first use)."""
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = PortfolioService()
    return _SERVICE


# ── Routes ───────────────────────────────────────────────────────────────────
@portfolio_router.get("/board", response_model=BoardOut)
async def get_board(horizon_capacity: int = DEFAULT_HORIZON_CAPACITY) -> BoardOut:
    """Return the full portfolio board (auto-built from live signals, cached)."""
    return get_service().board(horizon_capacity=horizon_capacity)


@portfolio_router.post("/refresh", response_model=BoardOut)
async def refresh_board() -> BoardOut:
    """Force a re-sweep of all signals and return the rebuilt board.

    Also materializes committed portfolio initiatives into tasks (default ON,
    flag PORTFOLIO_MATERIALIZE_ENABLED to disable).
    """
    svc = get_service()
    svc.refresh()

    # Materialize committed initiatives into tasks
    materialized_ids: list[str] = []
    try:
        from tasks.portfolio_intake import materialize_committed
        from tasks.store import get_task_store
        store = get_task_store()
        created = await materialize_committed(svc.portfolio, store=store)
        materialized_ids = [t.task_id for t in created]
    except Exception as exc:
        import logging
        logging.getLogger("qwen-proxy").debug("portfolio materialize failed (non-fatal): %s", exc)

    board = svc.board()
    board.materialized_task_ids = materialized_ids
    return board


@portfolio_router.post("/materialize", response_model=BoardOut)
async def materialize_portfolio() -> BoardOut:
    """Manually trigger portfolio → task materialization and return the board.

    Same auth as /refresh (none — portfolio is read-only + system task creation).
    """
    svc = get_service()
    svc.ensure_fresh()

    materialized_ids: list[str] = []
    try:
        from tasks.portfolio_intake import materialize_committed
        from tasks.store import get_task_store
        store = get_task_store()
        created = await materialize_committed(svc.portfolio, store=store)
        materialized_ids = [t.task_id for t in created]
    except Exception as exc:
        import logging
        logging.getLogger("qwen-proxy").debug("portfolio materialize failed (non-fatal): %s", exc)

    board = svc.board()
    board.materialized_task_ids = materialized_ids
    return board


# Backward-compatible alias for the old demo-seed route — now rebuilds from signals.
@portfolio_router.post("/seed", response_model=BoardOut)
async def reseed() -> BoardOut:
    """Deprecated alias for /refresh (the board is no longer demo-seeded)."""
    return await refresh_board()


@portfolio_router.post("/initiatives", response_model=InitiativeOut, status_code=201)
async def add_initiative(body: InitiativeIn) -> InitiativeOut:
    """Add a manual initiative on top of the auto-generated portfolio."""
    svc = get_service()
    svc.ensure_fresh()
    init = svc.portfolio.add_initiative(
        body.title,
        business_value=body.business_value,
        time_criticality=body.time_criticality,
        risk_reduction=body.risk_reduction,
        job_size=body.job_size,
        owner=body.owner,
    )
    init.source = "manual"
    init.rationale = "Added by a user"
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
    svc.ensure_fresh()
    try:
        svc.portfolio.remove_initiative(initiative_id)
    except KeyError:
        pass

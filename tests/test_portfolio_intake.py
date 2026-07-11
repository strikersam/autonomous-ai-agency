"""tests/test_portfolio_intake.py — Portfolio initiative → Task materializer tests."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tasks.store import TaskStore
from tasks.portfolio_intake import (
    portfolio_source_id,
    map_initiative_to_task,
    materialize_committed,
)


@dataclass
class FakeInitiative:
    """Minimal stand-in for agents.portfolio.Initiative."""
    initiative_id: str = "abc123"
    title: str = "Test initiative"
    description: str = "A test"
    business_value: int = 5
    time_criticality: int = 3
    risk_reduction: int = 2
    job_size: int = 3
    status: object = None
    horizon: object = None
    source: str = "manual"
    rationale: str = ""

    def wsjf(self) -> float:
        return (self.business_value + self.time_criticality + self.risk_reduction) / max(self.job_size, 1)


class FakeStatus:
    PROPOSED = "proposed"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class FakeHorizon:
    NOW = "now"
    NEXT = "next"
    LATER = "later"
    UNSCHEDULED = "unscheduled"


class FakeAllocation:
    def __init__(self, committed, deferred=None):
        self.committed = committed
        self.deferred = deferred or []
        self.capacity = 20
        self.committed_job_size = sum(i.job_size for i in committed)
        self.utilization = self.committed_job_size / self.capacity


class FakePortfolio:
    def __init__(self, initiatives):
        self._initiatives = {i.initiative_id: i for i in initiatives}

    def allocate_capacity(self, capacity=20):
        return FakeAllocation(list(self._initiatives.values()))

    def prioritized(self):
        return sorted(self._initiatives.values(), key=lambda i: i.wsjf(), reverse=True)


@pytest.fixture
def store():
    return TaskStore()


@pytest.fixture
def initiatives():
    return [
        FakeInitiative(
            initiative_id="i1",
            title="Implement auth",
            source="signal",
            status=FakeStatus.PROPOSED,
            horizon=FakeHorizon.NOW,
            business_value=8,
            job_size=3,
        ),
        FakeInitiative(
            initiative_id="i2",
            title="Add CI pipeline",
            source="signal",
            status=FakeStatus.APPROVED,
            horizon=FakeHorizon.NOW,
            business_value=5,
            job_size=2,
        ),
    ]


def test_portfolio_source_id_stable_across_rebuilds(initiatives):
    """source_id is content-derived (source|title), stable across rebuilds."""
    i = initiatives[0]
    sid1 = portfolio_source_id(i)
    # Simulate a rebuild: new UUID, same content
    i2 = FakeInitiative(
        initiative_id="new_uuid",
        title=i.title,
        source=i.source,
    )
    sid2 = portfolio_source_id(i2)
    assert sid1 == sid2
    assert sid1.startswith("portfolio:")


def test_map_initiative_to_task(initiatives):
    """map_initiative_to_task creates a Task with correct fields."""
    i = initiatives[0]
    task = map_initiative_to_task(i)
    assert task.source == "portfolio"
    assert task.source_id == portfolio_source_id(i)
    assert task.task_type == "portfolio_initiative"
    assert task.pending_agent_run is True
    assert "portfolio" in task.tags
    assert "Implement auth" in task.title


@pytest.mark.asyncio
async def test_materialize_creates_tasks(store, initiatives):
    """materialize_committed creates tasks from committed initiatives."""
    portfolio = FakePortfolio(initiatives)
    created = await materialize_committed(portfolio, store=store)
    assert len(created) == 2
    for t in created:
        assert t.source == "portfolio"
        assert t.source_id.startswith("portfolio:")


@pytest.mark.asyncio
async def test_materialize_idempotent(store, initiatives):
    """Second materialize run creates zero new tasks."""
    portfolio = FakePortfolio(initiatives)
    created1 = await materialize_committed(portfolio, store=store)
    assert len(created1) == 2

    # Simulate rebuild: new UUIDs, same content
    rebuilt = FakePortfolio([
        FakeInitiative(
            initiative_id="new_" + i.initiative_id,
            title=i.title,
            source=i.source,
            status=i.status,
        )
        for i in initiatives
    ])
    created2 = await materialize_committed(rebuilt, store=store)
    assert len(created2) == 0  # All already tracked


@pytest.mark.asyncio
async def test_materialize_excludes_pr_source(store):
    """Initiatives with source='pr' are excluded (already in-flight work)."""
    initiatives = [
        FakeInitiative(title="PR work", source="pr", status=FakeStatus.PROPOSED),
        FakeInitiative(title="Real work", source="signal", status=FakeStatus.PROPOSED),
    ]
    portfolio = FakePortfolio(initiatives)
    created = await materialize_committed(portfolio, store=store)
    assert len(created) == 1
    assert "Real work" in created[0].title


@pytest.mark.asyncio
async def test_materialize_respects_cap(store):
    """Cap limits the number of tasks created."""
    initiatives = [
        FakeInitiative(
            initiative_id=f"cap-{i}",  # unique IDs so FakePortfolio doesn't collapse them
            title=f"Init {i}",
            source="signal",
            status=FakeStatus.PROPOSED,
            business_value=10 - i,
            job_size=1,
        )
        for i in range(10)
    ]
    portfolio = FakePortfolio(initiatives)
    created = await materialize_committed(portfolio, store=store, cap=3)
    assert len(created) == 3


@pytest.mark.asyncio
async def test_materialize_flag_off(store, initiatives, monkeypatch):
    """When PORTFOLIO_MATERIALIZE_ENABLED=false, no tasks are created."""
    # Patch the flag on the singleton directly — `settings` is bound at
    # module import time so env-var changes don't propagate without a
    # full re-import. Patching the attribute is the cleanest test seam.
    from packages.config import settings
    monkeypatch.setattr(settings, "portfolio_materialize_enabled", "false")

    portfolio = FakePortfolio(initiatives)
    created = await materialize_committed(portfolio, store=store)
    assert len(created) == 0

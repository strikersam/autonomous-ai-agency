"""The dispatcher sizes itself to the providers that can take work right now.

Starting more tasks than usable providers sends them into 429s, failover churn
and timeouts; with no usable provider every task fails as "No runtime
available". These tests pin that the dispatcher holds work instead.
"""
from __future__ import annotations

import asyncio

import pytest

from tasks import dispatcher as dispatcher_mod
from tasks.dispatcher import TaskDispatcher, provider_capacity
from tasks.models import Task


def _summary(monkeypatch, **summary) -> None:
    import services.brain_failover as bf

    monkeypatch.setattr(bf, "brain_availability_summary", lambda: summary)


def test_capacity_is_usable_providers_times_slots(monkeypatch):
    _summary(monkeypatch, total=5, usable=2)
    assert provider_capacity(1) == 2
    assert provider_capacity(3) == 6


def test_no_usable_provider_means_no_capacity(monkeypatch):
    _summary(monkeypatch, total=5, usable=0)
    assert provider_capacity(1) == 0


@pytest.mark.parametrize("summary", [{"total": 0, "usable": 0}, {"total": 0, "usable": 0, "error": "boom"}])
def test_unknown_capacity_does_not_limit(monkeypatch, summary):
    _summary(monkeypatch, **summary)
    assert provider_capacity(1) is None


def test_zero_slots_turns_sizing_off(monkeypatch):
    _summary(monkeypatch, total=5, usable=0)
    assert provider_capacity(0) is None


def test_registry_error_does_not_limit(monkeypatch):
    import services.brain_failover as bf

    def _raise():
        raise RuntimeError("registry down")

    monkeypatch.setattr(bf, "brain_availability_summary", _raise)
    assert provider_capacity(1) is None


class _Store:
    def __init__(self, tasks):
        self._tasks = tasks

    async def list_pending(self, *, limit: int = 50):
        return self._tasks[:limit]


class _Coordinator:
    def __init__(self):
        self.started: list[str] = []
        self.release = asyncio.Event()

    async def execute(self, task_id: str):
        self.started.append(task_id)
        await self.release.wait()


async def _poll(monkeypatch, capacity):
    monkeypatch.setattr(dispatcher_mod, "provider_capacity", lambda slots: capacity)

    async def _keep(store, tasks):
        return tasks

    import services.company_cleanup as cc
    monkeypatch.setattr(cc, "filter_orphaned_tasks", _keep)
    pending = [Task(owner_id="o@example.com", task_id=f"t{i}", title=f"T{i}") for i in range(5)]
    coord = _Coordinator()
    d = TaskDispatcher(workspace_root=".", store=_Store(pending), coordinator=coord, max_concurrency=5)
    await d._poll_and_execute()
    await asyncio.sleep(0)
    started = list(coord.started)
    coord.release.set()
    await d.drain()
    return started


@pytest.mark.asyncio
async def test_dispatcher_starts_only_what_providers_can_carry(monkeypatch):
    assert len(await _poll(monkeypatch, 2)) == 2


@pytest.mark.asyncio
async def test_dispatcher_holds_work_when_no_provider_is_usable(monkeypatch):
    assert await _poll(monkeypatch, 0) == []


@pytest.mark.asyncio
async def test_dispatcher_keeps_its_ceiling_when_capacity_is_higher_or_unknown(monkeypatch):
    assert len(await _poll(monkeypatch, 50)) == 5
    assert len(await _poll(monkeypatch, None)) == 5

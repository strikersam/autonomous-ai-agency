"""packages/runs/budget.py — one budget per run tree, charged by every descendant.

The budget lives on the ROOT run (``RunRecord.budget``: ``max_cost_usd``,
``max_tokens``, ``max_steps``; a missing key is unlimited). Spend is kept in
three integer counters on the root record (micro dollars, tokens, steps) that
``charge`` advances with the store's atomic increment, so concurrent children
can never lose an update. A charge that takes the root past a limit raises
``BudgetExhausted`` and cancels the whole tree. The charge that crosses the
line is kept (a call already paid for is recorded); every later charge raises
again, so no work continues once a limit is hit.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from packages.runs.models import RunRecord
from packages.runs.store import RunStore
from packages.runs.tree import cancel_tree

log = logging.getLogger("qwen-proxy")

ACTOR = "system:run-budget"
_MICRO = 1_000_000
# budget key -> (counter field on the root, scale applied to the charge)
_LIMITS = {"max_cost_usd": ("spent_micro_usd", _MICRO), "max_tokens": ("spent_tokens", 1),
           "max_steps": ("spent_steps", 1)}


class BudgetExhausted(RuntimeError):
    """A charge took the run tree past a limit of its root budget."""

    def __init__(self, root_run_id: str, limit: str, remaining: "Remaining") -> None:
        super().__init__(f"run {root_run_id}: budget exhausted ({limit})")
        self.root_run_id, self.limit, self.remaining = root_run_id, limit, remaining


@dataclass(frozen=True)
class Remaining:
    """What is left of each limit (``None`` for a limit the root does not set)."""

    cost_usd: float | None = None
    tokens: int | None = None
    steps: int | None = None


def _limit(budget: dict[str, Any], key: str) -> float | None:
    value = budget.get(key)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _remaining(root: RunRecord) -> Remaining:
    left: dict[str, float | None] = {}
    for key, (field, scale) in _LIMITS.items():
        cap = _limit(root.budget, key)
        left[key] = None if cap is None else cap - getattr(root, field) / scale
    return Remaining(cost_usd=left["max_cost_usd"],
                     tokens=None if left["max_tokens"] is None else int(left["max_tokens"]),
                     steps=None if left["max_steps"] is None else int(left["max_steps"]))


def exceeded(root: RunRecord) -> str | None:
    """The first budget key the root's spend is over, or ``None``."""
    for key, (field, scale) in _LIMITS.items():
        cap = _limit(root.budget, key)
        if cap is not None and getattr(root, field) / scale > cap:
            return key
    return None


async def root_of(store: RunStore, run_id: str) -> RunRecord:
    """The root run of *run_id*'s tree. ``KeyError`` for an unknown run."""
    run = await store.get(run_id)
    if run is None:
        raise KeyError(run_id)
    if run.root_run_id and run.root_run_id != run.run_id:
        root = await store.get(run.root_run_id)
        if root is not None:
            return root
    return run


async def _advance(store: RunStore, root_id: str, field: str, by: int) -> None:
    if by > 0 and await store.runs.increment(root_id, field, by) is None:
        raise KeyError(root_id)


async def charge(store: RunStore, run_id: str, *, cost_usd: float = 0.0, tokens: int = 0,
                 steps: int = 0, task_store: Any = None) -> Remaining:
    """Charge the ROOT of *run_id*'s tree and return what is left.

    Raises ``BudgetExhausted`` (after cancelling the tree) when a limit is crossed,
    and on every later charge to an exhausted tree.
    """
    root = await root_of(store, run_id)
    await _advance(store, root.run_id, "spent_micro_usd", round(max(cost_usd, 0.0) * _MICRO))
    await _advance(store, root.run_id, "spent_tokens", max(int(tokens), 0))
    await _advance(store, root.run_id, "spent_steps", max(int(steps), 0))
    root = await root_of(store, root.run_id)
    over = exceeded(root)
    if over is None:
        return _remaining(root)
    flagged = await cancel_tree(store, root.run_id, reason=f"budget exhausted ({over})",
                                actor=ACTOR, task_store=task_store)
    if flagged:
        await store.append_event(root.run_id, "budget_exhausted", {
            "limit": over, "charged_by": run_id, "cancelled_runs": len(flagged),
        }, actor=ACTOR)
        log.warning("run %s: budget exhausted (%s); cancelled %d runs", root.run_id, over,
                    len(flagged))
    raise BudgetExhausted(root.run_id, over, _remaining(root))


async def remaining(store: RunStore, run_id: str) -> Remaining:
    """What is left of the tree's budget, without charging."""
    return _remaining(await root_of(store, run_id))

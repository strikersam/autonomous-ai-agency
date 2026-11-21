"""packages/runs/side_effects.py — record an external side effect in the run's ledger.

``recorded_effect`` wraps one side effecting call (a git push, opening a PR) in
the plan section 2.3 protocol when the current task execution is bound to a
durable run (``task_binding.current_run``) and ``RUNS_LEDGER_ENABLED`` is on:

1. ``should_skip_replay``: the k-th call with these arguments already committed
   in an earlier attempt, so the body is skipped (``effect.skipped``) and the
   committed ``result_ref`` is handed back instead.
2. The lease is renewed and ``OperationLedger.begin`` records the operation as
   ``executing`` (raising ``FencedOut`` when the run is no longer ours).
3. The body runs under a hard ``op_timeout_s``; success commits the record with
   ``effect.result_ref``, an exception fails it (it may then run again), and a
   cancellation leaves it ``executing`` for the recovery tick to reconcile.

Without a bound run, or with the ledger disabled, it is a plain pass through.

``require_release_approval`` is the gate a release, deploy or merge must pass:
it refuses unless a durable approval (``packages/runs/approvals.py``) exists for
the same run, action hash and target. Nothing in ``agent/`` or ``tasks/`` releases
today (``agent/autonomy_gate.py`` forbids agent merges), so no call site is wired;
the first one that does must call it before the side effect.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

from agent.action_hash import action_hash
from packages.config import runs_settings
from packages.runs.models import OperationState
from packages.runs.approvals import RunApprovals
from packages.runs.operations import OperationLedger
from packages.runs.store import FencedOut, RunStore, get_run_store

log = logging.getLogger("qwen-proxy")


class ReleaseNotApproved(PermissionError):
    """A release, deploy or merge was attempted without a matching durable approval."""


async def require_release_approval(run_id: str, tool: str, args: Any, target: dict[str, Any],
                                   *, store: RunStore | None = None) -> str:
    """Return the action hash when this exact action is approved for the run, else raise.

    The hash covers *tool* and *args*; *target* is matched too, so an approval for
    one environment or branch never opens another. Raises ``ReleaseNotApproved``.
    """
    digest = action_hash(tool, args)
    approvals = RunApprovals(store or get_run_store())
    if not await approvals.check(run_id, digest, dict(target)):
        log.warning("run %s: %s blocked, no durable approval for this action", run_id, tool)
        raise ReleaseNotApproved(f"{tool} needs an approval for this exact action and target")
    return digest


async def gate_release_if_bound(tool: str, args: Any, target: dict[str, Any]) -> None:
    """Inside a durable run, require an approval for this exact release; outside, no-op.

    Existing gates (``RENDER_MCP_ALLOW_WRITES``, the agent merge ban) still apply first;
    this adds the per run, per action approval the reliability plan requires.
    """
    from packages.runs.task_binding import current_run

    binding = current_run.get()
    run_id = (binding.run_id or binding.watch_run_id) if binding is not None else None
    if run_id:
        await require_release_approval(run_id, tool, args, target)


@dataclass
class Effect:
    """Handle the body of ``recorded_effect`` uses: skip flag in, result reference out."""

    skipped: bool = False
    result_ref: str | None = None


def _bound_run() -> Any | None:
    from packages.runs.task_binding import current_run

    binding = current_run.get()
    if binding is None or not binding.recording or binding.fenced:
        return None
    return binding if runs_settings.runs_ledger_enabled() else None


def task_branch_name() -> str:
    """``agent/task-<task_id>`` for a bound task (stable across attempts), else a fresh one."""
    from packages.runs.task_binding import current_run

    binding = current_run.get()
    task_id = getattr(binding, "task_id", None)
    if task_id:
        return f"agent/task-{task_id}"
    return f"agent/task-{uuid.uuid4().hex[:8]}"


async def checkout_branch(ws: Any, branch: str, start: str) -> None:
    """Create *branch* at *start*; a branch left by an earlier attempt is moved there.

    Local only (``git checkout -B``): the push that follows is never forced, so a
    remote branch that diverged rejects it instead of being overwritten.
    """
    try:
        await ws.create_branch(branch, start)
    except RuntimeError:
        rc, _, err = await ws._run("git", "checkout", "-B", branch, start)
        if rc != 0:
            raise RuntimeError(f"git checkout -B failed: {err.strip()}") from None


async def push_branch(ws: Any, branch: str) -> str:
    """Push *branch* and return the branch actually pushed. Never forces.

    A stable task branch can already exist remotely with other history (an earlier
    attempt, or an earlier life of the same task id). The remote rejects that push,
    so the work goes to a fresh sibling branch instead of being lost.
    """
    try:
        await ws.push(branch=branch, agent_initiated=True)
        return branch
    except Exception as exc:  # noqa: BLE001 - any refusal gets one fresh branch
        if not branch.startswith("agent/task-"):
            raise
        sibling = f"{branch}-{uuid.uuid4().hex[:8]}"
        log.warning("push to %s refused (%s); retrying on %s", branch, type(exc).__name__, sibling)
        rc, _, err = await ws._run("git", "checkout", "-b", sibling)
        if rc != 0:
            raise RuntimeError(f"git checkout -b failed: {err.strip()}") from exc
        await ws.push(branch=sibling, agent_initiated=True)
        return sibling


async def _committed_ref(ledger: OperationLedger, run_id: str, tool: str, args: Any) -> str | None:
    digest = action_hash(tool, args)
    for op in reversed(await ledger.list(run_id)):
        if op.action_hash == digest and op.state is OperationState.COMMITTED:
            return op.result_ref
    return None


async def _begin(binding: Any, ledger: OperationLedger, tool: str, args: Any,
                 target: dict[str, Any], op_timeout_s: float) -> Any:
    ttl = float(runs_settings.lease_ttl_s())
    if not await binding.lease.renew(binding.lease_key, binding.holder, binding.token, ttl):
        binding.fenced = True
        raise FencedOut(f"task {binding.task_id}: run lease lost before {tool}")
    return await ledger.begin(binding.run_id, tool, args, target, binding.token, op_timeout_s,
                              lease_remaining_s=ttl)


@asynccontextmanager
async def recorded_effect(tool: str, args: Any, target: dict[str, Any] | None,
                          op_timeout_s: float) -> AsyncIterator[Effect]:
    """Run the body as one recorded side effect (see the module docstring)."""
    effect = Effect()
    binding = _bound_run()
    if binding is None:
        yield effect
        return
    ledger = OperationLedger(binding.store)
    # begin() needs more lease left than the timeout; a short RUNS_LEASE_TTL_SEC
    # shortens the effect's timeout rather than refusing every effect.
    op_timeout_s = min(op_timeout_s, 0.9 * float(runs_settings.lease_ttl_s()))
    key = action_hash(tool, args)
    binding.occurrences[key] = occurrence = binding.occurrences.get(key, 0) + 1
    if await ledger.should_skip_replay(binding.run_id, tool, args, occurrence):
        effect.skipped = True
        effect.result_ref = await _committed_ref(ledger, binding.run_id, tool, args)
        log.info("run %s: %s already done in an earlier attempt; not repeating it",
                 binding.run_id, tool)
        yield effect
        return
    op = await _begin(binding, ledger, tool, args, dict(target or {}), op_timeout_s)
    if op.op_deadline is not None and time.time() >= op.op_deadline:
        await ledger.fail(op, "operation deadline passed before the effect started")
        raise FencedOut(f"run {binding.run_id}: {tool} deadline passed before it started")
    try:
        async with asyncio.timeout(op_timeout_s):
            yield effect
    except Exception as exc:
        await ledger.fail(op, f"{type(exc).__name__}: {exc}")
        raise
    await ledger.commit(op, effect.result_ref)

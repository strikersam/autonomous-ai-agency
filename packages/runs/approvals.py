"""packages/runs/approvals.py — durable approvals for run actions (plan decision D2).

An approval is bound to ONE run, ONE action (its ``action_hash``, from
``agent.action_hash``) and ONE target. ``check`` answers yes only for an
approved record that matches all three and has not passed its wall clock expiry,
so changing the arguments or the target of an action invalidates its approval.

Records live in the ``run_approvals`` collection of the run store's backend, so a
new process (or a new store over the same backend) sees them: a recovered run
that waits on an approval waits on the same record. Expiry denies: a pending
request past its expiry is marked ``expired`` and can no longer be approved.
Deciding needs a named resolver. ``check`` re-tests the expiry on every call, so
an approval granted at the very edge of its window still cannot authorise anything late. The in process ``ApprovalStore`` in
``packages/governance`` is unchanged and still serves callers that use no run.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel

from packages.config import runs_settings
from packages.runs.redaction import redact_text, redact_value
from packages.runs.store import RunStore

log = logging.getLogger("qwen-proxy")

RUN_APPROVALS = "run_approvals"
DEFAULT_TTL_S = 3600.0
MAX_TTL_S = 7 * 24 * 3600.0


class ApprovalState(str, Enum):
    """Where an approval is. Only ``approved`` before its expiry authorises anything."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class ApprovalError(ValueError):
    """An approval request or decision was invalid or arrived too late."""


class ApprovalRecord(BaseModel):
    """One stored approval (the target is shown redacted)."""

    approval_id: str
    run_id: str
    action_hash: str
    target: dict[str, Any]
    reason: str
    state: ApprovalState
    requested_at: float
    expires_at: float
    resolver: str | None = None
    resolved_at: float | None = None
    note: str | None = None


def target_digest(target: dict[str, Any]) -> str:
    """Stable digest of a target (key order independent); the raw target is not stored."""
    canonical = json.dumps(target, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _record(doc: dict[str, Any]) -> ApprovalRecord:
    return ApprovalRecord.model_validate({k: v for k, v in doc.items() if k in ApprovalRecord.model_fields})


class RunApprovals:
    """Durable approvals over the run store's backend."""

    def __init__(self, runs: RunStore) -> None:
        self._runs = runs
        self._table = runs.table(RUN_APPROVALS)

    async def request(self, run_id: str, action_hash: str, target: dict[str, Any], reason: str,
                      ttl_s: float = DEFAULT_TTL_S) -> str:
        """Open a pending approval and return its id. ``KeyError`` for an unknown run."""
        if not action_hash:
            raise ApprovalError("an approval needs an action hash")
        if await self._runs.get(run_id) is None:
            raise KeyError(run_id)
        now = time.time()
        approval_id = f"apr_{uuid.uuid4().hex}"
        doc = {
            "approval_id": approval_id, "run_id": run_id, "action_hash": action_hash,
            "target": redact_value(dict(target)), "target_digest": target_digest(target),
            "reason": redact_text(reason)[:2000], "state": ApprovalState.PENDING.value,
            "requested_at": now, "expires_at": now + min(max(float(ttl_s), 1.0), MAX_TTL_S),
        }
        await self._table.insert_if_absent(approval_id, doc)
        await self._runs.append_event(run_id, "approval_requested", {
            "approval_id": approval_id, "action_hash": action_hash, "reason": doc["reason"]})
        return approval_id

    async def get(self, approval_id: str) -> ApprovalRecord | None:
        """The approval, with an overdue pending one reported (and stored) as expired."""
        doc = await self._table.get(approval_id)
        if doc is None:
            return None
        if doc["state"] == ApprovalState.PENDING.value and time.time() >= float(doc["expires_at"]):
            await self._table.compare_and_set(approval_id, {"state": "pending"}, {"state": "expired"})
            doc["state"] = ApprovalState.EXPIRED.value
        return _record(doc)

    async def decide(self, approval_id: str, approve: bool, resolver: str,
                     note: str | None = None) -> ApprovalRecord:
        """Approve or deny a pending approval as the named *resolver*.

        Raises ``KeyError`` (unknown id) or ``ApprovalError`` (no resolver, already
        decided, or expired: an expired request cannot be approved).
        """
        if not resolver or not resolver.strip():
            raise ApprovalError("a named resolver is required")
        current = await self.get(approval_id)
        if current is None:
            raise KeyError(approval_id)
        if current.state is not ApprovalState.PENDING:
            raise ApprovalError(f"approval is already {current.state.value}")
        state = ApprovalState.APPROVED if approve else ApprovalState.DENIED
        now = time.time()
        if now >= current.expires_at:
            raise ApprovalError("approval has expired")
        applied = await self._table.compare_and_set(
            approval_id, {"state": "pending"},
            {"state": state.value, "resolver": redact_text(resolver)[:200], "resolved_at": now,
             "note": redact_text(note)[:1000] if note else None})
        if not applied:
            raise ApprovalError("approval is no longer pending")
        if time.time() >= current.expires_at:  # expired while the decision was written
            await self._table.compare_and_set(
                approval_id, {"state": state.value, "resolved_at": now}, {"state": "expired"})
            raise ApprovalError("approval has expired")
        await self._runs.append_event(current.run_id, "approval_decided", {
            "approval_id": approval_id, "state": state.value}, actor=redact_text(resolver))
        decided = await self.get(approval_id)
        if decided is None:  # the record vanished between write and read
            raise KeyError(approval_id)
        return decided

    async def check(self, run_id: str, action_hash: str, target: dict[str, Any]) -> bool:
        """True only for an unexpired approved record of this run, action hash AND target."""
        if not runs_settings.durable_approvals_enabled():
            return False
        digest, now = target_digest(target), time.time()
        docs = await self._table.find({"run_id": run_id, "state": ApprovalState.APPROVED.value})
        return any(d.get("action_hash") == action_hash and d.get("target_digest") == digest
                   and now < float(d.get("expires_at") or 0) for d in docs)

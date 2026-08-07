"""packages/governance/approvals.py — human-in-the-loop for high-risk actions.

The policy engine can return :attr:`~packages.governance.policy.Decision.REQUIRE_APPROVAL`,
which is only meaningful if something can actually hold the action and ask a
human. This module is that hold.

Design constraints that shaped it:

**Waiting must be bounded.** An agent blocked forever on an approval nobody
will ever see is indistinguishable from a hang, and this repo has a live
history of exactly that failure mode — the 600s execution timeout and the
`phase_start` with no `phase_end` described in the changelog. Every request
carries a TTL and resolves to ``expired`` on its own.

**Timeout denies, it does not allow.** An approval gate that opens when
ignored is theatre. The one exception is explicit: ``auto_approve`` is a
configured, audited, off-by-default escape hatch for local development, and
its use is recorded on the request as ``resolved_by="auto-approve"`` so an
audit reader can tell a human decision from a configured one.

**Approving is a decision by a named person.** ``resolved_by`` is required.
An approval trail whose entries say "approved" without saying by whom answers
none of the questions an auditor asks.

Storage is in-process and bounded. Approvals are short-lived by nature (the
agent waiting on one dies at its own timeout anyway), so durability across a
restart would be a false promise: after a restart there is no longer an agent
waiting to be unblocked. A restart therefore expires everything pending, which
is the fail-closed outcome.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

log = logging.getLogger("governance.approvals")


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    """One high-risk action awaiting a human decision."""

    approval_id: str
    agent_id: str
    owner: str
    session_id: str
    surface: str
    action: str
    reason: str
    rule_id: str
    arguments: dict[str, Any] = field(default_factory=dict)
    task_id: str | None = None
    repo: str | None = None
    branch: str | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: float = field(default_factory=time.monotonic)
    created_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ttl_s: float = 300.0
    resolved_by: str | None = None
    resolved_note: str | None = None
    resolved_iso: str | None = None

    @property
    def expired(self) -> bool:
        return (
            self.status is ApprovalStatus.PENDING
            and (time.monotonic() - self.created_at) >= self.ttl_s
        )

    @property
    def seconds_remaining(self) -> float:
        return max(0.0, self.ttl_s - (time.monotonic() - self.created_at))

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "agent_id": self.agent_id,
            "owner": self.owner,
            "session_id": self.session_id,
            "surface": self.surface,
            "action": self.action,
            "reason": self.reason,
            "rule_id": self.rule_id,
            "arguments": self.arguments,
            "task_id": self.task_id,
            "repo": self.repo,
            "branch": self.branch,
            "status": self.status.value,
            "created_at": self.created_iso,
            "ttl_s": self.ttl_s,
            "seconds_remaining": round(self.seconds_remaining, 1),
            "resolved_by": self.resolved_by,
            "resolved_note": self.resolved_note,
            "resolved_at": self.resolved_iso,
        }


class ApprovalStore:
    """Bounded, in-process store of approval requests.

    Uses a :class:`threading.Lock` rather than an asyncio lock because
    requests are created from async agent code but resolved from HTTP
    handlers, Telegram callbacks, and tests — a mix of loops and threads. The
    per-request :class:`asyncio.Event` that unblocks a waiter is created
    lazily on the waiting loop, which is the only place it is awaited.
    """

    def __init__(self, capacity: int = 200) -> None:
        self._requests: dict[str, ApprovalRequest] = {}
        self._events: dict[str, asyncio.Event] = {}
        self._lock = threading.Lock()
        self._capacity = max(1, capacity)
        self._counter = 0

    def create(
        self,
        *,
        agent_id: str,
        surface: str,
        action: str,
        reason: str,
        rule_id: str,
        owner: str = "system",
        session_id: str = "",
        arguments: dict[str, Any] | None = None,
        task_id: str | None = None,
        repo: str | None = None,
        branch: str | None = None,
        ttl_s: float = 300.0,
    ) -> ApprovalRequest:
        """Register a pending approval and return it.

        Arguments are scrubbed on the way in: an approval request is rendered
        in a dashboard and possibly a Telegram message, both of which are
        further from the process than the audit log is.
        """
        from packages.governance.audit import scrub

        with self._lock:
            self._counter += 1
            approval_id = f"apr_{int(time.time()):x}_{self._counter:04d}"
            request = ApprovalRequest(
                approval_id=approval_id,
                agent_id=agent_id,
                owner=owner,
                session_id=session_id,
                surface=surface,
                action=action,
                reason=reason,
                rule_id=rule_id,
                arguments=scrub(arguments or {}),
                task_id=task_id,
                repo=repo,
                branch=branch,
                ttl_s=max(1.0, float(ttl_s)),
            )
            self._requests[approval_id] = request
            self._evict_locked()
        log.info(
            "Approval requested: %s agent=%s surface=%s action=%s rule=%s",
            approval_id, agent_id, surface, action, rule_id,
        )
        return request

    def _evict_locked(self) -> None:
        """Drop the oldest resolved requests once over capacity.

        Resolved requests go first so a flood of decided approvals can never
        push out a request an agent is still blocked on.
        """
        if len(self._requests) <= self._capacity:
            return
        resolved = [
            (r.created_at, k) for k, r in self._requests.items()
            if r.status is not ApprovalStatus.PENDING
        ]
        for _, key in sorted(resolved):
            if len(self._requests) <= self._capacity:
                return
            self._requests.pop(key, None)
            self._events.pop(key, None)
        pending = sorted((r.created_at, k) for k, r in self._requests.items())
        for _, key in pending:
            if len(self._requests) <= self._capacity:
                return
            self._requests.pop(key, None)
            self._events.pop(key, None)

    def get(self, approval_id: str) -> ApprovalRequest | None:
        with self._lock:
            request = self._requests.get(approval_id)
        if request and request.expired:
            self._mark_expired(request)
        return request

    def _mark_expired(self, request: ApprovalRequest) -> None:
        with self._lock:
            if request.status is ApprovalStatus.PENDING:
                request.status = ApprovalStatus.EXPIRED
                request.resolved_by = "timeout"
                request.resolved_note = f"no decision within {request.ttl_s:.0f}s"
                request.resolved_iso = datetime.now(timezone.utc).isoformat()
            event = self._events.get(request.approval_id)
        if event is not None:
            _set_event_threadsafe(event)

    def resolve(
        self,
        approval_id: str,
        *,
        approved: bool,
        resolved_by: str,
        note: str | None = None,
    ) -> ApprovalRequest | None:
        """Approve or deny a pending request.

        Returns ``None`` for an unknown id. A request that is already resolved
        is returned unchanged — the first decision wins, so a double-click or
        a retried webhook cannot flip an approval into a denial.
        """
        with self._lock:
            request = self._requests.get(approval_id)
            if request is None:
                return None
            if request.status is not ApprovalStatus.PENDING:
                return request
            request.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.DENIED
            request.resolved_by = resolved_by or "unknown"
            request.resolved_note = note
            request.resolved_iso = datetime.now(timezone.utc).isoformat()
            event = self._events.get(approval_id)
        log.info(
            "Approval %s %s by %s", approval_id, request.status.value, request.resolved_by
        )
        if event is not None:
            _set_event_threadsafe(event)
        return request

    async def wait(self, approval_id: str, poll_s: float = 0.25) -> ApprovalStatus:
        """Block until *approval_id* is resolved or its TTL expires.

        Combines an event wait with a bounded overall deadline so a request
        that expires without anyone touching it still wakes its waiter. The
        poll interval only bounds how quickly expiry is noticed; a real
        decision wakes the waiter immediately via the event.
        """
        with self._lock:
            request = self._requests.get(approval_id)
            if request is None:
                return ApprovalStatus.DENIED
            event = self._events.get(approval_id)
            if event is None:
                event = asyncio.Event()
                self._events[approval_id] = event

        deadline = time.monotonic() + request.ttl_s
        while True:
            if request.status is not ApprovalStatus.PENDING:
                return request.status
            if time.monotonic() >= deadline:
                self._mark_expired(request)
                return request.status
            try:
                await asyncio.wait_for(event.wait(), timeout=poll_s)
            except asyncio.TimeoutError:
                continue
            except Exception as exc:  # noqa: BLE001 - degrade to polling
                log.debug("Approval wait fell back to polling: %s", exc)
                await asyncio.sleep(poll_s)

    def pending(self) -> list[dict[str, Any]]:
        """Pending requests, oldest first — the order a reviewer should work."""
        with self._lock:
            requests = list(self._requests.values())
        for request in requests:
            if request.expired:
                self._mark_expired(request)
        return [
            r.to_dict() for r in sorted(requests, key=lambda r: r.created_at)
            if r.status is ApprovalStatus.PENDING
        ]

    def all(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            requests = list(self._requests.values())
        newest = sorted(requests, key=lambda r: r.created_at, reverse=True)
        return [r.to_dict() for r in newest[: max(1, limit)]]

    def clear(self) -> None:
        with self._lock:
            self._requests.clear()
            self._events.clear()


def _set_event_threadsafe(event: asyncio.Event) -> None:
    """Set *event* from whichever thread resolved the approval.

    The waiter awaits on its own loop; the resolver is usually an HTTP handler
    on a different one (or a plain thread). ``call_soon_threadsafe`` is the
    only correct way across that boundary, and the direct ``set()`` fallback
    covers the same-thread case where no loop is running yet.
    """
    try:
        loop = event._loop  # type: ignore[attr-defined]
    except AttributeError:
        loop = None
    if loop is not None and loop.is_running():
        try:
            loop.call_soon_threadsafe(event.set)
            return
        except RuntimeError:  # pragma: no cover - loop closed mid-resolve
            pass
    try:
        event.set()
    except Exception as exc:  # noqa: BLE001 - waiter falls back to its poll loop
        log.debug("Could not set approval event: %s", exc)


_STORE: ApprovalStore | None = None
_STORE_LOCK = threading.Lock()


def get_approval_store() -> ApprovalStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = ApprovalStore()
        return _STORE


def reset_approval_store(store: ApprovalStore | None = None) -> None:
    """Replace the process-wide store. Tests only."""
    global _STORE
    with _STORE_LOCK:
        _STORE = store

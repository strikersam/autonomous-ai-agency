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
import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Literal

from packages.storage import state_persistence as _persist

log = logging.getLogger("governance.approvals")

GRANTS_COLLECTION = "governance_grants"
_DB_TIMEOUT_S = 2.0  # a slow DB reads as "no grant", never as a hung approval
_MAX_REVOKED = 1000  # revoked ids remembered so a late async write cannot resurrect one


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
        (or past its TTL) is returned unchanged — the first decision wins, so
        a double-click or a retried webhook cannot flip an approval into a
        denial, and an expired request can no longer be approved.
        """
        request, _ = self.resolve_ex(
            approval_id, approved=approved, resolved_by=resolved_by, note=note
        )
        return request

    def resolve_ex(
        self,
        approval_id: str,
        *,
        approved: bool,
        resolved_by: str,
        note: str | None = None,
    ) -> tuple[ApprovalRequest | None, bool]:
        """Like :meth:`resolve`, also reporting whether THIS call decided it.

        The flag is what lets a caller issue a follow-on effect (a sticky
        grant) only for the call that really performed PENDING -> decided.
        """
        with self._lock:
            request = self._requests.get(approval_id)
        if request is not None and request.expired:
            self._mark_expired(request)
        with self._lock:
            request = self._requests.get(approval_id)
            if request is None:
                return None, False
            if request.status is not ApprovalStatus.PENDING:
                return request, False
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
        return request, True

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


GrantScope = Literal["once", "action", "session"]

# Surfaces a sticky grant can never cover. A credential access is the one
# action where "the operator said yes a minute ago" is not a safe proxy for
# "the operator says yes now".
DEFAULT_GRANT_EXCLUDED_SURFACES: frozenset[str] = frozenset({"credential"})
_ANONYMOUS_SESSIONS = frozenset({"", "anonymous"})


def _is_anonymous(session_id: str) -> bool:
    """True for an empty or anonymous-sentinel id (case-insensitive).

    Surrounding whitespace is stripped first: identities are system-generated,
    so padding is not an attacker-controlled way to reach another session.
    """
    return str(session_id or "").strip().lower() in _ANONYMOUS_SESSIONS


@dataclass
class SessionGrant:
    """A standing approval for one agent session, bounded by a TTL."""

    grant_id: str
    session_id: str
    scope: str
    surface: str
    action: str
    granted_by: str
    ttl_s: float
    agent_id: str = ""
    owner: str = ""
    source_approval_id: str = ""
    created_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_at: float = field(default_factory=time.monotonic)

    @property
    def expired(self) -> bool:
        return (time.monotonic() - self.created_at) >= self.ttl_s

    def covers(self, surface: str, action: str) -> bool:
        if self.scope == "session":
            return True
        return self.scope == "action" and self.surface == surface and self.action == action

    def matches(
        self, session_id: str, surface: str, action: str, agent_id: str | None, owner: str | None
    ) -> bool:
        """Same session, covers the call, and any agent/owner binding agrees."""
        if self.session_id != session_id or not self.covers(surface, action):
            return False
        if self.agent_id and self.agent_id != agent_id:
            return False
        return not (self.owner and self.owner != owner)

    def to_doc(self) -> dict[str, Any]:
        """The persisted form: wall-clock ``expires_at`` drives the TTL index."""
        doc = {k: getattr(self, k) for k in (
            "session_id", "scope", "surface", "action", "granted_by", "ttl_s",
            "agent_id", "owner", "source_approval_id")}
        doc.update(
            _id=self.grant_id, created_iso=self.created_iso,
            expires_at=datetime.now(timezone.utc) + timedelta(
                seconds=max(0.0, self.ttl_s - (time.monotonic() - self.created_at))),
        )
        return doc

    @classmethod
    def from_doc(
        cls, doc: dict[str, Any],
        excluded: frozenset[str] = DEFAULT_GRANT_EXCLUDED_SURFACES,
    ) -> SessionGrant | None:
        """Rebuild a grant from its persisted form; ``None`` if expired or invalid.

        Re-applies the issue-time rules, so a forged or corrupt row can never
        be wider than :meth:`GrantStore.grant` would have allowed.
        """
        try:
            if doc.get("scope") not in ("action", "session") or _is_anonymous(str(doc.get("session_id"))):
                return None
            if str(doc.get("surface")) in excluded or not doc.get("granted_by"):
                return None
            if doc.get("agent_id") == "agent:unknown" and doc.get("owner") == "system":
                return None
            expires = doc["expires_at"]
            if expires.tzinfo is None:  # Motor returns naive UTC datetimes
                expires = expires.replace(tzinfo=timezone.utc)
            remaining = (expires - datetime.now(timezone.utc)).total_seconds()
            remaining = min(remaining, float(doc.get("ttl_s") or remaining))  # never outlive its own TTL
            if remaining <= 0:
                return None
            return cls(
                grant_id=str(doc["_id"]), session_id=str(doc["session_id"]),
                scope=str(doc["scope"]), surface=str(doc["surface"]), action=str(doc["action"]),
                granted_by=str(doc["granted_by"]), ttl_s=remaining,
                agent_id=str(doc.get("agent_id") or ""), owner=str(doc.get("owner") or ""),
                source_approval_id=str(doc.get("source_approval_id") or ""),
                created_iso=str(doc.get("created_iso") or ""),
            )
        except Exception as exc:  # noqa: BLE001 - a bad row is no grant
            log.warning("Ignoring malformed persisted grant: %s", exc)
            return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "grant_id": self.grant_id,
            "session_id": self.session_id,
            "scope": self.scope,
            "surface": self.surface if self.scope == "action" else None,
            "action": self.action if self.scope == "action" else None,
            "granted_by": self.granted_by,
            "agent_id": self.agent_id,
            "owner": self.owner,
            "source_approval_id": self.source_approval_id,
            "created_at": self.created_iso,
            "ttl_s": self.ttl_s,
            "seconds_remaining": round(max(0.0, self.ttl_s - (time.monotonic() - self.created_at)), 1),
        }


class GrantStore:
    """Bounded, in-process store of session approval grants.

    Grants only ever short-circuit a REQUIRE_APPROVAL verdict; the enforcement
    gate never consults them for DENY. Memory is the hot-path cache; issue and
    revoke are mirrored to the ``governance_grants`` collection (TTL on
    ``expires_at``) when ``AGENCY_STATE_PERSISTENCE_ENABLED`` is on, and
    :meth:`has_grant_async` also finds grants issued by another worker. Every
    lookup failure, DB errors included, means "no grant".
    """

    def __init__(
        self,
        capacity: int = 500,
        excluded_surfaces: frozenset[str] = DEFAULT_GRANT_EXCLUDED_SURFACES,
    ) -> None:
        self._grants: dict[str, SessionGrant] = {}
        self._lock = threading.Lock()
        self._capacity = max(1, capacity)
        self._excluded = frozenset(excluded_surfaces)
        self._counter = 0
        self._persisted: set[str] = set()  # grant ids whose DB write has landed
        self._revoked: OrderedDict[str, None] = OrderedDict()

    def grant(
        self,
        session_id: str,
        scope: str,
        surface: str,
        action: str,
        granted_by: str,
        ttl_s: float,
        *,
        agent_id: str = "",
        owner: str = "",
        source_approval_id: str = "",
    ) -> SessionGrant | None:
        """Create a grant, or return ``None`` when none may be issued.

        Refused for scope ``once``, an empty/anonymous session (shared by
        every caller without an identity, so a grant would leak across
        unrelated agents), excluded surfaces, and the fully generic
        ``agent:unknown`` + ``system`` identity. When ``agent_id`` / ``owner``
        are given the grant is bound to them as well as the session.
        """
        session_id = str(session_id or "").strip()
        if scope not in ("action", "session") or _is_anonymous(session_id):
            return None
        if agent_id == "agent:unknown" and owner == "system":
            return None
        if str(surface) in self._excluded or not granted_by:
            return None
        with self._lock:
            self._prune_locked()
            self._counter += 1
            grant_id = f"gnt_{secrets.token_hex(8)}"  # random: per-process counters collide across workers
            grant = SessionGrant(
                grant_id=grant_id, session_id=session_id, scope=scope,
                surface=str(surface), action=str(action), granted_by=granted_by,
                ttl_s=max(1.0, float(ttl_s)), agent_id=str(agent_id or ""),
                owner=str(owner or ""), source_approval_id=str(source_approval_id or ""),
            )
            self._grants[grant_id] = grant
            while len(self._grants) > self._capacity:
                oldest = min(self._grants.values(), key=lambda g: g.created_at)
                self._grants.pop(oldest.grant_id, None)
        log.info(
            "Approval grant %s issued from approval %s scope=%s session=%s surface=%s action=%s",
            grant_id, source_approval_id or "-", scope, session_id, surface, action,
        )
        if _persist.persistence_enabled():
            _persist.fire_and_forget(self._write_grant(grant))
        return grant

    async def _write_grant(self, grant: SessionGrant) -> None:
        """Mirror an issued grant to the DB. Never raises.

        A grant revoked before this write ran is not written; one revoked while
        the write was in flight is deleted again, so it cannot resurrect.
        """
        col = _persist.collection(GRANTS_COLLECTION)
        if col is None or grant.grant_id in self._revoked:
            return
        try:
            await _persist.ensure_ttl_index(GRANTS_COLLECTION, col, "expires_at")
            await _persist.ensure_index(GRANTS_COLLECTION, col, "session_id")
            await col.replace_one({"_id": grant.grant_id}, grant.to_doc(), upsert=True)
            with self._lock:
                live = grant.grant_id in self._grants
                if live:
                    self._persisted.add(grant.grant_id)
            if not live:
                await col.delete_one({"_id": grant.grant_id})
        except Exception as exc:  # noqa: BLE001 - grant stays valid on this worker only
            _persist.warn_limited("grant-write", "Grant %s not persisted (this worker only): %s",
                                  grant.grant_id, exc)

    def _mark_revoked_locked(self, grant_id: str) -> None:
        self._revoked[grant_id] = None
        while len(self._revoked) > _MAX_REVOKED:
            self._revoked.popitem(last=False)

    def _adopt(self, grant: SessionGrant) -> None:
        """Cache a grant found in the DB so this worker can revoke it by id."""
        with self._lock:
            self._prune_locked()
            self._grants[grant.grant_id] = grant
            self._persisted.add(grant.grant_id)
            while len(self._grants) > self._capacity:
                oldest = min(self._grants.values(), key=lambda g: g.created_at)
                self._grants.pop(oldest.grant_id, None)
                self._persisted.discard(oldest.grant_id)

    async def has_grant_async(
        self,
        session_id: str,
        surface: str,
        action: str,
        agent_id: str | None = None,
        owner: str | None = None,
    ) -> SessionGrant | None:
        """Like :meth:`has_grant`, but also honours grants issued by another worker.

        Memory is checked first; a memory hit whose DB copy has landed is
        re-checked against the DB so a revoke on another worker takes effect.
        Fail closed: any DB error or a lookup slower than 2s yields ``None``.
        Expired rows are never honoured.
        """
        local = self.has_grant(session_id, surface, action, agent_id, owner)
        col = _persist.collection(GRANTS_COLLECTION)
        if col is None:
            return local
        try:
            return await asyncio.wait_for(
                self._db_lookup(col, local, session_id, surface, action, agent_id, owner),
                _DB_TIMEOUT_S,
            )
        except Exception as exc:  # noqa: BLE001 - includes TimeoutError; fail closed
            _persist.warn_limited("grant-read", "Grant DB lookup failed, treating as no grant: %s", exc)
            return None

    async def _db_lookup(
        self, col: Any, local: SessionGrant | None, session_id: str, surface: str,
        action: str, agent_id: str | None, owner: str | None,
    ) -> SessionGrant | None:
        now = datetime.now(timezone.utc)
        if local is None:
            return await self._remote_grant(col, now, session_id, surface, action, agent_id, owner)
        if local.grant_id not in self._persisted:
            return local
        if await col.find_one({"_id": local.grant_id, "expires_at": {"$gt": now}}) is not None:
            return local
        with self._lock:
            self._grants.pop(local.grant_id, None)
            self._persisted.discard(local.grant_id)
        return None

    async def _remote_grant(
        self, col: Any, now: datetime, session_id: str, surface: str, action: str,
        agent_id: str | None, owner: str | None,
    ) -> SessionGrant | None:
        session_id = str(session_id or "").strip()
        if _is_anonymous(session_id) or str(surface) in self._excluded:
            return None
        rows = await col.find(
            {"session_id": session_id, "expires_at": {"$gt": now}}
        ).to_list(length=100)
        for row in rows:
            grant = SessionGrant.from_doc(row, self._excluded)
            if grant is not None and grant.matches(session_id, str(surface), str(action), agent_id, owner):
                self._adopt(grant)
                return grant
        return None

    async def list_grants_async(self) -> list[dict[str, Any]]:
        """Memory plus unexpired DB rows, so an admin sees other workers' grants."""
        merged = {g["grant_id"]: g for g in self.list_grants()}
        col = _persist.collection(GRANTS_COLLECTION)
        if col is not None:
            try:
                rows = await asyncio.wait_for(
                    col.find({"expires_at": {"$gt": datetime.now(timezone.utc)}}).to_list(length=500),
                    _DB_TIMEOUT_S,
                )
                for row in rows:
                    grant = SessionGrant.from_doc(row, self._excluded)
                    if grant is not None:
                        merged.setdefault(grant.grant_id, grant.to_dict())
            except Exception as exc:  # noqa: BLE001 - memory-only listing
                _persist.warn_limited("grant-list", "Grant DB listing failed, showing local grants: %s", exc)
        return sorted(merged.values(), key=lambda g: g["created_at"])

    async def revoke_grant_async(self, grant_id: str) -> SessionGrant | None:
        """Revoke here and in the DB so no worker honours the grant again.

        Returns the grant (for auditing) or ``None`` when it is unknown or expired.
        """
        with self._lock:
            removed = self._grants.pop(grant_id, None)
            self._persisted.discard(grant_id)
            self._mark_revoked_locked(grant_id)
        col = _persist.collection(GRANTS_COLLECTION)
        if col is not None:
            try:
                if removed is None:
                    doc = await asyncio.wait_for(col.find_one({"_id": grant_id}), _DB_TIMEOUT_S)
                    removed = SessionGrant.from_doc(doc, self._excluded) if doc else None
                await asyncio.wait_for(col.delete_one({"_id": grant_id}), _DB_TIMEOUT_S)
            except Exception as exc:  # noqa: BLE001 - other workers may still honour it
                _persist.warn_limited("grant-revoke", "Grant %s revoked locally but not in the DB: %s",
                                      grant_id, exc)
        if removed is not None:
            log.info("Approval grant %s revoked", grant_id)
        return removed

    async def _delete_grant(self, grant_id: str) -> None:
        col = _persist.collection(GRANTS_COLLECTION)
        if col is None:
            return
        try:
            await col.delete_one({"_id": grant_id})
        except Exception as exc:  # noqa: BLE001 - TTL still bounds it
            _persist.warn_limited("grant-revoke", "Grant %s revoked locally but not in the DB: %s",
                                  grant_id, exc)

    def has_grant(
        self,
        session_id: str,
        surface: str,
        action: str,
        agent_id: str | None = None,
        owner: str | None = None,
    ) -> SessionGrant | None:
        """The live grant covering this call, or ``None``. Never raises.

        A grant bound to an agent or owner only matches that exact one; a
        lookup that does not state them cannot match a bound grant.
        """
        try:
            session_id = str(session_id or "").strip()
            if _is_anonymous(session_id) or str(surface) in self._excluded:
                return None
            with self._lock:
                self._prune_locked()
                for grant in self._grants.values():
                    if grant.matches(session_id, str(surface), str(action), agent_id, owner):
                        return grant
        except Exception as exc:  # noqa: BLE001 - fail closed: no grant
            log.warning("Grant lookup failed, treating as no grant: %s", exc)
        return None

    def list_grants(self) -> list[dict[str, Any]]:
        with self._lock:
            self._prune_locked()
            grants = sorted(self._grants.values(), key=lambda g: g.created_at)
        return [g.to_dict() for g in grants]

    def revoke_grant(self, grant_id: str) -> SessionGrant | None:
        """Remove and return the grant (so the caller can audit it), or ``None``."""
        with self._lock:
            removed = self._grants.pop(grant_id, None)
            self._persisted.discard(grant_id)
            self._mark_revoked_locked(grant_id)
        if removed is not None:
            log.info("Approval grant %s revoked", grant_id)
        if _persist.persistence_enabled():  # also covers grants this worker never held
            _persist.fire_and_forget(self._delete_grant(grant_id))
        return removed

    def revoke(self, grant_id: str) -> bool:
        return self.revoke_grant(grant_id) is not None

    def clear(self) -> None:
        with self._lock:
            self._grants.clear()
            self._persisted.clear()

    def _prune_locked(self) -> None:
        for key in [k for k, g in self._grants.items() if g.expired]:
            self._grants.pop(key, None)
            self._persisted.discard(key)


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


_GRANTS: GrantStore | None = None


def get_grant_store() -> GrantStore:
    global _GRANTS
    with _STORE_LOCK:
        if _GRANTS is None:
            _GRANTS = GrantStore()
        return _GRANTS


def reset_grant_store(store: GrantStore | None = None) -> None:
    """Replace the process-wide grant store. Tests only."""
    global _GRANTS
    with _STORE_LOCK:
        _GRANTS = store

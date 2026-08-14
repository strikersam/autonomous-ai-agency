"""packages/governance/identity.py — who is acting, and under what mandate.

Docker AI Governance's first premise is that "agents are dangerous in
proportion to what they can authenticate as". Before this module every agent
action in this repo was anonymous: ``AgentRunner._dispatch_tool`` received a
tool name and an argument dict with no notion of *which* agent asked, who owns
it, or which policy applies. Audit rows could therefore record what happened
but never *who* did it, and no per-agent restriction was expressible.

:class:`AgentIdentity` is the missing subject. It is deliberately a frozen
dataclass with no I/O: identity is *derived* (from the agent name, the owning
user, and the task context the caller already holds), never fetched, so
resolving one cannot fail, block, or need a database.

Two ids, two different jobs:

  * ``agent_id`` is **stable** — a slug of the agent's name. The same
    specialist gets the same id across processes and deploys, so policy
    assignments and audit history join on it.
  * ``session_id`` is **per-execution** — a fresh random token per run. It is
    the unit credentials are scoped to and the key that ties a burst of audit
    rows back to one agent run.

The distinction matters for policy: rules attach to ``agent_id`` (durable),
while budgets and credential grants attach to ``session_id`` (ephemeral).
"""
from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

# Anything that is not a-z, 0-9, or a separator collapses to a single dash, so
# "Research Coordinator" and "research-coordinator" resolve to one identity
# rather than two that policy would have to be written for twice.
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")

# An agent whose name is empty / unresolvable. Never silently reused as a
# catch-all with elevated rights: the default policy group is the *least*
# privileged one, so an unnamed caller gets the tightest mandate, not the
# loosest.
UNKNOWN_AGENT_ID = "agent:unknown"

# Owner recorded when a run has no authenticated user behind it (a scheduled
# loop, a cron tick, a self-heal cycle). Distinct from an empty string so an
# audit row can never be misread as "we failed to record the owner".
SYSTEM_OWNER = "system"


def _coerce_text(value: Any) -> str:
    """Best-effort text from a loosely-typed context value. Never raises.

    Identity is derived from whatever the caller happens to hold in
    ``spec.context``, and callers are not uniform: ``runtimes/routing.py`` passes
    ``context.get("agent_name") or context.get("agent")``, and ``context["agent"]``
    is sometimes a full agent-profile *dict*, not a name string. Every derivation
    site here then calls ``.strip()``, which raises ``AttributeError`` on a dict —
    the governance seam catches it and fails *open*, so a mis-typed context value
    silently disables policy enforcement for that dispatch. Coercing to text here
    keeps the module's promised totality: a dict yields its best name field, any
    other non-string yields ``str(value)``, and ``None``/empty yield ``""``.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("name", "agent_name", "display_name", "id", "slug"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        return ""
    return str(value)


def slugify_agent(name: Any = None) -> str:
    """Return the stable ``agent:<slug>`` id for a human agent name.

    Deterministic and total: any input yields a usable id, because an agent
    that cannot be named must still be governable. Unnamed callers collapse
    to :data:`UNKNOWN_AGENT_ID`, which the default policy group treats as
    least-privileged. Non-string inputs (e.g. an agent-profile dict) are coerced
    to text rather than raising — see :func:`_coerce_text`.
    """
    slug = _SLUG_STRIP_RE.sub("-", _coerce_text(name).strip().lower()).strip("-")
    return f"agent:{slug}" if slug else UNKNOWN_AGENT_ID


def new_session_id() -> str:
    """Return a fresh, unguessable session id.

    Unguessable matters because the session id is what credential grants and
    budgets key on — a predictable id would let one run address another run's
    grant.
    """
    return "sess_" + secrets.token_hex(8)


@dataclass(frozen=True)
class AgentIdentity:
    """The acting subject of a governed action.

    Immutable by construction so a decision cannot be re-evaluated against a
    mutated identity: the value that was authorised is the value that gets
    audited. Use :meth:`with_context` to derive a narrowed copy.
    """

    agent_id: str
    display_name: str
    owner: str = SYSTEM_OWNER
    roles: tuple[str, ...] = ()
    policy_group: str = "default"
    session_id: str = field(default_factory=new_session_id)

    # ── Execution context (the "where" of an audit row) ──────────────────
    task_id: str | None = None
    run_id: str | None = None
    repo: str | None = None
    branch: str | None = None
    commit: str | None = None
    runtime: str | None = None
    sandbox_id: str | None = None
    source_ip: str | None = None
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def with_context(self, **updates: Any) -> "AgentIdentity":
        """Return a copy carrying extra execution context.

        Used when context arrives after the identity does — a sandbox id is
        only known once the sandbox exists, a commit only once it is written.
        Unknown field names are ignored rather than raising, because
        enriching an audit trail must never be able to break the run it is
        describing.
        """
        allowed = {k: v for k, v in updates.items() if k in self.__dataclass_fields__}
        return replace(self, **allowed) if allowed else self

    def to_dict(self) -> dict[str, Any]:
        """Serialise for audit rows and API responses.

        Every field here is non-secret by construction: an identity names a
        principal, it never carries the credential that authenticates it.
        """
        return {
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "owner": self.owner,
            "roles": list(self.roles),
            "policy_group": self.policy_group,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "run_id": self.run_id,
            "repo": self.repo,
            "branch": self.branch,
            "commit": self.commit,
            "runtime": self.runtime,
            "sandbox_id": self.sandbox_id,
            "source_ip": self.source_ip,
            "started_at": self.started_at,
        }


def resolve_identity(
    *,
    agent_name: str | None = None,
    owner: str | None = None,
    roles: list[str] | tuple[str, ...] | None = None,
    policy_group: str | None = None,
    session_id: str | None = None,
    **context: Any,
) -> AgentIdentity:
    """Build an :class:`AgentIdentity` from whatever the caller knows.

    Total by design — every argument is optional. A call site that has only an
    agent name still produces a governable identity, which is what makes it
    possible to wire governance into existing call sites incrementally without
    first threading a full identity object through every layer.

    ``policy_group`` defaults to the agent's own id when unset, so a group can
    be written for one specific agent without any assignment rule; the policy
    engine falls back to ``default`` when no such group exists.
    """
    agent_id = slugify_agent(agent_name)
    resolved_owner = _coerce_text(owner).strip() or SYSTEM_OWNER
    # Pass through only the *extra* context fields (task_id, repo, runtime, …).
    # The six fields this function sets explicitly below must be excluded, or a
    # caller whose context happens to carry one of those keys (``owner``,
    # ``policy_group``, …) would collide with the explicit keyword and raise
    # TypeError — which, for a function documented as total and wired into the
    # governance seam as fail-open, would silently disable enforcement.
    _explicit = {"agent_id", "display_name", "owner", "roles", "policy_group", "session_id"}
    known = {
        k: v for k, v in context.items()
        if k in AgentIdentity.__dataclass_fields__ and k not in _explicit
    }
    return AgentIdentity(
        agent_id=agent_id,
        display_name=_coerce_text(agent_name).strip() or "unknown",
        owner=resolved_owner,
        roles=tuple(roles or ()),
        policy_group=_coerce_text(policy_group).strip() or agent_id,
        session_id=session_id or new_session_id(),
        **known,
    )

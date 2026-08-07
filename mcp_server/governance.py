"""mcp_server/governance.py — governance adapter for the MCP HTTP surface.

Closes threat T11 in ``docs/governance/threat-model.md``.

Until now the governance layer covered ``AgentRunner._dispatch_tool`` — the
path all 34 autonomous loops run through — but **not** this server, which
exposes ``clone_repo``, ``write_file``, ``run_command``, ``git_push`` and
``delete_workspace`` over HTTP. Anything that could reach port 8008 with the
bearer token could edit files, run shell commands, and push to git with no
policy evaluation, no identity, and no audit row. That is a strictly larger
capability than the governed path, reachable by a shorter route.

**Why this is an adapter and not a direct import.** This server ships as its
own container (``mcp_server/Dockerfile``) whose image historically contained
only ``mcp_server/`` plus fastapi/uvicorn/httpx — ``packages.governance`` was
not importable there at all. The Dockerfile now vendors the governance
packages, but the import stays optional and guarded so that:

  * an older image, or a checkout without ``packages/``, still starts and
    serves rather than crash-looping on ImportError, and
  * the degraded state is **loud** — one warning naming the consequence,
    rather than silently serving ungoverned tools while a dashboard elsewhere
    implies coverage.

**On trusting identity headers.** The calling backend sends ``X-Agent-*``
headers so an agent's identity propagates across the process boundary. Those
headers are only as trustworthy as the ``MCP_SECRET_TOKEN`` that gates the
endpoint — a caller holding the token could claim any agent id. That is
acceptable, and deliberately so, because of how the policy engine is built:
``baseline`` rules are evaluated before any group and cannot be loosened by
one, so a spoofed identity still cannot read ``.env``, reach the metadata
endpoint, or run a denied shell shape. Spoofing can only ever move a caller
*between groups*, never past the baseline. What the headers really buy is
honest attribution in the audit trail for well-behaved callers.

A caller that sends no identity headers lands on the least-privileged default
group, not an unrestricted one.
"""
from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger("mcp-server.governance")

# Resolved once at import. `None` means governance is unavailable in this
# image; every call then passes through and the reason has already been logged.
_GOVERNANCE: Any = None
_UNAVAILABLE_REASON: str | None = None


def _load() -> None:
    """Import the governance layer once, recording why if it is absent."""
    global _GOVERNANCE, _UNAVAILABLE_REASON
    try:
        from packages.config import settings
        from packages.governance.audit import record_event
        from packages.governance.enforcement import evaluate_call
        from packages.governance.identity import resolve_identity
        from packages.governance.policy import Decision, get_policy_engine

        _GOVERNANCE = {
            "settings": settings,
            "record_event": record_event,
            "evaluate_call": evaluate_call,
            "resolve_identity": resolve_identity,
            "get_policy_engine": get_policy_engine,
            "Decision": Decision,
        }
        log.info(
            "MCP governance active (mode=%s) — tool calls are evaluated and audited",
            get_policy_engine().mode.value,
        )
    except Exception as exc:  # noqa: BLE001 - a missing layer must not stop the server
        _UNAVAILABLE_REASON = f"{type(exc).__name__}: {exc}"
        log.warning(
            "MCP governance UNAVAILABLE (%s). This server will execute tool "
            "calls WITHOUT policy evaluation, identity, or an audit trail. "
            "Rebuild the image so packages/governance is present.",
            _UNAVAILABLE_REASON,
        )


_load()


def is_active() -> bool:
    return _GOVERNANCE is not None


def status() -> dict[str, Any]:
    """Governance posture, for the ``/health`` payload.

    Surfaced on the health endpoint so an operator can tell a governed MCP
    server from an ungoverned one without reading container logs — the same
    reason ``GET /api/governance/status`` reports ``isolation: none`` rather
    than hiding it.
    """
    if _GOVERNANCE is None:
        return {"active": False, "reason": _UNAVAILABLE_REASON or "not loaded"}
    try:
        engine = _GOVERNANCE["get_policy_engine"]()
        return {"active": True, "mode": engine.mode.value, "policy_version": engine.version}
    except Exception as exc:  # noqa: BLE001
        return {"active": True, "mode": "unknown", "error": str(exc)}


def identity_from_headers(headers: Any) -> Any:
    """Build an AgentIdentity from the caller's ``X-Agent-*`` headers.

    Absent headers are fine: the resulting identity has no name, so it slugs
    to ``agent:unknown`` and resolves to the least-privileged default group.
    """
    if _GOVERNANCE is None:
        return None

    def h(name: str) -> str | None:
        try:
            return headers.get(name) or None
        except Exception:  # noqa: BLE001 - defensive against odd header objects
            return None

    return _GOVERNANCE["resolve_identity"](
        agent_name=h("X-Agent-Name"),
        owner=h("X-Agent-Owner"),
        session_id=h("X-Agent-Session"),
        task_id=h("X-Agent-Task"),
        repo=h("X-Agent-Repo"),
        branch=h("X-Agent-Branch"),
        runtime="mcp-server",
    )


def guard(identity: Any, tool: str, arguments: dict[str, Any]) -> tuple[bool, str, Any]:
    """Evaluate *tool* before it runs.

    Returns ``(allowed, message, decision)``. ``allowed`` is False only when
    the policy is in ``enforce`` mode **and** the verdict blocks — in
    ``observe`` mode the verdict is recorded and the call proceeds, matching
    the behaviour of the in-process gate exactly.

    Approval-gated actions are treated as **denied** here rather than parked.
    This is a JSON-RPC request with a client timeout on the other end, and
    there is no UI attached to this server to approve from; holding the socket
    open for up to the approval TTL would convert a governance decision into a
    hung request. The denial names the rule, so the caller can retry through
    the governed agent path where approvals do have a UI.

    Never raises: a governance bug must not take out the tool surface.
    """
    if _GOVERNANCE is None:
        return True, "", None
    try:
        engine = _GOVERNANCE["get_policy_engine"]()
        Decision = _GOVERNANCE["Decision"]
        decision, _surface, _action = _GOVERNANCE["evaluate_call"](
            engine, identity, tool, arguments
        )
        effective = decision.effective
        if effective is Decision.DENY:
            return False, (
                f"[governance] denied: {decision.reason} (rule {decision.rule_id})"
            ), decision
        if effective is Decision.REQUIRE_APPROVAL:
            return False, (
                f"[governance] requires human approval: {decision.reason} "
                f"(rule {decision.rule_id}). Approvals are not available on the "
                f"MCP surface — run this through the agent path instead."
            ), decision
        return True, "", decision
    except Exception as exc:  # noqa: BLE001 - fail open, like the in-process gate
        log.warning("MCP governance guard failed for %r (%s); allowing", tool, exc)
        return True, "", None


def record(
    identity: Any,
    tool: str,
    arguments: dict[str, Any],
    decision: Any,
    *,
    status_text: str,
    result: str = "",
    error: str | None = None,
    duration_ms: float = 0.0,
) -> None:
    """Write the audit row for a completed (or blocked) MCP tool call."""
    if _GOVERNANCE is None:
        return
    try:
        from packages.governance.audit import events_from_identity

        fields = events_from_identity(identity)
        if decision is not None:
            # The group that actually governed, not the one the caller asked
            # for — see the same note in packages/governance/enforcement.py.
            fields["policy_group"] = decision.group
        fields.update({
            "surface": decision.surface.value if decision is not None else "mcp",
            "action": decision.action if decision is not None else tool,
            "tool": tool,
            "arguments": arguments or {},
            "decision": decision.decision.value if decision is not None else "allow",
            "effective": decision.effective.value if decision is not None else "allow",
            "reason": decision.reason if decision is not None else "",
            "rule_id": decision.rule_id if decision is not None else "mcp.ungoverned",
            "mode": decision.mode.value if decision is not None else "observe",
            "result_status": status_text,
            "result": result,
            "error": error,
            "duration_ms": duration_ms,
            "runtime": "mcp-server",
        })
        _GOVERNANCE["record_event"](**fields)
    except Exception as exc:  # noqa: BLE001 - auditing must not break the call
        log.warning("MCP governance audit failed for %r: %s", tool, exc)


class Timer:
    """Wall-clock timer for the audit row's ``duration_ms``."""

    def __enter__(self) -> "Timer":
        self._start = time.monotonic()
        self.ms = 0.0
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.ms = (time.monotonic() - self._start) * 1000

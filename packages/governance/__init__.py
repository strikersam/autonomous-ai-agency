"""packages/governance — agent identity, policy, approvals, audit, sandboxes.

The runtime governance layer for this platform, modelled on Docker AI
Governance's control surfaces (network, filesystem, credentials, MCP tools)
and extended to the surfaces this repo actually exposes to agents.

Layering, and why it is split this way:

    identity     — who is acting (no I/O, cannot fail)
    policy       — what the rules say (pure evaluation, no side effects)
    approvals    — human decisions on high-risk actions
    audit        — the evidence trail (redacts before storing)
    sandbox      — hardened execution environments (docker / e2b / local)
    enforcement  — the ONLY module that acts on a decision

Judgement is separated from action so the engine can be tested without side
effects, and so "what blocked this?" has exactly one answer. Call sites should
import :func:`packages.governance.enforcement.guard_tool_call`; everything else
here is for the API layer, tests, and the dashboard.

Imports are lazy (``__getattr__``) so that importing this package costs
nothing at boot and a broken optional dependency in one submodule cannot stop
the platform from starting.
"""
from __future__ import annotations

from typing import Any

__all__ = [
    "AgentIdentity",
    "resolve_identity",
    "Decision",
    "Surface",
    "Mode",
    "PolicyDecision",
    "PolicyEngine",
    "get_policy_engine",
    "AuditEvent",
    "AuditLog",
    "get_audit_log",
    "record_event",
    "ApprovalRequest",
    "ApprovalStatus",
    "get_approval_store",
    "SandboxProfile",
    "SandboxManager",
    "SandboxUnavailableError",
    "get_sandbox_manager",
    "GovernanceGate",
    "GuardResult",
    "get_gate",
    "guard_tool_call",
    "governance_enabled",
]

_EXPORTS: dict[str, str] = {
    "AgentIdentity": "identity",
    "resolve_identity": "identity",
    "Decision": "policy",
    "Surface": "policy",
    "Mode": "policy",
    "PolicyDecision": "policy",
    "PolicyEngine": "policy",
    "get_policy_engine": "policy",
    "AuditEvent": "audit",
    "AuditLog": "audit",
    "get_audit_log": "audit",
    "record_event": "audit",
    "ApprovalRequest": "approvals",
    "ApprovalStatus": "approvals",
    "get_approval_store": "approvals",
    "SandboxProfile": "sandbox",
    "SandboxManager": "sandbox",
    "SandboxUnavailableError": "sandbox",
    "get_sandbox_manager": "sandbox",
    "GovernanceGate": "enforcement",
    "GuardResult": "enforcement",
    "get_gate": "enforcement",
    "guard_tool_call": "enforcement",
    "governance_enabled": "enforcement",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(f"{__name__}.{module_name}")
    return getattr(module, name)


def __dir__() -> list[str]:
    return sorted(__all__)

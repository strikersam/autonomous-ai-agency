"""services/spec_store.py — persisted, reviewable plan specifications.

Turns the in-memory ``AgentPlan`` produced by the planner into a durable,
human-reviewable spec artifact (markdown + structured record) stored in the
``agent_specs`` collection, with an approval workflow reusing the canonical
``ApprovalStatus`` states from ``models/company_graph.py``.

Behaviour contract (Golden Rule):
- Persistence is best-effort and additive — a storage failure never breaks a run.
- Runs are auto-approved by default; execution blocks on human approval only
  when ``AGENT_SPEC_APPROVAL_REQUIRED=true``.

Env vars (read here only, per the config-centralisation rule):
    AGENT_SPEC_PERSIST            default "true"  — write spec artifacts at all
    AGENT_SPEC_APPROVAL_REQUIRED  default "false" — block execution until approved
    AGENT_SPEC_APPROVAL_TIMEOUT   default "300"   — seconds to wait for approval
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

_VALID_STATUSES = ("pending", "approved", "rejected", "skipped")


def _flag(name: str, default: str) -> bool:
    return os.environ.get(name, default).strip().lower() in ("true", "1", "yes", "on")


def spec_persist_enabled() -> bool:
    return _flag("AGENT_SPEC_PERSIST", "true")


def spec_approval_required() -> bool:
    return _flag("AGENT_SPEC_APPROVAL_REQUIRED", "false")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db() -> Any:
    from backend.server import get_db
    return get_db()


def plan_to_markdown(goal: str, steps: list[dict[str, Any]], risks: list[str]) -> str:
    """Render a plan as a reviewable markdown spec (goal, steps, files, verification)."""
    lines = [f"# Spec: {goal}", "", "## Steps", ""]
    for step in steps:
        desc = step.get("description", "")
        lines.append(f"{step.get('id', '?')}. {desc}")
        files = step.get("files") or []
        if files:
            lines.append(f"   - Files: {', '.join(files)}")
        step_type = step.get("type")
        if step_type:
            lines.append(f"   - Type: {step_type}")
    lines += ["", "## Risks", ""]
    lines += [f"- {r}" for r in risks] if risks else ["- None identified"]
    lines += [
        "",
        "## Verification",
        "",
        "- Every changed Python file must byte-compile.",
        "- The step verifier must pass on every applied change.",
        "- Matching scoped tests must pass when empirical verification is enabled.",
        "",
    ]
    return "\n".join(lines)


async def persist_plan_spec(
    *,
    session_id: str | None,
    goal: str,
    steps: list[dict[str, Any]],
    risks: list[str] | None = None,
    requires_risky_review: bool = False,
) -> dict[str, Any] | None:
    """Persist a plan as a spec artifact. Returns the stored doc, or None."""
    if not spec_persist_enabled():
        return None
    risks = risks or []
    status = "pending" if spec_approval_required() else "approved"
    doc = {
        "spec_id": uuid.uuid4().hex,
        "session_id": session_id,
        "goal": goal,
        "steps": steps,
        "risks": risks,
        "requires_risky_review": requires_risky_review,
        "markdown": plan_to_markdown(goal, steps, risks),
        "status": status,
        "decided_by": None if status == "pending" else "auto",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    try:
        await _db().agent_specs.insert_one(dict(doc))
    except Exception as exc:  # nosec B110 -- spec persistence is best-effort
        log.debug("Spec persistence skipped (storage unavailable): %s", exc)
        return None
    return doc


async def get_spec(spec_id: str) -> dict[str, Any] | None:
    return await _db().agent_specs.find_one({"spec_id": spec_id})


async def list_specs(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"status": status} if status else {}
    cursor = _db().agent_specs.find(query).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def set_spec_status(spec_id: str, status: str, decided_by: str) -> dict[str, Any] | None:
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid spec status {status!r}; expected one of {_VALID_STATUSES}")
    result = await _db().agent_specs.update_one(
        {"spec_id": spec_id},
        {"$set": {"status": status, "decided_by": decided_by, "updated_at": _now_iso()}},
    )
    if getattr(result, "matched_count", 0) == 0:
        return None
    return await get_spec(spec_id)


async def await_spec_approval(spec_id: str, poll_seconds: float = 2.0) -> bool:
    """Block until the spec is approved (True) or rejected/timeout (False)."""
    timeout = float(os.environ.get("AGENT_SPEC_APPROVAL_TIMEOUT", "300"))
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        doc = await get_spec(spec_id)
        status = (doc or {}).get("status")
        if status == "approved":
            return True
        if status in ("rejected", "skipped"):
            return False
        await asyncio.sleep(poll_seconds)
    log.warning("Spec %s not approved within %ss — refusing to execute", spec_id, timeout)
    return False

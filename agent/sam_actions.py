"""agent/sam_actions.py — Deterministic actions SAM can take on the alerts feed.

SAM's HTTP chat path was pure LLM chat: asked to "look into the alerts and fix
them", it had no way to read the alerts bell or queue work, so the model could
only tell the Commander to do it themselves. This module gives SAM two grounded
actions over the same feed the bell renders (``/api/activity``):

* ``read``  — summarise the open error/warning alerts.
* ``fix``   — queue one agent task per distinct fixable alert, through
  ``TaskWorkflowService`` so the dispatcher actually picks it up.

Intent detection is keyword-based on purpose: an action that creates tasks
must not depend on a free-tier LLM deciding to call a tool.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("qwen-proxy")

_ALERT_TERMS = ("alert", "notification", "error", "warning", "bell")
_FIX_TERMS = (
    "fix", "resolve", "repair", "sort out", "sort it", "handle", "take care",
    "look into", "investigate", "address", "deal with", "clear them", "solve",
)
_READ_TERMS = (
    "what", "show", "list", "read", "check", "any ", "tell", "summar", "how many",
)
_FIXABLE_KINDS = {"error", "ci", "security", "infra"}
_MAX_FIX_TASKS = 5
_FEED_LIMIT = 50


@dataclass(frozen=True)
class SamAlert:
    """One actionable entry from the alerts feed."""

    title: str
    message: str
    kind: str
    severity: str

    @property
    def fixable(self) -> bool:
        return self.kind != "approval" and (
            self.kind in _FIXABLE_KINDS or self.severity == "error"
        )

    def fingerprint(self) -> str:
        """Stable id for dedup: volatile ids/numbers stripped, bucketed per UTC day."""
        norm = re.sub(r"[0-9a-f]{6,}|\d+", "#", f"{self.title}|{self.message}".lower())
        day = time.strftime("%Y-%m-%d", time.gmtime())
        return hashlib.sha256(f"{norm}|{day}".encode()).hexdigest()[:16]


def detect_alert_intent(text: str) -> str | None:
    """Return ``"fix"``, ``"read"`` or ``None`` for a Commander utterance."""
    lower = f" {text.lower()} "
    if not any(term in lower for term in _ALERT_TERMS):
        return None
    if any(term in lower for term in _FIX_TERMS):
        return "fix"
    if any(term in lower for term in _READ_TERMS):
        return "read"
    return None


def _to_alert(item: dict[str, Any]) -> SamAlert | None:
    """Map a raw feed entry to an alert — same P1/P2 rule as AlertsBell.jsx."""
    kind = str(item.get("type") or item.get("category") or "").lower()
    severity = str(item.get("severity") or item.get("level") or "").lower()
    if severity not in {"error", "warning", "critical"} and kind not in _FIXABLE_KINDS | {"approval"}:
        return None
    message = str(item.get("message") or item.get("description") or item.get("detail") or "")
    title = str(item.get("title") or item.get("action") or message[:80] or kind or "Alert")
    if severity == "critical":
        severity = "error"
    return SamAlert(title=title[:160], message=message[:500], kind=kind, severity=severity)


async def fetch_alerts(limit: int = _FEED_LIMIT) -> list[SamAlert]:
    """Read the alerts bell feed and return distinct error/warning alerts."""
    from backend.server import _get_activity_impl

    feed = await _get_activity_impl(limit)
    seen: set[str] = set()
    alerts: list[SamAlert] = []
    for item in feed.get("logs") or []:
        alert = _to_alert(item) if isinstance(item, dict) else None
        if alert is None:
            continue
        key = alert.fingerprint()
        if key in seen:
            continue
        seen.add(key)
        alerts.append(alert)
    return alerts


async def queue_fix_task(alert: SamAlert, owner_id: str) -> tuple[str, bool]:
    """Queue an agent task to fix *alert*. Returns (task_id, newly_created)."""
    from tasks.models import Task, TaskPriority
    from tasks.service import TaskWorkflowService
    from tasks.store import get_task_store

    store = get_task_store()
    source_id = f"sam-alert:{alert.fingerprint()}"
    existing = await store.find_by_source_id(source_id)
    if existing is not None:
        return existing.task_id, False
    task = Task(
        owner_id=owner_id or "sam-voice",
        title=f"Fix alert: {alert.title}"[:512],
        description=(
            f"Raised from the dashboard alerts bell via SAM.\n\n"
            f"Kind: {alert.kind or 'unknown'}\nSeverity: {alert.severity or 'unknown'}\n\n"
            f"Alert message:\n{alert.message}"
        ),
        prompt=(
            "Investigate the root cause of this platform alert and fix it. "
            "If the fix needs a code change, open a PR with a regression test. "
            f"Alert: {alert.title}. Details: {alert.message}"
        )[:32000],
        priority=TaskPriority.HIGH if alert.severity == "error" else TaskPriority.MEDIUM,
        task_type="bug_fix",
        tags=["sam-voice", "alert-fix"],
        source="sam-voice",
        source_id=source_id,
    )
    await TaskWorkflowService(store=store).create_task(task, actor=f"sam:{owner_id}")
    return task.task_id, True


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


async def fix_alerts(owner_id: str) -> str:
    """Queue fix tasks for the open alerts and return SAM's spoken report."""
    alerts = await fetch_alerts()
    fixable = [a for a in alerts if a.fixable]
    approvals = sum(1 for a in alerts if a.kind == "approval")
    if not fixable:
        tail = f" {_plural(approvals, 'run')} are waiting on your approval." if approvals else ""
        return f"I checked the alerts, Commander. There's nothing broken for me to fix.{tail} Standing by."
    created, already = 0, 0
    for alert in fixable[:_MAX_FIX_TASKS]:
        try:
            _, new = await queue_fix_task(alert, owner_id)
        except Exception:
            log.exception("SAM: failed to queue fix task for alert %r", alert.title)
            continue
        created += int(new)
        already += int(not new)
    if created == 0 and already == 0:
        return "I found the alerts, Commander, but couldn't queue fix tasks. Check the task store health."
    top = fixable[0].title
    parts = [f"I found {_plural(len(fixable), 'error alert')}, top one: {top}."]
    if created:
        parts.append(f"I've queued {_plural(created, 'fix task')} for the agents.")
    if already:
        parts.append(f"{_plural(already, 'alert')} already had a fix task in progress.")
    if len(fixable) > _MAX_FIX_TASKS:
        parts.append(f"I capped it at {_MAX_FIX_TASKS}; the rest will follow once these land.")
    if approvals:
        parts.append(f"{_plural(approvals, 'run')} still need your approval.")
    parts.append("Track them under Work.")
    return " ".join(parts)


async def summarize_alerts() -> str:
    """Return SAM's spoken summary of the open alerts."""
    alerts = await fetch_alerts()
    if not alerts:
        return "No open error or warning alerts, Commander. All clear."
    errors = sum(1 for a in alerts if a.severity == "error" or a.kind in _FIXABLE_KINDS)
    titles = "; ".join(a.title for a in alerts[:3])
    return (
        f"You have {_plural(len(alerts), 'open alert')}, {errors} of them errors. "
        f"Top ones: {titles}. Say 'fix the alerts' and I'll queue fix tasks."
    )


async def handle_alert_command(text: str, owner_id: str) -> str | None:
    """Run the alert action *text* asks for, or return None if it asks none."""
    intent = detect_alert_intent(text)
    if intent is None:
        return None
    try:
        if intent == "fix":
            return await fix_alerts(owner_id)
        return await summarize_alerts()
    except Exception:
        log.exception("SAM alert action %s failed", intent)
        return "I couldn't reach the alerts feed just now, Commander. Try again in a moment."

"""agent/sam_screen.py — what the Commander is looking at, for SAM.

The dashboard sends the current screen with each SAM message as
``hub`` or ``hub/tab`` (e.g. ``work/roadmap``). This module turns that into:

* a line of prompt context with live facts for the screens SAM can act on, and
* a screen-scoped action: on the Portfolio roadmap, "pick up the top one" /
  "start this one" means portfolio intake, which the bare words could not say.

The screen value comes from the client, so it only ever selects among
known labels and fixed reads; it is never echoed into a query or a path.
"""

from __future__ import annotations

import asyncio
import logging
import re

log = logging.getLogger("qwen-proxy")

_FACTS_TIMEOUT_SEC = 5.0
_LABELS = {
    "home": "the Home dashboard",
    "assistant/chat": "Assistant chat",
    "assistant/voice": "SAM voice mode",
    "work/now": "the task board",
    "work/roadmap": "the Portfolio roadmap",
    "work/autopilot": "Schedules",
    "company/overview": "the Company overview",
    "company/team": "the agent team",
    "company/knowledge": "Knowledge",
    "company/setup": "company setup",
    "insights/activity": "activity and logs",
    "insights/market": "market intelligence",
    "settings/controls": "Platform controls",
    "settings/providers": "Providers",
    "settings/doctor": "Doctor diagnostics",
}
_SCREEN_RE = re.compile(r"^[a-z_]{1,20}(?:/[a-z_-]{1,20})?$")
_DEICTIC_RE = re.compile(
    r"\b(?:(?:the\s+)?(?:top|first|next|this|that)\s+(?:one|initiative|item)s?"
    r"|pick\s+(?:it|this|that|them)\s+up|start\s+(?:it|this|that|them)"
    r"|work\s+on\s+(?:it|this|that|them))\b",
    re.IGNORECASE,
)


def normalise_screen(screen: str | None) -> str:
    """A safe screen path, or ``""`` when the client sent nothing usable."""
    value = (screen or "").strip().lower()
    return value if _SCREEN_RE.match(value) else ""


def screen_label(screen: str) -> str:
    screen = normalise_screen(screen)
    if not screen:
        return ""
    return _LABELS.get(screen) or _LABELS.get(screen.split("/")[0]) or f"the {screen.replace('/', ' ')} screen"


def screen_intent(text: str, screen: str) -> str | None:
    """Orchestration intent implied by *text* on *screen*, e.g. ``"portfolio"``."""
    if normalise_screen(screen) == "work/roadmap" and _DEICTIC_RE.search(text):
        return "portfolio"
    return None


async def _facts(screen: str) -> str:
    if screen == "work/roadmap":
        from agent.sam_orchestrator import _portfolio_line, portfolio_counts
        from agents.portfolio_api import get_service

        queued = [i.title for i in get_service().portfolio.prioritized()
                  if getattr(i.status, "value", "") in {"proposed", "approved"}][:3]
        top = f" Top queued: {'; '.join(queued)}." if queued else ""
        return _portfolio_line(portfolio_counts()) + top
    if screen == "work/now":
        from tasks.store import get_task_store

        pending = await get_task_store().list_pending(limit=3)
        return ("Next in the queue: " + "; ".join(t.title[:80] for t in pending) + ".") if pending \
            else "The task queue is empty."
    return ""


async def screen_context(screen: str) -> str:
    """One prompt line: where the Commander is, plus live facts when SAM has them."""
    screen = normalise_screen(screen)
    label = screen_label(screen)
    if not label:
        return ""
    try:
        facts = await asyncio.wait_for(_facts(screen), timeout=_FACTS_TIMEOUT_SEC)
    except Exception:
        log.warning("SAM screen facts unavailable for %s", screen, exc_info=True)
        facts = ""
    return f"The Commander is looking at {label}. {facts}".strip()

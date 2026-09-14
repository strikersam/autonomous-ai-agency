"""agent/time_tool.py — current-time capability for the agent loop.

The plan→execute→verify loop (agent/loop.py) runs open-weights models with no
harness system prompt (CLAUDE.md §2 header), so nothing tells them what the
actual wall-clock date is. This gives Planner/Executor/Verifier a
zero-argument, no-network, no-secret tool to ground date/recency reasoning
(e.g. "scan the last 7 days") in ground truth instead of the model's training
cutoff or an invented date.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("qwen-proxy")


def get_current_time() -> dict[str, Any]:
    """Return the current UTC time. Never raises — capability-registry convention."""
    try:
        now = datetime.now(timezone.utc)
        return {"ok": True, "utc": now.isoformat()}
    except Exception as exc:  # noqa: BLE001 - fail soft per registry convention
        log.warning("get_current_time failed: %s", exc)
        return {"ok": False, "error": str(exc)}

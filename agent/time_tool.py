"""agent/time_tool.py — current-time capability for the agent loop.

The plan-execute-verify loop (`agent/loop.py`) runs on open-weights models
with no harness system prompt (CLAUDE.md §2 header) — nothing today tells
the model what the actual current date/time is. `agent/trend_watcher.py`
already computes recency windows from wall-clock time it never exposes to
the model reasoning about them. This module closes that gap: a single
zero-argument tool the Planner/Executor/Verifier can call to ground any
date-relative reasoning (routine-backlog issue #1499, item 3).

Capability-registry path B (agent/CLAUDE.md): self-contained, no
`AgentRunner` state, no externally-influenced input, so no SSRF/traversal
guard applies.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("qwen-proxy")


def get_current_time() -> dict[str, Any]:
    """Return the current UTC time. Fails soft — never raises."""
    try:
        now = datetime.now(timezone.utc)
        return {
            "ok": True,
            "utc_iso8601": now.isoformat(),
            "unix_ts": int(now.timestamp()),
        }
    except Exception as exc:  # pragma: no cover - datetime.now(utc) does not fail
        log.debug("get_current_time failed: %s", exc)
        return {"ok": False, "error": str(exc)}

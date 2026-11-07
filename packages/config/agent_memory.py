"""packages/config/agent_memory.py — operator controls for per-agent memory.

Every agency agent keeps notes it learned from experience and has them
reorganised offline ("dreaming"); see ``services/agent_memory/``. These
readers are the only place the feature's environment variables are read
(CLAUDE.md rule 5). Values are re-read on every call, so a Platform Controls
change applies without a restart.
"""
from __future__ import annotations

import os

_TRUTHY = {"1", "true", "yes", "on"}


def _flag(name: str, default: str) -> bool:
    return os.environ.get(name, default).strip().lower() in _TRUTHY


def _int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, "").strip() or default)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def agent_memory_enabled() -> bool:
    """Agents read their memory before a task and record what they learned after."""
    return _flag("AGENT_MEMORY_ENABLED", "true")


def agent_memory_index_lines() -> int:
    """Cap on the always-loaded index layer, in lines (the top of the hierarchy)."""
    return _int("AGENT_MEMORY_INDEX_LINES", 40, 5, 200)


def agent_memory_recall_k() -> int:
    """How many task-relevant notes from the deeper store are loaded per task."""
    return _int("AGENT_MEMORY_RECALL_K", 5, 0, 20)


def agent_dream_enabled() -> bool:
    """Run the offline dreaming pass that corrects and reorganises memory."""
    return _flag("AGENT_DREAM_ENABLED", "true")


def agent_dream_interval_minutes() -> int:
    """Minimum minutes between dreaming cycles."""
    return _int("AGENT_DREAM_INTERVAL_MINUTES", 360, 5, 10080)


def agent_dream_max_agents() -> int:
    """Agents dreamed per cycle (those with the most new episodes go first)."""
    return _int("AGENT_DREAM_MAX_AGENTS", 5, 1, 50)

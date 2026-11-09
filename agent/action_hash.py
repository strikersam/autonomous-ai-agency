"""Stable identity for a tool call, so a resumed session can tell a replay from new work.

``side_effecting_calls`` lists what already ran; this module answers "is this exact call
one of them?". The hash covers the tool name and its arguments, independent of key
order, so an approval or a resume check can bind to the action itself.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from agent.checkpoint import side_effecting_calls


def action_hash(tool: str, args: Any) -> str:
    """Return a hex digest of ``tool`` plus ``args``, stable across dict key order.

    ``args`` must be JSON-serializable (as checkpointed history is); anything else raises
    ``TypeError`` rather than being coerced into a value that could collide with a string.

    Values that a JSON round trip changes are equivalent on purpose: a tuple equals a list
    and an int dict key equals its string, because checkpoints are stored as JSON and a
    resumed call must match the call that was recorded.
    """
    canonical = json.dumps(
        {"tool": tool, "args": args}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def already_executed(
    tool_call_history: list[dict[str, Any]],
    tool: str,
    args: Any,
    read_only: frozenset[str] | None = None,
) -> bool:
    """True when an identical side-effecting call is already in ``tool_call_history``.

    Read-only tools are never reported: repeating them is safe.
    """
    target = action_hash(tool, args)
    return any(
        action_hash(entry["tool"], entry.get("args")) == target
        for entry in side_effecting_calls(tool_call_history, read_only)
    )

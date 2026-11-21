"""Do not repeat an agent tool call that a resumed run already committed.

The agent loop calls :func:`run_recorded` for each tool call that is not a read.
With ``AGENT_REPLAY_GUARD_ENABLED`` on and a task-bound run, the call is recorded in
the run's ledger (``packages/runs/side_effects.recorded_effect``). An earlier attempt's
committed call with the same arguments is skipped on replay. Only a call that
succeeded is committed: a failed or rejected one is marked failed in the ledger, so a
resume runs it again. Without a bound run, or with the guard off, this is a plain
pass through.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

log = logging.getLogger("qwen-proxy")

# Generous: a tool call is not a short git push, but the ledger caps it below the lease.
_OP_TIMEOUT_S = 120.0


class _CallFailed(Exception):
    """Carries a failed tool result out of the ledger record so it is marked failed."""

    def __init__(self, result: Any) -> None:
        super().__init__("tool call failed")
        self.result = result


_FAILURE_WORDS = ("error", "refused", "denied", "blocked", "not applied", "not available", "governance")


def _failed(result: Any) -> bool:
    """Err on the side of failed: a call wrongly marked failed just runs again on a resume."""
    if isinstance(result, str):
        head = result[:100].lower()
        return head.startswith("[") and any(word in head for word in _FAILURE_WORDS)
    return isinstance(result, dict) and bool(result.get("error"))


def is_side_effecting(tool: str) -> bool:
    """True for a tool that is neither read-only nor one of the loop's control markers."""
    from agent.checkpoint import side_effecting_calls

    return bool(side_effecting_calls([{"tool": tool}]))


async def run_recorded(
    run_tool: Callable[..., Awaitable[Any]], tool: str, args: dict[str, Any], **kwargs: Any,
) -> Any:
    """Run ``run_tool(tool, args, **kwargs)``, recorded in the run ledger when that applies."""
    from packages.config import runs_settings

    if not runs_settings.replay_guard_enabled() or not is_side_effecting(tool):
        return await run_tool(tool, args, **kwargs)
    from agent.action_hash import action_hash
    from packages.runs import side_effects

    try:
        action_hash(tool, args)
    except (TypeError, ValueError):
        return await run_tool(tool, args, **kwargs)  # not JSON: cannot be keyed, so not guarded
    try:
        async with side_effects.recorded_effect(tool, args, {"tool": tool}, _OP_TIMEOUT_S) as fx:
            if fx.skipped:
                done = f" (earlier result: {fx.result_ref})" if fx.result_ref else ""
                return f"[{tool} skipped: this exact call already completed in an earlier attempt{done}]"
            result = await run_tool(tool, args, **kwargs)
            if _failed(result):
                raise _CallFailed(result)
            fx.result_ref = str(result)[:200]
            return result
    except _CallFailed as exc:
        return exc.result

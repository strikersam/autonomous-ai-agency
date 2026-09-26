"""packages/config/autonomy_limits.py — the operator's hard stops on autonomous work.

Two controls an agent can read but never write:

* ``AGENCY_KILL_SWITCH`` — one boolean that halts every autonomous action:
  scheduled jobs, workflow runs, cron ticks, agent commits and agent LLM calls.
  Human-initiated proxy traffic is untouched.
* ``AGENT_DAILY_KTOKENS_CAP`` (thousands of tokens) / ``AGENT_DAILY_USD_CAP`` —
  a per-agent, per-UTC-day ceiling enforced in the provider router. ``0`` means
  unlimited. (Not ``*_TOKEN*``: that suffix is reserved for secrets and the
  Platform Controls catalogue refuses it.)

Values are read from the environment on every call, not cached: a Platform
Controls save writes the process environment, so flipping the switch on the
dashboard takes effect on the very next check, with no restart. Agents cannot
reach this: the dashboard override is admin-only, and an agent's shell runs in
a separate process whose environment does not flow back here.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger("qwen-proxy")

_TRUTHY = {"1", "true", "yes", "on"}


class KillSwitchEngaged(RuntimeError):
    """Raised when an autonomous action is refused because the kill switch is on."""


def kill_switch_engaged() -> bool:
    """True when the operator has halted all autonomous work."""
    return os.environ.get("AGENCY_KILL_SWITCH", "").strip().lower() in _TRUTHY


def ensure_autonomy_allowed(action: str) -> None:
    """Raise ``KillSwitchEngaged`` naming *action* when the kill switch is on."""
    if kill_switch_engaged():
        log.warning("kill switch engaged — refused: %s", action)
        raise KillSwitchEngaged(f"AGENCY_KILL_SWITCH is on; refused: {action}")


def _non_negative(name: str, cast: type) -> float:
    try:
        value = cast(os.environ.get(name, "").strip() or 0)
    except (TypeError, ValueError):
        log.warning("%s is not a number — treating it as unlimited", name)
        return 0
    return max(value, 0)


def agent_daily_token_budget() -> int:
    """Per-agent daily token ceiling in tokens; ``0`` disables the cap."""
    return int(_non_negative("AGENT_DAILY_KTOKENS_CAP", float) * 1000)


def agent_daily_budget_usd() -> float:
    """Per-agent daily USD ceiling; ``0`` disables the cap."""
    return float(_non_negative("AGENT_DAILY_USD_CAP", float))

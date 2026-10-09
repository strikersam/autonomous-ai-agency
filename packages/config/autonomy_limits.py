"""packages/config/autonomy_limits.py — the operator's hard stops on autonomous work.

Two controls an agent can read but never write:

* ``AGENCY_KILL_SWITCH`` — one boolean that halts every autonomous action:
  scheduled jobs, workflow runs, cron ticks, agent commits and agent LLM calls.
  Human-initiated proxy traffic is untouched.
* ``AGENT_USER_TOKENS_PER_DAY`` — a per-user daily ceiling on the tokens an
  owner's agent runs may consume (``packages/ai/user_token_quota.py``).
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


def user_daily_token_cap() -> int:
    """``AGENT_USER_TOKENS_PER_DAY`` — per-user daily agent token ceiling; ``0`` disables."""
    return int(_non_negative("AGENT_USER_TOKENS_PER_DAY", int))


# ── Canary credential ─────────────────────────────────────────────────────────
# A decoy GitHub token planted in the process environment, which every agent
# shell and subprocess inherits. Nothing reads it legitimately, so seeing its
# value anywhere an agent can send data (an LLM prompt, an outbound URL) means
# something dumped the environment. That is the alarm (packages/security/canary.py).
CANARY_ENV = "LEGACY_DEPLOY_TOKEN"
_canary_value: str | None = None


def canary_enabled() -> bool:
    """``AGENCY_CANARY_ENABLED``, default on."""
    return os.environ.get("AGENCY_CANARY_ENABLED", "true").strip().lower() in _TRUTHY


def plant_canary() -> str | None:
    """Plant the decoy once per process and return it, or ``None`` when disabled.

    An operator-set value under the same name is left alone and never treated
    as a canary: it might be real.
    """
    global _canary_value
    if _canary_value is not None:
        return _canary_value
    if not canary_enabled() or os.environ.get(CANARY_ENV):
        return None
    import secrets
    import string

    alphabet = string.ascii_letters + string.digits
    _canary_value = "ghp_" + "".join(secrets.choice(alphabet) for _ in range(36))
    os.environ[CANARY_ENV] = _canary_value
    log.info("canary credential planted as %s", CANARY_ENV)
    return _canary_value


def canary_value() -> str | None:
    """The planted decoy, or ``None`` when none was planted in this process."""
    return _canary_value


def ceo_playbook_enforced() -> bool:
    """``CEO_PLAYBOOK_ENFORCE``, default on: the CEO drops its own repeat-failing directives.

    Off keeps the learned beliefs in the CEO's prompt but dispatches everything.
    """
    return os.environ.get("CEO_PLAYBOOK_ENFORCE", "true").strip().lower() in _TRUTHY

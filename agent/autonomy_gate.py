"""Autonomy gate — enforce 'agents propose via PR, humans merge'.

The agency can write code, but autonomous (agent-initiated) actions must never:
  * commit or push to a protected branch (main/master), or
  * merge a pull request.

This is a *security control*: it bounds what the autonomous loop can do to the
repository. Enforcement is opt-in per call via an ``agent_initiated`` flag that the
agent execution paths pass as True; human/API callers keep their existing behaviour
(default False), so this never weakens or blocks legitimate human operations.

The control is additive — it can only *refuse* an action, never grant new access.
"""

from __future__ import annotations

import os


class AutonomyViolation(PermissionError):
    """Raised when an agent-initiated action would exceed the propose-PR policy."""


def _protected_branches() -> set[str]:
    """Branches agents may never write to or merge into.

    Defaults to main/master; extend via AUTONOMY_PROTECTED_BRANCHES (comma-separated).
    """
    base = {"main", "master"}
    extra = os.environ.get("AUTONOMY_PROTECTED_BRANCHES", "")
    for name in extra.split(","):
        name = name.strip().lower()
        if name:
            base.add(name)
    return base


def is_protected_branch(branch: str | None) -> bool:
    if not branch:
        # An unknown/empty branch is treated as protected for agent writes — fail safe.
        return True
    return branch.strip().lower() in _protected_branches()


def agent_branch_name(seed: str, *, role: str | None = None) -> str:
    """Deterministic, namespaced branch for agent work, e.g. ``agent/dev/task-123``.

    Keeps autonomous work off shared branches and easy to identify/clean up.
    """
    safe_seed = "".join(c if (c.isalnum() or c in "-_") else "-" for c in str(seed))[:48]
    safe_seed = safe_seed.strip("-") or "work"
    if role:
        safe_role = "".join(c if c.isalnum() else "-" for c in str(role)).strip("-").lower()
        return f"agent/{safe_role or 'agent'}/{safe_seed}"
    return f"agent/{safe_seed}"


def assert_agent_can_write(branch: str | None, *, agent_initiated: bool, action: str = "write") -> None:
    """Refuse an agent-initiated write/push to a protected branch.

    No-op for human/API callers (``agent_initiated=False``).
    """
    if not agent_initiated:
        return
    if is_protected_branch(branch):
        raise AutonomyViolation(
            f"Autonomous {action} to protected branch '{branch}' is not allowed. "
            f"Agents must {action} to an 'agent/…' branch and open a pull request; "
            f"a human merges. (Set AUTONOMY_PROTECTED_BRANCHES to adjust.)"
        )


def assert_agent_can_merge(*, agent_initiated: bool) -> None:
    """Refuse any agent-initiated PR merge — only humans merge."""
    if agent_initiated:
        raise AutonomyViolation(
            "Autonomous PR merge is not allowed — agents propose via pull request and a "
            "human merges. Open/Update the PR instead of merging it."
        )

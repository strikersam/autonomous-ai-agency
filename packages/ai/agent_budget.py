"""packages/ai/agent_budget.py — per-agent daily spend cap for autonomous LLM calls.

Adapted from Paperclip's "monthly budget per agent: when they hit the limit,
they stop". ``packages/llm/budget.py`` already tracks spend per agent, but agent
traffic goes through ``ProviderRouter.chat_completion`` in ``packages/ai/router.py``
and never reaches it. This module is the router-side counterpart:

* ``agent_scope(name)`` binds the calling agent in a ``ContextVar``. The workflow
  orchestrator binds it for the length of a run. ``asyncio`` copies the context
  into every task it creates, so the router sees the agent without any change
  to the OpenAI-shaped payload.
* ``ensure_agent_can_spend()`` runs before each routed call. It refuses when the
  kill switch is on or when today's spend for the bound agent is at its cap.
* ``record_agent_spend()`` runs after each successful call.

Calls with no bound agent, such as human proxy traffic, are never capped and never
stopped by the kill switch. The ledger is in-memory, per process and per UTC
day, the same scope as ``packages/llm/budget.py``. A restart clears the day's
counts, and a daily cap tolerates that.
"""
from __future__ import annotations

import contextvars
import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

from packages.config.autonomy_limits import (
    agent_daily_budget_usd,
    agent_daily_token_budget,
    ensure_autonomy_allowed,
)

log = logging.getLogger("qwen-proxy")

_current_agent: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_agent", default=None
)
# Bounds the ledger: past this many agents in one day, new names fold into one
# shared bucket, so a runaway name generator cannot grow the dict without limit.
_MAX_AGENTS_PER_DAY = 500
_OVERFLOW = "other"


class AgentBudgetExceeded(RuntimeError):
    """Raised when an agent has spent its daily allowance."""


@dataclass
class _Spend:
    tokens: int = 0
    usd: float = 0.0


_lock = threading.Lock()
_day = ""
_ledger: dict[str, _Spend] = {}


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _bucket(agent: str) -> _Spend:
    """Return today's counter for *agent*; caller holds ``_lock``."""
    global _day
    today = _today()
    if today != _day:
        _day = today
        _ledger.clear()
    if agent not in _ledger and len(_ledger) >= _MAX_AGENTS_PER_DAY:
        agent = _OVERFLOW
    return _ledger.setdefault(agent, _Spend())


def current_agent() -> str | None:
    """The agent bound to the running context, or ``None`` for human traffic."""
    return _current_agent.get()


def bind_agent(name: str) -> None:
    """Re-point the current scope at *name* (e.g. once a specialist is chosen)."""
    if name:
        _current_agent.set(name)


@contextmanager
def agent_scope(name: str) -> Iterator[None]:
    """Attribute every routed LLM call inside the block to *name*."""
    token = _current_agent.set(name or None)
    try:
        yield
    finally:
        _current_agent.reset(token)


def ensure_agent_can_spend() -> None:
    """Refuse an autonomous call when the kill switch is on or the cap is spent."""
    agent = current_agent()
    if agent is None:
        return
    ensure_autonomy_allowed(f"LLM call by agent {agent!r}")
    token_cap = agent_daily_token_budget()
    usd_cap = agent_daily_budget_usd()
    if not token_cap and not usd_cap:
        return
    with _lock:
        spent = _bucket(agent)
        tokens, usd = spent.tokens, spent.usd
    if token_cap and tokens >= token_cap:
        raise AgentBudgetExceeded(
            f"agent {agent!r} spent {tokens} of {token_cap} daily tokens"
        )
    if usd_cap and usd >= usd_cap:
        raise AgentBudgetExceeded(
            f"agent {agent!r} spent ${usd:.4f} of ${usd_cap:.2f} daily budget"
        )


def record_agent_spend(tokens: int, usd: float) -> None:
    """Add one call's usage to the bound agent's daily total. Never raises."""
    agent = current_agent()
    if agent is None:
        return
    with _lock:
        spent = _bucket(agent)
        spent.tokens += max(int(tokens or 0), 0)
        spent.usd += max(float(usd or 0.0), 0.0)


def spend_snapshot() -> dict[str, dict[str, float]]:
    """Today's per-agent totals, for dashboards and tests."""
    with _lock:
        _bucket(_OVERFLOW)  # rolls the day over if needed
        return {
            name: {"tokens": s.tokens, "usd": round(s.usd, 6)}
            for name, s in _ledger.items()
            if s.tokens or s.usd
        }


def reset() -> None:
    """Clear the ledger. Test helper."""
    global _day
    with _lock:
        _ledger.clear()
        _day = ""

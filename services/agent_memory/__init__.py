"""Per-agent memory with offline dreaming.

Implements the components in Anthropic's "The components of agent memory"
(2026-11-06) for every agency agent:

* notes an agent writes in-session from its own judgment of salience
  (``capture``), each marked unverified / verified / refuted;
* episodes — the record of every run and its verifier verdict — as the ground
  truth notes are checked against (``capture``);
* a two-layer hierarchy: a small index loaded into every task and a store
  recalled by relevance (``recall``);
* dreaming, an offline pass that corrects, merges, adds cross-episode patterns
  and keeps the index small, focused on the agent's role (``dream``).

Memory is keyed by ``memory_key``: an agency agent's ``agent_id``, or
``role:<role>`` for the CEO dispatcher's role specialists.
"""
from __future__ import annotations

from services.agent_memory.service import (
    maybe_spawn_dream_cycle,
    memory_key_for,
    record_task_outcome,
    resolve_memory_key,
    run_dream_cycle,
    with_agent_memory,
)

__all__ = [
    "maybe_spawn_dream_cycle",
    "memory_key_for",
    "record_task_outcome",
    "resolve_memory_key",
    "run_dream_cycle",
    "with_agent_memory",
]

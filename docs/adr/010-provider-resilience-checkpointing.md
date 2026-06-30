---
title: ADR-010: Provider Resilience with Task Checkpointing
status: accepted
date: 2026-06-29
---

# ADR-010: Provider Resilience with Task Checkpointing

## Context

V2.0 has circuit breakers and failover (packages/ai/watchdog.py). But
when a provider fails mid-task, the entire task restarts from scratch
on the next provider — losing all intermediate work.

V2.1 needs transparent recovery: save progress, switch providers,
resume from the last checkpoint.

## Decision

Create `packages/resilience/` with:
1. `CheckpointManager` — saves task state after each step
2. On provider failure: load latest checkpoint, resume on new provider
3. Checkpoints persist to DB for cross-process recovery
4. `can_resume()` checks if a task can be resumed on a different provider

## Consequences

- No lost work when providers fail mid-task
- Transparent to the user — task continues without restart
- Works across processes (DB-persisted checkpoints)
- Minimal overhead (checkpoints are small dicts)

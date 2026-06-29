# ADR-004: Event bus for loosely coupled communication

## Status
Accepted

## Context
Components call each other directly, creating tight coupling. The scheduler
calls the dispatcher, which calls the runtime, which calls the provider. This
makes it hard to add new subscribers (e.g. telemetry, notifications).

## Decision
Create packages/events/bus.py — in-process pub/sub. Components publish events
instead of calling each other directly.

## Consequences
- Adding a new subscriber doesn't require modifying the publisher
- Events are typed (TASK_CREATED, PROVIDER_UNAVAILABLE, etc.)
- Migration is gradual — direct calls work alongside events
- Future: could be replaced with Redis pub/sub for multi-process

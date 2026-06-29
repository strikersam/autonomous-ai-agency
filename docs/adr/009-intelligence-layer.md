---
title: ADR-009: Intelligence Layer
status: accepted
date: 2026-06-29
---

# ADR-009: Intelligence Layer

## Context

V2.0 has a workflow_orchestrator that handles plan→execute→verify. But
planning, reflection, and verification are hardcoded inside specific
agents — not shared across the platform.

V2.1 needs a shared intelligence layer so every agent (SAM, direct chat,
autonomous loop, Hermes) uses the same planning, reflection, and
verification logic.

## Decision

Create `packages/intelligence/` with:
1. `Planner` — decomposes tasks into steps, selects tools per step
2. `Reflector` — evaluates output quality, suggests improvements
3. `Verifier` — checks output against requirements
4. All agents import from this layer — no agent has its own planning logic

## Consequences

- Consistent quality across all agents
- Improvements to planning/reflection benefit every agent
- No duplicated intelligence logic
- The layer is provider-independent (works with any LLM)
- Reflection suggestions require explicit approval before production changes

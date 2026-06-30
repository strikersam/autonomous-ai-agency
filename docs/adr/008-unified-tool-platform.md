---
title: ADR-008: Unified Tool Platform
status: accepted
date: 2026-06-29
---

# ADR-008: Unified Tool Platform

## Context

V2.0 established the packages/ architecture. V2.1 needs to add browser
automation, GitHub operations, shell execution, web search, and memory
operations as first-class platform capabilities available to every agent.

Previously, each agent had its own hardcoded tool implementations —
duplicated logic, inconsistent interfaces, no discovery.

## Decision

Create `packages/tools/` with:
1. Abstract `Tool` interface (`execute()`, `health()`, `schema()`)
2. `ToolRegistry` — central registry with capability-based discovery
3. Every capability (browser, github, shell, search, memory) implements `Tool`
4. Agents discover tools via `registry.find_by_capability("web")`
5. Tools export OpenAI function-calling schemas for LLM integration

## Consequences

- No duplicated tool logic — one implementation per capability
- Any agent can use any tool via the registry
- Tools are testable in isolation
- New tools are added by implementing `Tool` + registering
- LLM can discover available tools via `registry.to_openai_functions()`

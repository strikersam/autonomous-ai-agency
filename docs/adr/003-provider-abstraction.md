# ADR-003: Provider abstraction with unified interface

## Status
Accepted

## Context
Provider logic is spread across provider_router.py (1400+ lines),
brain_policy.py, brain_config_store.py, and 11 runtime adapters. Each
provider has different error handling, health checks, and cost tracking.

## Decision
Create packages/ai/provider.py with an abstract Provider interface.
Every provider implements: chat(), stream(), health(), cost(), limits().
ProviderManager (packages/ai/manager.py) handles failover + backoff.
ModelRegistry (packages/ai/registry.py) is the single source of model info.

## Consequences
- Adding a new provider = implementing one interface
- Provider-specific logic cannot leak into business code
- Failover is centralized in ProviderManager
- Model info is data-driven (no hardcoded models)

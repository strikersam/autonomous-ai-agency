# Graph Report

## WorkflowOrchestrator

The WorkflowOrchestrator manages plan→execute→verify cycles.
Located in services/workflow_orchestrator.py.

## ProviderRouter

The ProviderRouter handles multi-provider failover with exponential backoff.
Located in provider_router.py. Supports NVIDIA NIM, Cerebras, Groq, Anthropic, Ollama.

## BrainConfigStore

The BrainConfigStore persists brain configuration to MongoDB/SQLite.
Located in services/brain_config_store.py.

## AgentScheduler

The AgentScheduler manages scheduled jobs with durable persistence.
Located in agent/scheduler.py. Uses APScheduler under the hood.

## RuntimeManager

The RuntimeManager manages external runtimes (Hermes, Goose, Aider, etc).
Located in runtimes/manager.py. Health polling runs every 30 seconds.

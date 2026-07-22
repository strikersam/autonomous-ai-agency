# Agent Autonomy Roadmap

## Why this document exists

A research pass across how leading autonomous coding platforms structure their
agent loops surfaced eight concrete gaps between this repo's agency and
state-of-the-art practice — despite this repo already matching or exceeding
the field on several dimensions (task-complexity model routing, context
compaction, layered memory, role-separated agents, self-healing loops,
tracing). This document records the gap analysis and the implementation that
closed each gap.

## What was already strong (verified, no changes needed)

- **Task-complexity model routing** — `router/classifier.py` (12-category
  heuristic classifier) + `router/model_router.py` (cost-tier capability
  lookup) + circuit breaker/health failover. Genuine complexity-based
  selection, not just a failover chain.
- **Context engineering** — `services/context_window.py` (summarization at
  85% budget), layered memory (`agent/persistent_memory.py`, temporal/graph
  memory, dream consolidation), and the graphify codebase knowledge graph.
- **Role separation** — the 5 CRISPY roles in `agents/profiles.py` (read-only
  scout, architect, coder, critique-only reviewer, verifier) plus
  `services/ceo_dispatcher.py` decomposition.
- **Self-improvement** — `agent/improvement_loop.py` (6-hour scan → issues →
  scheduled fix jobs) + `services/reward_scorer.py`.
- **Observability** — Langfuse + OpenTelemetry tracing, an Observability
  dashboard.

## The eight gaps and what closed them

| # | Gap | What shipped |
|---|-----|---------------|
| G1 | The verify step judged diffs but never ran tests on them | `agent/loop.py`: opt-in `AGENT_EMPIRICAL_VERIFY` gate — byte-compiles changed files and runs matching scoped tests before a step is accepted, feeding failures into the existing retry loop |
| G2 | Plans were never approvable artifacts | `services/spec_store.py` + `backend/spec_router.py`: every plan is persisted as a reviewable markdown spec with an approval workflow (`/api/specs`); opt-in blocking via `AGENT_SPEC_APPROVAL_REQUIRED` |
| G3 | No inbound signal triage — only outbound task generation | `services/issue_triage.py`: classifies unlabeled open GitHub issues and routes them through the existing fix-dispatch pipeline; opt-in via `ISSUE_TRIAGE_ENABLED` |
| G4 | No pre-commit lint/test gate | `.pre-commit-config.yaml` exposing the existing `.claude/hooks` guardrails via the standard pre-commit framework |
| G5 | No retrospective mining over past agent sessions | `services/session_retro.py`: mines the durable session event log for recurring friction, clusters it, and files issues once a cluster crosses a threshold; opt-in via `SESSION_RETRO_ENABLED` |
| G6 | Cost data existed but wasn't broken down by task type | `packages/ai/cost_tracker.py` gained a `by_tag` breakdown (task category, not just model); surfaced as a "Spend by Task Type" table on the Observability page |
| G7 | No self-audit of the repo's own agent-readiness | `scripts/agent_readiness_audit.py`: scores 8 pillars (style/validation, build system, testing, docs, dev environment, observability, security, task discovery); `make agent-readiness` |
| G8 | No independent cross-verification or racing for high-stakes changes | `agent/verification_strategies.py`: `cross_verify` (independent re-check) and `race` (N concurrent attempts, reward-scored winner); auto-triggered for risky-module changes via `services/ceo_dispatcher.py`, gated by `AGENT_CROSS_VERIFY_ENABLED` |

## Proactive rate-limit pacing (free-tier reliability)

Investigating why free-tier providers (Cerebras, Groq, NVIDIA NIM) can churn
through fallback under load surfaced that the router's failure handling was
already solid — exponential backoff on repeated 429s, `Retry-After` honored
when a provider sends one, per-model skip on 419, dead-model memory on
410 — but entirely *reactive*: it always finds out about a rate limit by
eating a 429 first. `packages/ai/rate_limiter.py` adds the missing proactive
half: a token-bucket limiter, one per provider, that paces requests to stay
under a configured rate instead of bursting. It does not hardcode any
provider's "current" free-tier limit — those change over time and are
account-specific — so it is off by default; set `<PROVIDER_ID>_MAX_RPM`
(e.g. `CEREBRAS_MAX_RPM=28`) to that provider's real current limit (checked
from the provider's own dashboard) to enable pacing for it. Wired into
`packages/ai/router.py`'s per-model attempt loop, fire-and-forget (never
blocks a request past its own `max_wait`, and any internal error is
swallowed so pacing can never itself cause a failure).

The other two contributors to perceived "not always running" reliability are
infrastructure-level, not code bugs, and are out of scope for a code fix:
the production backend's uptime depends on the hosting tier not spinning the
process down during idle periods, and the `autonomous-cycle` GitHub Actions
workflow that pings/wakes it runs on a `*/2 * * * *` cron — GitHub does not
guarantee sub-5-minute cron fires exactly on schedule under load, and
disables scheduled workflows after 60 days of repository inactivity. An
always-on worker process (rather than relying on cron-triggered pings) would
remove that dependency; that's a hosting/deployment decision, not something
this PR changes.

## Design constraints honored

- **Golden Rule** — every behavior-adding item (G1, G2, G3, G5, G8) is
  config-gated, defaulting to the prior behavior. G6 is additive read-only
  data. G4/G7 are tooling/docs.
- **No duplicate logic** — G3 and G5 both register issues through the same
  `ImprovementLoop.register_external_issue()` entry point the scanner uses,
  instead of building a second issue pipeline.
- **No extension of deprecated paths** — G8 is a standalone module built on
  `AgentRunner` directly rather than growing `MultiAgentSwarm`, which is
  marked deprecated in favor of `WorkflowOrchestrator`.

## New environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_EMPIRICAL_VERIFY` | `false` | Run compile + scoped pytest on the agent's own changes before accepting a step |
| `AGENT_EMPIRICAL_VERIFY_TIMEOUT` | `120` | Timeout (seconds) for the empirical verification subprocess |
| `AGENT_SPEC_PERSIST` | `true` | Persist plans as reviewable markdown specs |
| `AGENT_SPEC_APPROVAL_REQUIRED` | `false` | Block execution until a human approves the spec via `/api/specs` |
| `AGENT_SPEC_APPROVAL_TIMEOUT` | `300` | Seconds to wait for spec approval before failing the run |
| `ISSUE_TRIAGE_ENABLED` | `false` | Enable inbound GitHub issue triage |
| `ISSUE_TRIAGE_OWNER` / `ISSUE_TRIAGE_REPO` | `strikersam` / `autonomous-ai-agency` | Target repo for issue triage |
| `ISSUE_TRIAGE_MAX_ISSUES` | `10` | Issues processed per triage cycle |
| `SESSION_RETRO_ENABLED` | `false` | Enable session retrospective mining |
| `SESSION_RETRO_LOOKBACK` | `50` | Most recent sessions scanned per cycle |
| `SESSION_RETRO_MIN_CLUSTER` | `3` | Occurrences before a friction cluster is filed as an issue |
| `AGENT_CROSS_VERIFY_ENABLED` | `false` | Auto-trigger independent cross-verification for risky-module changes |
| `<PROVIDER_ID>_MAX_RPM` | unset | Enable proactive rate-limit pacing for that provider (e.g. `CEREBRAS_MAX_RPM=28`) |

## Verification performed

- `python -m compileall -q .` — clean across the whole repo.
- Full `pytest` suite — 197+ backend tests passing (one pre-existing,
  unrelated live-AWS-Bedrock integration test fails without real credentials,
  identically on `master`).
- `python agent/loop_registry.py audit` — 97/100 (grade A), zero drift.
- `python scripts/agent_readiness_audit.py` — 100/100 (grade A; see the
  report's own caveat about what a presence-check score does and doesn't mean).
- Frontend: full Jest suite (117 tests, 22 suites) green; production build
  succeeds.

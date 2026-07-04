# Feature Support Matrix

This document is generated from the single source of truth in `features/matrix.py`.

## Maturity Tiers

| Tier | Meaning | Recommended for Production |
|------|---------|---------------------------|
| **stable** | Fully tested, production-ready, no known major issues | ✅ Yes |
| **beta** | Functional but may have edge cases or behavioral changes | ⚠️ With caution |
| **experimental** | Proof-of-concept, may be unstable or incomplete | ❌ Not recommended |
| **disabled** | Turned off, cannot be used without explicit override | ❌ No |

## Feature Matrix

<!-- AUTO-GENERATED from features/matrix.py -->

| Feature | ID | Maturity | Enabled | Dependencies | Config Flags | Notes |
|---------|----|----------|---------|--------------|-------------|-------|
| Proxy Endpoints | `proxy_endpoints` | stable | ✅ | — | — | Core OpenAI-compatible proxy endpoints (/v1/*). |
| Direct Chat | `direct_chat` | stable | ✅ | Ollama or cloud provider | — | Core synchronous chat feature. |
| OpenAI API Compatibility | `openai_compat` | stable | ✅ | Ollama | — | /v1/ chat completions endpoint. |
| Anthropic API Compatibility | `anthropic_compat` | stable | ✅ | Ollama | — | /v1/messages endpoint for Claude Code etc. |
| Ollama Native Passthrough | `ollama_passthrough` | stable | ✅ | Ollama | — | /api/* endpoints. |
| Multi-User Key Management | `key_management` | stable | ✅ | — | KEYS_FILE, API_KEYS | |
| Provider Routing & Fallback | `provider_routing_fallback` | stable | ✅ | — | PROVIDER_COOLDOWN_SECONDS | Timeout/cooldown/failover for providers. |
| Rate Limiting | `rate_limiting` | stable | ✅ | — | RATE_LIMIT_RPM | Per-key RPM limiting. |
| Runtime Preflight Validation | `runtime_preflight` | stable | ✅ | — | — | Structured readiness checks before execution. |
| Admin Dashboard | `admin_dashboard` | stable | ✅ | — | ADMIN_SECRET | |
| Langfuse Observability (Direct Chat) | `observability_langfuse` | stable | ✅ | Langfuse account | LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY | Traces + cost metadata. |
| Workspace Isolation | `workspace_isolation` | stable | ✅ | — | WORKSPACE_BASE_ROOT, WORKSPACE_RETENTION_TTL_SECONDS | Per-session/job isolated workspaces with manifests. |
| Planner / Executor / Verifier Pipeline | `agent_planner_executor_verifier` | stable | ✅ | Ollama or cloud provider | AGENT_PLANNER_MODEL, AGENT_EXECUTOR_MODEL, AGENT_VERIFIER_MODEL | Three-role plan-execute-verify loop. |
| Judge (Release Gate) | `agent_judge` | stable | ✅ | Ollama or cloud provider | AGENT_JUDGE_MODEL | Quality gate after verification. |
| Local Runtime (internal_agent) | `local_runtime` | stable | ✅ | — | RUNTIME_DEFAULT | Built-in agent loop, always available. |
| Local-First Model Routing | `local_model_routing` | stable | ✅ | Ollama | — | |
| Runtime Readiness Diagnostics | `runtime_readiness_diagnostics` | beta | ✅ | — | — | Preflight validation with structured issues. |
| Policies & Governance | `policies_governance` | beta | ✅ | — | — | Approval gates, RBAC, admin controls. |
| Sidecar Runtimes (Hermes/OpenCode/Goose) | `sidecar_runtimes` | **beta** | ✅ | Sidecar process running, `RuntimeManager.wake_all_sleeping_runtimes()` | CEO_WAKE_COOLDOWN_SEC | **Promoted from disabled** — every CEO delegation wakes + health-checks sidecars before dispatch (real guarantee, not a guess) and routes around any still sleeping. Hermes ships deployed by default (`agency-hermes` on Render); OpenCode/Goose remain opt-in. |
| Multi-Agent / Swarm | `multi_agent_swarm` | **beta** | ✅ | CEO dispatcher (`services/ceo_dispatcher.py`) | CEO_FANOUT_COMPLEXITY, CEO_MAX_CONCURRENT, QN_ATOMIC_CLAIM | **Promoted from disabled** — wired into the golden path via `CEODispatcher.delegate`; the `WorkflowOrchestrator` EXECUTE phase fans out across N specialists for medium/high-complexity tasks. |
| CRISPY Workflow Engine | `crispy_workflow` | experimental | ✅ | — | CRISPY_ARTIFACTS_ROOT, CRISPY_WORKSPACE_ROOT | **Re-enabled** from disabled — phase-sequence enforcement (`PhaseSequenceError`) and per-task workspace isolation added. Flag flip to stable is gated on burn-in criteria (issue #467 follow-up). |
| Async Agent Jobs | `async_agent_jobs` | disabled | ❌ | Agent runtime | DIRECT_CHAT_AGENT_WORKSPACE_ROOT | **Demoted** per issue #467 Section I — contract gaps, not production-ready. Re-enable with `FEATURE_ASYNC_AGENT_JOBS=enabled`. |
| Task-Harness Runtime | `task_harness_runtime` | disabled | ❌ | task-harness binary | TASK_HARNESS_REQUIRED, TASK_HARNESS_BIN | **Demoted** per issue #467 Section I — external binary dependency, not self-contained. |
| OpenHands Runtime | `openhands_runtime` | disabled | ❌ | Docker, OpenHands image | OPENHANDS_ENABLED | **Demoted** per issue #467 Section I — Docker dependency, unmaintained. |
| Telegram Bot | `telegram_bot` | disabled | ❌ | Telegram Bot Token | TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_IDS | **Demoted** per issue #467 Section I pending an isolation/gating review, despite a full implementation + test suite. Re-enable with `FEATURE_TELEGRAM_BOT=experimental`. |
| Tunnels (Cloudflare/ngrok) | `tunnels` | disabled | ❌ | cloudflared or ngrok | NGROK_AUTH_TOKEN, CLOUDFLARED_EXE | **Demoted** per issue #467 Section I — stability not verified. |
| OpenClaw Integration | `openclaw_integration` | disabled | ❌ | OpenClaw | — | **Demoted** per issue #467 Section I — not verified, docs only. |
| JCode Runtime | `jcode_runtime` | disabled | ❌ | JCode | — | **Demoted** per issue #467 Section I — not self-contained, no test coverage. |
| Quick Actions / iOS Shortcuts | `quick_actions_ios` | disabled | ❌ | — | — | **Demoted** per issue #467 Section I — no test coverage, not self-contained. |
| Machine Sync / Peer Sync | `machine_peer_sync` | disabled | ❌ | — | — | **Demoted** per issue #467 Section I — not implemented, no test coverage. |

## Config Overrides

Any feature can be overridden via environment variables:

```bash
# Disable a feature
FEATURE_TELEGRAM_BOT=disabled

# Change a feature's maturity
FEATURE_ASYNC_AGENT_JOBS=stable

# Enable/disable explicitly
FEATURE_OPENHANDS_RUNTIME=true
FEATURE_SIDECAE_RUNTIMES=false
```

The environment variable pattern is `FEATURE_<UPPERCASE_FEATURE_ID>`.

## Admin API

The support matrix is exposed at:

- `GET /admin/features` — full matrix with summary
- `GET /admin/features/{feature_id}` — single feature details + warnings
- `POST /admin/features/check` — check if a feature is available

## Gating Behavior

- **disabled** features: code calling `matrix.check_available(feature_id)` receives a `FeatureUnavailableError` with structured `code`, `feature_id`, `maturity`, `reason`, and `fix_hint`.
- **beta/experimental** features: `matrix.maturity_warning(feature_id)` returns a warning string. API responses include a `warning` field.
- **enabled + stable** features: no warnings, normal operation.

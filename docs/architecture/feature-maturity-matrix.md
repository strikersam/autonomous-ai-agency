# Feature Maturity / Support Matrix

> **This document is a summary.** The canonical, machine-readable source of truth is `features/matrix.py`. The admin API at `/admin/features` and the generated docs at [docs/support-matrix.md](../support-matrix.md) reflect the same state.

## Maturity Tiers

| Tier | Description | Production Use |
|------|-------------|---------------|
| **stable** | Fully tested, production-ready | ✅ Recommended |
| **beta** | Functional, may change | ⚠️ With caution |
| **experimental** | Proof-of-concept, may be unstable | ❌ Not recommended |
| **disabled** | Turned off | ❌ Requires explicit override |

## Stable Core

- OpenAI / Anthropic / Ollama API compatibility
- Multi-user key management
- Provider routing & fallback (timeout/cooldown/failover)
- Rate limiting
- Runtime preflight validation
- Admin dashboard
- Langfuse observability (direct chat)
- Workspace isolation
- Planner / executor / verifier pipeline
- Judge (release gate)
- Local runtime (internal_agent)
- Local-first model routing
- Multi-agent orchestration (CEO → single specialist; Golden-Path plan→execute→verify→judge)

> **Note on the Telegram bot:** it is a production-quality implementation (service manager, inbound routing, approval gates, `/diag`, full test suite) but was **demoted to disabled** per issue #467 Section I pending an isolation/gating review — `telegram_bot` = `disabled` in `features/matrix.py`. Re-enable with `TELEGRAM_BOT_TOKEN` + `FEATURE_TELEGRAM_BOT=experimental`.

## Beta

- Runtime readiness diagnostics
- Policies & governance
- Sidecar runtimes (Hermes/OpenCode/Goose) — **promoted from disabled**. Hermes ships deployed by default (`agency-hermes` on Render) and is the default runtime for `code_generation` tasks; `RuntimeManager.wake_all_sleeping_runtimes()` gives every CEO delegation a real, rate-limited health check before dispatch, with automatic fallback to `internal_agent` if a sidecar stays down. OpenCode/Goose remain optional and are absent on the default cloud deploy.
- Multi-agent / deep swarm (multi-specialist hand-off chains) — **promoted from disabled**. Wired into the golden path via `services/ceo_dispatcher.py:CEODispatcher.delegate`; the `WorkflowOrchestrator` EXECUTE phase fans the CEO out across N specialists for medium/high-complexity tasks.

## Experimental

- CRISPY workflow engine — re-enabled from disabled with phase-sequence enforcement (`PhaseSequenceError`) and per-task workspace isolation; promotion to stable is gated on burn-in data (issue #467 follow-up)

## Disabled (demoted per issue #467 Section I)

These features were re-assessed and demoted pending re-engineering, isolation, or test coverage — re-enable with `FEATURE_<ID>=enabled` (or `=experimental` where noted):

- Async agent jobs (202 + pollable job ID) — contract gaps, not production-ready
- Task-harness runtime — external binary dependency, not self-contained
- OpenHands runtime — Docker dependency, unmaintained (re-enable via `OPENHANDS_ENABLED=true` + `FEATURE_OPENHANDS_RUNTIME=experimental`)
- Telegram bot remote control — see note above
- Tunnels (Cloudflare/ngrok) — stability not verified
- OpenClaw integration — not verified, docs only
- JCode runtime — not self-contained, no test coverage
- Quick Actions / iOS Shortcuts — no test coverage, not self-contained
- Machine sync / peer sync — not implemented, no test coverage

## Enforcement

The matrix is enforced in code, not just documentation:

- `FeatureMatrix.check_available(feature_id)` raises `FeatureUnavailableError` for disabled features
- `FeatureMatrix.maturity_warning(feature_id)` returns warnings for beta/experimental features
- Admin API reflects the actual support state
- Config overrides allow operators to adjust tiers at deployment time

## Config Overrides

```bash
# Pattern: FEATURE_<UPPERCASE_FEATURE_ID>=<value>
FEATURE_TELEGRAM_BOT=disabled    # Disable
FEATURE_ASYNC_AGENT_JOBS=stable  # Promote to stable
FEATURE_OPENHANDS_RUNTIME=true   # Enable
```

See [docs/configuration-reference.md](../configuration-reference.md) for the full list.

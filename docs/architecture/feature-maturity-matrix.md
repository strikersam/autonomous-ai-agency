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

> **Note on opt-in features:** the **Telegram bot remote control** is production-quality (service manager, inbound routing, approval gates, `/diag`, full test suite) but ships **disabled by default** (`telegram_bot` = `disabled` in `features/matrix.py`). Enable it with `TELEGRAM_BOT_TOKEN` + `FEATURE_TELEGRAM_BOT=stable`. It is "stable, opt-in" rather than "stable core."

## Beta

- Async agent jobs (202 + pollable job ID)
- Runtime readiness diagnostics
- Policies & governance
- CRISPY workflow engine
- Task-harness runtime
- Sidecar runtimes (Hermes/OpenCode/Goose) — optional; absent on the default cloud deploy, where routing falls back to `internal_agent`
- Multi-agent / deep swarm (multi-specialist hand-off chains)

## Experimental

- OpenHands runtime (opt-in via `OPENHANDS_ENABLED=true`)
- Tunnels (Cloudflare/ngrok)
- OpenClaw integration
- JCode runtime
- Quick Actions / iOS Shortcuts
- Machine sync / peer sync

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

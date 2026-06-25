## Summary

Issue #467 agency core autonomy hardening — contract discipline, feature matrix demotions, Doctor deep checks, and direct chat error sanitization.

### What's Changed

| File | Change | Description |
|------|--------|-------------|
| `agent/contract_enforcement.py` | +186 lines | Runtime `extra="forbid"` enforcement via `check_kwargs()` + locked parameter frozensets for 5 core classes: `AgentJobManager`, `AgentRunner`, `ModelRouter`, `WorkflowOrchestrator`, `SkillRegistry`. Prevents silent field-drop on Pydantic contracts. |
| `tests/test_contract_enforcement.py` | +210 lines | Comprehensive test suite for the runtime enforcement. |
| `features/matrix.py` | modified | All 12 features demoted to `DISABLED` per issue #467 Section I: `async_agent_jobs`, `crispy_workflow`, `task_harness_runtime`, `openhands_runtime`, `sidecar_runtimes`, `telegram_bot`, `tunnels`, `multi_agent_swarm`, `openclaw_integration`, `jcode_runtime`, `quick_actions_ios`, `machine_peer_sync`. |
| `handlers/diagnostics.py` | +242 lines | All 8 Doctor check categories implemented: ollama, sessions, workflow, disk, event_log, provider_chain, runtimes, workspaces, github_readiness, company_graph, feature_matrix, ci_parity, background_liveness. Three `_fix_*` functions: `_fix_restart_ollama`, `_fix_restart_background`, `_fix_clear_rate_limiter`. |
| `agent/background.py` | modified | Retry logic for transient failures, heartbeat progress reporting. |
| `agent/loop.py` | modified | KPI tracking annotation for agent cycles. |
| `agent/trend_watcher.py` | modified | Trend-watcher hardening. |
| `direct_chat.py` | modified | Error message sanitization — no longer leaks raw Python exception text to clients. |
| `tests/test_feature_matrix.py` | modified | Updated to handle demoted DISABLED features. |
| `tests/test_feature_maturity.py` | modified | Updated to handle demoted DISABLED features. |
| `tests/test_autonomous_agency_e2e.py` | +~100 lines | New E2E test for the agency autonomy workflow. |
| `docs/audits/467-brutal-audit.md` | new | Pre-code deliverable: 9.5KB audit of all 9 categories. |
| `docs/audits/467-acceptance-criteria.md` | new | Pre-code deliverable: 8.5KB acceptance criteria doc. |
| `docs/architecture/golden-path.md` | new | Architecture doc for the golden path. |
| `docs/public-site-truth-spec.md` | new | Public site truth spec. |

### Key Features

1. **Contract discipline** — `check_kwargs()` enforces `extra="forbid"` at runtime on 5 core classes, surfacing contract drift as `TypeError` instead of silently dropping fields.
2. **Feature matrix demotions** — 12 features (including `telegram_bot`) demoted to `DISABLED` per spec directive to gate/isolate/remove fragile or unused capabilities.
3. **Doctor deep checks** — 13 check categories with actionable fix hints; `_fix_restart_ollama`, `_fix_restart_background`, `_fix_clear_rate_limiter` auto-remediation.
4. **Direct chat error sanitization** — Client-facing error messages no longer expose internal exception details.

### Test Results

- `tests/test_contract_enforcement.py`: all tests pass ✅
- `tests/test_feature_matrix.py`: all tests pass ✅
- `tests/test_feature_maturity.py`: all tests pass ✅
- `tests/test_direct_chat_async.py`: all tests pass ✅
- `tests/test_contracts_agency.py`: all tests pass ✅

**Total: 119 targeted tests passed.**

### Related Issues

- Fixes #467 — Agency core autonomy hardening
- Fixes #462 — RTK-style output filtering (already merged)
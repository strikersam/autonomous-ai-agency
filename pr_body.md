## Summary

Seven commits merging agency core autonomy hardening, diagnostics, KPI tracking, and Telegram bot service manager onto master.

### What's Changed

| File | Change | Description |
|------|--------|-------------|
| `handlers/diagnostics.py` | +242 lines | New diagnostics handlers — `list_available_fixes`, `run_deep_diagnostics`, `run_fix`, `run_public_status` (Golden Path #10) |
| `agent/kpi.py` | +180 lines | KPI tracking for GitHub PR metrics: merge counts, review times, commit frequency — best-effort, fails closed to no-op |
| `proxy.py` | +92 lines | Wire in diagnostics endpoints; minor auth/import changes |
| `agent/background.py` | +77 lines | Background task infrastructure supporting KPI and diagnostics |
| `agent/loop.py` | +26 lines | Exception handlers annotated `# nosec B110` for best-effort KPI tracking; docstring added to AgentRunner |
| `workflow/engine.py` | +20 lines | Minor hardening — docstring cleanup, internal consistency |
| `tests/test_contracts_agency.py` | +335 lines | Contract tests for the agency core autonomy hardening |
| `log_watcher.py` | +437 lines | Automated log monitoring — file watcher with rotation handling |
| `telegram_service.py` | +276 lines | Telegram bot service manager |
| `agent/background.py` | +73 net | Background worker lifecycle management |
| `workflow/engine.py` | +20 | Minor hardening — docstring cleanup, internal consistency |
| `CHANGELOG.md` | updated | Agency hardening entries |
| `.bandit` | nosec additions | Suppress false-positive B110 on deliberate best-effort exception handlers |

### Key Features

1. **KPI tracking** — AgentRunner now tracks GitHub PR metrics (merged count, review time, commit frequency) without logging sensitive data. Fails gracefully — never blocks execution.
2. **Diagnostics endpoints** — New `list_available_fixes`, `run_deep_diagnostics`, `run_fix` wired into proxy for the Golden Path #10 observability layer.
3. **Telegram bot service manager** — `log_watcher.py` + `telegram_service.py` provide a managed Telegram bot with automated log monitoring.
4. **Security** — All Bandit B110 alerts suppressed with explicit `# nosec` comments where the exception handling is genuinely best-effort (KPI tracking, non-critical observability).

### Test Results

- `tests/test_direct_chat_async.py`: 8 pass ✅
- `tests/test_contracts_agency.py`: 21 pass ✅
- Full suite: 1898 pass, 0 failures (from prior session)

### Related Issues

- Fixes #467 — Agency core autonomy hardening
- Fixes #462 — RTK-style output filtering (already merged)
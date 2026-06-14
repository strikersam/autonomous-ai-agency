# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Agency Core Autonomy Hardening** (#468): Replaced BackgroundAgent `_process()` no-op stub with real AgentRunner dispatch. Added Doctor diagnostics module with public/authenticated split and one-click fixes. Added AutonomyTracker KPI singleton. Added 21 Golden Path contract tests.
- **RTK-style Output Filtering** (#463): Added `output_filter.py` with command-specific compressors for 60-90% token reduction. Fixed #462.
- **Telegram Bot Service Manager & Log Monitoring** (#486): `telegram_service.py` integrates bot lifecycle into service_manager. `log_watcher.py` scans logs for errors and files GitHub issues automatically.
- **MongoDB Skip Flag for CI** (#484): Added `SKIP_MONGO_TESTS` env var to allow CI to run without MongoDB.

### Fixed
- **Specialist provisioning timeout (25000ms) + masked "Something went wrong" on scans/audits**: `OnboardingService.start_onboarding()` Step 8 previously awaited `CompanyAgencyService.activate_company()` (docker compose runtime startup) synchronously, regularly exceeding the onboarding Done step's 25s timeout. It now runs via `asyncio.create_task(self._activate_agency_background(...))` so the request returns promptly with an `in_progress` `activate_agency` step; `runtimes/control.py` `start_runtime`/`stop_runtime` move their blocking `docker compose` calls onto `asyncio.to_thread()` with a 10s timeout. Separately, `frontend/src/api.js`'s `fmtErr()` returned the literal `'Something went wrong.'` for `null`/`undefined` detail (network errors, timeouts, non-JSON responses — e.g. the gucci.com website scan and SEO/GEO/AIO audit), always masking the real `e.message` in `fmtErr(detail) || e.message || fallback` chains; it now returns `''`. Added a 45s default axios timeout plus longer per-call timeouts for `scanWebsite`/`scanRepo` (120s) and `runSeoAudit` (180s).
- **Three pre-existing CI-blocking bugs on `master`**: `.github/scripts/implement_agent.py` had 2968 trailing NUL bytes causing `python -m py_compile` to fail with `SyntaxError: source code string cannot contain null bytes` (stripped); `frontend/src/v5/screens/CompanyScreen.jsx` was truncated mid-statement (`exp` instead of `export default CompanyScreen;`), breaking `npm run build` and the Docker-based Playwright E2E build (completed the statement); `proxy.py`'s `/v1/models` alias entries used the stale `"owned_by": "llm-relay-alias"` instead of `"autonomous-ai-agency-alias"`, failing `tests/test_daily_automation_2026_05_14.py::TestModelsEndpointAliases::test_list_models_includes_alias_entries` (updated to match the project's current name).
- **Direct chat stuck at "planning" in Agent Mode**: the chat Agent-Mode job ran `AgentRunner.run()` with no aggregate wall-clock budget, so a hung provider connection (httpx read timeout is 300s/call across plan+execute+verify) left the job stuck at phase "planning" indefinitely. Added `CHAT_AGENT_RUN_BUDGET_SEC` (default 240s) `asyncio.wait_for` wrapper in `backend/server.py:_run_agent_loop` that fails the job cleanly with a recoverable message.
- **Issue → implementation-PR autonomy regression**: `issue-context-generator.yml` closed each issue (`--reason completed`) immediately after creating the context-doc draft PR, but `process-quick-note.yml` only picks up *open* issues — so no issue was ever auto-implemented. The context generator now leaves the issue OPEN and auto-dispatches `process-quick-note.yml` for it via `gh workflow run`, restoring the issue→code-PR pipeline.
- **Specialist loading hangs on "Loading specialists…"**: `OnboardingScreen` `DoneStep` only set the specialists state inside `startOnboarding().finally()`, so a hung provisioning request (the backend serializes onboarding under a global lock) never settled and the spinner ran forever. Added a 30s watchdog, a bounded 25s request timeout, and a guaranteed single-settle path so the UI always exits the loading state. `api.startOnboarding` now forwards a request config.
- **`_resolve_brain_provider` import error broke the orchestrator-failover test suite** (`tests/test_orchestrator_failover.py` collection ImportError): promoted the nested provider resolver to a module-level `async _resolve_brain_provider(exclude_base_urls=None)` supporting `AGENT_LLM_*` env override, priority sorting, and exclusion-based failover. Wired the EXECUTE phase to re-raise on provider failure (so the retry loop engages) and accumulate failed provider URLs in `llm_provenance["_failed_execute"]`, giving real per-provider failover (#522 acceptance criterion 2).

### Added
- **Scanner parity with BuiltWith (off-HTML evidence)**: `services/scanner.py` now inspects the TLS certificate (`_analyze_ssl_cert` — issuer + Subject Alternative Names → CDN/host/cert-provider) and performs explicit high-signal response-header detection (`_analyze_response_headers` — CF-Ray, X-Served-By, X-Amz-Cf-Id, Server, X-Powered-By, etc.) on top of the existing DNS (MX/NS/TXT/CNAME) and regex-DB passes. All four evidence sources merge with highest-confidence-wins.

- **PR #461**: Removed all hardcoded credential fallbacks from proxy.py and test configurations.
- **PR #466**: Agent now accepts command/task/text as instruction aliases in spawn_subagent.

### Changed
- **PR #459**: Deploy CI switched to wrangler-action v3 with --config wrangler.jsonc.

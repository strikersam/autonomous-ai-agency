# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed
- **README accuracy pass**: documented the technology scanner's true depth (BuiltWith-parity, four evidence sources — HTML / DNS / TLS cert / response headers — with bot-wall escalation) and added an honest **Feature maturity** matrix (Stable / Beta / Experimental) so the README no longer over-promises relative to the support matrix.

### Added
- **Agency Core Autonomy Hardening** (#468): Replaced BackgroundAgent `_process()` no-op stub with real AgentRunner dispatch. Added Doctor diagnostics module with public/authenticated split and one-click fixes. Added AutonomyTracker KPI singleton. Added 21 Golden Path contract tests.
- **RTK-style Output Filtering** (#463): Added `output_filter.py` with command-specific compressors for 60-90% token reduction. Fixed #462.
- **Telegram Bot Service Manager & Log Monitoring** (#486): `telegram_service.py` integrates bot lifecycle into service_manager. `log_watcher.py` scans logs for errors and files GitHub issues automatically.
- **MongoDB Skip Flag for CI** (#484): Added `SKIP_MONGO_TESTS` env var to allow CI to run without MongoDB.

### Fixed
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

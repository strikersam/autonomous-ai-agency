# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed
- **SSL/TLS certificate analysis in the scanner returned nothing** (pre-mortem follow-up): `services/scanner.py::_analyze_ssl_cert` disabled verification (`CERT_NONE`) before calling `getpeercert()`, but CPython only populates the parsed issuer/SAN dict when the cert is verified — so SSL-based detection silently produced zero systems on every scan. Now does a verified handshake first (common case) and falls back to decoding the raw DER cert via `cryptography` (`_decode_der_cert`) for unverified certs (expired / self-signed / hostname-mismatch). Verified live: github.com→Sectigo, shopify.com→Shopify.

### Security
- **Proxy CORS no longer silently sends credentials to a wildcard origin**: `proxy.py` now enables `allow_credentials=True` (`CORS_ALLOW_CREDENTIALS`) only when an explicit `CORS_ORIGINS` allow-list is configured; with the default `*` it stays off — the only browser-safe combination — so the admin session cookie works cross-origin in production without being exposed to arbitrary origins in dev.

### Added
- **Dashboard data visualizations** (frontend polish): new dependency-free SVG chart kit `frontend/src/v5/components/Charts.jsx` (`Sparkline`, `BarChart`, `Donut`) themed via design-system CSS variables. Wired into the v5 Dashboard: a real request-volume sparkline driven by the observability `time_series`/`buckets` data, and a new "Task Distribution" donut breaking down tasks by status. All charts degrade gracefully on empty/short/all-zero data. Added the missing `@keyframes pulse` animation that the live status dots reference.
- **Agency Core Autonomy Hardening** (#468): Replaced BackgroundAgent `_process()` no-op stub with real AgentRunner dispatch. Added Doctor diagnostics module with public/authenticated split and one-click fixes. Added AutonomyTracker KPI singleton. Added 21 Golden Path contract tests.
- **RTK-style Output Filtering** (#463): Added `output_filter.py` with command-specific compressors for 60-90% token reduction. Fixed #462.
- **Telegram Bot Service Manager & Log Monitoring** (#486): `telegram_service.py` integrates bot lifecycle into service_manager. `log_watcher.py` scans logs for errors and files GitHub issues automatically.
- **MongoDB Skip Flag for CI** (#484): Added `SKIP_MONGO_TESTS` env var to allow CI to run without MongoDB.

### Fixed
- **Direct chat stuck at "planning" in Agent Mode**: the chat Agent-Mode job ran `AgentRunner.run()` with no aggregate wall-clock budget, so a hung provider connection (httpx read timeout is 300s/call across plan+execute+verify) left the job stuck at phase "planning" indefinitely. Added `CHAT_AGENT_RUN_BUDGET_SEC` (default 240s) `asyncio.wait_for` wrapper in `backend/server.py:_run_agent_loop` that fails the job cleanly with a recoverable message.
- **Issue → implementation-PR autonomy regression**: `issue-context-generator.yml` closed each issue (`--reason completed`) immediately after creating the context-doc draft PR, but `process-quick-note.yml` only picks up *open* issues — so no issue was ever auto-implemented. The context generator now leaves the issue OPEN and auto-dispatches `process-quick-note.yml` for it via `gh workflow run`, restoring the issue→code-PR pipeline.
- **Specialist loading hangs on "Loading specialists…"**: `OnboardingScreen` `DoneStep` only set the specialists state inside `startOnboarding().finally()`, so a hung provisioning request (the backend serializes onboarding under a global lock) never settled and the spinner ran forever. Added a 30s watchdog, a bounded 25s request timeout, and a guaranteed single-settle path so the UI always exits the loading state. `api.startOnboarding` now forwards a request config.
- **`_resolve_brain_provider` import error broke the orchestrator-failover test suite** (`tests/test_orchestrator_failover.py` collection ImportError): promoted the nested provider resolver to a module-level `async _resolve_brain_provider(exclude_base_urls=None)` supporting `AGENT_LLM_*` env override, priority sorting,
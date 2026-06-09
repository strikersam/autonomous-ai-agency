# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Agency Core Autonomy Hardening** (#468): Replaced BackgroundAgent `_process()` no-op stub with real AgentRunner dispatch. Added Doctor diagnostics module with public/authenticated split and one-click fixes. Added AutonomyTracker KPI singleton. Added 21 Golden Path contract tests.
- **RTK-style Output Filtering** (#463): Added `output_filter.py` with command-specific compressors for 60-90% token reduction. Fixed #462.
- **Telegram Bot Service Manager & Log Monitoring** (#486): `telegram_service.py` integrates bot lifecycle into service_manager. `log_watcher.py` scans logs for errors and files GitHub issues automatically.
- **MongoDB Skip Flag for CI** (#484): Added `SKIP_MONGO_TESTS` env var to allow CI to run without MongoDB.

### Fixed
- **PR #461**: Removed all hardcoded credential fallbacks from proxy.py and test configurations.
- **PR #466**: Agent now accepts command/task/text as instruction aliases in spawn_subagent.

### Changed
- **PR #459**: Deploy CI switched to wrangler-action v3 with --config wrangler.jsonc.

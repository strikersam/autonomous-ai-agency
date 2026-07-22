# Agent Readiness Report

**Overall score: 100/100 (grade A)**

Self-generated — run `python scripts/agent_readiness_audit.py` to refresh.

> **Read this as a floor, not a ceiling.** Each pillar checks for the *presence* of specific infrastructure (a file, a Makefile target, a wired-in module) — it does not judge the quality of what it finds. A perfect score means the expected scaffolding exists, not that the codebase is flawless; treat drops in this score as real regressions, but treat a maxed score as "nothing obviously missing," not "done."

## Style And Validation — 100/100

- `.pre-commit-config.yaml` present — fast local feedback before CI.
- `.claude/hooks/pre-commit` guardrail hook present.

## Build System — 100/100

- Makefile present with named targets — agents don't need tribal-knowledge build steps.
- `make test` target available.
- `make lint` target available.
- `make doctor` target available.
- `make ci-parity` target available.

## Testing — 100/100

- 360 Python test files under tests/.
- 22 frontend test files.
- Agent loop can run empirical (compile + scoped pytest) verification on its own changes.

## Documentation — 100/100

- `CLAUDE.md` present.
- `AGENTS.md` present.
- `ARCHITECTURE.md` present.
- `ENGINEERING_STANDARDS.md` present.
- `CONTRIBUTING.md` present.
- `CHANGELOG.md` present.

## Dev Environment — 100/100

- `requirements.txt` pins the Python dependency surface.
- Frontend has a committed lockfile.
- .devcontainer present — reproducible dev environment.
- `agent/doctor.py` gives agents a programmatic environment diagnostic.

## Observability — 100/100

- Langfuse tracing wired in (`langfuse_obs.py`).
- OpenTelemetry tracing wired in (`services/otel_tracing.py`).
- Cost attribution breaks spend down by task type, not just by model.

## Security — 100/100

- Dedicated security-scan CI workflow present.
- Risky-module-review discipline codified as a skill.
- Independent cross-verification available for changes touching risky modules.

## Task Discovery — 100/100

- Automated scanner turns failing tests/FIXMEs into scheduled fix tasks.
- Inbound GitHub issues can be auto-classified and routed (opt-in).
- Session retrospective mining surfaces recurring agent friction as issues.

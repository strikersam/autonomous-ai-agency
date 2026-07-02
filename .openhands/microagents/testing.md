---
name: testing
type: knowledge
version: 1.0.0
triggers:
- test
- pytest
- regression
- ci
---

Testing rules for this repo:

- Run `pytest -x` before every commit; frontend uses
  `cd frontend && npm test -- --watchAll=false --forceExit`.
- Tests must be hermetic — no shared mutable state; reset module-level
  singletons via `monkeypatch.setattr(module, "_store", None)`.
- The `client` fixture is function-scoped and calls `reset_store()` to avoid
  motor event-loop binding.
- Test env: `TESTING=true`, `AGENCY_CEO_ENABLED=false`,
  `RUN_BACKGROUND_IN_WEB=false` (set in conftest).
- Never use real credentials in tests — mock/fake objects or source-inspection
  tests only.

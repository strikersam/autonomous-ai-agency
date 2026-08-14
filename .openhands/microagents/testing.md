---
name: testing
type: knowledge
version: 2.0.0
triggers:
- test
- pytest
- regression
- ci
---

See `CLAUDE.md` rules 30–33 for the binding requirements, and
`ENGINEERING_STANDARDS.md` for fixture examples.

Commands: `pytest -x` for Python;
`cd frontend && npm test -- --watchAll=false --forceExit` for the frontend.

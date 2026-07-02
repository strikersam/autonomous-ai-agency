---
name: repo
type: repo
version: 1.0.0
---

Repository ground rules (from CLAUDE.md — the full constitution):

- No user-visible behaviour may change unless explicitly requested.
- All LLM calls go through the provider router; never call a provider API directly.
- Never read environment variables outside config modules (`brain_policy.py`, `packages/config/`).
- Secrets are env-only — never write them to disk or code.
- Every new endpoint needs a test in `tests/test_*.py`; every bug fix needs a regression test.
- Every behaviour change updates BOTH `CHANGELOG.md` and `docs/changelog.md` (CI enforces parity).
- Use `logging`, never `print()`. Max 50 lines per function. Type hints on all Python functions.

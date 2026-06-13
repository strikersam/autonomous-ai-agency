# Pre-mortem Remaining Work — 2026-06-13

Tracking the remaining pre-mortem bug fixes for `autonomous-ai-agency`.

- [x] **P0** — `agent/tools.py`: path-traversal guard in `apply_diff()` / `read_file` / `search_files` (+ regression tests)
- [x] **P1** — Verify chat timeout fix (`CHAT_AGENT_RUN_BUDGET_SEC` + `asyncio.wait_for`) is wired — VERIFIED already correct in `backend/server.py:177` (constant `_AGENT_RUN_BUDGET_SEC`) and wired at `backend/server.py:3182` wrapping `runner.run()` with a `TimeoutError` 504-style graceful response. No change needed.
- [x] **P2** — `key_store.py`: verify key hashing + constant-time compare; add in-memory failed-lookup rate limiter
- [ ] **P3a** — `remote-admin/` brand rename to "Autonomous AI Agency"
- [ ] **P3b** — Keep this checklist updated as each fix lands

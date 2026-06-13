# Pre-mortem Remaining Work — 2026-06-13

Tracking the remaining pre-mortem bug fixes for `autonomous-ai-agency`.

- [x] **P0** — `agent/tools.py`: path-traversal guard in `apply_diff()` / `read_file` / `search_files` (+ regression tests)
- [ ] **P1** — Verify chat timeout fix (`CHAT_AGENT_RUN_BUDGET_SEC` + `asyncio.wait_for`) is wired
- [ ] **P2** — `key_store.py`: verify key hashing + constant-time compare; add in-memory failed-lookup rate limiter
- [ ] **P3a** — `remote-admin/` brand rename to "Autonomous AI Agency"
- [ ] **P3b** — Keep this checklist updated as each fix lands

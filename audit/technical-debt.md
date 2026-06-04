# Technical Debt Register — local-llm-server

*Audit Date: 2026-06-04*

---

## Summary

The codebase has grown rapidly into a 621-file, 60,000+ LOC platform. While each individual feature is reasonably well-implemented, the accumulation of features has created significant structural technical debt — primarily in the form of large files, duplicated abstractions, and unclear module boundaries.

---

## Category 1 — God Files

### TD-001 [HIGH] — `proxy.py` is 1,719 Lines

**Impact:** Hard to navigate, test, and onboard new contributors. All authentication, rate limiting, API routing, admin management, and agent endpoints are in one file.

**Proposed decomposition:**
```
proxy.py (keep ~200 lines — just app factory + middleware)
├── auth/
│   ├── api_key.py      (verify_api_key, check_rate_limit)
│   └── admin.py        (_require_admin, _get_admin_identity_from_request)
├── routes/
│   ├── chat.py         (/v1/chat/completions, /api/chat, /v1/messages)
│   ├── admin.py        (/admin/*, POST /admin/keys)
│   ├── agent.py        (/agent/*, /v1/agents/*)
│   └── health.py       (/health, /version, /models)
```

**Effort:** 2-3 days with tests
**Risk:** Medium (lots of downstream imports)

---

### TD-002 [HIGH] — `backend/server.py` is 6,487 Lines

**Impact:** This is the most extreme case of a god file in the entire codebase. Navigating this file requires extensive scrolling. Import time is measurably slow.

**Proposed decomposition:**
```
backend/
├── server.py           (FastAPI app factory, middleware, lifespan)
├── routers/
│   ├── companies.py    (company CRUD, graph)
│   ├── agents.py       (agent fleet management)
│   ├── workflows.py    (workflow orchestration API)
│   ├── onboarding.py   (wizard endpoints)
│   ├── skills.py       (skill registry endpoints)
│   ├── secrets.py      (secrets management)
│   ├── tasks.py        (task queue API)
│   ├── wiki.py         (wiki/knowledge endpoints)
│   ├── doctor.py       (health check endpoints)
│   └── admin.py        (admin-only endpoints)
```

**Effort:** 4-6 days with tests
**Risk:** High (many test files import from backend.server directly)

---

### TD-003 [MEDIUM] — `services/workflow_orchestrator.py` is 1,119 Lines

**Impact:** Single file implements 11-phase workflow execution. Adding new phases or modifying existing ones is risky.

**Fix:** Extract each phase into a separate module with a common interface.

---

### TD-004 [MEDIUM] — `services/company_graph_store.py` is 1,660 Lines and `services/company_graph.py` is 2,030 Lines

**Impact:** These two files together hold the company knowledge graph. The boundary between them is unclear.

**Fix:** Define clear contracts: `company_graph.py` = domain model, `company_graph_store.py` = persistence layer.

---

## Category 2 — API Key Naming Confusion

### TD-005 [MEDIUM] — Production Keys Have `test-key-` Prefix

**Issue:** Both `issue_new_api_key()` and `rotate_plain()` in `key_store.py` generate keys with the prefix `"test-key-"`. This is inherited from development and is misleading in production.

**Affected code:**
- `key_store.py:197`: `plain_key = "test-key-" + secrets.token_urlsafe(32)`
- `key_store.py:242`: `plain_key = "test-key-" + secrets.token_urlsafe(32)`

**Fix:** Change prefix to `"llms-"` or `"sk-"` (3-4 chars + separator, matching common conventions).

---

## Category 3 — Dual App Architecture

### TD-006 [MEDIUM] — Two FastAPI Apps with Separate Auth

**Issue:** `proxy.py` (port 8000) and `backend/server.py` (port 8001) are separate FastAPI applications with separate authentication systems. This creates:
- Token confusion (a proxy Bearer token cannot call backend endpoints)
- Doubled middleware
- Inconsistent CORS and session handling
- Doubled CI test setup complexity

**Fix:** Long-term: merge into one app with feature flags. Short-term: document which auth to use for which surface.

---

## Category 4 — Dual Storage Backend

### TD-007 [MEDIUM] — MongoDB + SQLite with Incomplete Parity

**Issue:** The storage layer supports both MongoDB and SQLite (via `STORAGE_BACKEND` env var). However, SQLite support has repeatedly had bugs (missing tables, async cursor issues — documented in changelog). This creates a maintenance burden of two code paths.

**Fix options:**
1. Drop SQLite backend for server deployments (keep only for development/testing)
2. Or write a proper test suite that validates both backends on every PR

**Currently:** SQLite bugs are fixed reactively after user reports. Proactive parity testing is needed.

---

## Category 5 — Test File Sprawl

### TD-008 [MEDIUM] — 158 Test Files with Inconsistent Organization

**Issue:** The `tests/` directory has 158 test files with inconsistent naming, structure, and coverage focus. Some patterns observed:
- `test_daily_2026_06_04.py` — date-stamped test files (should be removed or renamed)
- `test_daily_automation_2026_05_14.py`, `test_daily_automation_2026_05_15.py` — more dated files
- Multiple overlapping test files for similar functionality

**Fix:**
1. Remove date-stamped test files (incorporate useful tests into proper test modules)
2. Create a test organization guide: `tests/unit/`, `tests/integration/`, `tests/e2e/`
3. Add test coverage reporting to CI

---

## Category 6 — Environment Variable Documentation

### TD-009 [LOW] — 50+ Env Vars with Inconsistent Defaults

**Issue:** The codebase uses 50+ environment variables documented in `docs/configuration-reference.md`. However:
- Some vars have no defaults (fail silently)
- Some vars have insecure defaults (`CORS_ORIGINS=*`)
- No validation schema for env vars at startup

**Fix:** Create a Pydantic `Settings` model using `pydantic-settings` that validates all env vars at startup with clear error messages for missing required values.

---

## Category 7 — Missing Type Annotations

### TD-010 [LOW] — Inconsistent Type Annotations

**Issue:** CLAUDE.md requires "Type annotations on all public functions," but several files (particularly older ones) have incomplete annotations. The `backend/server.py` changelog mentions "missing return type annotations on new endpoints."

**Fix:** Add mypy to CI and enforce `--strict` mode on new code, `--ignore-missing-imports` on existing.

---

## Category 8 — Comments and Documentation Debt

### TD-011 [LOW] — Stale CLAUDE.md References

**Issue:** The root `CLAUDE.md` references `scripts/ai_runner.py` commands but several command descriptions may be outdated as the script has evolved.

**Fix:** Run `python scripts/ai_runner.py manifest` and verify CLAUDE.md matches.

---

## Category 9 — Legacy Code

### TD-012 [LOW] — Multiple Launcher Scripts (Windows + Unix)

**Issue:** The root directory contains many platform-specific launcher scripts: `run.bat`, `run.sh`, `run_proxy.bat`, `run_proxy.sh`, `start_server.ps1`, `start_server.sh`, `stop_server.ps1`, `stop_server.sh`, etc.

These scripts duplicate the `scripts/ai_runner.py` functionality and create confusion about which script to use.

**Fix:** Consolidate into a single `Makefile` target system (already partially exists) and document the authoritative way to start the server.

---

## Category 10 — Patch Files in Root

### TD-013 [LOW] — `fix-pr271-remaining-bugs.patch` in Root Directory

**Issue:** A `.patch` file (`fix-pr271-remaining-bugs.patch`) is committed to the root directory. Patch files are typically temporary artifacts that should not be committed to version control.

**Fix:** Remove and add `*.patch` to `.gitignore`.

---

## Technical Debt Register Summary

| ID | Category | Severity | Effort | Priority |
|----|----------|----------|--------|----------|
| TD-001 | God file | High | 2-3 days | Sprint 2 |
| TD-002 | God file | High | 4-6 days | Sprint 3 |
| TD-003 | God file | Medium | 1-2 days | Sprint 3 |
| TD-004 | God file | Medium | 2-3 days | Sprint 3 |
| TD-005 | Naming | Medium | <1 hour | **Immediate** |
| TD-006 | Architecture | Medium | 1 week | Long-term |
| TD-007 | Storage | Medium | 2 days | Sprint 2 |
| TD-008 | Tests | Medium | 1-2 days | Sprint 2 |
| TD-009 | Config | Low | 1 day | Sprint 3 |
| TD-010 | Types | Low | Ongoing | Sprint 3 |
| TD-011 | Docs | Low | 1 hour | Sprint 1 |
| TD-012 | Legacy | Low | 2 hours | Sprint 2 |
| TD-013 | Cleanup | Low | 10 mins | **Immediate** |

---

## Debt Velocity Indicator

Based on changelog review, the team is actively paying down debt (SQLite bugs fixed, ESLint issues resolved, missing type annotations added). The main risk is **debt accumulation outpacing remediation** as new features are added. 

**Recommendation:** Designate 20% of each sprint to debt reduction. Prioritize TD-001 and TD-002 (god files) as they block all other improvements.

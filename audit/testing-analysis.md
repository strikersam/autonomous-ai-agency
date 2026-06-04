# Testing Analysis — local-llm-server

*Audit Date: 2026-06-04*

---

## Summary

The test suite is extensive (158 test files, ~15,000+ LOC) and covers a broad range of functionality. However, coverage reporting is missing from CI, several test files contain placeholder tests, and the test organization is inconsistent.

---

## Test Suite Inventory

### Unit Tests
- Router tests: `test_model_router.py` (603 lines) ✓ Well-structured
- Agent tools: `test_agent_tools.py` ✓
- Key store: `test_secrets.py` ✓
- RBAC: `test_rbac.py` ✓
- Rate limiter: `test_rate_limiter_concurrency.py` ✓
- Token budget: `test_token_budget.py` ✓
- URL guard: `test_url_guard.py` ✓

### Integration Tests
- Agent runner: `test_agent_runner.py` (665 lines) ✓
- Chat integration: `test_agent_chat_integration.py` ✓
- Backend server: `test_backend_server_features.py` ✓
- Provider router: `test_provider_router.py` ✓
- Workflow orchestrator: `test_workflow_orchestrator.py` ✓
- SQLite store: `test_sqlite_store.py` ✓

### E2E Tests
- `tests/e2e/test_live_server.py` (664 lines) ✓
- `tests/e2e/test_regression.py` (1,054 lines) ✓
- `tests/test_browser.py` — browser automation tests ✓
- `tests/test_scanner_e2e.py` — scanner E2E ✓

### Live/External Tests (skipped in standard CI)
- `test_bedrock_live.py` — requires AWS credentials
- `test_scanner_live.py` — requires network
- `test_skill_executors_live.py` — requires real models

---

## Findings

### TEST-001 [HIGH] — No Coverage Reporting in CI

**Issue:** The CI workflow (`ci.yml`) runs pytest but does not collect or report coverage metrics. There is no target coverage threshold, no badge, and no PR comment with coverage delta.

**Impact:** Coverage can silently decrease with new features. There is no visibility into which parts of the codebase are untested.

**Fix:**
```yaml
- name: Run tests with coverage
  run: |
    pytest -x -v --tb=short --timeout=120 \
      --cov=. --cov-report=xml --cov-report=term-missing \
      --cov-fail-under=70 \
      --ignore=tests/test_hardware.py
      
- name: Upload coverage
  uses: codecov/codecov-action@v4
  with:
    file: coverage.xml
```

**Priority:** High — add to next sprint

---

### TEST-002 [HIGH] — Date-Stamped Test Files Should Be Removed

**Issue:** Test files with date stamps in their names indicate ad-hoc regression tests that were created for a specific PR but never integrated:
- `tests/test_daily_2026_06_04.py`
- `tests/test_daily_automation_2026_05_14.py`
- `tests/test_daily_automation_2026_05_15.py`
- Likely others

**Impact:** These files clutter the test directory, may contain outdated mocks, and create confusion about which tests are authoritative.

**Fix:** Audit each dated test file. Merge valuable tests into the appropriate permanent test module. Remove the dated originals.

---

### TEST-003 [MEDIUM] — Placeholder Tests with `pass`

**Issue:** The changelog mentions fixing tests that had `pass` placeholder assertions:
> "Replaced `test_single_word_no_false_positive` `pass` with a real assertion"
> "Replaced `test_recommend_favors_dynamic_match_over_map_match` `pass` with a meaningful check"

This pattern may recur in other test files. Tests with `pass` give false confidence.

**Fix:** Add a custom pytest plugin or linting rule that fails the build if any test function body consists only of `pass`. Run a one-time audit:
```bash
grep -rn "def test_.*:\n\s*pass" tests/
```

---

### TEST-004 [MEDIUM] — Missing Tests for Authentication Paths

**Issue:** The authentication middleware (`verify_api_key` in `proxy.py`) has some test coverage (`test_admin_auth.py`, `test_v3_auth.py`) but the following scenarios may be untested:
- Rate limit bypass via process restart simulation
- Concurrent auth requests (race condition in rate bucket)
- Invalid key timing behavior
- Key rotation mid-request

**Fix:** Expand `test_admin_auth.py` and `test_v3_auth.py` with parameterized edge cases.

---

### TEST-005 [MEDIUM] — No Mutation Testing

**Issue:** With 158 test files, it's easy to write tests that pass without actually covering the code's behavior. Mutation testing (e.g., with `mutmut` or `pytest-mutmut`) verifies that tests catch real bugs.

**Fix:** Run mutation testing on critical modules (router, auth, key_store) quarterly and track mutation score.

---

### TEST-006 [MEDIUM] — CI Uses Single Python Version (3.13 Only)

**Issue:** CI tests only run against Python 3.13. The codebase may be used on 3.11 or 3.12 systems.

**Fix:** Add Python 3.11 and 3.12 to the test matrix, or explicitly document that 3.13 is the minimum supported version.

---

### TEST-007 [LOW] — Test Timeouts are 120 Seconds

**Issue:** The global test timeout is 120 seconds per test. Some tests may be masking slow operations (waiting for timeouts rather than failing fast). Some tests may be unreliable due to system-level dependencies.

**Fix:** Review tests with execution time >10s. Add explicit `@pytest.mark.timeout(N)` decorators to tests with expected long duration.

---

### TEST-008 [LOW] — Async Test Configuration

**Issue:** `pytest-asyncio` is configured in `pytest.ini`. Verify that `asyncio_mode = "auto"` is set or that all async tests use `@pytest.mark.asyncio`. Missing decorators can cause async tests to not actually run.

**Fix:** Verify `pytest.ini` has:
```ini
[pytest]
asyncio_mode = auto
```

---

## Test Coverage Estimates by Module

| Module | Estimated Coverage | Confidence |
|--------|-------------------|------------|
| router/ | ~85% | High (603-line test file) |
| agent/loop.py | ~60% | Medium |
| agent/tools.py | ~70% | Medium |
| key_store.py | ~80% | High |
| admin_auth.py | ~70% | Medium |
| proxy.py (auth) | ~60% | Medium |
| chat_handlers.py | ~50% | Low |
| backend/server.py | ~40% | Low (6487 lines) |
| services/ | ~50% | Low |
| workflow/ | ~60% | Medium |

---

## Missing Test Areas

| Area | Test File | Status |
|------|-----------|--------|
| CORS enforcement | None | Missing |
| Rate limit concurrency | test_rate_limiter_concurrency.py | Exists |
| Key rotation edge cases | Partial | Needs expansion |
| Agent path traversal prevention | Partial | Needs expansion |
| Provider failover under load | test_provider_failover_integration.py | Exists |
| Frontend component tests | frontend/ | Unknown |
| Cloudflare Worker behavior | None | Missing |
| Docker health check | None | Missing |

---

## Testing Recommendations

### Immediate (Current Sprint)
1. Add `--cov-fail-under=70` to CI to prevent coverage regressions
2. Fix date-stamped test files
3. Verify no tests have `pass`-only bodies

### Sprint 1
4. Add coverage reporting to CI (Codecov or GitHub PR comment)
5. Expand auth edge case tests
6. Add CORS enforcement tests

### Sprint 2
7. Add Python 3.11/3.12 to test matrix
8. Document async test configuration requirements
9. Add mutation testing for key_store.py and router/

### Sprint 3
10. Add load/stress tests for rate limiter
11. Add contract tests for Ollama API surface
12. Add frontend component test coverage reporting

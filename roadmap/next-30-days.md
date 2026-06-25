# Roadmap — Next 30 Days

*Last Updated: 2026-06-04*

---

## Theme: Security Hardening & Production Readiness

### Week 1 — Immediate Security Fixes

| Task | Priority | Owner | Audit Ref |
|------|----------|-------|-----------|
| Remove hardcoded `<redacted-rotated>` from `ci.yml` | P0 | DevOps Agent | SEC-015 |
| Add `pip-audit` to CI pipeline | P0 | DevOps Agent | SEC-011 |
| Change API key prefix from `test-key-` to `llms-` | P1 | Bug Fix Agent | TD-005 |
| Add startup CORS wildcard warning | P1 | Bug Fix Agent | SEC-005 |
| Add `hmac.compare_digest` for admin secret | P1 | Security Agent | SEC-003 |
| Add minimum 32-char validation for ADMIN_SECRET | P1 | Security Agent | PR-013 |

### Week 2 — Testing Infrastructure

| Task | Priority | Owner | Audit Ref |
|------|----------|-------|-----------|
| Add `--cov-fail-under=70` to CI | P1 | QA Agent | TEST-001 |
| Add Codecov integration to CI | P1 | QA Agent | TEST-001 |
| Remove date-stamped test files | P2 | QA Agent | TEST-002 |
| Fix placeholder tests (grep for `pass`-only bodies) | P2 | QA Agent | TEST-003 |

### Week 3 — Documentation

| Task | Priority | Owner | Audit Ref |
|------|----------|-------|-----------|
| Create `SECURITY.md` | P1 | Docs Agent | DOC-001 |
| Create `CONTRIBUTING.md` | P1 | Docs Agent | DOC-002 |
| Archive/remove `REVIEW_AND_FIXES.md` and `AGENCY_CORE_V5_PROGRESS.md` | P2 | Docs Agent | DOC-005 |
| Remove `fix-pr271-remaining-bugs.patch` from root | P2 | Docs Agent | TD-013 |

### Week 4 — Performance Quick Wins

| Task | Priority | Owner | Audit Ref |
|------|----------|-------|-----------|
| Convert rate limiter lock from `threading.Lock` to `asyncio.Lock` | P1 | Bug Fix Agent | PERF-001 |
| Fix rate bucket key eviction to use `set` instead of `list` | P2 | Bug Fix Agent | PERF-002 |
| Add X-Request-ID middleware to proxy.py | P2 | Bug Fix Agent | PR-006 |

---

## Success Metrics

- [ ] Zero P0 security findings open
- [ ] CI passes with `pip-audit` and coverage gate
- [ ] `SECURITY.md` and `CONTRIBUTING.md` exist at root
- [ ] Rate limiter uses async lock
- [ ] No hardcoded passwords in workflow files

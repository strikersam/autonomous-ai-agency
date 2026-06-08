# Roadmap — Next 90 Days

*Last Updated: 2026-06-04*

---

## Theme: Architecture Hardening & Developer Experience

### Month 2 — Architecture Improvements

| Task | Priority | Effort | Audit Ref |
|------|----------|--------|-----------|
| Decompose `proxy.py` (1,719 lines) into sub-routers | High | 2-3 days | TD-001 |
| Add Sentry error tracking integration | High | 0.5 days | PR-005 |
| Implement graceful shutdown handler | High | 0.5 days | PR-002 |
| Add retry logic for Ollama failures (exponential backoff) | Medium | 1 day | PR-003 |
| Configure external uptime monitoring | Medium | 0.5 days | PR-004 |
| Generate `requirements.lock` with `pip-compile` | High | 0.5 days | DEP-001 |
| Move `playwright` to optional extra | High | 1 day | DEP-002 |
| Add shared httpx client for Ollama connections | Medium | 0.5 days | PERF-003 |
| Fix MongoDB query indexes for company graph | Medium | 1 day | PERF-011 |

### Month 3 — Quality & Reliability

| Task | Priority | Effort | Audit Ref |
|------|----------|--------|-----------|
| Fix dual storage backend SQLite parity tests | Medium | 2 days | TD-007 |
| Add Python 3.11/3.12 to CI test matrix | Medium | 0.5 days | TEST-006 |
| Add mutation testing for `key_store.py` and `router/` | Medium | 1 day | TEST-005 |
| Add CORS enforcement tests | Medium | 0.5 days | TEST-004 |
| Add auth edge case tests (concurrency, rotation) | Medium | 1 day | TEST-004 |
| Implement database backup policy | High | 1 day | PR-014 |
| Mount persistent volume for SQLite (Render config) | High | 0.5 days | PR-015 |
| Add database migration system (Alembic for SQLite) | Medium | 2 days | PR-008 |

---

## Feature Roadmap

### New Features (90 days)

1. **Secrets Rotation Policy**
   - Add expiry field to KeyRecord
   - Send rotation reminders via Telegram bot
   - Force rotation after 90 days

2. **Request ID Propagation**
   - X-Request-ID middleware
   - Correlation across proxy ↔ backend ↔ agent

3. **OpenAPI Export**
   - Export OpenAPI spec to `docs/openapi.json`
   - Enable Swagger UI at `/admin/api-docs` (admin-protected)

4. **CONTRIBUTING.md & Developer Onboarding**
   - Step-by-step dev setup guide
   - Contribution checklist
   - Architecture decision guide

---

## Success Metrics (90 days)

- [ ] `proxy.py` decomposed — no file >800 lines
- [ ] Sentry capturing 100% of unhandled exceptions
- [ ] `requirements.lock` in use in CI
- [ ] Database backups automated
- [ ] Coverage ≥75%
- [ ] All P0/P1 security issues resolved

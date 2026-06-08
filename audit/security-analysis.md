# Security Analysis — local-llm-server

*Audit Date: 2026-06-04*

---

## Executive Summary

The codebase demonstrates solid security awareness (hashed keys, weak-secret detection, startup guards, path traversal protection). However, several high-severity issues require remediation before this can be considered production-hardened.

---

## 1. Authentication & Authorization

### API Key Authentication

**Status: ADEQUATE with caveats**

- Keys hashed with SHA-256 before storage in `key_store.py` ✓
- Plain-text keys never logged ✓
- Startup rejects placeholder/weak keys ✓
- Dual header support (`Authorization: Bearer` and `x-api-key`) ✓
- `KeyStore.rotate_plain()` generates new key but prefix is `"test-key-"` — **semantic bug** ⚠️

**Finding SEC-001 [MEDIUM]:** Generated API keys have prefix `"test-key-"` in both `issue_new_api_key()` (key_store.py:242) and `rotate_plain()` (key_store.py:197). This prefix is misleading in production and may cause operators to distrust valid production keys.

**Fix:** Change prefix to `"llms-"` or `"sk-"` in both locations.

---

### Admin Authentication

**Status: ADEQUATE**

- Admin secret compared with constant-time-equivalent string comparison ✓
- Session tokens use `secrets.token_urlsafe(32)` ✓
- Session TTL is 12 hours ✓
- Windows Credential authenticator for local domain auth ✓
- Startup rejects known-weak admin secrets ✓

**Finding SEC-002 [MEDIUM]:** `proxy.py:_get_admin_identity_from_request()` falls back to Starlette session cookie if no Bearer token. This means if `SessionMiddleware` is installed (only when admin enabled), a session cookie can grant admin access. The session cookie secret is derived from `ADMIN_SECRET` — if `ADMIN_SECRET` is short or guessable, cookies can be forged.

**Fix:** Enforce minimum length on `ADMIN_SECRET` (≥32 chars). Consider HMAC rotation.

**Finding SEC-003 [LOW]:** `AdminAuthManager.authenticate()` compares password with `self.admin_secret` using Python `==` operator (not constant-time). This is marginally vulnerable to timing attacks on local networks.

**Fix:** Use `hmac.compare_digest()` for the admin secret comparison.

---

### JWT / Token Auth

**Finding SEC-004 [HIGH]:** `backend/server.py` uses JWT-based authentication separately from `proxy.py`'s Bearer token auth. The two auth systems are not unified — a token valid in one app is not valid in the other. This creates potential for confused deputy attacks if internal services call each other without re-authentication.

**Fix:** Unify authentication. Use shared JWT secret across both FastAPI apps, or implement a shared session store.

---

## 2. CORS Configuration

**Finding SEC-005 [HIGH]:** `proxy.py` defaults `CORS_ORIGINS = ["*"]` when `CORS_ORIGINS` env var is not set. For a local proxy, this is fine, but in production (Render, Cloudflare) this exposes all endpoints to cross-origin requests from any domain.

**Affected code:** `proxy.py:100-101`

```python
_raw_cors = os.environ.get("CORS_ORIGINS", "*").strip()
CORS_ORIGINS = [o.strip() for o in _raw_cors.split(",") if o.strip()] or ["*"]
```

**Fix:** Change default to `""` (empty) and require explicit configuration for production. Add a startup warning when CORS is `*`.

---

## 3. Agent Filesystem Writes

**Finding SEC-006 [HIGH]:** `agent/tools.py WorkspaceTools._resolve_path()` enforces that resolved paths stay within `self.root`. However:
- The root defaults to `"."` (CWD) when `AGENT_WORKSPACE_ROOT` is not set
- In production on Render, CWD is the repo root — agent can write to any file in the repo
- No OS-level sandbox (container isolation, seccomp, etc.)

**Affected code:** `agent/tools.py:55-59`

**Fix:**
1. Require `AGENT_WORKSPACE_ROOT` to be explicitly set in production
2. Add startup validation that `AGENT_WORKSPACE_ROOT` is set and does not equal repo root
3. Consider running agent execution in a separate container/subprocess with restricted filesystem access

---

## 4. Secrets Management

**Finding SEC-007 [MEDIUM]:** `secrets_store.py` stores secrets for external integrations. The storage backend (MongoDB/SQLite) may not encrypt secrets at rest — only the key names are validated, not their sensitivity.

**Fix:** Encrypt secrets at rest using `cryptography.fernet` or similar before persisting to database.

**Finding SEC-008 [LOW]:** `.env` file patterns. The codebase correctly uses `python-dotenv` and documents environment variables. However, there is no check that `.env` files are excluded from Docker builds.

**Fix:** Verify `.dockerignore` excludes `.env`.

---

## 5. Input Validation

**Finding SEC-009 [MEDIUM]:** `proxy.py AdminControlBody` uses pattern validation for `action` and `target` fields:
```python
action: str = Field(..., pattern="^(start|stop|restart)$")
target: str = Field(..., pattern="^(ollama|proxy|tunnel|stack)$")
```
This is good. However, `service_manager.py` invokes these as subprocess commands — command injection is possible if the service manager builds shell strings from these values without quoting.

**Fix:** Verify `service_manager.py` uses list-form subprocess calls (not shell=True with string concatenation).

**Finding SEC-010 [MEDIUM]:** Agent task instructions from API requests may contain prompt injection payloads. The `AgentRunner.run()` includes `_local_safety_check()` for generated code, but there is no pre-execution prompt injection filter on incoming user instructions.

**Fix:** Add an input sanitization pass for obvious prompt injection patterns (e.g., "ignore previous instructions", "you are now...") before passing to the planner LLM.

---

## 6. Dependency Security

**Finding SEC-011 [HIGH]:** No automated CVE scanning in the CI pipeline. The `security-scan.yml` workflow exists but its implementation should be verified to actually run `pip-audit` or `safety` against `requirements.txt`.

**Fix:** Add `pip-audit` step to CI, block merges on HIGH severity CVEs.

**Finding SEC-012 [MEDIUM]:** `requirements.txt` pins minimum versions (`>=`) but not exact versions (`==`). This allows CI to silently pick up new (potentially vulnerable) transitive dependencies.

**Fix:** Use `pip-compile` (pip-tools) to generate a locked `requirements.lock` file and use that in CI.

---

## 7. Logging & Information Disclosure

**Finding SEC-013 [MEDIUM]:** Several error handlers use `str(exc)` in API responses, which can leak internal paths, stack traces, or connection strings to clients.

**Affected locations (from recent changelog):** Fixed in `proxy.py` skill-registry and agency status — check for regressions in other handlers.

**Fix:** Audit all `HTTPException(detail=str(exc))` patterns. Replace with generic messages + `log.exception()`.

---

## 8. Rate Limiting

**Finding SEC-014 [MEDIUM]:** The in-memory rate limiter (`proxy.py:168-191`) uses a Python `threading.Lock`. Under high concurrency (async), this can become a bottleneck. Additionally, the limiter resets on process restart — allowing rate-limit bypass via process cycling.

**Fix:** Replace in-memory rate limiter with Redis-backed limiter (or Cloudflare rate limiting rules at the edge) for production deployments.

---

## 9. Production Secrets in GitHub Actions

**Finding SEC-015 [HIGH]:** CI workflow `ci.yml` hard-codes `ADMIN_PASSWORD: "WikiAdmin2026!"` in plain text as an environment variable in the workflow file. Even if this is a test-only password, it sets a bad precedent and could be accidentally reused.

**Affected code:** `.github/workflows/ci.yml:89`

**Fix:** Use `${{ secrets.CI_ADMIN_PASSWORD }}` or use a random value generated at test time.

---

## 10. Cloudflare Worker Security

**Finding SEC-016 [MEDIUM]:** The Cloudflare Worker (`worker/`) proxies requests to the backend. If the Worker does not validate that incoming requests are from legitimate clients (e.g., missing auth passthrough), it could act as an unauthenticated proxy.

**Fix:** Verify Cloudflare Worker forwards `Authorization` headers and does not strip auth.

---

## Severity Summary

| ID | Severity | Category | Status |
|----|----------|----------|--------|
| SEC-001 | Medium | Key naming | Open |
| SEC-002 | Medium | Admin auth | Open |
| SEC-003 | Low | Timing attack | Open |
| SEC-004 | High | Auth fragmentation | Open |
| SEC-005 | High | CORS wildcard | Open |
| SEC-006 | High | Filesystem sandbox | Open |
| SEC-007 | Medium | Secrets at rest | Open |
| SEC-008 | Low | Docker secrets | Open |
| SEC-009 | Medium | Command injection risk | Open |
| SEC-010 | Medium | Prompt injection | Open |
| SEC-011 | High | No CVE scanning | Open |
| SEC-012 | Medium | Unpinned deps | Open |
| SEC-013 | Medium | Info disclosure | Partially fixed |
| SEC-014 | Medium | Rate limit bypass | Open |
| SEC-015 | High | Password in CI | Open |
| SEC-016 | Medium | Worker auth passthrough | Open |

---

## Recommended Remediation Order

1. **[Immediate]** SEC-015: Remove hardcoded CI password
2. **[Immediate]** SEC-011: Add `pip-audit` to CI
3. **[Sprint 1]** SEC-005: Restrict CORS in production
4. **[Sprint 1]** SEC-006: Require explicit `AGENT_WORKSPACE_ROOT`
5. **[Sprint 1]** SEC-004: Unify auth across both FastAPI apps
6. **[Sprint 2]** SEC-001, SEC-003, SEC-009, SEC-012, SEC-013
7. **[Sprint 3]** SEC-002, SEC-007, SEC-010, SEC-014, SEC-016

# Production Readiness Assessment — local-llm-server

*Audit Date: 2026-06-04*

---

## Scoring Summary

| Dimension | Score | Grade |
|-----------|-------|-------|
| Authentication & Authorization | 7/10 | B |
| Availability & Reliability | 5/10 | C+ |
| Observability | 6/10 | B- |
| Security Posture | 6/10 | B- |
| Deployment & Operations | 6/10 | B- |
| Testing & Quality | 7/10 | B |
| Documentation | 7/10 | B |
| **Overall** | **6.3/10** | **B-** |

---

## 1. Availability & Reliability

### Current State
- Single-instance deployment (no horizontal scaling)
- In-memory rate limiter (lost on restart)
- No circuit breaker for Ollama failures
- Health endpoint exists (`/health`) ✓
- Auto-resume watchdog (`agent/watchdog.py`) ✓
- Background error recovery (`agent/self_healing.py`) ✓
- Doctor endpoint (`/api/doctor/public`) ✓

### Issues

**PR-001 [HIGH] — No Process Supervisor in Production**

The application is run as a plain Python process on Render. If the process crashes (OOM, unhandled exception), Render will restart it but there's a potential downtime window of 30-60s.

**Fix:** Configure Render's healthcheck endpoint and automatic restart policy. Use the existing `/health` endpoint.

**PR-002 [HIGH] — No Graceful Shutdown**

FastAPI supports lifespan events, but it's unclear if the agent runner gracefully stops ongoing agent sessions on shutdown. An abrupt shutdown could leave agent sessions in an inconsistent state.

**Fix:** Implement `asyncio.shutdown_asyncgens()` in a lifespan shutdown handler. Persist in-flight agent session state before shutdown.

**PR-003 [MEDIUM] — No Retry Logic for Ollama Failures**

If Ollama returns a 500 or is temporarily unavailable, the proxy returns the error immediately without retry.

**Fix:** Add retry with exponential backoff (2 attempts max) before surfacing the error to the client.

**PR-004 [MEDIUM] — No Uptime Monitoring**

There is no external uptime monitoring (UptimeRobot, Pingdom, Freshping) configured for the production endpoints.

**Fix:** Configure external uptime monitoring for:
- `https://local-llm-server.strikersam.workers.dev/health` (Cloudflare Worker)
- Backend API health endpoint

---

## 2. Observability

### Current State
- Langfuse LLM trace emission ✓ (when configured)
- Structured logging with `logging` module ✓
- Agent event log (append-only SQLite) ✓
- Doctor endpoint with system diagnostics ✓
- Error tracking: not configured (no Sentry/Rollbar)

### Issues

**PR-005 [HIGH] — No Error Tracking Service**

Unhandled exceptions in production generate logs but are not aggregated, alerted on, or tracked over time. Developers must manually scan logs to find issues.

**Fix:** Add Sentry integration:
```python
import sentry_sdk
sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    traces_sample_rate=0.1,
)
```

**PR-006 [MEDIUM] — No Request ID Propagation**

API requests do not have a unique request ID (`X-Request-ID` header). This makes it impossible to correlate a client error with a specific log entry in multi-request sessions.

**Fix:** Add middleware that generates and propagates `X-Request-ID`:
```python
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```

**PR-007 [MEDIUM] — Langfuse Traces Not Always Enabled**

Langfuse is only enabled when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set. In production deployments where Langfuse is not configured, there is no LLM observability.

**Fix:** Document Langfuse as a recommended production dependency. Add a startup warning when Langfuse is not configured.

---

## 3. Deployment Architecture

### Current State
- Render: backend API server ✓
- Vercel: frontend SPA ✓
- Cloudflare Workers: remote admin SPA (`remote-admin/`) ✓
- GitHub Actions: CI/CD (20+ workflows) ✓
- Docker: containerized deployment ✓
- No Redis or distributed cache

### Issues

**PR-008 [HIGH] — No Database Migration System**

Both MongoDB and SQLite are used. Changes to the data schema require manual migration. There is no versioned migration system.

**Fix:** 
- For SQLite: use Alembic or custom migration scripts in `db/migrations/`
- For MongoDB: document schema changes in ADRs with backward-compatible transitions

**PR-009 [MEDIUM] — Docker Images Not Versioned**

The `Dockerfile` family builds `latest` tags. Without versioned image tags, rolling back a bad deployment is difficult.

**Fix:** Tag Docker images with Git SHA and semantic version:
```yaml
- name: Build image
  run: docker build -t local-llm-server:${{ github.sha }} .
```

**PR-010 [MEDIUM] — No Blue/Green or Canary Deployment**

Deployments are direct, with potential downtime during Render restarts. No canary testing of new versions.

**Fix:** Configure Render's deploy preview environments or implement blue/green deployment for zero-downtime updates.

**PR-011 [MEDIUM] — Frontend Build Uses Hardcoded Example URL**

In `ci.yml:163`:
```yaml
REACT_APP_BACKEND_URL: https://relay.example.com
```

This means the production build URL must be configured in the deployment environment, not CI. Ensure Render/Vercel sets this correctly.

---

## 4. Configuration & Secrets

**PR-012 [HIGH] — No Secrets Rotation Policy**

API keys and admin secrets have no expiry or rotation policy enforced at the application level. A compromised key is valid indefinitely.

**Fix:** 
1. Add optional expiry to `KeyRecord` (field already has `created` timestamp)
2. Send expiry warning emails via the `telegram_bot.py` notification system
3. Force rotation after 90 days for production keys

**PR-013 [MEDIUM] — Admin Secret Not Validated Against Minimum Entropy**

The startup check validates that `ADMIN_SECRET` is not in the known-weak list, but doesn't check length or entropy.

**Fix:** Require `ADMIN_SECRET` to be at least 32 characters:
```python
if ADMIN_SECRET and len(ADMIN_SECRET) < 32:
    log.error("ADMIN_SECRET must be at least 32 characters")
    sys.exit(1)
```

---

## 5. Recovery & Backup

**PR-014 [HIGH] — No Database Backup Policy**

The MongoDB database (company graphs, agent sessions, secrets) has no documented backup policy or automated backup.

**Fix:** Configure MongoDB Atlas automated backups, or set up `mongodump` cron jobs.

**PR-015 [MEDIUM] — Agent Sessions May Be Lost on Restart**

Agent sessions are stored in SQLite (`agent/state.py`). If the SQLite file is on ephemeral storage (e.g., Render ephemeral filesystem), sessions are lost on restart.

**Fix:** Mount a persistent volume for the SQLite database, or migrate agent sessions to MongoDB.

---

## 6. Cloudflare Worker Audit

**PR-016 [MEDIUM] — Worker Code Not Reviewed in This Audit**

The `worker/` directory contains Cloudflare Worker code. Full review requires access to the deployed worker at `https://local-llm-server.strikersam.workers.dev`.

**Known configuration (`wrangler.jsonc`):**
- Should have route bindings, KV namespaces, secrets configured
- Auth passthrough must forward `Authorization` headers to the backend

**Action:** Fetch the deployed worker's behavior via the production URL and verify auth flows work end-to-end.

---

## Production Readiness Checklist

### Must-Fix Before Scaling Traffic

- [ ] Configure Sentry error tracking (PR-005)
- [ ] Add graceful shutdown handler (PR-002)
- [ ] Add retry logic for Ollama failures (PR-003)
- [ ] Set up external uptime monitoring (PR-004)
- [ ] Implement database backup policy (PR-014)
- [ ] Add secrets rotation policy (PR-012)

### Should-Fix Before Production Hardening

- [ ] Add X-Request-ID middleware (PR-006)
- [ ] Version Docker images with SHA (PR-009)
- [ ] Fix frontend build URL (PR-011)
- [ ] Validate ADMIN_SECRET entropy (PR-013)
- [ ] Mount persistent volume for SQLite (PR-015)
- [ ] Add database migration system (PR-008)

### Nice-to-Have for Operations

- [ ] Blue/green deployment (PR-010)
- [ ] Canary deployments (PR-010)
- [ ] Langfuse setup documentation (PR-007)
- [ ] Request tracing (PR-006)

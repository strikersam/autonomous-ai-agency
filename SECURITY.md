# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest (`master`) | ✅ |
| Previous releases | ⚠️ Best-effort |

---

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities as public GitHub issues.**

### How to Report

1. **Email:** strikersam@gmail.com with subject `[SECURITY] local-llm-server vulnerability`
2. **GitHub Private Advisory:** Use [GitHub Security Advisories](https://github.com/strikersam/local-llm-server/security/advisories/new) to report privately

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (optional)

### Response Timeline

| Stage | Timeframe |
|-------|-----------|
| Acknowledgement | Within 48 hours |
| Initial assessment | Within 5 business days |
| Fix deployed | Within 30 days for critical, 90 days for medium |
| Public disclosure | After fix is deployed |

---

## Security Design

### Authentication

- API keys are stored as SHA-256 hashes — plaintext is shown only once at creation
- Admin secrets must be ≥32 characters and not match known-weak values
- Session tokens use `secrets.token_urlsafe(32)` and expire after 12 hours
- Admin secret comparison uses `hmac.compare_digest` to prevent timing attacks

### Authorization

- Role-based access control (admin / user / guest)
- Every API endpoint requires authentication (except `/health`, `/version`, `/api/doctor/public`)
- Agent filesystem writes are bounded to `AGENT_WORKSPACE_ROOT`

### Known Security Trade-offs

- SHA-256 is used for API key lookup (not password storage) — this is appropriate because keys have 256-bit entropy making preimage attacks infeasible
- In-memory rate limiting does not persist across restarts — use `RATE_LIMIT_RPM=0` to disable if using an external rate limiter

---

## Scope

The following are **in scope** for this security policy:
- Authentication bypass
- Authorization bypass (accessing another user's data)
- Remote code execution via API
- Path traversal in agent filesystem operations
- Injection attacks (SQL, command, prompt)
- Secrets disclosure

The following are **out of scope**:
- Vulnerabilities requiring physical access to the host
- Social engineering attacks
- Denial of service via resource exhaustion (mitigated by rate limiting)
- Issues in third-party dependencies (report directly to the dependency maintainer)

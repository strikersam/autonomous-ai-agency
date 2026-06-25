# Dependency Analysis — local-llm-server

*Audit Date: 2026-06-04*

---

## Summary

The project has **~40 direct Python dependencies** and a full npm dependency tree for the React frontend. Dependencies use minimum-version constraints (`>=`) rather than pinned versions, creating supply-chain risk. No lockfile exists for Python.

---

## Python Dependencies (`requirements.txt`)

### Core Web Framework

| Package | Version Constraint | Purpose | Risk |
|---------|-------------------|---------|------|
| fastapi | >=0.136.1 | Web framework | Low |
| uvicorn[standard] | >=0.47.0 | ASGI server | Low |
| httpx | >=0.28.1 | Async HTTP client | Low |
| pydantic | >=2.13.4 | Data validation | Low |
| python-dotenv | >=1.2.2 | Env file loading | Low |
| jinja2 | >=3.1.6 | Template rendering | Low |
| python-multipart | >=0.0.30 | Form data parsing | Low |
| itsdangerous | >=2.2.0 | Session signing | Low |

### AI / LLM

| Package | Version Constraint | Purpose | Risk |
|---------|-------------------|---------|------|
| anthropic | >=0.105.2 | Anthropic SDK | Medium (fast-moving API) |
| langfuse | >=4.7.1, <5 | Observability | Medium (major version pinned) |

### Storage / Database

| Package | Version Constraint | Purpose | Risk |
|---------|-------------------|---------|------|
| motor | >=3.7.1 | Async MongoDB | Low |
| pymongo | >=4.17.0 | Sync MongoDB | Low |
| aiosqlite | >=0.19.0 | Async SQLite | Low |

### Security / Auth

| Package | Version Constraint | Purpose | Risk |
|---------|-------------------|---------|------|
| bcrypt | >=5.0.0 | Password hashing | Low |
| PyJWT | >=2.12.1 | JWT tokens | Low |
| cryptography | >=48.0.0 | Crypto ops | Low |
| oauthlib | >=3.3.1 | OAuth 2.0 | Low |

### Cloud / Infrastructure

| Package | Version Constraint | Purpose | Risk |
|---------|-------------------|---------|------|
| boto3 | >=1.43.19 | AWS SDK (Bedrock) | Low |
| pyngrok | >=8.1.2 | ngrok tunneling | Medium |
| curl_cffi | >=0.15.0 | CFFI-based curl | Medium (less common) |

### Data Processing

| Package | Version Constraint | Purpose | Risk |
|---------|-------------------|---------|------|
| beautifulsoup4 | >=4.14.3 | HTML parsing | Low |
| lxml | >=6.1.1 | XML/HTML parsing | Low |
| pillow | >=12.2.0 | Image processing | Medium (CVE history) |
| pygments | >=2.20.0 | Syntax highlighting | Low |

### Browser Automation

| Package | Version Constraint | Purpose | Risk |
|---------|-------------------|---------|------|
| playwright | >=1.55.0 | Browser automation | High (large dep, requires browser install) |

### Networking

| Package | Version Constraint | Purpose | Risk |
|---------|-------------------|---------|------|
| requests | >=2.34.2,<2.35 | HTTP client | Low (version-capped) |
| certifi | >=2026.4.22 | TLS certificates | Low |
| idna | >=3.17 | IDNA encoding | Low |
| urllib3 | >=2.7.0 | HTTP library | Low |
| dnspython | >=2.8.0 | DNS toolkit | Low |

### System / Build

| Package | Version Constraint | Purpose | Risk |
|---------|-------------------|---------|------|
| psutil | >=7.2.2 | System monitoring | Low |
| setuptools | >=82.0.1 | Build tools | Low |
| wheel | >=0.47.0 | Package building | Low |
| pyasn1 | >=0.6.3 | ASN.1 parsing | Low |
| zipp | >=3.23.1 | ZIP utility | Low |

### Testing

| Package | Version Constraint | Purpose | Risk |
|---------|-------------------|---------|------|
| pytest | >=9.0.3 | Test runner | Low |
| pytest-asyncio | >=1.4.0 | Async test support | Low |
| pytest-timeout | >=2.4.0 | Test timeouts | Low |

### AI Tooling

| Package | Version Constraint | Purpose | Risk |
|---------|-------------------|---------|------|
| graphifyy | >=0.8.27 | Knowledge graph CLI | Medium (third-party, less common) |

---

## Findings

### DEP-001 [HIGH] — No Python Lockfile

**Issue:** `requirements.txt` uses minimum-version constraints (`>=`). There is no `requirements.lock` or `pip-compile`-generated lockfile. This means:
- Different CI runs can install different package versions
- A malicious transitive dependency update could be silently included
- Reproducibility is not guaranteed across environments

**Fix:**
```bash
pip install pip-tools
pip-compile requirements.txt --output-file requirements.lock
# Use requirements.lock in CI and production
```

**Priority:** High

---

### DEP-002 [HIGH] — `playwright` as a Runtime Dependency

**Issue:** `playwright>=1.55.0` is a very large dependency (downloads Chromium ~150MB) that is only needed for the scanner feature (`services/scanner.py`). It adds significant image size, attack surface, and install time to deployments that don't use scanning.

**Fix:** 
1. Move `playwright` to an optional dependency: `pip install local-llm-server[scanner]`
2. Or gate its import with a try/except and a clear error message
3. Ensure `Dockerfile` uses a browser-enabled image only for scanner workloads

**Priority:** High

---

### DEP-003 [MEDIUM] — `boto3` Unconditional Install

**Issue:** `boto3>=1.43.19` is only needed for AWS Bedrock provider. It's a large package with many AWS sub-dependencies but is installed unconditionally.

**Fix:** Gate behind optional extra: `pip install local-llm-server[bedrock]`

**Priority:** Medium

---

### DEP-004 [MEDIUM] — `graphifyy` Third-Party Package

**Issue:** `graphifyy>=0.8.27` is a third-party package used for knowledge graph generation. It is a non-standard package (not widely known) used in production hooks. Its security posture and maintenance status are unclear.

**Fix:**
1. Audit `graphifyy` source code and maintainership
2. Pin to exact version: `graphifyy==0.8.27`
3. Consider vendoring or replacing with an internal implementation

**Priority:** Medium

---

### DEP-005 [MEDIUM] — `curl_cffi` Unusual Dependency

**Issue:** `curl_cffi>=0.15.0` is used for advanced HTTP client capabilities (TLS fingerprinting bypass). This is unusual in a server context and may indicate use for scraping. The package is less audited than `httpx` or `requests`.

**Fix:** Audit all usages of `curl_cffi`. Replace with `httpx` where possible. Remove if unused.

**Priority:** Medium

---

### DEP-006 [MEDIUM] — `pillow` CVE History

**Issue:** `pillow` has a history of CVEs (buffer overflows, parser vulnerabilities). The minimum version `>=12.2.0` is recent, but without pinning, a new vulnerability release won't automatically be picked up in existing deployments.

**Fix:** Pin to latest patched version. Add `pip-audit` step to CI.

**Priority:** Medium

---

### DEP-007 [LOW] — Duplicate HTTP Clients

**Issue:** The project uses three HTTP client libraries: `httpx`, `requests`, and `curl_cffi`. This increases attack surface and maintenance burden.

**Fix:** Standardize on `httpx` for all async code. Remove `requests` (or keep only for sync contexts that can't use httpx). Remove `curl_cffi` if unused.

**Priority:** Low

---

### DEP-008 [LOW] — `motor` + `pymongo` Both Present

**Issue:** Both `motor` (async MongoDB) and `pymongo` (sync MongoDB) are installed. The codebase should use `motor` for all async operations. Having both increases attack surface.

**Fix:** Audit for any sync `pymongo` calls in async contexts. Remove if all usage migrated to `motor`.

**Priority:** Low

---

## Frontend Dependencies (`frontend/package.json`)

**Status:** Not fully audited. The following observations apply:

### FE-DEP-001 [HIGH] — CRA (Create React App) is Deprecated

**Issue:** The frontend uses Create React App (CRA), which was officially abandoned by the React team in 2023. It uses Webpack 4, is slower than Vite, and has known vulnerabilities in its toolchain.

**Fix:** Migrate to Vite + React. See Vite migration guide.

**Priority:** High (medium-term)

---

### FE-DEP-002 [MEDIUM] — `--legacy-peer-deps` in CI

**Issue:** The CI workflow uses `npm install --legacy-peer-deps`. This flag bypasses peer dependency conflict resolution and can result in incompatible package versions being installed silently.

**Fix:** Resolve peer dependency conflicts properly rather than bypassing them.

**Priority:** Medium

---

## Dependency Audit Action Plan

| Priority | Action | Owner |
|----------|--------|-------|
| Immediate | Generate `requirements.lock` with `pip-compile` | DevOps |
| Immediate | Add `pip-audit` to CI pipeline | Security |
| Sprint 1 | Move `playwright` to optional extra | Dev |
| Sprint 1 | Move `boto3` to optional extra | Dev |
| Sprint 1 | Audit and pin `graphifyy` | Security |
| Sprint 2 | Consolidate HTTP clients → `httpx` | Dev |
| Sprint 2 | Resolve CRA deprecation (Vite migration) | Frontend |
| Sprint 3 | Audit `curl_cffi` usage | Dev |
| Sprint 3 | Resolve `--legacy-peer-deps` conflicts | Frontend |

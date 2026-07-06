# ENGINEERING_STANDARDS.md — Coding, Security & Testing Standards

> **Every PR must comply with these standards. CI enforces them automatically.**
> Violations are blocking — no exceptions.

---

## 1. Coding Standards

### Naming conventions
| Type | Convention | Example |
|------|-----------|---------|
| Python files | `snake_case.py` | `brain_config_store.py` |
| Python classes | `PascalCase` | `BrainConfigStore` |
| Python functions | `snake_case` | `get_brain_config()` |
| Python constants | `UPPER_SNAKE` | `DEFAULT_FREE_NVIDIA_MODEL` |
| JS files | `PascalCase.jsx` or `camelCase.js` | `DoctorScreen.jsx`, `api.js` |
| JS components | `PascalCase` | `DoctorScreen` |
| JS functions | `camelCase` | `getBackendUrl()` |
| JS constants | `UPPER_SNAKE` | `PRODUCTION_WORKER_URL` |
| CSS classes | `kebab-case` | `app-button-secondary` |
| env vars | `UPPER_SNAKE` | `NVIDIA_API_KEY` |
| API paths | `kebab-case` for multi-word | `/api/activation/settings` |

### Import rules
```python
# Python — standard import order
from __future__ import annotations          # 1. Future
import os, sys, logging                      # 2. Stdlib
import httpx, pydantic                       # 3. Third-party
from services.brain_config_store import ...  # 4. Local (absolute)
from .helpers import ...                     # 5. Local (relative, same package only)
```

```javascript
// JavaScript — import order
import React from 'react';                    // 1. React
import { useNavigate } from 'react-router';   // 2. Third-party
import { useAuth } from '../AuthContext';     // 3. Local (relative)
import { API } from '../api';                 // 4. Local (utilities)
```

### Function rules
- **Max 50 lines** per function — extract helpers if longer
- **Single responsibility** — one function, one job
- **Type hints** on all Python functions (use `from __future__ import annotations`)
- **Docstrings** on all public functions (Google style)
- **No `import *`** — explicit imports only

### File rules
- **Max 500 lines** per Python file — split if larger (exception: `backend/server.py` is being migrated)
- **Max 300 lines** per JSX component — extract sub-components
- **No commented-out code** — delete it, git preserves history
- **No `print()`** — use `logging` (Python) or `console.log` (JS, dev only)

### Error handling
```python
# Python — never bare except
try:
    result = await api_call()
except SpecificError as exc:
    log.warning("API call failed: %s", exc)
    return fallback
except Exception as exc:  # noqa: BLE001 — last resort
    log.exception("Unexpected error in api_call")
    raise  # re-raise unexpected errors
```

```javascript
// JavaScript — always handle both success and error
try {
  const { data } = await API.get('/endpoint');
  setData(data);
} catch (err) {
  setError(err?.response?.data?.detail || err?.message || 'Unknown error');
}
```

---

## 2. Logging Standards

### Log levels
| Level | When to use |
|-------|-------------|
| `DEBUG` | Detailed diagnostic info (watchdog notifications, cache hits) |
| `INFO` | Normal operations (startup, config changes, task dispatched) |
| `WARNING` | Recoverable issues (provider 429, fallback triggered, cache miss) |
| `ERROR` | Unexpected failures (NVIDIA 410, DB connection lost) |
| `CRITICAL` | System-wide failures (startup crash, all providers down) |

### Log format
```python
log.info("Brain config updated by %s: provider=%s model=%s", actor, provider, model)
log.warning("Provider %s placed on cooldown for %ds", provider_id, secs)
log.error("NVIDIA NIM returned 410 Gone — endpoint/model permanently removed")
```

### Rules
- Never log secrets (API keys, tokens, passwords)
- Always include context (provider ID, task ID, user ID)
- Use `%s` formatting (not f-strings) for log messages — lazy evaluation

---

## 3. Security Standards

### Secrets management
- **No secrets in code** — `os.environ.get()` only, in config modules
- **No secrets in logs** — never log API keys, tokens, passwords
- **No secrets in git** — `.env` is in `.gitignore`, `.env.example` has placeholder values only
- **Secrets validation at startup** — fail fast if required secrets are missing

### Authentication
- Every mutating endpoint requires `get_current_user` (JWT) or `_require_admin`
- API key auth (`verify_api_key`) for proxy endpoints only
- Service token (`X-Service-Token`) for Telegram bot → backend calls only
- OAuth tokens are exchanged server-side (never expose client secrets to frontend)

### Authorization
```python
# Admin-only endpoints
_require_admin(user)  # raises 403 if not admin

# Per-user scoping
owner_id = None if _is_admin(user) else _resolve_user_id(user)
tasks = await store.list_tasks(owner_id=owner_id)
```

### Headers
- `Cache-Control: no-store` on all API responses (prevent CDN caching)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- CORS: only allow configured origins

### Rate limiting
- API key users: 100 req/min (configurable)
- JWT users: 60 req/min
- OAuth callbacks: 10 req/min per IP

---

## 4. Testing Standards

### Test structure
```
tests/
├── unit/           # Pure function tests (no DB, no network)
├── integration/    # Tests with DB (MongoDB or SQLite)
├── e2e/            # End-to-end browser tests (Playwright)
└── conftest.py     # Shared fixtures
```

### Test rules
1. **Every new endpoint** must have at least one test
2. **Every bug fix** must include a regression test
3. **Tests must be hermetic** — no shared mutable state between tests
4. **Tests must not depend on external services** (mock NVIDIA API, etc.)
5. **Tests must run in < 5 seconds** each (use `--timeout=120` as safety net)
6. **Test names** must be descriptive: `test_<what>_<condition>`

### Fixture rules
```python
@pytest.fixture
def client() -> TestClient:
    """Function-scoped TestClient with motor reset."""
    from db import reset_store
    reset_store()
    with TestClient(backend_app) as c:
        yield c

@pytest.fixture(autouse=True)
async def reset_provider_cooldowns():
    """Clear cooldown + probe-lock state before every test."""
    await clear_cooldowns()
    await clear_all_locks()
    yield
    await clear_cooldowns()
    await clear_all_locks()
```

### Frontend test rules
```javascript
// Mock API calls — never hit real backend
jest.mock('../api', () => ({
  API: { get: jest.fn(), post: jest.fn() },
  getBackendUrl: jest.fn(() => 'https://test.example.com'),
}));

// Test user-visible behaviour, not implementation details
test('shows spinner when social login button is clicked', () => {
  render(<LoginPage />);
  const button = screen.getByText('GitHub');
  fireEvent.click(button);
  expect(screen.getByText('Redirecting…')).toBeInTheDocument();
});
```

---

## 5. CI/CD Standards

### PR requirements
- ✅ All 22 CI checks pass
- ✅ `CHANGELOG.md` + `docs/changelog.md` updated (parity)
- ✅ `compileall` clean
- ✅ `loop_registry audit --check` drift-free (if touching workflows)
- ✅ No new Bandit security alerts
- ✅ No hardcoded secrets
- ✅ Squash-merge to master

### Commit message format
```
<type>(<scope>): <description>

<body>

<footer>
```

Types: `feat`, `fix`, `chore`, `docs`, `test`, `ci`, `refactor`, `perf`
Scopes: `auth`, `provider`, `scheduler`, `voice`, `frontend`, `worker`, etc.

### Branch naming
- Feature: `feat/<description>`
- Fix: `fix/<description>`
- Docs: `docs/<description>`

---

## 6. Performance Standards

| Metric | Target | Current |
|--------|--------|---------|
| Cold start | < 30s | ~15s |
| Dashboard initial load | < 3s | ~2s |
| API response (cached) | < 100ms | ~50ms |
| API response (uncached) | < 500ms | ~200ms |
| Scheduler tick | < 5s | ~2s |
| Frontend bundle size | < 1MB | ~850KB |
| Test suite (full) | < 120s | ~90s |

### Caching strategy
- Dashboard data: TTL cache (8s for tasks, 60s for autonomy status)
- Provider health: in-memory cache (polled every 30s)
- Brain config: in-memory cache (invalidated on change)
- Static assets: Cloudflare CDN (cache-control headers)

### Database indexes
- `users.email` (unique)
- `tasks.user_id`, `tasks.status`, `tasks.owner_id`
- `activity_log.created_at`
- `api_keys.key_hash` (unique)
- `oauth_states.state` (TTL 10min)

---

## 7. Documentation Standards

### Every module should have
1. **Module docstring** — what it does, why it exists
2. **Function docstrings** — for all public functions (Google style)
3. **README** — for complex modules (optional, in module directory)

### Architecture docs
- `CLAUDE.md` — operating manual (updated when architecture changes)
- `ARCHITECTURE.md` — target architecture (updated when design changes)
- `ENGINEERING_STANDARDS.md` — this document (updated when standards change)
- `REWRITE_PLAN.md` — migration plan (updated after each phase completes)
- `CHANGELOG.md` + `docs/changelog.md` — every PR (parity enforced)

### Decision records
When making a significant architectural decision, add an ADR:
```
docs/adr/
├── 001-use-mongodb-as-primary-db.md
├── 002-cloudflare-worker-for-frontend.md
└── 003-merge-hermes-into-backend.md
```

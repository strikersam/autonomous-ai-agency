# ENGINEERING_STANDARDS.md — Patterns & Reference

> **The rules are in [`CLAUDE.md` §1](CLAUDE.md#1-the-rules).** This file holds the
> worked examples and lookup tables behind them — what a conforming fixture looks like,
> which log level means what, where the indexes are. Nothing here is binding on its own,
> and nothing here restates a rule.
>
> Conventions that you can read off the surrounding code — file naming, import order,
> component structure — are not documented here either. Match what the neighbouring file
> does.

---

## Log levels

| Level | When |
|-------|------|
| `DEBUG` | Detailed diagnostics — watchdog notifications, cache hits |
| `INFO` | Normal operations — startup, config change, task dispatched |
| `WARNING` | Recoverable — provider 429, fallback triggered, cache miss |
| `ERROR` | Unexpected failure — NVIDIA 410, DB connection lost |
| `CRITICAL` | System-wide — startup crash, all providers down |

```python
log.info("Brain config updated by %s: provider=%s model=%s", actor, provider, model)
log.warning("Provider %s placed on cooldown for %ds", provider_id, secs)
log.error("NVIDIA NIM returned 410 Gone — endpoint/model permanently removed")
```

Always carry context — provider ID, task ID, user ID. Rules 6 and 26 cover the rest.

---

## Error handling

```python
# Python — name the exception you expect; re-raise the ones you don't
try:
    result = await api_call()
except SpecificError as exc:
    log.warning("API call failed: %s", exc)
    return fallback
except Exception:  # noqa: BLE001 — last resort
    log.exception("Unexpected error in api_call")
    raise
```

```javascript
// JavaScript — handle both paths, and unwrap the API's error shape
try {
  const { data } = await API.get('/endpoint');
  setData(data);
} catch (err) {
  setError(err?.response?.data?.detail || err?.message || 'Unknown error');
}
```

---

## Authorization patterns

```python
# Admin-only endpoint
_require_admin(user)                 # raises 403 if not admin

# Per-user scoping — admins see everything, users see their own
owner_id = None if _is_admin(user) else _resolve_user_id(user)
tasks = await store.list_tasks(owner_id=owner_id)
```

Rate limits in force: API-key users 100 req/min (configurable), JWT users 60 req/min,
OAuth callbacks 10 req/min per IP.

---

## Test fixtures

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
    """Clear cooldown + probe-lock state before and after every test."""
    await clear_cooldowns()
    await clear_all_locks()
    yield
    await clear_cooldowns()
    await clear_all_locks()
```

```javascript
// Frontend — mock the API module, never hit a real backend
jest.mock('../api', () => ({
  API: { get: jest.fn(), post: jest.fn() },
  getBackendUrl: jest.fn(() => 'https://test.example.com'),
}));

// Assert on what the user sees, not on internals
test('shows spinner when social login button is clicked', () => {
  render(<LoginPage />);
  fireEvent.click(screen.getByText('GitHub'));
  expect(screen.getByText('Redirecting…')).toBeInTheDocument();
});
```

Test layout, environment flags, and the hermeticity requirement are rules 31–33.

---

## Commit messages

```
<type>(<scope>): <description>

<body>
```

Types: `feat`, `fix`, `chore`, `docs`, `test`, `ci`, `refactor`, `perf`, `style`,
`revert`, `build`. Scopes: `auth`, `provider`, `scheduler`, `voice`, `frontend`,
`worker`, and so on.

The type is not cosmetic — the `commit-msg` hook exempts `chore:`, `docs:`, `style:`,
`ci:`, `test:`, `revert:`, `build:`, and `wip:` from the changelog requirement and blocks
everything else that touches code (rule 34).

Branches: `feat/<description>`, `fix/<description>`, `docs/<description>`.

---

## Performance targets

Aspirational, not gated. Measure before quoting these — the "current" column was last
sampled some time ago and nothing keeps it fresh.

| Metric | Target |
|--------|--------|
| Cold start | < 30s |
| Dashboard initial load | < 3s |
| API response, cached | < 100ms |
| API response, uncached | < 500ms |
| Scheduler tick | < 5s |
| Frontend main bundle | < 1MB |
| Full test suite | < 120s |

Caching in place: dashboard data on a TTL cache (8s tasks, 60s autonomy status);
provider health in memory, polled every 30s; brain config in memory, invalidated on
change; static assets on the Cloudflare CDN.

---

## Database indexes

| Collection | Index |
|------------|-------|
| `users` | `email` (unique) |
| `tasks` | `user_id`, `status`, `owner_id` |
| `activity_log` | `created_at` |
| `api_keys` | `key_hash` (unique) |
| `oauth_states` | `state` (TTL 10 min) |

---

## Architecture decision records

Significant decisions get an ADR in `docs/adr/`:

```
docs/adr/
├── 001-use-mongodb-as-primary-db.md
├── 002-cloudflare-worker-for-frontend.md
└── 003-merge-hermes-into-backend.md
```

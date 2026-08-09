# Platform Controls

**Dashboard → System → Platform Controls** (`/controls`, admin only).

The screen where feature switches and multi-option settings are chosen, instead
of editing ~100 `true`/`false` rows in the Render environment editor and waiting
for a redeploy.

- Catalogue: [`packages/config/control_registry.py`](../packages/config/control_registry.py)
- Override layer: [`packages/config/control_overrides.py`](../packages/config/control_overrides.py)
- API: [`backend/platform_controls_router.py`](../backend/platform_controls_router.py)
- UI: [`frontend/src/pages/PlatformControlsPage.js`](../frontend/src/pages/PlatformControlsPage.js)

---

## How a value is resolved

```
DB override  →  Render environment  →  code default
```

A control with no dashboard override behaves exactly as it did before this
screen existed. Overrides live in one `app_settings` document
(`platform_control_overrides`) and are re-applied on every boot, near the top of
the FastAPI lifespan — deliberately before `start_background_services()` builds
the runtime manager and starts the autonomy loops, so an override of
`RUNTIME_DEFAULT` or `AGENCY_CEO_ENABLED` is already in place when they read it.

Each control shows its source in the UI:

| Badge | Meaning |
|-------|---------|
| **Dashboard** | An override is set here. It wins over Render. |
| **Render env** | No override; the value comes from the Render environment. |
| **Code default** | Neither is set; the value is the default in the source. |

The reset button (↺) drops the override and hands the key back to Render.

---

## Live vs restart-required

Saving a control always persists and applies it to the process environment. What
differs is whether code that already ran sees the new value:

- **Live** — the value is re-read at each use, or comes from the `settings`
  singleton, which is re-initialised in place on every save. Takes effect
  immediately.
- **Restart required** — the reader captured the value at import time or baked
  it into a cached singleton (module-level constants, adapter registration).
  The UI badges these and the save response names them.

There is no third state: a control never claims to be live when it is not.

Runtime *routing policy* keys (`RUNTIME_DEFAULT`, the per-task-type routes,
paid-escalation guards) are live — they are pushed through the runtime manager's
own `update_policy` API. Runtime *registration* keys (`RUNTIME_*_ENABLED`) need a
restart, because registration happens once when the manager is built.

### Across processes

"Live" means live *in the process that handled the save* — the web service.
Production also runs `local-llm-server-worker` (`worker_main.py`), a separate
process running the same background services. It loads and applies the same
overrides at its own startup, so a change reaches it on its next restart, not
immediately. If a control governs an autonomy loop and the worker is deployed,
restart the worker for the change to take hold there.

---

## Groups

| Group | What it covers |
|-------|----------------|
| Agent Runtimes | Default and per-task-type runtime, which adapters are registered, paid-escalation guards, health poll interval |
| Brain & Model Routing | Brain preference, provider routing strategy, caching, circuit breaker, paid-brain guard, Ollama thinking effort |
| Autonomy Loops | CEO loop, self-healing, log monitor, trend watcher, self-repo shipping, issue triage, workflow mode |
| Agent Loop Budgets | Max steps, time budget, task timeout, dispatch concurrency, verification and memory switches |
| Governance & Safety | Governance layer, sandbox backend, approvals, guardrails, output filter, outbound URL guard, activation |
| Platform Operations | Render ops loop, Render write permission, operational-incident thresholds |
| Integrations | Telegram, FreeBuff, SAM voice, browser automation, SEO crawler backend, published model catalogue |
| Observability & Proxy | OpenTelemetry, proxy response-shaping switches |

---

## What is deliberately **not** here

Secrets (`*_API_KEY`, `*_TOKEN`, `JWT_SECRET`, `ADMIN_PASSWORD`) and
infrastructure endpoints (`MONGO_URL`, `*_BASE_URL`) stay environment-only, per
the repository constitution. They are not in the catalogue, and the catalogue is
an allow-list — the override endpoint validates every key against it before
writing, so it cannot be used to set a secret or as a general `os.environ` write
primitive. A test asserts no secret-shaped key ever enters the catalogue.

---

## Adding a control

1. Confirm the environment variable is actually read somewhere in the Python
   source. `tests/test_platform_controls.py` fails the build otherwise.
2. Add a `ControlSpec` to the relevant tuple in `control_registry.py`. Use
   `_toggle` / `_number` helpers, or `ControlSpec` directly for a choice.
3. Set `live=True` **only** after checking the read site: a module-level
   constant or a cached singleton is not live.
4. If the control is inert without a secret, list it in `requires` so the UI can
   say so instead of the operator wondering why nothing happened.
5. If a change should reach a running singleton, add the key to `_POLICY_KEYS`
   (or the equivalent) in `control_overrides.py` and push only that key —
   never rewrite a whole policy object, or you will clobber state the singleton
   set for itself.

---

## API

All three endpoints require an admin role.

```
GET    /api/admin/platform-controls          → {groups, control_count, override_count}
PUT    /api/admin/platform-controls          ← {"updates": {"RUNTIME_DEFAULT": "hermes"}}
DELETE /api/admin/platform-controls/{key}    → reverts the key to the environment
```

`PUT` validates the whole batch before writing anything, so one invalid field
rejects the request with a 400 rather than half-applying it. Both mutating
responses carry `changed`, `restart_required`, and a fresh snapshot.

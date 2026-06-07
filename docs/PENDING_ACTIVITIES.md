# Pending Activities — Implementation Playbook

> **Audience:** any engineer or AI agent picking up this work cold.
> **Goal:** finish turning `local-llm-server` into a fully autonomous, self-improving AI
> agency. This document is **prescriptive** — follow each task top-to-bottom. Every task
> lists the exact files, the steps, the acceptance criteria, and the tests to add.
>
> **Ground rules (apply to every task):**
> 1. Branch from `master`: `git checkout -b agent/<short-task-name>`. **Never push to master.**
> 2. `pip install -r requirements.txt` (skip the debian-managed `wheel`/`setuptools`/`PyJWT`
>    if `--ignore-installed` is needed). Run `pytest -x` for a baseline **before** changing code.
> 3. Add/extend tests in `tests/` for every change. Run the affected suites with
>    `SKIP_DB_TESTS=1 STORAGE_BACKEND=sqlite pytest -q tests/<file>` (no MongoDB in CI-less envs).
> 4. Update `docs/changelog.md` under `## [Unreleased]` (CI **blocks** merge without it).
> 5. Keep Bandit clean: the Security Gate fails if total alerts increase vs `master`.
>    - Don't pass secret-looking string **literals** as kwargs named `token`/`password`/`secret`
>      (Bandit **B106**). Source them from `os.environ.get(...)` or a variable instead.
>    - For vetted `subprocess` calls use list-form argv (no `shell=True`) and add
>      `# nosec B603,B607` with a one-line justification.
> 6. Open a PR against `master`. Do **not** self-merge — a human merges.
> 7. For changes to `admin_auth.py`, `key_store.py`, `agent/tools.py`, `agent/github_tools.py`,
>    or any auth/secret path, follow `.claude/skills/risky-module-review`.

---

## Context: what already works (do NOT redo)

The execution spine and the reported UI/data bugs were fixed in PR #399:
- Orchestrator-mode block lifted for the **sanctioned** callers (`TaskExecutionCoordinator.execute`,
  `Agency.run_cycle`); direct `/runtimes/{id}/execute` stays gated.
- Free **Kimi web-bridge provider** abstraction (`providers/kimi_bridge.py`) — *endpoint mode only*.
- Hermes/Goose/Aider registered by default (graceful when their CLI/sidecar is absent).
- Task **follow-up/rerun** (`POST /api/tasks/{id}/follow-up`) + conversation carry-over.
- **Quick-notes → Tasks**, **company priorities** persisted, **in-memory alerts feed**,
  **Doctor skills-repo check**, **viewport-aware chat dropdowns**, **Skills tab switcher**.
- **PR-autonomy gate** (`agent/autonomy_gate.py`) wired into `GitHubTools` (agents never push
  to protected branches or merge).
- **Self-onboarding bootstrap** (`services/self_bootstrap.py`) registers the platform as a company.

The items below are the **remaining** work, in priority order.

---

## P0 — Make autonomy real in production

### Task 1 — Build the actual Kimi web-bridge service (free inference, no API key)

**Why:** `providers/kimi_bridge.py` only emits an OpenAI-compatible `ProviderConfig` pointing at
`KIMI_BRIDGE_URL`. Nothing actually serves that URL yet, so with no paid keys the agents still
have no model. This task builds the small service that backs the bridge.

**Deliverable:** a standalone OpenAI-compatible HTTP service that proxies chat-completions to
Kimi/Moonshot via a logged-in **browser session** (no paid API key), runnable separately from the
main backend.

**Files to create:**
- `services/kimi_bridge_server/__init__.py`
- `services/kimi_bridge_server/app.py` — FastAPI app exposing `POST /v1/chat/completions`
  (and `GET /v1/models`) in OpenAI format.
- `services/kimi_bridge_server/browser_driver.py` — drives kimi.com with Playwright
  (already a dependency, see `requirements.txt`): holds a persistent context, submits the prompt,
  streams the answer back.
- `services/kimi_bridge_server/README.md` — how to log in once and run it.
- `Dockerfile.kimibridge` — Playwright base image + this app.
- `tests/test_kimi_bridge_server.py`.

**Steps:**
1. Implement `app.py` with a Pydantic request model matching the OpenAI chat-completions schema
   (messages, model, temperature, stream). Map it to `browser_driver.ask(messages) -> str`.
2. `browser_driver.py`: use Playwright with a **persistent user-data dir**
   (`PLAYWRIGHT_USER_DATA_DIR`) so the Kimi login cookie survives restarts. Provide a
   `login()` helper (headed) for the one-time manual login, and `ask()` (headless) for inference.
   Add a queue/lock so concurrent requests serialize on the single browser tab.
3. Bearer-auth the service with `KIMI_BRIDGE_TOKEN` (compare with `hmac.compare_digest`); reject
   if unset in production.
4. Return responses in OpenAI shape (`choices[0].message.content`, `usage` best-effort).
5. Wire env: the main backend already reads `KIMI_BRIDGE_URL`/`KIMI_BRIDGE_TOKEN`. Document that
   `KIMI_BRIDGE_ENABLED=true` + `KIMI_BRIDGE_URL=http://kimibridge:8011/v1` connects them.

**Acceptance criteria:**
- `curl -H "Authorization: Bearer $T" -d '{"model":"kimi-k2.6","messages":[{"role":"user","content":"hi"}]}' localhost:8011/v1/chat/completions` returns a valid OpenAI-shaped reply.
- With the bridge up and `KIMI_BRIDGE_ENABLED=true`, a task created via the API completes
  (non-BLOCKED) and `decision.selected_runtime_id` shows `internal_agent` using the bridge provider.

**Tests:** mock the browser driver (`monkeypatch browser_driver.ask`) and assert the HTTP layer
returns OpenAI-shaped JSON and enforces the bearer token. Do **not** hit the real network in tests.

**Risks:** never auto-launch a browser inside the main backend (`KIMI_BRIDGE_MODE=browser` must stay
opt-in). Keep this as a separate process/container.

---

### Task 2 — Always-on Worker service (24×7 without the web process)

**Why:** the `TaskDispatcher`, CEO `Agency` loop, and `SCHEDULER` run as asyncio tasks **inside the
web process**. On Render the web service sleeps on inactivity, so "24×7" is impossible.

**Files to create/modify:**
- `worker_main.py` (repo root) — a script that starts `RuntimeManager`, `TaskDispatcher`,
  the `Agency`, and `SCHEDULER` **without** the FastAPI HTTP server, and runs forever.
- `render.yaml` — add a second service of `type: worker` running `python worker_main.py`.
- `Procfile` (if present) — add `worker: python worker_main.py`.
- `docs/runbooks/worker.md` — operations notes.

**Steps:**
1. Extract the startup wiring from `backend/server.py` `lifespan` (runtime manager + dispatcher +
   scheduler + `ensure_self_company`) into a reusable `async def start_background_services()` in a
   new `services/background.py`, and call it from **both** the web `lifespan` and `worker_main.py`.
   Guard with an env flag `RUN_BACKGROUND_IN_WEB` (default `true` today; set to `false` once the
   worker is deployed, so work isn't double-processed).
2. `worker_main.py`: `asyncio.run()` an entrypoint that calls `start_background_services()` and
   awaits forever, with graceful shutdown on SIGTERM.
3. Ensure the worker and web share the **same database** (see Task 3) so tasks created via the API
   are visible to the worker.

**Acceptance criteria:** killing/sleeping the web service does not stop task execution or the CEO
loop when the worker is running; no task is executed twice (claim logic in
`TaskExecutionCoordinator._claim_task` already guards within a process — cross-process needs Task 4).

**Tests:** unit-test `start_background_services()` wiring with stubs (mirror
`tests/test_backend_runtime_bootstrap.py`).

---

### Task 3 — Durable managed datastore (stop losing state on redeploy)

**Why:** SQLite on Render's ephemeral disk is wiped on every redeploy; companies, tasks,
knowledge, and memory vanish. The code already supports MongoDB.

**Files to modify:** none in code (it's config) — but add `docs/runbooks/datastore.md`.

**Steps:**
1. Provision MongoDB Atlas (free tier) **or** Render Postgres. For Mongo: set `MONGO_URL` and
   `DB_NAME=llm_wiki_dashboard` on **both** the web and worker services.
2. Verify `services/company_graph_store.py` and `tasks/store.py` pick the Mongo backend when
   `MONGO_URL` is set (`STORAGE_BACKEND` unset/`mongodb`).
3. Add a startup readiness log line that states which backend is active.

**Acceptance criteria:** create a company, redeploy, confirm it still exists. `/api/doctor` Company
Graph check shows persisted companies after a restart.

**Tests:** none new (infra) — but keep `SKIP_DB_TESTS=1` working for CI without Mongo.

---

### Task 4 — Shared state across web + worker (Redis)

**Why:** once web and worker are separate processes (Task 2), in-memory state must be shared:
`TaskExecutionCoordinator._active_task_ids` (claim lock), provider cooldowns
(`provider_router.mark_provider_failed`), and rate limits. Otherwise both processes can run the
same task or mis-track cooldowns.

**Files to create/modify:**
- `services/shared_state.py` — a small abstraction with two backends: in-memory (default) and
  Redis (when `REDIS_URL` is set). Functions: `claim(key, ttl) -> bool`, `release(key)`,
  `cooldown_set/get`, `incr_window` for rate limits.
- Modify `tasks/service.py` `_claim_task`/`_release_task` to use `shared_state.claim/release`.
- Modify `provider_router.py` cooldown helpers to use `shared_state` when configured.

**Steps:**
1. Implement the abstraction; default to the current in-memory behaviour so nothing changes until
   `REDIS_URL` is set.
2. Swap the call sites. Keep signatures identical.
3. Add `REDIS_URL` to `.env.example` and the runbook.

**Acceptance criteria:** with two worker processes pointed at the same Redis, a single task is
executed exactly once. With `REDIS_URL` unset, behaviour is byte-for-byte the same as today.

**Tests:** `tests/test_shared_state.py` — in-memory claim/release semantics; mock Redis with
`fakeredis` for the Redis path.

---

## P1 — Close the remaining product gaps

### Task 5 — Custom skills & workflows (create, not just view)

**Why:** the Skills page can now reach live skills, but there is still **no way to add a custom
skill or workflow**. The frontend has buttons that aren't wired.

**Files to create/modify:**
- Backend: add to the skills API (near `backend/server.py` `/api/skills` and
  `services/skill_bindings.py`):
  - `POST /api/skills/custom` — create a custom skill (id, name, description, category, safety,
    inputs/outputs, specialist_families). Persist to the company graph or a `custom_skills`
    collection/table.
  - `GET /api/skills/custom`, `DELETE /api/skills/custom/{id}`.
  - `POST /api/company/workflows` — create a custom workflow (name, trigger, ordered steps each
    referencing a skill id). Persist on the `CompanyGraph`.
- Frontend `frontend/src/v5/screens/SkillsScreen.jsx`: wire the existing "add" affordances to these
  endpoints; add a simple create form (name, description, category, steps).
- `frontend/src/api.js`: add `createCustomSkill`, `listCustomSkills`, `deleteCustomSkill`,
  `createWorkflow`.

**Steps:**
1. Define Pydantic models for `CustomSkill` and `CustomWorkflow` (reuse `models/company_graph.py`
   `KnowledgeItem`/`Workflow` patterns; keep `extra="forbid"`).
2. Implement CRUD endpoints with the existing auth dependency and per-user/company scoping
   (`_resolve_user_id`, `get_company_access`).
3. Wire the frontend form + list; after create, refresh the Registry tab.
4. Validate the React build: `cd frontend && CI=false npm run build`.

**Acceptance criteria:** a user can create a custom skill and see it in the Registry tab; create a
workflow referencing it; both persist across reload.

**Tests:** `tests/test_custom_skills_api.py` (create/list/delete, auth required, validation errors).

---

### Task 6 — Deeper website/repo scanning (more than "2 systems")

**Why:** the operator reported the URL scan finds only ~2 systems. `services/scanner.py` and
`services/specialist.py` over-index on e-commerce and shallow signals.

**Files to modify:** `services/scanner.py`, `services/specialist.py`, `services/technologies.json`.

**Steps:**
1. In `scanner.py`, broaden detection beyond e-commerce keywords: parse `<meta generator>`,
   script/src hosts, response headers (`Server`, `X-Powered-By`, `Via`, CDN headers), DNS records
   (already uses `dnspython`), and common framework fingerprints. Map each to a `DetectedSystem`
   with a `confidence` and `evidence` string.
2. Add **repo-stack detection**: read `requirements.txt`/`package.json`/`Dockerfile`/`wrangler.*`
   from the linked GitHub repo and emit systems (FastAPI, React, Cloudflare Workers, Render,
   Ollama, MongoDB, etc.). For *this* platform that should yield ≥6 systems, not 2.
3. In `specialist.py`, make `_get_default_capabilities`/`_get_default_tools` **domain-aware**:
   choose the family set from detected systems instead of defaulting to e-commerce. Keep e-commerce
   only when an e-commerce system is actually detected.
4. Extend `technologies.json` with the new fingerprints.

**Acceptance criteria:** scanning `https://local-llm-server.strikersam.workers.dev` + the repo
yields ≥6 detected systems and provisions non–e-commerce specialists (e.g. Backend/API, Frontend,
DevOps, QA, Security, Docs).

**Tests:** extend `tests/test_onboarding_provisioning.py` / add `tests/test_scanner_detection.py`
with fixture HTML/headers + a fake repo file set; assert detected system count and families.

---

### Task 7 — Knowledge base auto-reflect (ECC / Obsidian / graphify-style)

**Why:** repo changes, quick-notes, and scan results should flow into a queryable knowledge base
automatically. Today `KnowledgeItem` exists but is not populated.

**Files to create/modify:**
- `services/knowledge_ingest.py` — `record_event(company_id, source, title, content, tags)` that
  writes a `KnowledgeItem` (dedupe by `content_hash`) via `services/company_graph.add_knowledge_item`.
- Hooks: call it from `services/scanner.py` (after a scan), from the quick-note→task path in
  `backend/server.py`, and from a new post-merge/post-commit emitter.
- Optional retrieval upgrade: `services/knowledge_index.py` with embeddings (sqlite-vec or Chroma;
  see Task 8) and `GET /api/company/{id}/knowledge/search?q=`.

**Steps:**
1. Implement `record_event` with `content_hash` dedupe and `source` tagging
   (`automated_scan|quick_note|repo_change|manual`).
2. Add the call sites (scan complete, quick-note created, self-bootstrap connect task result).
3. Surface a "Knowledge" view in the frontend that lists recent items (read-only first).

**Acceptance criteria:** after a scan and a quick-note, `GET /api/company/{id}/graph` shows new
`knowledge` items; re-running the same scan does not duplicate them.

**Tests:** `tests/test_knowledge_ingest.py` — ingestion + dedupe; endpoint returns items.

---

### Task 8 — Vector retrieval for the knowledge base (self-learn)

**Why:** keyword listing isn't enough for agents to "learn and improve". Add semantic retrieval over
the knowledge base + `graphify-out/graph.json`.

**Files to create:** `services/knowledge_index.py` (embed + nearest-neighbour search), backed by
`sqlite-vec` (no external service) or `pgvector` if Task 3 chose Postgres.

**Steps:**
1. On `record_event`, compute an embedding (local model or a free provider) and store the vector.
2. Add `search(company_id, query, k)` and wire it into the agent's `BIND_CONTEXT` phase so tasks get
   relevant prior knowledge injected.
3. Gate behind `KNOWLEDGE_VECTOR_ENABLED` (default off) so it never breaks deploys without the dep.

**Acceptance criteria:** `search("how does routing work")` returns the routing knowledge items ranked
above unrelated ones. Disabled flag = no behaviour change.

**Tests:** `tests/test_knowledge_index.py` with a deterministic fake embedder.

---

### Task 9 — Finish the autonomy-gate wiring (defense in depth)

**Why:** `GitHubTools` is gated, but `LocalWorkspace.push`/`stage_and_commit` and the workspace
`open_pr` endpoint (`agent/github_tools.py` ~line 590-630) accept the per-call `agent_initiated`
flag but agent paths don't always set it.

**Files to modify:** `agent/github_tools.py` (workspace commit/PR endpoint), and any agent caller
that constructs a `LocalWorkspace` for autonomous work.

**Steps:**
1. Thread `agent_initiated=True` from agent-driven workspace operations into `LocalWorkspace.push`
   and `stage_and_commit`.
2. For the agent loop's PR-open path, ensure `head` is an `agent/...` branch via
   `autonomy_gate.agent_branch_name(...)` and `base` is the repo default branch.
3. Add a regression test that an agent-driven workspace push to `master` raises `AutonomyViolation`.

**Acceptance criteria:** no autonomous code path can push to a protected branch or merge a PR.

**Tests:** extend `tests/test_autonomy_gate.py`.

---

## P2 — ECC harness & polish

### Task 10 — ECC cross-harness adapter (currently PLANNED only)

**Why:** `.claude/skills/ecc-harness-patterns/SKILL.md` describes cross-harness orchestration that
isn't implemented.

**Files to create:** `agents/harness_adapter.py` (detect active harness from env, normalize
request/response), `.claude/state/harness-registry.json` (track harnesses + success rates), and
session lifecycle hooks under `.claude/hooks/session-*`.

**Steps:** implement harness detection + a registry the router can consult; extend
`router/model_router.py` to factor harness capability into model selection. Keep everything behind a
flag so default behaviour is unchanged.

**Acceptance criteria:** the router logs which harness it detected and selects an appropriate model;
registry updates after each session. **Run `router/` changes through `tests/test_model_router.py`.**

**Tests:** `tests/test_harness_adapter.py` + router test updates.

---

## How to verify the whole thing end-to-end (local, no external infra)

```bash
# 1. Backend on SQLite with the free bridge pointed at a local stub
SKIP_DB_TESTS=1 STORAGE_BACKEND=sqlite SELF_BOOTSTRAP_ENABLED=true \
  KIMI_BRIDGE_ENABLED=true KIMI_BRIDGE_URL=http://localhost:8011/v1 \
  uvicorn backend.server:app --port 8001
# 2. Create a task via the API and confirm it reaches a non-BLOCKED terminal state.
# 3. Submit a quick-note and confirm a Task appears (GET /api/tasks).
# 4. GET /api/doctor — Skills Repos + Company Graph checks green.
# 5. Full test gate:
SKIP_DB_TESTS=1 STORAGE_BACKEND=sqlite pytest -q
```

## Definition of done (per task)
- [ ] Tests added and green (`pytest -q` for the affected suites).
- [ ] `docs/changelog.md` updated under `## [Unreleased]`.
- [ ] Bandit total not increased vs `master` (Security Gate green).
- [ ] Frontend builds (`cd frontend && CI=false npm run build`) if UI changed.
- [ ] PR opened against `master`; **not** self-merged.

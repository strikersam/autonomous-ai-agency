# Worker Service — Operations Runbook

## Overview

The **always-on worker** (`worker_main.py`) runs the `RuntimeManager`,
`TaskDispatcher`, CEO `Agency` loop, and `SCHEDULER` **without** the FastAPI
HTTP server.  On Render's free tier the web service sleeps when idle (≥15 min
of no inbound traffic), stopping task execution.  The worker keeps running 24×7
regardless of web traffic.

---

## Architecture

```
┌──────────────────────────────────┐   ┌──────────────────────────────────┐
│  Web service (local-llm-server)  │   │  Worker (local-llm-server-worker)│
│  - FastAPI HTTP endpoints         │   │  - RuntimeManager                │
│  - Admin dashboard               │   │  - TaskDispatcher (poll every 10s)│
│  - RUN_BACKGROUND_IN_WEB=false   │   │  - AgentScheduler                │
└──────────────────────────────────┘   │  - CEO Agency loop               │
              ↓ same DB ↑              └──────────────────────────────────┘
        ┌─────────────┐
        │  MongoDB    │   (or SQLite for local dev)
        └─────────────┘
```

Both processes share the same database.  Tasks created via the API are
immediately visible to the worker's dispatcher.

---

## Deployment on Render

### First-time setup

1. Add the worker service from `render.yaml` (it's declared under `services`).
2. Set `MONGO_URL` on **both** the web and worker service to the same Atlas URL.
3. Once the worker is healthy, flip the web service env var:
   ```
   RUN_BACKGROUND_IN_WEB=false
   ```
   This stops the web process from also running background services.

### Verifying the worker is alive

```bash
# Check recent dispatcher logs
render logs --service local-llm-server-worker --tail 50

# Or POST a task via the API and confirm it reaches COMPLETED status
curl -X POST https://local-llm-server.onrender.com/api/tasks \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"title":"ping","description":"echo hello"}'
```

---

## Local development

The web process runs background services by default (`RUN_BACKGROUND_IN_WEB=true`).
You only need `worker_main.py` when testing the worker separately:

```bash
# Terminal 1 — web (no background services)
RUN_BACKGROUND_IN_WEB=false uvicorn backend.server:app --port 8001

# Terminal 2 — worker
STORAGE_BACKEND=sqlite python worker_main.py
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `RUN_BACKGROUND_IN_WEB` | `true` | Set `false` on the web service when the worker is running |
| `STORAGE_BACKEND` | `mongodb` | `sqlite` for local dev / `mongodb` for production |
| `MONGO_URL` | — | Required when `STORAGE_BACKEND=mongodb` |
| `REDIS_URL` | — | Optional; enables cross-process task claim locking (see Task 4) |

---

## Graceful shutdown

The worker handles `SIGTERM` (Render sends this before stopping a service) and
`SIGINT` (Ctrl-C).  It stops the dispatcher, waits for the current task to
finish, then exits cleanly.  Average shutdown time: <5 s.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Tasks stuck in PENDING | Worker not running | Check Render worker service logs |
| Tasks executed twice | Both web + worker running background services | Set `RUN_BACKGROUND_IN_WEB=false` on web |
| Worker crashes on startup | Missing `MONGO_URL` | Add env var or set `STORAGE_BACKEND=sqlite` |
| "DB bootstrap deferred" in logs | Transient Atlas connection issue | Harmless — worker retries next dispatcher cycle |

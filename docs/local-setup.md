# Run the agency locally

Two supported paths. Both run entirely on your machine — **no data leaves your
server**, no cloud account, no per-seat metering.

- [**One command** (recommended)](#one-command-recommended) — a single script that
  configures, installs, builds, and launches the full single-process agency.
- [**Docker Compose**](#docker-compose) — the multi-container topology (Ollama,
  Mongo, runtime sidecars, tunnel) closer to production.

> Prefer manual control? The step-by-step version and every configuration
> variable are in [platform-guide.md](platform-guide.md#setup) and
> [configuration-reference.md](configuration-reference.md).

---

## One command (recommended)

```bash
git clone https://github.com/strikersam/autonomous-ai-agency.git
cd autonomous-ai-agency
./scripts/quickstart.sh          # or: make up
```

Then open **http://localhost:8001/** and sign in with the credentials the script
prints (default `admin@llmrelay.local` / `changeme` — change `ADMIN_PASSWORD` in
`.env` before exposing the instance).

### What the script does

It is **idempotent** — safe to re-run. On the first run it:

1. Writes a local `.env` from `.env.example` **without overwriting anything you
   set**, adding only safe local defaults: `STORAGE_BACKEND=sqlite`,
   `ACTIVATION_REQUIRED=false`, `RUN_BACKGROUND_IN_WEB=true`, a freshly generated
   random `JWT_SECRET`.
2. Creates a `.venv` virtualenv and installs `backend/requirements.txt`.
3. Builds the React dashboard (`frontend/build`) so the backend serves the full
   UI at `/`.
4. Launches the FastAPI backend on port `8001` with the **24×7 autonomy loops
   running in-process**.

Later runs skip the slow install/build steps and start in seconds.

### What comes up

| Running on your machine | Port |
|---|---|
| Backend API + dashboard UI | `http://localhost:8001` |
| SQLite storage (a local file — no DB server) | — |
| CEO / dispatch / self-heal / scheduled loops (in-process) | — |

### Flags

| Flag | Effect |
|---|---|
| `--api-only` | Skip the frontend build — API surface only, no dashboard UI |
| `--rebuild-ui` | Force a fresh frontend build |
| `--reinstall` | Reinstall Python dependencies |
| `--port N` | Backend port (default `8001`, or `$PORT`) |
| `--help` | Show usage |

### Add a model provider (optional but recommended)

The agency boots and the UI works with no provider key, but agent output is
degraded until you add one. The quickest is a **free NVIDIA NIM** key — no GPU,
no card:

1. Get a key at <https://build.nvidia.com>.
2. Add `NVIDIA_API_KEY=nvapi-...` to `.env`.
3. Restart the script.

Any of these providers works the same way (add its key to `.env`): NVIDIA NIM,
TokenIn, Groq, Cerebras, DeepSeek, Anthropic, OpenAI-compatible endpoints, AWS
Bedrock, or a local **Ollama** (`OLLAMA_BASE=http://localhost:11434`). The router
tries them in priority order with automatic failover — see
[model-routing.md](model-routing.md).

### What this path does *not* start

By design, the one-command path is the single-process developer setup. It does
**not** launch MongoDB (production storage), the Cloudflare Worker / public
tunnel, the Telegram bot, or the containerised runtime sidecars. For those, use
Docker Compose below or the production deployment guide in
[platform-guide.md](platform-guide.md#setup).

### Requirements

- **Python 3.11+** (3.13 recommended)
- **Node 20+** (only for building the dashboard UI; not needed with `--api-only`)
- No database server, no Docker, no cloud account for this path.

---

## Docker Compose

Closer to production: Ollama, MongoDB, the authenticated proxy, and lightweight
runtime sidecars, each in its own container.

```bash
cp .env.example .env      # set ADMIN_PASSWORD and any provider keys
docker compose --profile dashboard up
```

- Dashboard: **http://localhost:3000**
- Authenticated OpenAI/Anthropic/Ollama-compatible proxy: **http://localhost:8000**

Optional profiles:

```bash
docker compose --profile tunnel up     # + cloudflared public HTTPS URL
docker compose --profile ngrok up      # + ngrok tunnel (needs NGROK_AUTHTOKEN)
```

See the header of [`docker-compose.yml`](../docker-compose.yml) for the full
service list and GPU notes.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `npm not found` | Install Node 20+, or run `./scripts/quickstart.sh --api-only` for the API only. |
| Backend starts but the dashboard 404s | The UI isn't built — run `./scripts/quickstart.sh --rebuild-ui`. |
| Agent replies are low quality / time out | No/weak provider key — add `NVIDIA_API_KEY` (free) to `.env` and restart. |
| Port `8001` already in use | `./scripts/quickstart.sh --port 8080`. |
| Dependency errors after a `git pull` | `./scripts/quickstart.sh --reinstall`. |

More: [troubleshooting.md](troubleshooting.md).

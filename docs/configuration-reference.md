# Configuration Reference

Complete reference for every environment variable in `.env`. Copy `.env.example` to `.env` and fill in the values that apply to your setup. Variables not listed in `.env` use the documented defaults.

> **Most feature switches no longer need an environment edit.** 109 of the
> variables below — agent runtime selection, brain preference, autonomy loops,
> governance, routing strategy — are settable from **Dashboard → System →
> Platform Controls** (`/controls`), which stores the choice in the database and
> takes precedence over the environment. See
> [platform-controls.md](platform-controls.md). Secrets and connection URLs are
> deliberately excluded and remain environment-only.

---

## Authentication and Keys

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `API_KEYS` | (none) | If no `KEYS_FILE` | Legacy comma-separated bearer tokens. All traffic from these keys appears as `user=unknown` in Langfuse. Prefer `KEYS_FILE` for team use. |
| `KEYS_FILE` | (none) | Recommended | Path to the JSON key store (e.g. `keys.json`). Created automatically by `generate_api_key.py`. Enables per-user email/department tracking. |
| `ADMIN_SECRET` | (none) | For admin UI/API | Strong random secret for the browser admin UI and admin API. Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `ADMIN_WINDOWS_AUTH` | `true` on Windows | No | Enable Windows credential-based admin login. Users log in with their Windows machine username and password. |
| `ADMIN_WINDOWS_ALLOWED_USERS` | (empty) | No | Comma-separated Windows usernames allowed to log in (e.g. `HOSTNAME\alice,alice`). Empty = all local users allowed. |
| `ADMIN_WINDOWS_DEFAULT_DOMAIN` | `.` | No | Default domain for username normalization. `.` means local machine. |

---

## Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE` | `http://localhost:11434` | URL of the Ollama server. Change only if running Ollama on a different machine or port. |
| `PROXY_PORT` | `8000` | Port the FastAPI proxy listens on. |
| `RATE_LIMIT_RPM` | `60` | Max requests per minute per API key. Set to `0` to disable. |
| `CORS_ORIGINS` | `*` | Comma-separated allowed browser origins, or `*` for any. Restrict for production: `https://myapp.example.com` |
| `LOG_LEVEL` | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`. Use `DEBUG` during setup. |

---

## Proxy Behavior

| Variable | Default | Description |
|----------|---------|-------------|
| `PROXY_INJECT_STREAM_USAGE` | `true` | Inject token usage into SSE stream chunks. Disable if your Ollama build rejects `stream_options`. |
| `PROXY_DEFAULT_SYSTEM_PROMPT_ENABLED` | `false` | Inject the configured system prompt into requests that don't include one. Disable for Claude Code and Continue (they send their own). |
| `PROXY_DEFAULT_SYSTEM_PROMPT` | (none) | Inline system prompt text. Takes precedence over `PROXY_DEFAULT_SYSTEM_PROMPT_FILE`. |
| `PROXY_DEFAULT_SYSTEM_PROMPT_FILE` | `templates/codex_local_ide_system_prompt.txt` | Path to system prompt file (relative to repo root). |
| `PROXY_STRIP_THINK_TAGS` | `true` | Remove `<think>...</think>` blocks from model responses. Recommended for DeepSeek-R1 and other reasoning models. |
| `PROXY_DEFAULT_MAX_TOKENS` | `8192` | Fallback `max_tokens` applied when the client does not send one. **Must be ≥ 4096 for Claude Code.** The old default of 1200 truncates code generation responses. |

---

## Anthropic API Compatibility / Claude Code

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_MAP` | (built-in defaults) | Maps Anthropic model names to local Ollama model names. Format: `anthropic_name:local_name` — comma-separated. `*` is a catch-all fallback. Example: `claude-sonnet-4-6:qwen3-coder:30b,claude-opus-4-6:deepseek-r1:32b,*:qwen3-coder:30b` |

Built-in default mappings (active when `MODEL_MAP` is not set):

| Anthropic name | Mapped to |
|----------------|-----------|
| `claude-opus-4-6` | `deepseek-r1:32b` |
| `claude-sonnet-4-6` | `qwen3-coder:30b` |
| `claude-haiku-4-5-20251001` | `qwen3-coder:30b` |
| `claude-3-5-sonnet-20241022` | `qwen3-coder:30b` |
| `claude-3-opus-*` | `deepseek-r1:32b` |
| `*` (catch-all) | `qwen3-coder:30b` |

See [docs/claude-code-setup.md](claude-code-setup.md) for full Claude Code setup instructions.

---

## Agent Models

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_PLANNER_MODEL` | `nvidia/llama-3.3-nemotron-super-49b-v1` | Model used for task planning (breaks task into ≤5 steps, returns JSON). Reasoning models work best. |
| `AGENT_EXECUTOR_MODEL` | `nvidia/llama-3.3-nemotron-super-49b-v1` | Model used for code writing and file manipulation. Coding-specialist models recommended. |
| `AGENT_VERIFIER_MODEL` | `nvidia/llama-3.3-nemotron-super-49b-v1` | Model used to validate each code change (returns pass/fail JSON). |
| `AGENT_JUDGE_MODEL` | `nvidia/llama-3.3-nemotron-super-49b-v1` | Final release-gate judge model (verdict / security / correctness). |
| `AGENT_WORKSPACE_ROOT` | (repo root) | Absolute path to the workspace the agent operates on. Defaults to the directory containing `proxy.py`. |

---

## Workspace Isolation

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_WORKSPACE_BASE` | `.workspaces/` next to `proxy.py` | Base root for all per-job isolated workspaces.  All job directories are created as hashed subdirectories under this path. |
| `WORKSPACE_TTL_HOURS` | `24` | Number of hours after job completion before the workspace becomes eligible for cleanup.  Workspaces in active states are never deleted regardless of TTL. |

---

## Feature Flags

| Variable | Default | Description |
|----------|---------|-------------|
| `FEATURE_DISABLE` | (none) | Comma-separated list of feature IDs to force-disable at startup (e.g. `async_agent_jobs,telegram_bot`).  Takes precedence over `FEATURE_ENABLE`. |
| `FEATURE_ENABLE` | (none) | Comma-separated list of feature IDs to force-enable at startup.  Can enable `beta` or `experimental` features.  Cannot enable features with maturity=`disabled`. |

See [docs/support-matrix.md](support-matrix.md) for the full list of feature IDs.

---

## Web UI (Claude Code–style)

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBUI_DATA_DIR` | `.data` | Directory for server-side Web UI config storage (providers/workspaces). Not served to clients. Use a persistent volume path in production if you want provider/workspace config to survive restarts. |
| `DATA_DIR` | (unset) | Alias for `WEBUI_DATA_DIR` (kept for convenience). |
| `WEBUI_CMD_ALLOWLIST` | `pytest,rg,git,ls,cat` | Comma-separated allowlist for the admin-only command runner (`POST /admin/api/commands/run`). `git` is further restricted to safe subcommands (`status`, `diff`, `log`, `show`, `rev-parse`). |
| `DEFAULT_TEMPERATURE` | `0.2` | Default temperature used when seeding providers from env (can be overridden per provider in the Admin app). |
| `OPENAI_COMPAT_BASE_URL` | (unset) | Optional: seed a remote OpenAI-compatible provider on first boot (e.g. `https://api.openai.com`). Also accepted as `OPENAI_BASE_URL`. |
| `OPENAI_COMPAT_API_KEY` | (unset) | Optional: API key for the seeded provider. Also accepted as `OPENAI_API_KEY`. |
| `OPENAI_COMPAT_MODEL` | (unset) | Optional: default model for the seeded provider. Also accepted as `OPENAI_MODEL`. |

---

## Dashboard (React UI on :3000, API on :8001)

These settings apply to the "LLM Relay" dashboard (`frontend/` + `backend/server.py`).

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_URL` | `mongodb://localhost:27017` | MongoDB connection string for wiki pages, sources, providers, and chat sessions. |
| `DB_NAME` | `llm_wiki_dashboard` | Mongo database name. |
| `JWT_SECRET` | (random per start) | Secret used to sign access/refresh tokens. Set a stable value for production. |
| `ADMIN_EMAIL` | `admin@llmrelay.local` | Seeded admin email for the dashboard login. |
| `ADMIN_PASSWORD` | (none) | Seeded admin password. Set this explicitly before exposing the dashboard. |
| `FRONTEND_URL` | `http://localhost:3000` | Default CORS origin when a request has no Origin header. |
| `LLM_PROVIDER` | `deepseek` | Which seeded provider should be default (`deepseek`, `ollama`, `huggingface`, `openrouter`, `together`). |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama base URL for the default provider. |
| `OLLAMA_MODEL` | `llama3.2` | Default model for the seeded Ollama provider. |
| `HF_TOKEN` | (unset) | Hugging Face token for the seeded HF provider (also accepted as `HUGGINGFACE_API_TOKEN`). Optional but recommended. |
| `HF_BASE_URL` | `https://router.huggingface.co` | OpenAI-compatible Hugging Face router base URL. |
| `HF_MODEL_ID` | `Qwen/Qwen2.5-Coder-7B-Instruct` | Default model for the seeded Hugging Face provider. |

---

## Langfuse Observability

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGFUSE_PUBLIC_KEY` | (none) | Langfuse project public key (starts with `pk-lf-`). |
| `LANGFUSE_SECRET_KEY` | (none) | Langfuse project secret key (starts with `sk-lf-`). |
| `LANGFUSE_BASE_URL` | `https://cloud.langfuse.com` | Langfuse instance URL. Change for self-hosted. Also accepted as `LANGFUSE_HOST`. |
| `LANGFUSE_USE_HTTP_ONLY` | `false` | Force REST-only ingestion (no Python SDK). Use if SDK has SSL or compatibility issues. |
| `LANGFUSE_FLUSH_AT` | (auto) | SDK event batch size before flush. Set to `1` for low-latency event delivery. |
| `COMMERCIAL_EQUIVALENT_PRICES_FILE` | (none) | Path to JSON file with custom pricing overrides. See [Langfuse observability guide](langfuse-observability.md). |
| `COMMERCIAL_EQUIVALENT_PRICES_JSON` | (none) | Inline JSON pricing override. Takes precedence over file. |

---

## Infrastructure Cost Tracking

Used to calculate the true cost of local inference and emit it to Langfuse.

Measure your actual values with GPU-Z, HWiNFO64 (Windows) or `nvidia-smi` (Linux) under inference load, or use a wall-outlet power meter for the most accurate whole-system reading.

| Variable | Default | Description |
|----------|---------|-------------|
| `INFRA_GPU_ACTIVE_WATTS` | `150` | GPU power draw during active inference (W). Typical ranges: Intel AI PC iGPU: 30–50W; RTX 4080: 150–200W; RTX 4090: 200–300W. |
| `INFRA_GPU_IDLE_WATTS` | `20` | GPU power when model is loaded but idle (W). |
| `INFRA_SYSTEM_WATTS` | `50` | CPU, RAM, SSD, and overhead (W). |
| `INFRA_ELECTRICITY_USD_KWH` | `0.12` | Your electricity rate in USD/kWh. Check your utility bill. US average ~$0.12; EU varies $0.15–0.35. |
| `INFRA_HARDWARE_COST_USD` | `2000` | Total purchase cost of inference hardware (GPU + system). Used for amortization. |
| `INFRA_AMORTIZATION_MONTHS` | `36` | How many months to spread the hardware cost over (36 = 3 years). |
| `INFRA_MODEL_STORAGE_GB` | (optional) | Model weights disk footprint (GB). Informational only. |
| `INFRA_STORAGE_USD_GB_MO` | `0.023` | Storage cost per GB/month. Default: AWS S3 pricing. Adjust for your NAS/SSD cost. |

**Preset examples:**

```env
# Intel AI PC (Lunar Lake / Meteor Lake with Arc iGPU)
INFRA_GPU_ACTIVE_WATTS=35
INFRA_GPU_IDLE_WATTS=8
INFRA_SYSTEM_WATTS=25
INFRA_HARDWARE_COST_USD=1500

# RTX 4090 workstation
INFRA_GPU_ACTIVE_WATTS=250
INFRA_GPU_IDLE_WATTS=20
INFRA_SYSTEM_WATTS=80
INFRA_HARDWARE_COST_USD=3500

# Mac Studio M4 Ultra
INFRA_GPU_ACTIVE_WATTS=90
INFRA_GPU_IDLE_WATTS=15
INFRA_SYSTEM_WATTS=20
INFRA_HARDWARE_COST_USD=3000
```

---

## Telegram Bot

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | (none) | Bot token from @BotFather. Required to run `telegram_bot.py`. |
| `TELEGRAM_CHAT_ID` | (none) | Single-operator shortcut: your numeric Telegram user ID. Falls back for `TELEGRAM_ALLOWED_USER_IDS`, `TELEGRAM_ADMIN_USER_IDS`, and `TELEGRAM_NOTIFY_CHAT_IDS` (bot auth AND the Telegram approval-gate / notification pushes). Set the more specific vars below only if they need to differ. |
| `TELEGRAM_ALLOWED_USER_IDS` | (none) | Comma-separated Telegram user IDs that can use the bot (read-only commands). Get IDs via @userinfobot. Falls back to `TELEGRAM_CHAT_ID` if unset. |
| `TELEGRAM_ADMIN_USER_IDS` | (none) | Subset of `ALLOWED` that can run service control and key management commands, **and** approve/reject Telegram approval-gate runs. Falls back to `TELEGRAM_CHAT_ID` if unset. |
| `TELEGRAM_NOTIFY_CHAT_IDS` | (none) | Comma-separated chat IDs that receive task-completion and approval-gate notifications. Falls back to `TELEGRAM_CHAT_ID`, then `TELEGRAM_ADMIN_USER_IDS`, then `TELEGRAM_ALLOWED_USER_IDS`. |
| `TELEGRAM_PROXY_API_KEY` | (none) | API key the bot uses to call `/admin/*` endpoints. Use your `ADMIN_SECRET` value here. |
| `PROXY_BASE_URL` | `http://localhost:8000` | Proxy URL the bot calls. Change if running the bot on a different machine than the proxy. |

See [docs/telegram-bot.md](telegram-bot.md) for full setup instructions.

---

## Model Storage and Executable Paths

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_MODELS` | `~/.ollama/models` | Directory where Ollama stores downloaded model weights. Recommended: `D:\aipc-models` (Windows), `/mnt/data/ollama-models` (Linux). Needs lots of free space. |
| `OLLAMA_EXE` | (auto-detect) | Explicit path to `ollama.exe` or `ollama` binary. Only needed if Ollama is not on `PATH`. Windows AI PC example: `C:\Users\<you>\AppData\Roaming\aipc\runtime\ollama\ollama.exe`. |
| `PYTHON_EXE` | (auto-detect) | Explicit path to Python. Needed on Windows if `python` opens the Store app. Example: `C:\Users\<you>\AppData\Local\Programs\Python\Python312\python.exe` |
| `CLOUDFLARED_EXE` | (auto-detect) | Explicit path to `cloudflared.exe`. Default install: `C:\Program Files (x86)\cloudflared\cloudflared.exe`. |
| `NGROK_EXE` | (auto-detect) | Explicit path to `ngrok` binary. Auto-detected from pyngrok's download location if blank. |

---

## Render MCP — platform debugging and environment monitoring

Gives the agency the view of Render that `agent/log_monitor.py` cannot have:
build failures, OOM kills, restart loops, stalled deploys, and memory pressure
all happen where no Python process was alive to log them. Full guide:
[`docs/render-mcp.md`](render-mcp.md).

In production the MCP server runs as the `agency-render-mcp` service declared in
`render.yaml` (built from `Dockerfile.render-mcp`), reached over Render's private
network. The loop is **on by default**; the only thing an operator must supply is
`RENDER_API_KEY`, which cannot be committed.

| Variable | Default | Description |
|----------|---------|-------------|
| `RENDER_API_KEY` | (empty) | Render API key (dashboard → Account Settings → API Keys). The one required manual step. |
| `RENDER_MCP_URL` | `http://127.0.0.1:10000/mcp` | Streamable-HTTP endpoint. The loopback default suits local development; `render.yaml` sets `http://agency-render-mcp:10000/mcp` in production. |
| `RENDER_WORKSPACE_ID` | (empty) | Render workspace (owner) ID, passed as `workspaceId` on every resource tool call. Upstream deprecated implicit session-scoped selection. |
| `RENDER_SERVICE_IDS` | (empty) | Comma-separated service IDs the monitoring loop watches. Empty means discover every service in the workspace. |
| `RENDER_OPS_ENABLED` | `true` | Master switch for the autonomous monitoring loop. Only honoured when `RENDER_API_KEY` is also set — that credential check is what makes defaulting it on safe, not a second off-switch. |
| `RENDER_OPS_INTERVAL_SECONDS` | `600` | Poll interval, floored at 60s. Under the ~15-minute free-plan idle timeout so the sidecar stays warm. |
| `RENDER_MCP_ALLOW_WRITES` | `false` | Permit mutating Render tools (`trigger_deploy`, `update_environment_variables`, `create_*`). The monitoring loop stays read-only regardless. |
| `MALLOC_ARENA_MAX` | `2` (Dockerfile) | Caps glibc per-thread malloc arenas. This async service runs many threads (motor, httpx, APScheduler, `asyncio.to_thread`); glibc's default of up to 8×CPU arenas retains freed memory per-arena and inflates RSS until the 512MB instance OOM-restarts. Raise only on a ≥2GB instance. |
| `MALLOC_TRIM_THRESHOLD_` | `100000` (Dockerfile) | Bytes of free space at the top of the heap before glibc returns it to the OS. Low value keeps the baseline down; mid-arena fragmentation is handled by the memory guard's explicit `malloc_trim(0)`. |
| `MEMORY_GUARD_ENABLED` | `true` | In-process loop (`services/memory_guard.py`) that periodically runs `gc.collect()` + glibc `malloc_trim(0)` to hand freed pages back to the kernel — the piece automatic top-of-heap trimming misses. Fail-soft; skips the trim on non-glibc libc. |
| `MEMORY_GUARD_INTERVAL_SEC` | `180` | How often the memory guard sweeps. A trim is microseconds, so the cost is negligible. |

The `agency-render-mcp` service itself takes no secrets: in HTTP mode it reads
the Render token per-request from the caller's `Authorization` header, so the
only key involved is the backend's.

### Operational-incident tracker

`agent/operational_incidents.py`. Operational failures — timeouts, "all
runtimes failed", rate limits — never become code-fix tasks, because an LLM
editing source cannot fix a saturated free tier and one task per timeout is a
self-amplifying storm. They are counted instead, and a signature that recurs
past the threshold inside the window is diagnosed (Render logs plus the
`phase_start`/`phase_end` markers that name the stalled agent phase) and filed
**once** through the existing improvement-loop intake.

These four values are the anti-storm bounds. Raising the threshold or lowering
the cap makes the tracker quieter; it can never make it louder.

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPS_INCIDENT_THRESHOLD` | `4` | Occurrences of one normalised signature inside the window before it counts as an incident. Below this a failure is indistinguishable from a transient blip. |
| `OPS_INCIDENT_WINDOW_SECONDS` | `1800` | Rolling window (30m) the threshold is counted over. |
| `OPS_INCIDENT_COOLDOWN_SECONDS` | `21600` | Per-signature quiet period (6h) after a successful filing. A *failed* filing releases its cooldown so the next recurrence retries. |
| `OPS_INCIDENT_MAX_PER_HOUR` | `3` | Hard ceiling on incidents filed per rolling hour across all signatures. `0` disables the cap. |
| `OPS_INCIDENT_LOOKBACK_MINUTES` | `20` | How far back Render logs are pulled when building the evidence bundle. |

Counters are exposed on `GET /api/metrics/self-heal` under
`operational_incidents`, including `incidents_attempted` vs `incidents_filed` —
they differ when the intake was unreachable.

---

## Agent governance — identity, policy, approvals, audit, sandboxes

`packages/governance/`. Runtime governance for autonomous agent actions.
Full guide: [`docs/governance/README.md`](governance/README.md).

> **`GOVERNANCE_ENABLED` is not the enforcement switch.** The layer ships
> enabled, but `config/agent_policy.yaml` ships in `mode: observe`: every rule
> is evaluated and every verdict audited, and **nothing is blocked**. Enabling
> governance is behaviour-neutral by design. Enforcement is a separate,
> deliberate edit to the policy file — see
> [Turning on enforcement](governance/README.md#turning-on-enforcement).

| Variable | Default | Purpose |
|----------|---------|---------|
| `GOVERNANCE_ENABLED` | `true` | Master switch. `false` removes the layer entirely — the instant kill switch if a control ever misbehaves, no deploy needed. |
| `GOVERNANCE_POLICY_PATH` | `config/agent_policy.yaml` | Policy document. Git-reviewed; there is deliberately **no HTTP endpoint that writes policy**, so "who changed the rules" stays answerable. Reload without a restart via `POST /api/governance/policy/reload`. |
| `GOVERNANCE_SANDBOX_PROFILES_PATH` | `config/sandbox_profiles.yaml` | Sandbox profile definitions, merged over the built-ins. |
| `GOVERNANCE_SANDBOX_BACKEND` | `auto` | `auto` \| `docker` \| `e2b` \| `local`. `auto` probes Docker, then E2B, then falls back to `local`. Pin only when the probe order is wrong for your install. |
| `GOVERNANCE_AUDIT_CAPACITY` | `2000` | Ring-buffer size for the API and dashboard. The durable record is the `governance.audit.events` log stream — past ~100 concurrent agents this buffer covers minutes, not hours, so SIEM shipping stops being optional. |
| `GOVERNANCE_APPROVAL_TTL_S` | `300` | How long an agent blocks on a human approval. On expiry the request is **denied**, not allowed — an approval gate that opens when ignored is theatre. |
| `GOVERNANCE_AUTO_APPROVE` | `false` | Self-approve approval-gated actions. Local development only. Audited as `resolved_by=auto-approve` whenever it fires, so its use is always visible in the trail. |
| `GOVERNANCE_MAX_SANDBOXES` | `8` | Cap on concurrently live sandboxes. Exceeding it raises `SandboxUnavailableError` — backpressure rather than host resource exhaustion. |
| `GOVERNANCE_ARTIFACTS_DIR` | `.artifacts` | Where sandbox artifacts are captured **before** teardown. |

### Sandbox isolation in production

Render deploys this backend with `env: docker` — the application *is* a
container on a managed host, with no Docker socket, so it cannot create sibling
containers. The Docker backend therefore cannot engage in production. Set
`E2B_ENABLED=true` and `E2B_API_KEY` (see the E2B section) to get real
isolation there via Firecracker micro-VMs reached over HTTPS.

Without a working backend the manager resolves to `local`, which provides **no
isolation at all** — only in-process policy. That is reported honestly by
`GET /api/governance/status` as `backend: local`, `isolation: none`, rather
than being hidden behind a green dashboard.

Per-group cost ceilings (`max_tool_calls`, `max_cost_usd`, `max_tokens`,
`max_duration_s`, `max_depth`, `max_retries`) live in the policy file rather
than in environment variables, because they differ per agent. A **missing**
limit key means unlimited, never zero.

---


## Tunnel — Permanent Static URL (ngrok)

Run `setup_ngrok.py` once to populate these automatically. Get your token free at [dashboard.ngrok.com](https://dashboard.ngrok.com).

| Variable | Default | Description |
|----------|---------|-------------|
| `PUBLIC_URL` | (empty) | Pinned public URL shown in the Admin UI and returned by `get_tunnel_url()`. Overrides the auto-detected quick-tunnel URL. Set by `setup_ngrok.py` or paste manually in the Admin UI. |
| `NGROK_AUTH_TOKEN` | (empty) | Your ngrok account token. Used by `run_tunnel.sh` / `run_tunnel.bat` after running `setup_ngrok.py`. |
| `NGROK_DOMAIN` | (empty) | Your free static ngrok domain (e.g. `yourword-yourword-1234.ngrok-free.app`). Used by the tunnel scripts. |

---


## Workspace Isolation

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKSPACE_BASE_ROOT` | `.data/workspaces` | Base directory for all isolated workspaces. Every session/job workspace is created under this root. |
| `WORKSPACE_RETENTION_TTL_SECONDS` | `604800` (7 days) | Time in seconds before a completed/failed/cancelled/archived workspace becomes eligible for cleanup. Set to `0` for immediate eligibility. |
| `DIRECT_CHAT_AGENT_WORKSPACE_ROOT` | `.data/direct-chat-agent-workspaces` | Override base root for direct chat agent workspaces. If not set, uses the default workspace root. |

## Feature Maturity Overrides

Any feature in the support matrix can be overridden via environment variables using the pattern `FEATURE_<UPPERCASE_FEATURE_ID>`.

| Variable Pattern | Values | Description |
|-----------------|--------|-------------|
| `FEATURE_<ID>` | `stable`, `beta`, `experimental`, `disabled`, `true`, `false` | Override a feature's maturity tier or enabled state. Example: `FEATURE_TELEGRAM_BOT=disabled` disables the Telegram bot. |

Common overrides:

| Variable | Example | Effect |
|----------|---------|--------|
| `FEATURE_TELEGRAM_BOT` | `disabled` | Disable the Telegram bot |
| `FEATURE_OPENHANDS_RUNTIME` | `true` | Enable the OpenHands runtime (opt-in) |
| `FEATURE_ASYNC_AGENT_JOBS` | `stable` | Promote async agent jobs to stable tier |
| `FEATURE_SIDECAE_RUNTIMES` | `false` | Disable sidecar runtimes |

## Traffic Distribution and Rate Limits

Controls how requests are spread across LLM providers and how the router avoids
`429` rate limits. See [`traffic-distribution.md`](traffic-distribution.md) for
the full explanation of each strategy.

Every one of these is **unset by default**, and unset means "no limit". So does
zero, a negative number, `inf`, `nan`, or anything unparseable — a limit of zero
would wedge a provider out of rotation permanently, which is never what a
malformed value should mean.

`<PROVIDER>` is the provider id upper-cased. Ids containing dashes accept the
dash-to-underscore form (`NVIDIA_NIM_MAX_RPM`), which is the one most shells and
dashboards will actually let you set; the literal name is still read first.

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_ROUTING_STRATEGY` | `priority` | How traffic is spread across providers: `priority` (strict order, the historical behaviour), `weighted-shuffle`, `least-busy`, `usage-based`, `latency-based`. An unrecognised value warns once and behaves as `priority`. |
| `<PROVIDER>_MAX_RPM` | (unset) | Requests/minute ceiling. Used both to pace requests and to route around a provider that has spent its minute. Set it to the provider's real current limit from its own dashboard — none is hardcoded, because they change and are account-specific. |
| `<PROVIDER>_MAX_TPM` | (unset) | Tokens/minute ceiling. Free tiers usually publish one alongside the request limit, and large-context agent calls hit the token limit first. |
| `<PROVIDER>_MAX_PARALLEL` | (unset) | In-flight request ceiling — the concurrency limit NVIDIA NIM enforces with `419`. A fractional value is rounded; anything rounding below 1 reads as unset. |
| `<PROVIDER>_WEIGHT` | (unset) | Share weight for the `weighted-shuffle` strategy. Weight 3 receives roughly three times the traffic of weight 1. |
| `<PROVIDER>_KEY_ROTATION` | `false` | **Opt-in** for using more than one API key for a provider (`<KEY>`, `<KEY>_2`, `<KEY>_3`...). Off unless set to `true`/`1`/`yes`/`on`; sibling keys are ignored entirely without it. **Several providers' terms prohibit registering extra accounts to exceed published limits - check yours before enabling.** |
| `PROVIDER_COOLDOWN_SECONDS` | `30` | Default cooldown applied to a provider after a generic failure. |
| `PROVIDER_RATELIMIT_COOLDOWN_SECONDS` | `20` | Base cooldown after a `429`. Doubles per consecutive rate limit. |
| `PROVIDER_RATELIMIT_COOLDOWN_MAX_SECONDS` | `120` | Ceiling for the exponential 429 backoff. |
| `PROVIDER_DEAD_MODEL_COOLDOWN_SECONDS` | `3600` | How long a model that returned `410 Gone` is skipped before being re-probed. |

Observability for all of the above: `GET /api/metrics/traffic-distribution`
(authenticated) reports the active strategy plus per-provider window usage,
configured budgets, EWMA latency and how many requests were routed away.

---

## Prime Agent runtime — opt-in external executor

Drives [prime-agent](https://github.com/PrimeIntellect-ai/prime-agent) (or the
`pi` CLI it wraps) as a runtime behind `RuntimeManager`. Off by default; when the
binary is absent the adapter reports `available=False` and the router falls back
to `internal_agent`. Full runbook: [`runbooks/prime-agent.md`](runbooks/prime-agent.md).

| Variable | Default | Purpose |
|---|---|---|
| `RUNTIME_PRIME_AGENT_ENABLED` | `false` | Register the adapter at all |
| `INSTALL_PRIME_AGENT` | `false` | Docker build arg that bakes the CLI into the image |
| `PRIME_AGENT_BIN` | `prime-agent`, then `pi` | Binary name or path |
| `PRIME_AGENT_MODEL` | (unset) | Model id passed to `--model` |
| `PRIME_AGENT_PROVIDER` | `agency` | Provider name passed to `--provider` |
| `PRIME_AGENT_EXTENSION` | (unset) | Path to `agency-provider.ts`; **required** when the provider is `agency` |
| `PRIME_AGENT_MODELS` | `meta/llama-3.3-70b-instruct` | Model ids the extension advertises |
| `PRIME_AGENT_WORKSPACE` | `.` | Default working directory |
| `PRIME_AGENT_TIMEOUT_SEC` | `900` | Per-task timeout |
| `PRIME_AGENT_MAX_TURNS` | (unset) | `--autonomous-max-turns`, when the build supports it |
| `PRIME_AGENT_TRUST_WORKSPACE` | `false` | `true` loads workspace-local extensions, skills, and `AGENTS.md`/`CLAUDE.md` |
| `AGENCY_PROXY_URL` | `http://localhost:8000` | Base URL serving `/v1/chat/completions` (`proxy.py`) |
| `PROXY_API_KEY` | (unset) | **Secret.** Bearer token the extension sends to that proxy |

The CLI has no base-URL variable of its own, so `PRIME_AGENT_EXTENSION` is what
keeps its traffic inside our router. Without it the CLI falls back to whatever
provider keys are in the environment, bypassing `packages/ai/router.py` — so the
adapter refuses to run `agency` without it rather than failing open.

`PROXY_API_KEY` is never written into the extension file: it declares the literal
string `"$PROXY_API_KEY"`, which the CLI interpolates at request time. The
subprocess receives an allowlisted environment, not the worker's, because the CLI
exposes a model-controlled `bash` tool.

## Continual Harness

Promotes a repeated failure lesson into a standing instruction stored in
`.agency/harness.md`. Reading is on by default; writing is opt-in. Full runbook:
[`runbooks/continual-harness.md`](runbooks/continual-harness.md).

| Variable | Default | Purpose |
|---|---|---|
| `HARNESS_SPEC_ENABLED` | `true` | Kill switch for reading and injecting the spec |
| `HARNESS_SPEC_AUTO_REFINE` | `false` | Allow runs to append entries |
| `HARNESS_SPEC_MIN_HITS` | `2` | Repeats before a lesson is promoted |
| `HARNESS_SPEC_MAX_ENTRIES` | `40` | Entries retained in the file |
| `HARNESS_SPEC_MAX_CHARS` | `1200` | Cap on the injected prompt block |

---

## Quick Reference — Minimal Configs

### Personal use (single key)

```env
API_KEYS=your-key-here
OLLAMA_MODELS=D:\aipc-models
PROXY_DEFAULT_MAX_TOKENS=8192
PROXY_STRIP_THINK_TAGS=true
```

### Team use with observability

```env
KEYS_FILE=keys.json
ADMIN_SECRET=strong-random-secret
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
OLLAMA_MODELS=D:\aipc-models
PROXY_DEFAULT_MAX_TOKENS=8192
PROXY_STRIP_THINK_TAGS=true
```

### Claude Code setup

```env
API_KEYS=your-key-here
PROXY_DEFAULT_MAX_TOKENS=8192
PROXY_STRIP_THINK_TAGS=true
PROXY_DEFAULT_SYSTEM_PROMPT_ENABLED=false
MODEL_MAP=claude-sonnet-4-6:qwen3-coder:30b,claude-opus-4-6:deepseek-r1:32b,*:qwen3-coder:30b
```

### Full setup with Telegram bot

```env
KEYS_FILE=keys.json
ADMIN_SECRET=strong-random-secret
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
OLLAMA_MODELS=D:\aipc-models
PROXY_DEFAULT_MAX_TOKENS=8192
PROXY_STRIP_THINK_TAGS=true
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_ALLOWED_USER_IDS=12345678
TELEGRAM_ADMIN_USER_IDS=12345678
TELEGRAM_PROXY_API_KEY=strong-random-secret
INFRA_GPU_ACTIVE_WATTS=150
INFRA_GPU_IDLE_WATTS=20
INFRA_SYSTEM_WATTS=50
INFRA_ELECTRICITY_USD_KWH=0.12
INFRA_HARDWARE_COST_USD=2000
INFRA_AMORTIZATION_MONTHS=36
```

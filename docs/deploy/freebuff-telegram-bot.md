# Deploy: FreeBuff Telegram bot (24×7)

Run the FreeBuff coding agent as an always-on bot you can drive from your phone,
anywhere. It clones this repo, edits it on **free NVIDIA NIM models**, and opens
a **draft PR** — all from a Telegram chat.

The bot runs in **embedded mode**: the agent executes in-process, so it's a
single self-contained worker — no proxy server, no MongoDB, no public port
(Telegram long-polling works behind any network).

---

## Option A0 — Run inside your existing web service (free tier: ONE service)

If you can only run a single Render service, host the bot **inside** the
`local-llm-server` web service. On startup the app launches the bot in-process
(embedded mode) when a token is present.

On the **`local-llm-server`** service, set these env vars:

| Variable | Value |
|----------|-------|
| `RUN_TELEGRAM_BOT` | `true` |
| `TELEGRAM_BOT_TOKEN` | BotFather token |
| `TELEGRAM_ALLOWED_USER_IDS` | your numeric user ID |
| `TELEGRAM_ADMIN_USER_IDS` | your numeric user ID |
| `NVIDIA_API_KEY` | your `nvapi-...` key |
| `GH_PAT` (or `GITHUB_TOKEN`) | token with `repo` scope |

Defaulted automatically (override if needed): `FREEBUFF_EMBEDDED=true`,
`AGENT_AUTO_PR_ENABLED=true`, `FREEBUFF_REPO_URL`, `FREEBUFF_BASE_BRANCH=master`,
`BOT_KEEPALIVE=true`.

Then redeploy and watch the **`local-llm-server`** logs for:
```
FreeBuff Telegram bot starting inside web process (embedded mode).
Bot @<yourbot> online. Allowed users: {…} Admin users: {…}
Cleared any existing webhook (deleteWebhook ok=True).
```

Notes:
- The web service runs in **orchestrator** mode; FreeBuff runs are allowed via a
  scoped, per-run bypass (the same mechanism the task coordinator uses).
- Free web services **sleep after ~15 min of no inbound traffic**, and the bot's
  outbound long-poll does not keep it awake. `BOT_KEEPALIVE=true` makes the app
  self-ping `RENDER_EXTERNAL_URL/api/ping` every 10 min so it stays up. (You can
  also point an external uptime pinger at `…/api/ping`.)

---

## Option A — Dedicated Render worker (if you can run a second service)

`render.yaml` already defines the worker `freebuff-telegram-bot`
(`Dockerfile.telegram`). Render workers don't sleep, so the bot stays responsive.

### 1. Create the Telegram bot
1. Message **@BotFather** → `/newbot` → copy the **bot token**.
2. Message **@userinfobot** → copy your numeric **user ID**.

### 2. Deploy
- Push this repo to GitHub (already done) and let Render pick up `render.yaml`
  (Blueprint), **or** create a new **Background Worker** pointing at
  `Dockerfile.telegram`.

### 3. Set environment variables (Render dashboard → the worker → Environment)
These are marked `sync:false` in `render.yaml`, so you set them once:

| Variable | Value |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | the BotFather token |
| `TELEGRAM_ALLOWED_USER_IDS` | your user ID (comma-separated for more) |
| `TELEGRAM_ADMIN_USER_IDS` | your user ID (admins can run `/freebuff`) |
| `NVIDIA_API_KEY` | your free `nvapi-...` key |
| `GITHUB_TOKEN` (or `GH_PAT`) | a token with `repo` scope (push + open PRs) |

Already defaulted in `render.yaml` (no action needed): `FREEBUFF_EMBEDDED=true`,
`AGENCY_WORKFLOW_MODE=legacy`, `AGENT_AUTO_PR_ENABLED=true`,
`FREEBUFF_REPO_URL=https://github.com/strikersam/autonomous-ai-agency`,
`FREEBUFF_BASE_BRANCH=master`.

> **Note:** Render env vars are per-service. The `NVIDIA_API_KEY` on your existing
> web service is **not** shared — set it again on this worker.

### 4. Use it
From Telegram, send your bot:

```
/freebuff add a /version endpoint that returns the app version
```

Then: tap a model → review the plan → **✅ Accept & run**. The bot replies with a
summary and the **draft PR link**. Review and merge the PR from GitHub.

---

## Option B — Docker (any host / VPS / your PC)

```bash
docker build -f Dockerfile.telegram -t freebuff-bot .

docker run -d --name freebuff-bot --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN=123:abc \
  -e TELEGRAM_ALLOWED_USER_IDS=8120976 \
  -e TELEGRAM_ADMIN_USER_IDS=8120976 \
  -e NVIDIA_API_KEY=nvapi-xxx \
  -e GITHUB_TOKEN=ghp_xxx \
  -e FREEBUFF_REPO_URL=https://github.com/strikersam/autonomous-ai-agency \
  freebuff-bot
```

`--restart unless-stopped` keeps it running 24×7 across reboots. Check logs with
`docker logs -f freebuff-bot`.

---

## Troubleshooting (bot is silent)

If the bot doesn't respond to your Telegram messages, check these in order:

### 1. Hit the diagnostic endpoint

```bash
curl -s https://local-llm-server.onrender.com/api/telegram/diag | python3 -m json.tool
```

This returns a non-sensitive snapshot of the bot's runtime config (token masked,
allowlist IDs, poller state, repo URL, keepalive flag). Verify:
- `bot_token_set` is `true`
- `allowed_user_ids` contains your numeric Telegram ID (message [@userinfobot](https://t.me/userinfobot) to get it)
- `poller_disabled` is `false` on the service that should poll
- `freebuff_repo_url` is `https://github.com/strikersam/autonomous-ai-agency` (not `local-llm-server`)

### 2. Single-poller guard (409 conflict)

Telegram allows only ONE `getUpdates` consumer per bot token. If both the web
service (`RUN_TELEGRAM_BOT=true`) and the worker (`TELEGRAM_POLLER_DISABLED=false`)
poll the same token, you get a 409/429 conflict storm and the bot goes silent.

**Fix — pick one:**
- **Option 1 (recommended):** Give the worker its OWN bot token (create a second
  bot via @BotFather), set `TELEGRAM_POLLER_DISABLED=false` on the worker, and
  set `RUN_TELEGRAM_BOT=false` on the web service. Each service polls its own
  token — no conflict.
- **Option 2 (single-bot):** Keep the worker's `TELEGRAM_POLLER_DISABLED=true`
  and rely on the web service's `RUN_TELEGRAM_BOT=true` + `BOT_KEEPALIVE=true`
  self-ping to keep the free web dyno awake. Verify `BOT_KEEPALIVE` is actually
  pinging `/api/ping` every 10 min (check Render logs for "keepalive ping").
  If the web dyno sleeps, the bot goes silent.
- **Option 3 (paid):** Upgrade the web service to a paid plan so it never
  sleeps — keepalive is not needed.

### 3. Webhook set → long-poll blocked

If `getUpdates` returns 409 "Conflict: terminated by other getUpdates request",
a webhook may be set. The bot calls `deleteWebhook` on startup, but if the
conflict persists, run manually:

```bash
curl -s "https://api.telegram.org/bot<YOUR_TOKEN>/deleteWebhook"
```

Then restart the bot and confirm the startup log line:
```
Cleared any existing webhook (deleteWebhook ok=True).
Bot @<yourbot> online.
```

### 4. Validate the token

```bash
curl -s "https://api.telegram.org/bot<YOUR_TOKEN>/getMe" | python3 -m json.tool
```

If this fails with 401, the token is wrong or revoked. Create a new one via
@BotFather → `/revoke` → `/newbot`.

### 5. Check allowed IDs

If the bot is online but doesn't respond to YOUR messages (only silently drops
them), your numeric Telegram user ID is not in the allowlist. Message
[@userinfobot](https://t.me/userinfobot) to get your ID, then set:
- `TELEGRAM_CHAT_ID=<your_numeric_id>` (single-operator shortcut — falls back
  for both `TELEGRAM_ALLOWED_USER_IDS` and `TELEGRAM_ADMIN_USER_IDS`)

---

## How it works / safety

- **Free only:** routing is pinned to free NVIDIA NIM models; non-free model
  requests are coerced to a free one (`FreeBuffAgent.resolve_model`).
- **PR-only:** the agent never pushes to `master` directly — it creates a feature
  branch and opens a PR for you to review (autonomy gate + `AGENT_AUTO_PR_ENABLED`).
- **Auth:** only `TELEGRAM_ALLOWED_USER_IDS` can talk to the bot; only
  `TELEGRAM_ADMIN_USER_IDS` can run `/freebuff`. Everyone else is silently dropped.
- **Plan first:** planning is read-only; nothing is written until you tap Accept.

## Optional env

| Variable | Default | Purpose |
|----------|---------|---------|
| `FREEBUFF_MODELS` | built-in list | override the free-model set |
| `FREEBUFF_MAX_STEPS` | `10` | max agent steps per run (1–20) |
| `GIT_AUTHOR_NAME` / `GIT_AUTHOR_EMAIL` | `FreeBuff Bot` / noreply | commit identity |
| `PROXY_BASE_URL` | (HTTP mode only) | point at a running proxy if `FREEBUFF_EMBEDDED` is off |

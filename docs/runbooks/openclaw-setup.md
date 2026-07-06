# OpenClaw — iOS Control of the Agency (Single-Service Free-Tier Deploy)

## What is OpenClaw?

[OpenClaw](https://openclaw.ai) is a self-hosted Gateway + native iOS/Android
app. The Gateway holds the "brain"; phones pair as WebSocket companion nodes
via a QR code. This repo runs the Gateway **inside the existing web service**
(as a background subprocess) so it works on the Render free tier — no separate
service needed.

## Architecture (single-service)

```
┌─────────────┐    HTTPS          ┌──────────────────────────────────────────┐
│  OpenClaw   │ ────────────────► │  local-llm-server (Render, port $PORT)   │
│  iOS app    │   /openclaw/*     │  ┌─────────────────────────────────────┐ │
└─────────────┘                   │  │  FastAPI (uvicorn)                   │ │
                                  │  │  /api/openclaw/status                │ │
                                  │  │  /api/openclaw/qr                    │ │
                                  │  │  /openclaw/* ──► reverse-proxy       │ │
                                  │  └──────────────┬──────────────────────┘ │
                                  │                 │ localhost:18789        │
                                  │  ┌──────────────▼──────────────────────┐ │
                                  │  │  OpenClaw Gateway (Node.js, bg)     │ │
                                  │  │  → agency /v1 proxy (NVIDIA NIM)    │ │
                                  │  │  → agency /mcp-internal (MCP tools) │ │
                                  │  └─────────────────────────────────────┘ │
                                  └──────────────────────────────────────────┘
```

- **FastAPI app** (port `$PORT`): serves the agency backend + reverse-proxies
  `/openclaw/*` to the background OpenClaw Gateway on `localhost:18789`.
- **OpenClaw Gateway** (port 18789, background subprocess): launched by
  `docker/start_web_with_openclaw.sh` when the container starts. The OpenClaw
  CLI is installed in `Dockerfile.backend` (with a graceful fallback if it's
  not yet published to npm).
- **iOS app**: pairs against `https://local-llm-server.onrender.com/openclaw`,
  then sends commands that the Gateway routes to the agency backend.

## Setup (Render free tier)

### 1. Set env vars on the existing `local-llm-server` service

Go to Render dashboard → `local-llm-server` → Environment. These are already
in `render.yaml` but you need to set the `sync:false` secrets:

| Variable | Value |
|----------|-------|
| `OPENCLAW_AGENT_API_KEY` | Your `NVIDIA_API_KEY` (the `nvapi-...` key) |
| `OPENCLAW_MCP_SECRET_TOKEN` | Must match `MCP_SECRET_TOKEN` on this service |
| `OPENCLAW_PAIRING_TOKEN` | `openssl rand -hex 32` (gates who can pair) |

### 2. Deploy

Push to GitHub → Render rebuilds the image (now includes Node.js + OpenClaw
CLI) → the startup wrapper launches the Gateway in the background.

### 3. Check the status

```bash
curl -s https://local-llm-server.onrender.com/api/openclaw/status | python3 -m json.tool
```

You should see:
```json
{
  "enabled": true,
  "cli_installed": true/false,
  "gateway_alive": true/false,
  "gateway_url": "https://local-llm-server.onrender.com/openclaw",
  "qr_payload": "openclaw://pair?gateway=...&token=..."
}
```

### 4. Get the pairing QR

```bash
curl -s https://local-llm-server.onrender.com/api/openclaw/qr | python3 -m json.tool
```

This returns a `payload` string (`openclaw://pair?gateway=...&token=...`).
Generate a QR code from it (e.g. `qrencode -o qr.png "openclaw://pair?..."`)
and scan with the OpenClaw iOS app.

Or use manual entry — the response includes `manual_entry.host`, `path`, and
`token` for the app's manual pairing screen.

### 5. Pair and verify

1. Download OpenClaw from the App Store.
2. Tap "Pair via QR" → scan the QR (or enter host + path + token manually).
3. Send "list the files in the repo" → the Gateway routes to the MCP server →
   you see the file listing.

## Free-tier caveats

- **Sleep**: Render free web services sleep after ~15 min of no traffic.
  `BOT_KEEPALIVE=true` self-pings `/api/ping` to keep the service awake.
  If the service sleeps, the OpenClaw Gateway subprocess also sleeps — the
  iOS app will disconnect. For 24×7, upgrade to a paid plan.
- **No persistent disk**: On the free tier there's no persistent disk, so
  `~/.openclaw` (pairing tokens + device registrations) is ephemeral. Every
  redeploy un-pairs the phone — re-scan the QR after each deploy. On a paid
  plan, mount a persistent disk at `/root/.openclaw` to survive redeploys.
- **OpenClaw CLI not yet published**: If `npm install -g @openclaw/cli` fails
  (the package isn't published yet), the startup wrapper skips the gateway
  subprocess gracefully. The `/api/openclaw/status` endpoint reports
  `gateway_alive: false`, and `/openclaw/*` returns a 503 with a friendly
  hint. The Telegram bot is the alternative control path.

## Security

- The OpenClaw Gateway binds to `localhost:18789` inside the container — it's
  NOT directly exposed. All access goes through Render's HTTPS + the FastAPI
  reverse-proxy.
- `OPENCLAW_PAIRING_TOKEN` gates who can pair. Treat it like a password.
- `OPENCLAW_MCP_SECRET_TOKEN` must match `MCP_SECRET_TOKEN` on the web service.
- Alternative: if you don't want a public gateway, run OpenClaw on a
  Tailscale-connected host.

## Alternative: Telegram bot

If OpenClaw isn't available yet, the FreeBuff Telegram bot is the existing
iOS-friendly control channel — it works from any phone with Telegram, no app
install needed. See `docs/deploy/freebuff-telegram-bot.md`.

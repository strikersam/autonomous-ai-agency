# OpenClaw — iOS Control of the Agency

## What is OpenClaw?

[OpenClaw](https://openclaw.ai) is a self-hosted Gateway + native iOS/Android
app (launched June 2026). The Gateway holds the "brain"; phones pair as
WebSocket companion nodes via `openclaw pair qr` (QR encodes gateway host +
pairing token) or a manual host+port/setup code.

This repo runs the Gateway on Render 24×7, pointed at the agency's existing
OpenAI-compatible proxy + MCP server so the iOS app can drive agency workflows
(clone_repo, git_commit, git_push, run_command, apply_diff), not just chat.

## Architecture

```
┌─────────────┐    WebSocket     ┌──────────────────┐    HTTPS     ┌────────────────────────┐
│  OpenClaw   │ ◄──────────────► │  OpenClaw Gateway │ ───────────► │  Agency (local-llm-   │
│  iOS app    │   companion node │  (Render 24×7)    │              │  server.onrender.com)  │
└─────────────┘                  └──────────────────┘              └────────────────────────┘
                                          │                                  │
                                          │  OpenAI-compatible /v1           │  MCP /mcp-internal
                                          └──────────────────────────────────┘
                                             (free NVIDIA NIM routing + MCP tools)
```

- **Gateway** (`openclaw-gateway` service): runs the OpenClaw daemon, binds to
  `$PORT`, serves `/health`, `/pair` (QR), `/ws` (WebSocket). Persistent disk
  at `/root/.openclaw` holds pairing tokens + device registrations.
- **Agency backend** (`local-llm-server` service): the existing OpenAI-compatible
  proxy at `https://local-llm-server.onrender.com/v1` + MCP server at
  `/mcp-internal`. The Gateway's agent uses this as its brain.
- **iOS app**: pairs to the Gateway via QR, then sends commands that the
  Gateway routes to the agency backend.

## Deployment (Render)

### 1. The Gateway service is already in `render.yaml`

```yaml
- type: web
  name: openclaw-gateway
  env: docker
  dockerfilePath: ./Dockerfile.openclaw
  plan: free
  healthCheckPath: /health
  disk:
    name: openclaw-state
    mountPath: /root/.openclaw
    sizeGB: 1
  envVars:
    - key: OPENCLAW_AGENT_BASE_URL
      value: "https://local-llm-server.onrender.com/v1"
    - key: OPENCLAW_MCP_BASE_URL
      value: "https://local-llm-server.onrender.com/mcp-internal"
    # ... (see render.yaml for the full list)
```

### 2. Set the sync:false secrets in the Render dashboard

On the `openclaw-gateway` service → Environment:

| Variable | Value |
|----------|-------|
| `OPENCLAW_AGENT_API_KEY` | The agency's API key (or a bearer token accepted by the proxy) |
| `OPENCLAW_MCP_SECRET_TOKEN` | Must match `MCP_SECRET_TOKEN` on the `local-llm-server` web service |
| `OPENCLAW_PAIRING_TOKEN` | A strong random string: `openssl rand -hex 32` |
| `GITHUB_TOKEN` | A token with `repo` scope (needed for repo-editing workflows) |

### 3. Deploy

Push to GitHub → Render picks up `render.yaml` (Blueprint) → the
`openclaw-gateway` service boots. Check the logs for:

```
OpenClaw Gateway started on port $PORT
Health check: ok
```

### 4. Pair your iPhone

Once the Gateway is live:

```bash
# From your laptop (or Render shell), generate the pairing QR:
openclaw pair qr --gateway https://openclaw-gateway.onrender.com --token $OPENCLAW_PAIRING_TOKEN
```

This prints a QR code in the terminal. Scan it with the OpenClaw iOS app
(download from the App Store). The app connects to the Gateway over
WebSocket and you should see:

```
✓ Paired: iPhone (Sam's iPhone)
✓ Connected to gateway: openclaw-gateway.onrender.com
```

### 5. Verify end-to-end

From the OpenClaw iOS app:
1. Open the **Chat** tab → send "list the files in the repo"
2. The Gateway routes the request to the agency's MCP server
   (`/mcp-internal` → `list_files` tool)
3. You should see the file listing in the chat

For repo editing:
1. Send "add a /version endpoint that returns the app version"
2. The Gateway routes to the MCP server → `clone_repo` → `apply_diff` →
   `git_commit` → `git_push` (opens a branch/PR)
3. Review and merge the PR from GitHub

## Free-tier caveats

- **Sleep**: Render free web services sleep after ~15 min of no inbound
  traffic. The OpenClaw Gateway's WebSocket companion-node protocol keeps
  the connection alive, but if the phone disconnects the Gateway may sleep.
  For 24×7 availability, upgrade to a paid plan.
- **Ephemeral disk**: The `openclaw-state` disk (1 GB) is persistent on paid
  plans. On the free plan, Render disks are persistent but the service may
  sleep — pairing tokens survive sleep but not a full service deletion.
  Re-pair by re-running `openclaw pair qr` if the phone loses connection
  after a redeploy.
- **Single poller**: If you also run the Telegram bot, note that the Gateway
  and the Telegram bot are separate services — no conflict. But the Telegram
  single-poller guard (issue #656) still applies between the web service and
  the `freebuff-telegram-bot` worker.

## Security

- **Never expose port 18789 directly.** The Gateway binds to `$PORT` (Render
  injects this) and Render's HTTPS proxy handles TLS. OpenClaw's
  device-pairing + token auth (`OPENCLAW_PAIRING_TOKEN`) gates who can pair.
- **Pairing token**: set `OPENCLAW_PAIRING_TOKEN` to a strong random string.
  Anyone with this token can pair a device — treat it like a password.
- **MCP secret token**: `OPENCLAW_MCP_SECRET_TOKEN` must match the agency's
  `MCP_SECRET_TOKEN`. The MCP server rejects requests without the correct
  bearer token.
- **Alternative (no public gateway)**: if you don't want a public Gateway,
  run OpenClaw on a Tailscale-connected host or a small always-on VPS. The
  iOS app can pair to any reachable host:port — it doesn't need to be public.

## Troubleshooting

### Gateway won't start
- Check Render logs for the `openclaw-gateway` service.
- Verify `Dockerfile.openclaw` built successfully (the OpenClaw CLI may not
  yet be published to npm — the Dockerfile has a placeholder health server
  fallback so the service boots even if the CLI is missing).
- Verify `$PORT` is being respected (Render injects it; the Gateway must
  bind to `$PORT`, not a hardcoded 18789).

### iPhone won't pair
- Verify the QR was generated against the correct Gateway URL
  (`https://openclaw-gateway.onrender.com`, not localhost).
- Verify `OPENCLAW_PAIRING_TOKEN` is set and matches what was used to
  generate the QR.
- Check the Gateway logs for pairing attempt lines.

### Paired but commands don't reach the agency
- Verify `OPENCLAW_AGENT_BASE_URL` is `https://local-llm-server.onrender.com/v1`
  (the OpenAI-compatible proxy, not the MCP server).
- Verify `OPENCLAW_AGENT_API_KEY` is set and accepted by the proxy.
- Verify `OPENCLAW_MCP_BASE_URL` is `https://local-llm-server.onrender.com/mcp-internal`.
- Verify `OPENCLAW_MCP_SECRET_TOKEN` matches `MCP_SECRET_TOKEN` on the web service.
- Hit `https://local-llm-server.onrender.com/api/ping` to confirm the agency
  backend is awake.

### Phone loses pairing after redeploy
- Verify the `openclaw-state` disk is mounted at `/root/.openclaw` and is
  persistent (paid plan). On the free plan, the disk survives sleep but not
  service deletion.
- Re-pair by re-running `openclaw pair qr`.

## Alternative: Telegram bot (already deployed)

If you don't want to run OpenClaw, the FreeBuff Telegram bot
(`docs/deploy/freebuff-telegram-bot.md`) is the existing iOS-friendly control
channel — it works from any phone with Telegram, no app install needed. See
the troubleshooting section in that doc if the bot is silent.

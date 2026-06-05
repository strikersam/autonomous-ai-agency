# Kimi Web-Bridge Service

A standalone OpenAI-compatible HTTP service that proxies chat-completions to
[Kimi / Moonshot](https://kimi.moonshot.cn) via a logged-in **browser session**
(no paid API key required).

## How It Works

A Playwright Chromium browser holds a persistent session with kimi.com.
Each `POST /v1/chat/completions` request submits the prompt to the web UI and
captures the response.  A single asyncio lock serialises concurrent callers
so the browser tab is never in two conversations simultaneously.

---

## One-Time Login

You must log in to Kimi manually once so the session cookie is persisted:

```bash
# Install Playwright browsers (only needed once)
python -m playwright install chromium

# Open headed browser and log in
PLAYWRIGHT_USER_DATA_DIR=~/.kimi_bridge_profile \
  python -m services.kimi_bridge_server.browser_driver --login
```

Close the browser window after logging in.  The session cookie is saved to
`~/.kimi_bridge_profile` and reused by all subsequent headless runs.

---

## Running the Service

```bash
# Generate a random token
export KIMI_BRIDGE_TOKEN=$(python -c "import secrets; print(secrets.token_hex(32))")

# Start the service
KIMI_BRIDGE_TOKEN=$KIMI_BRIDGE_TOKEN \
  uvicorn services.kimi_bridge_server.app:app --host 0.0.0.0 --port 8011
```

## Connecting to the Main Backend

Set these environment variables on the **main backend** service:

```
KIMI_BRIDGE_ENABLED=true
KIMI_BRIDGE_URL=http://kimibridge:8011/v1
KIMI_BRIDGE_TOKEN=<same token>
```

---

## Docker

```bash
docker build -f Dockerfile.kimibridge -t kimi-bridge .
docker run -p 8011:8011 \
  -e KIMI_BRIDGE_TOKEN=$KIMI_BRIDGE_TOKEN \
  -v ~/.kimi_bridge_profile:/root/.kimi_bridge_profile \
  kimi-bridge
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `KIMI_BRIDGE_TOKEN` | *(unset)* | Bearer token for auth. Required in production. |
| `PLAYWRIGHT_USER_DATA_DIR` | `~/.kimi_bridge_profile` | Persistent Chromium profile dir (login cookie lives here). |
| `KIMI_BRIDGE_HEADLESS` | `true` | Set `false` to run the browser headed (debugging). |
| `KIMI_BRIDGE_MODEL` | `kimi-k2.6` | Model ID returned in OpenAI-shaped responses. |

---

## API

### `POST /v1/chat/completions`

OpenAI-compatible endpoint. `stream=true` is not supported — use `stream=false`.

```bash
curl -s -X POST http://localhost:8011/v1/chat/completions \
  -H "Authorization: Bearer $KIMI_BRIDGE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kimi-k2.6",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

### `GET /v1/models`

Returns the configured model ID in OpenAI list format.

### `GET /health`

Returns `{"status": "ok", "driver_ready": true}` when the browser is running.

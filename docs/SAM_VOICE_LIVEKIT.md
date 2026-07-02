# SAM Realtime Voice over LiveKit

Talk to SAM hands-free and hear SAM talk back — full-duplex voice command and
control of the agency, modelled on
[keithschacht/taskmaster](https://github.com/keithschacht/taskmaster).

## Architecture

```
┌──────────────────────┐   WebRTC    ┌──────────────────┐
│  Dashboard (browser) │◄───────────►│  LiveKit room     │
│  SamVoiceScreen      │             │  (Cloud or self-  │
│  livekit-client      │             │   hosted)         │
└──────────┬───────────┘             └────────┬─────────┘
           │ POST /agent/sam/livekit/token    │ agent dispatch
           ▼                                  ▼
┌──────────────────────┐             ┌──────────────────────────────┐
│  backend/server.py   │             │  voice/sam_livekit_worker.py │
│  mints room JWT      │             │  Silero VAD → STT → SAM LLM  │
│  (PyJWT, no new dep) │             │  (+ agency tools) → TTS      │
└──────────────────────┘             └──────────────────────────────┘
```

- The dashboard fetches a room token from the backend and joins the room.
- The worker is dispatched into the room and converses in realtime.
- SAM's tools run **in-process** against the agency (same env as the backend):
  `get_agency_status`, `list_pending_tasks`, `create_task`.
- The existing push-to-talk flow in SamVoiceScreen is unchanged and remains
  the fallback whenever LiveKit is not configured.

## Setup

### 1. Get LiveKit credentials

Create a free project at <https://cloud.livekit.io> (or self-host
`livekit-server`). Note the project URL, API key, and API secret.

### 2. Configure the backend (Render env vars)

| Variable | Required | Purpose |
|----------|----------|---------|
| `LIVEKIT_URL` | yes | `wss://<project>.livekit.cloud` |
| `LIVEKIT_API_KEY` | yes | LiveKit API key |
| `LIVEKIT_API_SECRET` | yes | Signs room tokens |
| `SAM_LIVEKIT_ROOM` | no | Room name prefix (default `sam-voice`) |

Once set, `GET /agent/sam/livekit/status` returns `configured: true` and the
dashboard's SAM screen shows **Start live conversation**.

### 3. Run the SAM voice worker

The worker needs the same env as the backend **plus** one STT and one TTS key:

| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | Free STT (Whisper large v3 turbo) **and** free TTS (PlayAI) — the one-key path |
| `DEEPGRAM_API_KEY` | Preferred STT when set |
| `ELEVENLABS_API_KEY` / `ELEVENLABS_VOICE_ID` | Preferred TTS when set |
| `SAM_LLM_BASE_URL` | SAM's brain (OpenAI-compatible). Default: NVIDIA NIM. Hermes: `http://localhost:8100/v1`. Proxy: `http://localhost:8000/v1` |
| `SAM_LLM_MODEL` | Default: `NVIDIA_DEFAULT_MODEL` |
| `SAM_LLM_API_KEY` | Default: `NVIDIA_API_KEY` |

```bash
pip install -r voice/requirements-livekit.txt
python -m voice.sam_livekit_worker dev      # local development (hot reload)
python -m voice.sam_livekit_worker start    # production worker
```

Run it from the repo root next to the backend (a Render background worker
works well), or deploy it to LiveKit Cloud Agents. LiveKit dispatches the
worker into every new SAM voice room automatically.

### 4. Talk to SAM

Open the dashboard → **SAM** screen → **Start live conversation**. Grant the
microphone permission and just talk — SAM answers out loud, shows live
captions, reports agency status, and creates tasks on request.

## Troubleshooting

- **No "Start live conversation" button** — `GET /agent/sam/livekit/status`
  lists which `LIVEKIT_*` vars are missing.
- **Token endpoint returns 503** — same cause: backend env vars unset.
- **Room connects but SAM never speaks** — the worker isn't running or wasn't
  dispatched; check its logs (`SAM voice session: room=…`).
- **Worker exits at startup** — it prints exactly which STT/TTS/LLM key is
  missing; the free path is a single `GROQ_API_KEY`.

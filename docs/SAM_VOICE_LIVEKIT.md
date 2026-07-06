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

1. Sign in at <https://cloud.livekit.io> (free — Google/GitHub login works)
   and create a project if you don't have one.
2. `LIVEKIT_URL` — copy the `wss://<project>.livekit.cloud` URL shown at the
   top of the project dashboard.
3. `LIVEKIT_API_KEY` + `LIVEKIT_API_SECRET` — project **Settings → Keys →
   Create key**. The secret is shown **once** at creation; copy both then.

(Self-hosting `livekit-server` instead also works — use its URL and the
key/secret pair from its config.)

### 2. Configure the backend (Render env vars)

| Variable | Required | Purpose |
|----------|----------|---------|
| `LIVEKIT_URL` | yes | `wss://<project>.livekit.cloud` |
| `LIVEKIT_API_KEY` | yes | LiveKit API key |
| `LIVEKIT_API_SECRET` | yes | Signs room tokens |
| `SAM_LIVEKIT_ROOM` | no | Room name prefix (default `sam-voice`) |

Once set, `GET /agent/sam/livekit/status` returns `configured: true` and the
dashboard's SAM screen shows **Start live conversation**.

### 3. The SAM voice worker

Two ways to run it — pick by instance size:

**A. Standalone container — `Dockerfile.voice` (recommended).**
The heavy deps (livekit-agents, onnxruntime, av — ~600MB installed, ~300MB+
RAM at runtime) live in their own image, NOT in the web image, so the 512MB
Render web service never carries them. The worker dials **out** to LiveKit
Cloud, so no inbound networking/ngrok is needed — your local Ollama box is a
perfect free host:

```bash
docker build -f Dockerfile.voice -t sam-voice .
docker run --rm --env-file .env sam-voice
```

(`.env` needs `LIVEKIT_*`, one STT/TTS key, the brain key, and `MONGO_URL`
so voice tools see the same tasks/schedules as the app.)

**B. Bare process, no Docker.** Same thing without the container:

```bash
pip install -r backend/requirements.txt      # agency-tool imports (tasks/, agent/, packages/)
pip install -r voice/requirements-livekit.txt
python -m voice.sam_livekit_worker dev      # local development (hot reload)
python -m voice.sam_livekit_worker start    # production worker
```

**C. In-process (≥2GB instances only, and deps must be re-added).** Set
`SAM_VOICE_IN_PROCESS=true` and the backend starts the worker inside the web
process on boot (`start_in_process()`). Since the voice deps were moved out
of `Dockerfile.backend`, this mode also requires re-adding the
`pip install -r voice/requirements-livekit.txt` layer there (the commented
lines in the Dockerfile show exactly where). Running it inside a 512MB
instance OOM-kills the service at boot — that is why the flag defaults to
`false`.

Either way, LiveKit dispatches the worker into every new SAM voice room
automatically. The worker needs one STT and one TTS key alongside the
backend env:

| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | Free STT (Whisper large v3 turbo) **and** free TTS (PlayAI) — the one-key path |
| `DEEPGRAM_API_KEY` | Preferred STT when set |
| `ELEVENLABS_API_KEY` / `ELEVENLABS_VOICE_ID` | Preferred TTS when set |
| `SAM_LLM_BASE_URL` | SAM's brain (OpenAI-compatible). Default: NVIDIA NIM. Hermes: `http://localhost:8100/v1`. Proxy: `http://localhost:8000/v1` |
| `SAM_LLM_MODEL` | Default: `NVIDIA_DEFAULT_MODEL` |
| `SAM_LLM_API_KEY` | Default: `NVIDIA_API_KEY` |

### 4. Talk to SAM

Open the dashboard → **SAM** screen → **Start live conversation**. Grant the
microphone permission and just talk — SAM answers out loud, shows live
captions, reports agency status, and creates tasks on request.

## Troubleshooting

- **No "Start live conversation" button** — `GET /agent/sam/livekit/status`
  lists which `LIVEKIT_*` vars are missing.
- **Token endpoint returns 503** — same cause: backend env vars unset.
- **Room connects but SAM never speaks** — check the backend logs for
  `SAM voice worker started in-process` / `SAM voice session: room=…`; if the
  start line says which keys are missing, add them. In dedicated-process mode,
  make sure the worker process is actually running.
- **Worker exits at startup (dedicated mode)** — it prints exactly which
  STT/TTS/LLM key is missing; the free path is a single `GROQ_API_KEY`.

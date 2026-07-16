# Colibri Local Brain — Operator Cheatsheet

> **No hardcoded operator paths.** Before running `pwsh scripts/start_colibri_server.ps1`,
> set the env vars below. Defaults resolve to `$Env:USERPROFILE\local-models\colibri`
> (Win) or `$Env:HOME/local-models/colibri`; clones on other operator machines just
> override the env vars — no path edits to this cheatsheet necessary.
>
> ```
> $Env:COLIBRI_ROOT              = '<your colibri checkout>'      # must contain c\glm.exe + c\coli + c\openai_server.py
> $Env:COLIBRI_WEIGHTS_DIR       = '<your GLM-5.2 weights dir>'   # .out-*.safetensors
> $Env:COLIBRI_LOCAL_LLAMA_PORT  = 8081                           # match $Env:COLIBRI_URL in .env
> ```

Single-machine setup that runs the agency's primary brain on the operator's
Windows box against the JustVugg/colibri C runtime serving GLM-5.2. No API
key. No cloud billing. The rendered outputs are 100% offline.

This doc covers: tools, prerequisites, install sequence, runtime toggles,
monitoring, and tearing down — all on a fresh Windows 11 / PowerShell 7 host.

---

## 1. Tools & artifacts

| Item | Path on this box | Size | Purpose |
|------|------------------|------|---------|
| JustVugg/colibri repo | `$Env:COLIBRI_ROOT` | ~30 MB | C runtime + Python OAI-compat gateway |
| Colibri build outputs | `$Env:COLIBRI_ROOT\c\glm.exe` | ~3 MB | The C engine (built via `make -C $Env:COLIBRI_ROOT\c`) |
| Colibri Python wrapper | `$Env:COLIBRI_ROOT\c\coli` | ~35 KB | Drives `glm.exe` + `openai_server.py` |
| OAI-compat gateway | `$Env:COLIBRI_ROOT\c\openai_server.py` | ~80 KB | Listens on `:8081/v1` |
| GLM-5.2 weights | `$Env:COLIBRI_WEIGHTS_DIR` | ~370 GB | Mateogrgic int4 + int8-MTP SD checkpoint |

The repo scripts this doc references:

| Script | Purpose |
|--------|---------|
| `scripts/setup_colibri.ps1` | One-shot toolchain + clone + `make -C c` |
| `scripts/download_glm52_weights.ps1` | Resume-friendly HF download (uses `HF_TOKEN` from `.env`) |
| `scripts/start_colibri_server.ps1` | Start `coli serve` on `:8081` |
| `scripts/wait_for_colibri_ready.ps1` | Block until download + `/v1/models` both green |
| `scripts/status_colibri_server.ps1` | One-shot health snapshot |
| `scripts/stop_colibri_server.ps1` | Stop `coli serve` (kills task tree + cleans PID file) |
| `scripts/local_controller.py` | Cloud-bridge daemon: polls Render, starts/stops local |

---

## 2. Prerequisites (machine state)

1. PowerShell 7 (`pwsh`; `winget install Microsoft.PowerShell` if 5.1 is current)
2. MinGW-w64 toolchain with `make` (or `mingw32-make`) on PATH
   - w64devkit recommended: [skeeto/w64devkit releases](https://github.com/skeeto/w64devkit/releases)
   - Strawberry Perl alternates: ships gcc + make
3. `huggingface_hub[cli]` (`pip install -U 'huggingface_hub[cli]'`) — gives `hf`
4. `$Env:COLIBRI_WEIGHTS_DIR`'s parent directory (`local-models\`) with **>=410 GB free** (370 GB weights + 50 GB llama.cpp overhead)
5. `HF_TOKEN` in this machine's `.env` (gitignored) — set via:

   ```powershell
   $env:HF_TOKEN = 'hf_xxxxxxxx'              # current session
   setx HF_TOKEN 'hf_xxxxxxxx'                # all sessions, persisted
   ```

   Or accept slower anonymous-tier downloads (rate-limited; expect 2-3x slower).

---

## 3. Install sequence (cold machine → specced)

```powershell
# 1. Build the C runtime (one-shot, ~30 sec)
pwsh scripts/setup_colibri.ps1

# 2. Pull the GLM-5.2 weights (multi-hour; resume-friendly)
pwsh scripts/download_glm52_weights.ps1

# 3. Once both finished, start coli on :8081
pwsh scripts/start_colibri_server.ps1

# 4. Block until /v1/models returns glm-5.2
pwsh scripts/wait_for_colibri_ready.ps1 -MaxWaitSeconds 600
```

The watcher reports a `BrainResolution`-shape JSON when ready:

```json
{
  "provider_id": "colibri",
  "base_url": "http://localhost:8081/v1",
  "model": "glm-5.2",
  "source": "env_colibri",
  "priority": 100
}
```

---

## 4. Wiring the agency brain

The repo already has the wiring complete (commits through `0ed95c9`). Three
env vars + one preference are all you need:

```powershell
$env:COLIBRI_ENABLED    = 'true'                       # register the provider
$env:COLIBRI_URL        = 'http://localhost:8081/v1'   # where coli serve is listening
$env:COLIBRI_MODEL      = 'glm-5.2'                    # model id llama-server advertises
$env:BRAIN_PREFERENCE   = 'colibri'                    # skip cloud brain entirely
```

Or persist via `setx`. The provider is auto-registered by `ProviderRouter.from_env()`
on next boot from `providers/colibri.py`, and is classified `free_cloud` so
the routing policy never refuses it as "paid escalation".

---

## 5. Verifying end-to-end

```powershell
# 1. coli /v1/models must list glm-5.2
curl http://localhost:8081/v1/models

# 2. Brain resolver picks colibri (run from any shell with the env above)
python -c "import asyncio, os; from brain import resolve_active_brain; print(asyncio.run(resolve_active_brain()))"

# 3. Tiny chat via the proxy (online)
curl http://localhost:8000/v1/chat/completions `
     -H 'Content-Type: application/json' `
     -d '{"model":"glm-5.2","messages":[{"role":"user","content":"hi"}]}'
```

---

## 6. Local controller daemon — the cloud bridge

The agency on Render needs to know whether the local brain is up. The
`scripts/local_controller.py` daemon (registered in Task Scheduler as
`ColibriLocalBrainController`) polls the cloud every 30 s (env
`LOCAL_BRAIN_INTERVAL`) and:

- when desired=`on`: starts `start_local_glm_server.ps1` and probes
  `http://127.0.0.1:8072/v1/models` until glm-5.2 is reported, posting
  `status=starting` heartbeats so the admin UI shows liveness during the
  cold start
- when desired=`off`: runs `stop_local_glm_server.ps1` (`taskkill /T /F`
  frees VRAM)
- on every cycle: posts `{status, port_state, v1_models, models_has_glm52,
  error}` to `/api/local-brain/heartbeat`

**Caveat (port/script mismatch):** the daemon currently defaults to port **8072**
and calls `start_local_glm_server.ps1`. The colibri wiring ships at port **8081**
with `start_colibri_server.ps1`. Align these by editing the env overrides
(`LOCAL_BRAIN_HTTP_PORT=8081`,
`LOCAL_BRAIN_START_SCRIPT=...\\start_colibri_server.ps1`) in the wrapper.cmd
registered with Task Scheduler, or update `scripts/local_controller.py`'s
defaults to the colibri paths.

---

## 7. Cloud-side toggle

The cloud-side admin Providers page exposes a single "Local Colibri brain"
toggle. The toggle writes to Render's `/api/local-brain/state` DB row, and
the local daemon picks up the change on its next tick. Permission model:

- Cloud PATCH requires authenticated admin JWT (admin SPA auto-injects).
- Local daemon posts heartbeats with `X-Service-Token: <LOCAL_BRAIN_TOKEN>` —
  `LOCAL_BRAIN_TOKEN` must equal the cloud's `SERVICE_TOKEN`. On Render
  this is `rnd_...` token kept in the dashboard env (`sync: false`); on the
  local box, it lives in the wrapper.cmd registered with Task Scheduler.

When you change the cloud token (rotation), regenerate both sides in the
same PR/turn.

---

## 8. Tear-down

```powershell
# Stop coli serve
pwsh scripts/stop_colibri_server.ps1

# Optionally disable in the agency:
$env:BRAIN_PREFERENCE = 'nvidia'           # back to cloud brain
$env:COLIBRI_ENABLED  = 'false'           # unregister the provider
```

---

## 9. Failure modes

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `curl /v1/models` returns `[]` and HTTP 200 | Weights still streaming from disk; expert dispatch not finished | Wait — first load writes ~60-90 GB then pauses; check `.colibri.log` |
| `AttributeError: 'APIRouter' has no attribute 'router'` at import | FastAPI 0.110+ removed `APIRouter.router` — pre-existing repo bug in `backend/server.py:9558`, unrelated to colibri | File a regression issue; do not block colibri work on it |
| `BRAIN_PREFERENCE=colibri` resolves to `provider_id='ollama'` | `COLIBRI_URL` not set or stale | `setx COLIBRI_URL http://localhost:8081/v1` + restart shells |
| Cloud `/api/local-brain/heartbeat` returns 401 | `LOCAL_BRAIN_TOKEN` rotated but daemon was not updated | Re-run `pwsh scripts/setup_local_controller.ps1` after each Render token rotation |
| Local daemon's `/v1/models` probe returns HTTP 0 (connection refused) for >240 s | Cold start hit VRAM-swapping or expert-dispatch stall | Inspect `logs/glm-5.2*.log` for `dispatcher.exhausted`; raise `LOCAL_BRAIN_START_TIMEOUT` |

---

## 10. Cheatsheet one-liners

```powershell
# Start the whole stack from scratch in 4 lines:
pwsh scripts/setup_colibri.ps1; pwsh scripts/download_glm52_weights.ps1;
pwsh scripts/start_colibri_server.ps1; setx BRAIN_PREFERENCE colibri

# Stop everything:
pwsh scripts/stop_colibri_server.ps1; setx BRAIN_PREFERENCE nvidia

# Diagnose (one-shot health snapshot):
python -m scripts.local_controller --diagnose

# Continuous liveness watch (refresh every 10 s in your terminal):
while ($true) { python -m scripts.local_controller --once ; Start-Sleep -Seconds 10 }
```

---

## See also

- `docs/runbooks/render-multiacct.md` — multi-account Render tier (the
  agency-hub + forum-brain + workers live on a second Render account)
- `docs/architecture/brain-routing.md` — how `brain_policy.py` + `provider_router.py`
  collapse the free/paid priority tree into a single resolved model id
- `AGENTS.md § Risky Module Review Required` — `agent/tools.py`,
  `admin_auth.py`, and `key_store.py` require the `risky-module-review`
  skill before any change; `scripts/local_controller.py` is **not** on the
  risky list but operates as a writing process on the operator's box, so
  review every diff that adds new env vars or new outer-process spawns.

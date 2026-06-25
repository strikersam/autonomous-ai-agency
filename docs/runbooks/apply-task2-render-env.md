# Runbook — Apply the Fast Free NVIDIA Brain to Render (TASK 2)

The live `https://local-llm-server.onrender.com/api/autonomy/status` reports

```json
"brain": { "configured": true,
            "model": "nvidia/nemotron-3-ultra-550b-a55b",
            "provider": "nvidia-nim",
            "paid_allowed": false }
```

— the **slow** 550B-a55b ultra (≈55B params/token) is still pinned in the Render
dashboard env. `render.yaml` on `master` already specifies the faster
`nvidia/nemotron-3-super-120b-a12b` (≈12B params/token, same-generation MoE,
free, no rate limit). **Render does not auto-apply `render.yaml` env changes on
a code redeploy**, so this runbook is the manual sync step.

> This runbook writes only **env values**. It changes no source files and does
> not set `ALLOW_PAID_BRAIN=true`. The free-only brain policy is preserved.

---

## TL;DR

| Option | When to use | Effort |
|--------|-------------|--------|
| **A. Blueprint sync** | You have write access to the Render Blueprint for this repo | 1 click + wait for redeploy |
| **B. Manual per-service editor** | The Blueprint won't sync (e.g. YAML drift, locked infra) | ~5 minutes per service |

After either path, the verification curls at the bottom of this doc must show
`status:"autonomous"`, `brain.model:"nvidia/nemotron-3-super-120b-a12b"`,
`missing_secrets:[]`, and all four loops `true`.

---

## Status quo — what render.yaml already pins on master

For reference, the *current* correct values (read from `render.yaml` on
`master`, commit `2fc8435`):

- Web service `local-llm-server`:
  `NVIDIA_DEFAULT_MODEL`, `AGENT_PLANNER_MODEL`, `AGENT_EXECUTOR_MODEL`,
  `AGENT_VERIFIER_MODEL`, `AGENT_JUDGE_MODEL` = `nvidia/nemotron-3-super-120b-a12b`
- Worker service `local-llm-server-worker`: same five keys.
- `LLM_PROVIDER` = `nvidia-nim` on both.
- `RUN_BACKGROUND_IN_WEB` = `true` on the **web** service (loops run here on
  the free tier — no paid worker required).
- `AUTONOMY_PROTECTED_BRANCHES` = `main,master` on both.
- `TELEGRAM_POLLER_DISABLED` = `true` on the `freebuff-telegram-bot` worker
  (single-poller guard against Telegram `409 getUpdates` conflicts).

The five **fast-model** env keys above are the only ones this runbook flips.
All other secrets and knobs left alone.

---

## Option A — Blueprint sync (preferred)

1. Render dashboard → **Blueprints** → the blueprint linked to
   `strikersam/autonomous-ai-agency`.
2. If the dashboard shows **"Review changes"** for the latest sync, click
   **Apply Changes**.
3. Render queues a redeploy on **both** `local-llm-server` (web) and
   `local-llm-server-worker`, applying every `value:` line in `render.yaml`
   while preserving `sync: false` secrets.

If no "Review changes" prompt is queued (the Blueprint was already in sync
but the values have drifted in the dashboard), jump to **Option B**.

---

## Option B — manual per-service editor

Repeat each step twice: once for `local-llm-server` (web), once for
`local-llm-server-worker`. The freebuff-telegram-bot worker is already
configured correctly per `render.yaml` — leave it alone.

### B.1 — Open the service's Environment tab

Render dashboard → service → **Environment** → **Add Environment Variable** /
edit existing keys → **Save**. Save auto-triggers a redeploy.

### B.2 — Set these five keys on each service

Set (or update) the **same value** on both services:

| Key | Value |
|-----|-------|
| `NVIDIA_DEFAULT_MODEL` | `nvidia/nemotron-3-super-120b-a12b` |
| `AGENT_PLANNER_MODEL` | `nvidia/nemotron-3-super-120b-a12b` |
| `AGENT_EXECUTOR_MODEL` | `nvidia/nemotron-3-super-120b-a12b` |
| `AGENT_VERIFIER_MODEL` | `nvidia/nemotron-3-super-120b-a12b` |
| `AGENT_JUDGE_MODEL` | `nvidia/nemotron-3-super-120b-a12b` |

If `AGENT_JUDGE_MODEL` is **not yet present** in the dashboard (older
deploys only had four `AGENT_*_MODEL` keys), add it as a new key.

### B.3 — Sanity-check the secrets that must NOT regress

For both services, confirm the following are intact — **do not edit them** unless
the verification curls later show they are missing. Render the value with the
**eye icon** (not the clipboard) and visually re-type-if-needed; never paste.

| Service | Key | Expectation |
|---------|-----|-------------|
| both | `NVIDIA_API_KEY` | starts with `nvapi-` (mask as `nvapi-****`) |
| web | `LLM_PROVIDER` | `nvidia-nim` |
| web | `RUN_BACKGROUND_IN_WEB` | `true` |
| web | `RUN_TELEGRAM_BOT` | `true` (only once a Telegram token is set; see runbook for TASK 3) |
| both | `AUTONOMY_PROTECTED_BRANCHES` | `main,master` |
| both | `AGENCY_WORKFLOW_MODE` | `orchestrator` |
| **NEVER** | `ALLOW_PAID_BRAIN` | **unset** or `false` — do not turn on paid Anthropic |

### B.4 — Trigger TASK 5 keep-alive immediately

`render.yaml` includes a keep-alive GitHub Actions cron at `.github/workflows/keepalive.yml`
(10-minute cadence). After the redeploy completes, **also** trigger one
`workflow_dispatch` run now so the service stays warm until the cron fires:

> Requires a GitHub PAT with `workflow` scope on `strikersam/autonomous-ai-agency`.
> Never commit the PAT.

```bash
# Replace <PAT> with a token of yours, then strip from history immediately.
curl -X POST \
  -H "Authorization: token <PAT>" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/strikersam/autonomous-ai-agency/actions/workflows/keepalive.yml/dispatches \
  -d '{"ref":"master"}'
```

Success is a `204 No Content`. Open the Actions tab → **Keep-alive** → the
green run tells you the service was awake enough to answer `/api/health`
within ~60 s.

> For the **full** keep-alive verification (GitHub cron health, external
> 5-minute monitor recipe, acceptance table) see
> `verify-task3-5-telegram-and-keepalive.md` §5.

---

## Verification

Run all three in sequence. Re-run until each one satisfies its expectation.

### V.1 — liveness

```bash
curl -fsS https://local-llm-server.onrender.com/api/health
```

Expect: `200 OK`, body `{"status":"ok","mongo":true}`.

### V.2 — autonomy readiness

```bash
curl -fsS https://local-llm-server.onrender.com/api/autonomy/status | python -m json.tool
```

Expect (key fields):

| Field | Expected |
|-------|----------|
| `status` | `"autonomous"` (warm) or `"partial"` (still warming — re-run in 30 s) |
| `brain.configured` | `true` |
| `brain.model` | `"nvidia/nemotron-3-super-120b-a12b"` |
| `brain.provider` | `"nvidia-nim"` |
| `brain.paid_allowed` | `false` |
| `missing_secrets` | `[]` |
| `loops.log_monitor` | `true` |
| `loops.self_healing` | `true` |
| `loops.improvement_loop` | `true` |
| `loops.trend_watcher` | `true` |
| `loops_running` | `4` |

### V.3 — doctor (public, no auth)

```bash
curl -fsS https://local-llm-server.onrender.com/api/doctor/public | python -m json.tool
```

Expect: `ready: true`, `summary: "5/5 checks passing — healthy"` (or 4/5 with
only the harmless `Ollama unreachable — start with ollama serve` warn —
`LLM_PROVIDER=nvidia-nim` so the local Ollama absence is expected).

---

## Rollback

The five env keys are independent. If the 120B-a12b endpoint starts returning
errors (rare; it briefly 404'd around issue #656 — re-confirmed live at
<https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b>), revert each
key on both services to its prior value. The documented rollback target is
`nvidia/llama-3.3-nemotron-super-49b-v1` — also a free NIM model, denser, and
in the curated live list.

Render dashboard → service → Environment → edit key → Save. The redeploy is
fast (~30 s for the web service, ~60 s for the cold-start-free worker).

---

## Security notes

- Never print the full `NVIDIA_API_KEY`. The dashboard's eye-icon reveals are
  fine for verification; never paste into chats, commits, PRs, or logs — mask
  as `nvapi-****`.
- Never set `ALLOW_PAID_BRAIN=true`. The free-only brain policy is the
  on-by-default charter invariant; turning it on bypasses the budget gate and
  costs real money per task.
- Never point any `AGENT_*_MODEL` at a `claude-*` / `us.anthropic.*` model.
  Those will silently route to api.anthropic.com / Bedrock and fail with 4xx
  on the free policy.

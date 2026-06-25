# Runbook — Verify Telegram Approval Gate + Keep-Alive (TASK 3, 4, 5)

This runbook covers the **human-in-the-loop** verification steps for the
autonomous agency on Render. It pairs with `apply-task2-render-env.md`
(TASK 2). Both must be green before declaring the platform "verified
fully autonomous".

> **Out of scope here:** the *brain fix* (TASK 2 / slow-model pin) and any
> change to source code. This runbook only verifies env-driven behaviour.

---

## TL;DR

| Task | What success looks like | Automatable from a CI? |
|------|--------------------------|------------------------|
| **5 — Keep-alive** | `.github/workflows/keepalive.yml` ran green; `/api/health` returns `200` within 60 s of every trigger | partial — the **dispatch + curl** step is automatable; the **5-min external monitor** is a manual signup |
| **3 — Telegram bot** | Web service has `RUN_TELEGRAM_BOT=true` + valid `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`; worker has `TELEGRAM_POLLER_DISABLED=true`; bot replies to `/start` or `/status` | only the **API curl** leg is automatable; the **chat interaction** is human-in-the-loop |
| **4 — Approval gate (E2E)** | A workflow run that pauses at `ApprovalGate` delivers a Telegram message with `[✅ Approve] [❌ Reject]` buttons; pressing either resolves the run | only the **enqueue + status** legs are automatable; the **button press** is human-in-the-loop |

A non-human verification harness could exercise the API path end-to-end (a
fake Telegram server stub + a stubbed callback). That is intentionally out
of scope of this runbook — the proof of the gate is the *real* push and the
*real* operator response.

---

## Background — why one process owns the poll

Telegram allows **only one** `getUpdates` consumer per bot token. The web
service runs the `WorkflowOrchestrator` in-process
(`RUN_BACKGROUND_IN_WEB=true`), so the **G1 approval-gate Approve/Reject
callbacks** must be answered by the same process that emits the message.

`render.yaml` already encodes this:

- web service `local-llm-server`: `RUN_TELEGRAM_BOT: "true"`, owns the poll.
- worker `local-llm-server-worker`: not configured for Telegram polling —
  sends notifications only.
- worker `freebuff-telegram-bot`: `TELEGRAM_POLLER_DISABLED: "true"` — the
  single-poller guard. Only enable polling here if you give it a **separate**
  bot token (set the guard to `"false"`).

If you ever see a Telegram `409 Conflict: terminated by other getUpdates
request` or a `429 Too Many Requests` storm in the logs, it is because two
processes tried to poll the same token. Re-enable the guard.

---

## TASK 5 — Keep-alive (free-tier 24×7)

### 5.1 — Confirm the workflow exists

`.github/workflows/keepalive.yml` is already on `master` (commit `2fc8435`).
Schema:

- `on.schedule: "*/10 * * * *"` — every 10 minutes.
- `on.workflow_dispatch` — manual run.
- Pings `$BASE_URL/api/health` with 6 retries × 15 s backoff
  (60 s timeout each), survives cold-start.
- `BASE_URL` defaults to `https://local-llm-server.onrender.com`; override
  via repo variable `KEEPALIVE_URL` if the service URL ever changes.

### 5.2 — Trigger one run now (don't wait for the cron)

> Requires a GitHub PAT with **Actions: Write** scope on
> `strikersam/autonomous-ai-agency`. Mask the PAT in any output.

```bash
# Replace <PAT> with a token dropped into your shell history **only** for the
# duration of this command, then rotate it.
curl -fsS -X POST \
  -H "Authorization: Bearer <PAT>" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/strikersam/autonomous-ai-agency/actions/workflows/keepalive.yml/dispatches \
  -d '{"ref":"master"}' && echo OK
```

Expect: `204 No Content`, terminal prints `OK`. Then:

```bash
gh run list --repo strikersam/autonomous-ai-agency --workflow keepalive.yml --limit 3
```

Expect: the newest run is **green** within ~60 s, the run log contains
`GET /api/health -> 200` on the first or second attempt.

### 5.3 — Add an external 5-minute monitor (hard uptime)

GitHub cron is best-effort (delays under load). For hard 24×7, point a free
monitoring service at the same URL:

- **UptimeRobot** → Add Monitor → HTTP(s) →
  `https://local-llm-server.onrender.com/api/health` → interval **5 min**.
- **cron-job.org** → Create Cronjob → URL above → every **5 min**.
- **Better Uptime** (alternative) — same shape.

If the monitor fails twice consecutively, ping the operator (you). This
catches Render free-tier spin-down faster than the GitHub cron alone.

### 5.4 — TASK 5 acceptance

- ✅ keepalive workflow has at least 3 green runs within the last hour.
- ✅ External monitor reports **up** for the last 24 h (skip if not yet
  configured; the GitHub cron is still in effect).

---

## TASK 3 — Telegram bot (config + chat verification)

### 3.1 — Confirm env vars on the **web** service

Render dashboard → `local-llm-server` → **Environment**. Verify (do not
print full values to chat or logs):

| Key | Expectation | Mask |
|-----|-------------|------|
| `RUN_TELEGRAM_BOT` | `"true"` | — |
| `TELEGRAM_BOT_TOKEN` | looks like `<digits>:<base64>` from @BotFather | `****` |
| `TELEGRAM_CHAT_ID` | your **numeric** Telegram user ID from @userinfobot | `****` |
| `BOT_KEEPALIVE` | `"true"` (ensures the bot self-pings so the free instance stays awake) | — |

If `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` is missing, generate them:

1. @BotFather → `/newbot` → save the token → paste into
   `TELEGRAM_BOT_TOKEN` (sync:`false`).
2. In Telegram, message @userinfobot → it returns your numeric id → paste
   into `TELEGRAM_CHAT_ID`.
3. **Save** in Render → auto-redeploy.

### 3.2 — Confirm single-poller guard on the **worker**

Render dashboard → `freebuff-telegram-bot` → Environment. Verify:

- `TELEGRAM_POLLER_DISABLED` = `true`.

If you ever decide to run a *second* bot here on a separate token, you must
also set `TELEGRAM_BOT_TOKEN` to that separate token (do **not** reuse the
web service's token) and set `TELEGRAM_POLLER_DISABLED` to `false`.

### 3.3 — Verify the bot responds (human-in-the-loop)

Open Telegram, find your bot by its @handle, send `/start` (or `/status`).

Expect within ~2 s:

```
🤖 Hello! I'm your autonomous-ai-agency control bot.
   company, status: <…>, autonomy.status: <…>
```

> This is the only step in this runbook that requires opening Telegram.
> Everything else can be exercised with `curl`.

### 3.4 — TASK 3 acceptance

- ✅ Bot replies to `/start` / `/status` within 2 s.
- ✅ Web service env has all 4 keys from §3.1.
- ✅ `freebuff-telegram-bot` worker has `TELEGRAM_POLLER_DISABLED=true`.

---

## TASK 4 — End-to-end approval-gate test

This is the **real proof** that a risky/outward-facing action pauses for
human approval.

### 4.1 — Acquire an admin session

The login route is **`POST /api/auth/login`** in `backend/server.py` (uses
`LoginBody` and `_token_response`). It returns a session cookie + a token
JSON (`access` / `refresh` — confirm against `backend/server.py::_token_response`
on the running build). The orchestrator endpoints use `Depends(get_current_user)`,
so the session cookie (not a `Bearer` header) carries through.

```bash
# Replace with your Render-deployed admin creds (ADMIN_EMAIL / ADMIN_PASSWORD).
curl -fsS -c /tmp/.agency-cookies.txt \
  -X POST https://local-llm-server.onrender.com/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"<ADMIN_EMAIL>","password":"<ADMIN_PASSWORD>"}' \
  | python -m json.tool
chmod 600 /tmp/.agency-cookies.txt
```

> Strip `/tmp/.agency-cookies.txt` from any chat/log/commit immediately. The
> session has a finite TTL; re-mint per verification.

### 4.2 — Trigger an outward-facing workflow run

The orchestrator executes the 11-phase golden path and **must pause at the
ApprovalGate before any code is written** whenever `decide_merge()` returns
`requires_approval=True` (charter G5 — first unattended merge on a newly
connected repo; any merge under protected-branch policy; anything inferred
as outward-facing from the goal text). The request body is a typed
`ExecutionRequest` (`services/workflow_orchestrator.py:513–538`) — **it has
no `risk_class` field**; risk is inferred from the goal text + `decide_merge()`.

```bash
curl -fsS -b /tmp/.agency-cookies.txt -X POST \
  https://local-llm-server.onrender.com/api/workflow/orchestrator/execute \
  -H 'Content-Type: application/json' \
  -d @- <<'JSON'
{
  "request": "Open a draft PR titled 'docs: smoke test for ApprovalGate' on master.",
  "company_id": "<a real onboarded company id>",
  "auto_approve": false,
  "max_steps": 30
}
JSON
```

> Goal-text phrasing tips to maximise the gate pausing: mention **"PR"**,
> **"push"**, **"merge"**, or a **specific repo/branch** in the request
> string. `auto_approve: false` is the **default** — only set it `true` for
> trusted internal callers you want to bypass the gate.
> The endpoint returns 200/404/503 in normal operation and 202 for async
> modes (corroborated by `tests/e2e/test_live_server.py`). Treat any other
> 5xx as a regression.

Capture the returned `id`/`run_id` from the response envelope (shape per
`backend/server.py:7252` — `_workflow_orchestrator_create(orchestrator, body)`).

### 4.3 — Watch the run until it pauses

```bash
curl -fsS -b /tmp/.agency-cookies.txt \
  https://local-llm-server.onrender.com/api/workflow/orchestrator/runs \
  | python -c "
import sys, json
data = json.load(sys.stdin)
for r in data.get('runs', []):
    print(r.get('run_id') or r.get('id'), r.get('status'))
" | head -20
```

> The list endpoint (`backend/server.py:7361`) returns
> **`{"runs": [ {...}, ... ]}`** — non-admin users see only their own runs;
> admins see every run. Filter for the run you just created.

Expect within ~30 s:

```
<run_id>   awaiting_approval
```

> If the run goes straight to `done` without pausing, the planner's risk
> classifier did not flag the goal as outward-facing, or `auto_approve`
> was mistakenly `true`. Tighten the goal text (explicitly mention "PR",
> "push", or "merge") or use the admin UI workflow screen to pick a
> flagged workflow.

### 4.4 — Confirm the Telegram message arrived

In Telegram, your bot should have sent a message to `TELEGRAM_CHAT_ID`
containing:

- run id,
- company name,
- redacted plan summary,
- risk reason (e.g. `outward_facing`, `first_unattended_merge`),
- inline `[✅ Approve]  [❌ Reject]` buttons.

### 4.5 — Press ✅ Approve

Click **Approve** in Telegram (`telegram_bot.py` handles the `wfo:approve:<run_id>`
callback; only `TELEGRAM_ADMIN_USER_IDS` or the `TELEGRAM_CHAT_ID` fallback
can press it).

Expect within ~5 s:

- The Telegram message edits to `<run_id> approved by <chat_id> — resumed`.
- The run status moves from `awaiting_approval` → `approved` → `running` → `done`.
- `GET /api/workflow/orchestrator/runs/<run_id>` shows the run in a terminal state.

```bash
curl -fsS -b /tmp/.agency-cookies.txt \
  https://local-llm-server.onrender.com/api/workflow/orchestrator/runs/<run_id> \
  | python -m json.tool
```

The detailed endpoint (`backend/server.py:7378`) returns
**`{"run": {<run_dict>}}`**. Expect `status: "done"`, and for the
default draft-PR case `run.merge_decision.action` ∈
`{"open_pr", "direct_push", "telegram_gate", "awaiting_repo_connection"}`.

### 4.6 — Trigger another and press ❌ Reject

Re-run §4.2 with the same goal — or wait for the next loop-driven run.

Press **Reject** in Telegram.

Expect: message edits to `<run_id> rejected by <chat_id> — cancelled`, run
status moves to `cancelled`.

### 4.7 — TASK 4 acceptance

- ✅ `awaiting_approval` runs push a Telegram message with both buttons.
- ✅ Approve resumes the run, terminal status is `done`.
- ✅ Reject cancels the run, terminal status is `cancelled`.

### 4.8 — Optional TASK 4.D (issue→task intake)

Only if `GITHUB_WEBHOOK_SECRET` is set in the Render dashboard **and** a
GitHub webhook → `POST /api/webhooks/github` is configured for
`strikersam/autonomous-ai-agency`:

1. Create an issue with the label `autonomy:intake`.
2. Within ~60 s a Task appears on the board with `source_id =
   "strikersam/autonomous-ai-agency#<number>"` (idempotent — re-label won't
   duplicate).
3. An agent picks it up and proposes its change as a **draft PR** — never a
   direct push. The first unattended merge on a connected repo will pause
   for the Telegram gate per Autonomy Charter G5 (`merge_decision.action:
   "telegram_gate"`), then subsequent merges follow the recorded policy
   (`open_pr` / `direct_push`).

---

## Definition of done — six-item PASS/FAIL grid

Mirror of the **Definition of Done** in `AUTONOMOUS_AGENCY_SETUP.md`:

| # | Item | Evidence | PASS / FAIL |
|---|------|----------|-------------|
| 1 | `/api/autonomy/status` reports `status:"autonomous"`, `brain.model:"nvidia/nemotron-3-super-120b-a12b"`, `missing_secrets:[]`, all 4 loops `true` | curl + JSON dump | ☐ |
| 2 | `/api/doctor/public` shows no critical failures (5/5 passing, or 4/5 with the harmless Ollama warn) | curl + JSON dump | ☐ |
| 3 | Telegram bot responds (`/start`), and an `awaiting_approval` run pushed a message with both buttons | Telegram screenshot + run id | ☐ |
| 4 | Pressing Approve resumed a run; pressing Reject cancelled one | two runs, terminal `done` and `cancelled` | ☐ |
| 5 | Keep-alive workflow ran successfully and the service stays warm | `gh run list` 3/3 green + external monitor up | ☐ |
| 6 | (Optional) An `autonomy:intake` issue produced a Task → PR, gated for first merge | issue link + draft PR link + run with `merge_decision.action:"telegram_gate"` | ☐ |

Once items 1–5 are all ✅, the platform is **verified fully autonomous**.
Item 6 is **strongly recommended** before connecting any non-toy repo.

---

## Security notes

- Never paste a real admin token, bot token, chat id, or PAT into chat,
  logs, commits, or PRs. Mask everywhere: `<BOT_TOKEN>`, `<CHAT_ID>`,
  `<PAT>` style placeholders only.
- The admin session token (§4.1) is short-lived by design — re-mint a fresh
  one for each verification run.
- Rotate any token immediately if it is ever pasted into the wrong context.
- Keep `ALLOW_PAID_BRAIN` unset / `false`. The approval gate is intentionally
  a *human* checkpoint on top of the free-only brain — bypassing the brain
  budget does not bypass the gate, and vice versa.

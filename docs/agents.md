# Agents

This document covers the coding agents exposed by `local-llm-server`, with a
focus on **FreeBuff** — a self-hosted, Codebuff-style coding agent that runs on
free NVIDIA NIM models and is controllable from your phone via Telegram.

For the underlying three-role orchestration loop (planner → executor → verifier)
see `agent/CLAUDE.md` and `docs/architecture/agent-orchestration.md`.

---

## FreeBuff — free-NVIDIA coding agent

`FreeBuffAgent` (in `agent/loop.py`) is a thin subclass of `AgentRunner` that
**pins model selection to a curated set of free NVIDIA NIM models**. It reuses
the full plan → execute → verify loop and all existing `WorkspaceTools` file
operations, but it will never route to a paid endpoint — `resolve_model()`
coerces any non-free model request back to a free one.

### Free model set

The default free models are:

| Model | Role |
|-------|------|
| `nvidia/nemotron-3-super-120b-a12b` | heavy reasoning / execution |
| `qwen/qwen2.5-coder-32b-instruct` | coding |
| `meta/llama-3.3-70b-instruct` | general |
| `meta/llama-3.1-8b-instruct` | fast / cheap |
| `deepseek-ai/deepseek-r1` | reasoning |

Override the list with `FREEBUFF_MODELS` (comma-separated) for new-model
rollouts without touching code.

When `NVIDIA_API_KEY` (or `NVidiaApiKey`) is set, the runner is pinned to the
NVIDIA NIM base URL (`https://integrate.api.nvidia.com/v1`) with the key in the
`Authorization` header. With no key set it falls back to a local OpenAI-compatible
base so construction never fails (tests / local-only deployments).

### HTTP API

All endpoints require a valid API key (`Authorization: Bearer <key>` or
`x-api-key: <key>`), same as the rest of the proxy.

| Method & path | Purpose |
|---------------|---------|
| `GET /freebuff/models` | List the free models a user can pick. |
| `POST /freebuff/plan` | Generate a **read-only** plan (no files written) for review. |
| `POST /freebuff/run` | Execute the task; optionally commit and open a draft PR. |

Request body for `plan`/`run` (`FreeBuffRunRequest`):

```json
{
  "instruction": "fix the failing health check",
  "model": "qwen/qwen2.5-coder-32b-instruct",
  "auto_commit": false,
  "open_pr": false,
  "repo_url": null,
  "max_steps": 10
}
```

`model` is coerced to a free model if a paid/unknown id is supplied. PRs are
never pushed to protected branches directly — the runner isolates changes on a
fresh feature branch and opens a PR (gated by `AGENT_AUTO_PR_ENABLED`). The repo
target comes from `repo_url` or the `FREEBUFF_REPO_URL` env var.

### Unlimited by default

FreeBuff is meant to be an *unlimited* free coding agent, so the `/freebuff/*`
routes **skip the per-key RPM limiter by default** (`proxy._is_freebuff_unlimited`).
The routes are still fully auth-gated (a valid API key is required) and only ever
run free NVIDIA models, so this doesn't open up paid endpoints. To re-impose the
limiter on FreeBuff routes:

```
FREEBUFF_UNLIMITED=false
```

Separately, specific store-backed keys can be exempted from the limiter on **all**
endpoints via an allowlist (e.g. for the Telegram bot's own key when it also calls
`/agent/run` or chat):

```
FREEBUFF_RATELIMIT_EXEMPT_KEY_IDS=kid_telegrambot
```

This is opt-in (default empty). Legacy keys (no `key_id`) are never exempt, and
all non-FreeBuff endpoints stay rate-limited as usual.

---

## Telegram phone control

The Telegram bot (`telegram_bot.py`) drives FreeBuff entirely from a phone using
inline buttons. Admin-only.

### `/freebuff <task>`

1. The bot fetches the free model list (`GET /freebuff/models`) and shows a
   **model-picker** inline keyboard (one button per model).
2. Tapping a model generates a plan (`POST /freebuff/plan`) and shows the steps
   with **✅ Accept & run** / **❌ Reject** buttons.
3. **Accept** runs the task (`POST /freebuff/run` with `auto_commit` + `open_pr`)
   and reports the result summary and PR URL.
4. **Reject** discards the task — nothing is written.

Because planning is read-only, the accept/reject review happens *before* any code
is changed. Callback buttons re-check that the user is an allowed admin, and the
per-user FreeBuff state expires when a session is started, accepted, or rejected.

Inline-button callbacks use compact `fb:<action>[:<arg>]` data (e.g.
`fb:model:1`, `fb:accept`, `fb:reject`); model selection sends an **index** into
the per-user model list to stay within Telegram's 64-byte callback_data limit.

---

## Running 24×7

To drive FreeBuff from your phone anytime, run the Telegram bot as an always-on
worker (Render free tier or Docker). It runs the agent in-process (**embedded
mode**) — no proxy server needed — clones the repo, edits on free models, and
opens a draft PR. Full step-by-step: [`docs/deploy/freebuff-telegram-bot.md`](deploy/freebuff-telegram-bot.md).

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `FREEBUFF_MODELS` | (built-in list) | Comma-separated free model override. |
| `FREEBUFF_UNLIMITED` | `true` | When on, `/freebuff/*` routes skip the RPM limiter. |
| `FREEBUFF_RATELIMIT_EXEMPT_KEY_IDS` | (empty) | key_ids exempt from rate limiting everywhere. |
| `FREEBUFF_REPO_URL` | (none) | Default repo for FreeBuff draft PRs. |
| `NVIDIA_API_KEY` / `NVidiaApiKey` | (none) | Enables NVIDIA NIM routing. |
| `AGENT_AUTO_PR_ENABLED` | off | Master switch for agent-initiated PRs. |

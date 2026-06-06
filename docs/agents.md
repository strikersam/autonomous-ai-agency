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

### Rate-limit exemption

Phone-driven FreeBuff runs can be exempted from the per-key RPM limiter so a
long agent session isn't throttled. This is **opt-in and narrowly scoped**:

```
FREEBUFF_RATELIMIT_EXEMPT_KEY_IDS=kid_telegrambot
```

Only store-backed keys whose `key_id` is on this allowlist skip the limiter
(`proxy.is_rate_limit_exempt`). The default is empty, so no key is exempt and
all paid/general endpoints stay protected. Legacy keys (no `key_id`) are never
exempt.

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

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `FREEBUFF_MODELS` | (built-in list) | Comma-separated free model override. |
| `FREEBUFF_RATELIMIT_EXEMPT_KEY_IDS` | (empty) | key_ids exempt from rate limiting. |
| `FREEBUFF_REPO_URL` | (none) | Default repo for FreeBuff draft PRs. |
| `NVIDIA_API_KEY` / `NVidiaApiKey` | (none) | Enables NVIDIA NIM routing. |
| `AGENT_AUTO_PR_ENABLED` | off | Master switch for agent-initiated PRs. |

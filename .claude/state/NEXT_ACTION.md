# Next Action

_Updated 2026-08-28._

## Nothing is blocked on an agent. Two things need a human.

### 0. The NVIDIA default model was a retired id — fixed, one item left open

Every "model to use when `NVIDIA_DEFAULT_MODEL` is unset" fallback in the tree
pointed at `meta/llama-3.3-70b-instruct`, which answers `410 Gone` since
2026-08-26. All of them now point at `nvidia/nemotron-3-ultra-550b-a55b`, with
`nvidia/nemotron-3-super-120b-a12b` as the first fallback in
`.github/scripts/nvidia_models.py`. Both ids came from the account owner.

**Open, needs a human or a key:** `config/llm/models.yaml` has no entry for
either id, so `packages/llm/registry.py` treats them with cautious defaults and
`require_tools` filtering may drop them on that path. Adding entries needs real
context-window / max-output / capability numbers, which cannot be read from a
sandbox without egress to the NVIDIA catalogue. Anyone with the key can get
them from `GET /v1/models` and fill the entries in.

### 1. Render is suspended for billing — this is the big one

Service `srv-d7cb43beo5us73e1leug` (`local-llm-server`) is `suspended`,
`suspenders: ["billing"]`. Everything below is dark until that is resolved, and
none of it is fixable from a session:

- `PR_APPROVAL_GATE_ENABLED=true` cannot be set (`400 cannot deploy suspended
  service`), so there is no Telegram gate on PR approval.
- The in-process agency is down: CEO loop, self-healing, dispatcher, Telegram
  bot, `services/pr_approval_gate.py`.
- **Langfuse tracing is already wired** across `proxy.py`, `agent/loop.py`,
  `agent/agency.py`, `tasks/service.py`, `packages/ai/self_heal.py`,
  `services/otel_tracing.py`, `handlers/anthropic_compat.py`,
  `agent/trend_watcher.py`, `agent/sam.py`, `packages/config/settings.py`, with
  keys in `render.yaml` as `sync: false`. It emits nothing because the service
  is not running. No code change is needed — only billing.

`/api/ping` returns 000; Hermes 404s. The GitHub-Actions half of the agency
(37 loops) is unaffected and running.

### 2. PR #1336 needs a human decision

`anthropic >=0.122.0 → >=1.0.0`, against an SDK this repo calls through
`packages/ai/router.py` and `handlers/anthropic_compat.py`. Auto-merge was
disabled by hand and a comment posted. Rule 40 reserves a breaking dependency
upgrade for a person. Green CI is necessary but not sufficient — the risk is the
breaking change the suite does not cover.

## Running unattended, no action needed

- **Dependabot backlog: 12 open, draining ~1/hour.** `dependabot-auto-merge.yml`
  runs hourly, updates one stale branch per run (branch protection means only one
  PR can merge per run regardless), classifies each up-to-date PR with
  `scripts/classify_dependabot_update.py`, and arms auto-merge only for
  `group`/`minor`/`patch`. `major` and `unknown` go to a human. #1346 and #1345
  merged this way.
- **The plan→implement loop converged.** `agency-cycle` run 380 ran on `50b04aa7`
  (contains the parser fix `cfea9ff`) and filed no new failure issue — the first
  clean tick since the ghost-node-ID bug. #1331 and #1317 closed themselves;
  #1312 is on `retry:1`. Open issues 10 → 8.
- `process-quick-note.yml` picks the oldest open non-exhausted issue every 4h.
- `orphaned-pr-sweep.yml` runs daily at 06:00 UTC.

## If you pick this up next

Check that the Dependabot count keeps falling (12 → 0 over ~12 hours). If it
stalls, read the sweep log first — the exit code has been misleading three
separate times on this workflow, and every real defect was found by comparing
the log against the PRs' actual state.

# NEXT_ACTION — updated 2026-10-10 (UI revamp + rule 49)

Branch `claude/ui-revamp`: full dashboard and landing-page redesign (see `docs/design-system.md`) plus CLAUDE.md rule 49 (no "done" without an independent verifier's PASS, mirrored into every agent instruction file).

1. **Rule 49 verdict for this branch: PASS+NOTES.** Open note: on a deep link (e.g. /v5/work) the first Tab in headless Chromium did not always land on the skip link; not reproduced as a regression yet.
2. **Backend gate for rule 49 is not built.** Agency task completion is set in several places in `backend/server.py` (`task.status = "done"`); enforcing a verifier verdict there changes the task API and needs a human decision (rule 40).
3. Screens still worth a bespoke pass: Onboarding wizard steps, Skills catalogue, Provider console table density on tablets.

---

# NEXT_ACTION — updated 2026-10-10 (daily automation, GPT-6.1 Sol)

**Updated:** 2026-10-10 (daily automation, branch `claude/intelligent-gates-5hxtio`)

GPT-6.1 Sol (`gpt-6.1-sol`, OpenAI, released 2026-09-29) added to the model catalogue. PR [#1715](https://github.com/strikersam/autonomous-ai-agency/pull/1715) open, CI pending. 18 tests pass; compileall clean; changelog parity OK. The Claude GitHub App is not installed on this repo so PR events won't wake this session — check CI status manually.

## Open items for next daily run

1. **Check CI on PR #1715** — if green, merge. If red, investigate.
2. **GPT model deprecations (Oct 23, 2026)**: `gpt-3.5-turbo-0125`, `gpt-4-0613`, `gpt-4-1106-preview` retiring on 2026-10-23. Check if these IDs are in routing candidates and add deprecation notes.
3. **Groq Llama 4 Scout probe** (`meta-llama/llama-4-scout-17b-16e-instruct`) — move to active routing if probe passes (currently explicit-only, priority 99).
4. **Mistral Large 4 live probe** — not yet probed; router health checks will test once PR #1707 is merged.
5. **GPT-6.1 Sol live probe** — priority 99 (explicit-only); lower after confirming the model answers on OpenRouter.

---

# NEXT_ACTION — updated 2026-10-08 (screen audit fixes)

Branch `claude/project-thread-21yb6b`: fixes for the v5 screen vs backend audit (admin API gaps, QuickNotes, provider policy surfaces, Logs/Skills/GitHub shapes, voice STT containers, workflow route order, scheduler fail_count). Open PR, merge when CI is green. Not fixed on purpose: AgentsScreen per-agent counts (backend has no per-agent weekly stats, screen already falls back), Skills enable/disable still localStorage-only, MCP rows inert, no sprint start/complete UI, `/api/activation/settings` left readable by any signed-in user (documented design).
# NEXT_ACTION — updated 2026-10-09

**Updated:** 2026-10-09 (daily automation, branch `claude/intelligent-gates-rfkpo8`)

Mistral Large 4 ("Le Chonk", `mistral-large-4-0`) added to model catalogue. PR [#1707](https://github.com/strikersam/autonomous-ai-agency/pull/1707) open, auto-merge armed (squash). 17 tests, all green; compileall clean; changelog parity OK; loop registry no drift.

## Open items for next daily run

1. **Check CI on PR #1707** — if green, should have auto-merged. If red, investigate.

2. **Mistral Large 4 context window** — currently set to 131072 (conservative). Mistral docs may clarify whether 524K or 1M is the actual API limit; update `config/llm/models.yaml` when confirmed.

3. **GPT model deprecations (Oct 23, 2026)**: `gpt-3.5-turbo-0125`, `gpt-4-0613`, `gpt-4-1106-preview` retiring on 2026-10-23. Check if these IDs are in routing candidates and add deprecation notes.

4. **Groq Llama 4 Scout probe** (`meta-llama/llama-4-scout-17b-16e-instruct`) — move to active routing if probe passes (currently priority 99, explicit-only).

5. **Mistral Large 4 live probe** — model not yet probed on this account. Once the PR merges, the router's health check cycle will test it. If the probe fails, it enters the dead-model list until next health-check cycle.

---

# NEXT_ACTION — updated 2026-10-07

## Last session (2026-10-07, daily automation)

**What ran:** Daily 9 AM automation. Researched AI ecosystem developments since 2026-10-06.

**What shipped:** PR [#1697](https://github.com/strikersam/autonomous-ai-agency/pull/1697) — `feat(models): Groq prompt-caching cost fractions` (the proposed Nemotron 49B addition was dropped in review: the id is on RETIRED)
- `packages/ai/cost_tracker.py`: `qwen/` and `meta-llama/` added to `_CACHE_READ_FRACTIONS` (50 % Groq cache discount)
- `tests/test_daily_automation_2026_10_07.py`: 9 tests, all green
- Auto-merge armed (squash)

## Open items for next daily run

1. **Do not re-add retired ids.** Before proposing any model, check `RETIRED` in `tests/test_nvidia_default_model.py` and the retired comments in `config/models.yaml`; `nvidia/llama-3.3-nemotron-super-49b-v1.5` (2026-10-07) and `nvidia/nemotron-3.5-lightning-30b-a3b` (2026-10-06) were both proposed and rejected for this.

2. **GPT model deprecations (Oct 23, 2026)**: `gpt-3.5-turbo-0125`, `gpt-4-0613`, `gpt-4-1106-preview` are being retired by OpenAI on 2026-10-23. Check if these IDs are in the repo's routing candidates and add a deprecation note if so.

3. **Groq Llama 4 Scout probe** (`meta-llama/llama-4-scout-17b-16e-instruct`) — move to active routing if probe passes (currently explicit-only, priority 99).

4. **Cerebras `qwen3-235b` preview** — Cerebras account currently returns 402; add as a conservative candidate once the model answers HTTP 200.
# NEXT_ACTION — updated 2026-10-08

**Updated:** 2026-10-08 (daily automation, branch `claude/intelligent-gates-5vo4pc`)

Claude Haiku 5.5 (`claude-haiku-5-5`) released 2026-10-07 — added to cost tracker and models.yaml. PR #1698 opened, awaiting CI and merge. Priority 68 (candidate only; add to routing presets after a live probe on this account confirms it answers correctly). Next daily run: check CI on #1698, then scan for further new model releases (Claude Haiku 5.5 also available on Amazon Bedrock and Google Cloud — if new model IDs are announced for those platforms, add them as aliases).

# NEXT_ACTION — updated 2026-10-05

**Updated:** 2026-10-05 (daily routine, branch `routine/daily-2026-10-05`)

Sonnet 5.5 cost table corrected to $2/$10 (was $1.6/$8). Backlog issue #1688 items 2-4 remain: agent web-access master switch (S), "n of m" approval counter (XS-S), and a read-only compound-shell audit of `agent/tools.py` (risky module, needs human sign-off).


**Updated:** 2026-10-04 (bounty hunter, branch `claude/bounty-hunter`)

Bounty hunter shipped behind repo variable `BOUNTY_HUNTER_ENABLED`. After merge: owner sets the
variable, then runs the workflow once by hand (Actions → Bounty Hunter → Run) and checks the
run's job summary (the P&L table) and any `bounty:awaiting-review` issues. First real run is the
first time the Docker sandbox and fork push execute — watch that job's log.

**Updated:** 2026-10-04 (gpt-oss reasoning + reconciler loop, branch `fix/agent-loop-gpt-oss`)

Prod 12:05–12:38: Bedrock answers every call but steps fail (inline <reasoning>, 20b invents
tool results) and the reconciler loops 2 FAILED tasks at "retry 0/5". Fixed on this branch.
After deploy: watch for the first agent PR that passes agent/pr_gate.py.

**Updated:** 2026-10-04 (agent PR quality gate, branch `fix/agent-pr-quality-gate`)

First agent PRs exist (#1656, #1658–#1660) but none was mergeable: test for a missing module,
three async_queue.py copies with no tests/changelog. Now gated by `agent/pr_gate.py`; one PR per
initiative; DEFERRED work closed WONT_DO. After deploy: next agent PRs should carry tests +
changelog and go green; close the four bad PRs (done in this session with a comment).

---

**Updated:** 2026-10-04 (Bedrock model → Qwen3 Coder Next)

## Bedrock model switch 2026-10-04 — branch `fix/bedrock-qwen3-coder`
#1662 merged (gpt-oss reasoning strip, reconciler retry count). This branch moves the `bedrock`
provider to the Mantle endpoint (`bedrock-mantle.<region>.api.aws/v1`) with
`qwen.qwen3-coder-next` as its only model. After deploy check Render logs for
`attempt bedrock/qwen.qwen3-coder-next ok`; a 401/404 there means the Bedrock key is not
accepted on Mantle → revert providers.yaml base_url. Then watch step-error rate and the first
agent PR that passes `agent/pr_gate.py`. Groq gpt-oss "Tool choice is none" 400 still open.

---

**Updated:** 2026-10-04 (Bedrock live; tool-call aliases)

## Bedrock live 2026-10-04
#1654 and #1655 are on master and deployed (`4ea8b8a`). Render has AWS_BEARER_TOKEN_BEDROCK +
BEDROCK_BRAIN_ENABLED=true. Logs 08:26: `9 provider(s) ready: ... bedrock ...` and
`attempt bedrock/openai.gpt-oss-20b-1:0 ok`. Intake now picks fresh initiatives (no DEFERRED repeats).
Branch `fix/tool-call-aliases`: executor accepts `command`/`action`/`operation`/... as the tool name.
Next: watch for the first `Auto-PR opened` / `agent/task-*` PR, and Bedrock spend in the cost tracker.

---

**Updated:** 2026-10-04 (portfolio duplicate loop, row 97)

## Portfolio duplicate loop 2026-10-04 — branch `fix/portfolio-duplicate-loop`

#1654 is live (`ff58848`): prod tasks now run in a fresh clone + E2B sandbox. After this merges,
check Render logs: no new `portfolio_intake: created task` for the same initiative within an hour.
Biggest remaining blocker is LLM capacity: google 429 quota, groq 429/413, nvidia 429 within
~60 s; ~9 tasks sit BLOCKED on "All brain providers exhausted" and auto-retry burns more quota.
The open Bug Log rows marked DEFERRED / risky-module-review need a human decision; agents no
longer pick them up.
Bedrock (row 98): after merge set `AWS_BEARER_TOKEN_BEDROCK` (secret) and turn on
`BEDROCK_BRAIN_ENABLED`, then check logs for `llm.router: ... ready: ... bedrock` and
`attempt bedrock/openai.gpt-oss-120b-1:0 ok`. Spend shows in the cost tracker at $0.15/$0.60 per 1M.
Not fixed: Groq gpt-oss 400 "Tool choice is none, but model called a tool" (fails fast, ~0.3 s).

---


## Agent code work ships 2026-10-04 — branch `fix/agent-work-ships`

After merge and deploy, verify on prod: the next portfolio or issue task that changes files
opens an `agent/task-*` PR on GitHub. Tasks whose changes did not reach a PR now show FAILED
with a `Not delivered:` reason; check the Render logs for the clone/push error if they recur.
A portfolio or issue task that changed nothing now waits In Review. Clear those by hand or retry them.
E2B is on in prod (`E2B_ENABLED=true`): sandbox edits are now synced to the host before each step
commit. Follow-up: a custom `E2B_TEMPLATE` with the repo's deps so scoped pytest can run in the sandbox.
Bedrock: works (Opus 4.6 only; 4.7 denied). It is paid (AWS credit), agent brain stays off unless
`ALLOW_PAID_BRAIN=true`; proxy lists it last after free providers. Live test marked `integration`.
Known stale test: `tests/test_internal_agent_did_work.py` re-implements the gate (ratio 0.5,
the code uses 1.0) instead of calling the adapter, so it cannot catch regressions.

---
**Updated:** 2026-10-03 (portfolio drain + idle agents, row 94)
## Last session (2026-10-04, daily automation)

**What ran:** Daily 9 AM automation. Researched AI ecosystem developments since 2026-10-03.

**What shipped:** PR [#1653](https://github.com/strikersam/autonomous-ai-agency/pull/1653) — `feat(models): add GPT-5.5, GPT-Realtime-2.1, and Groq Llama 4 Scout to cost catalogue`
- `packages/ai/cost_tracker.py`: 5 new cost entries (gpt-5.5, gpt-5.5-pro, gpt-realtime-2.1, gpt-realtime-2.1-mini, meta-llama/llama-4-scout-17b-16e-instruct)
- `config/llm/models.yaml`: Groq Llama 4 Scout declared (priority 99, explicit-only, unprobed)
- `tests/test_daily_automation_2026_10_04.py`: 29 tests, all green
- Auto-merge armed (squash)

## Open items for next daily run

1. **Probe Groq Llama 4 Scout** (`meta-llama/llama-4-scout-17b-16e-instruct`) — if the Groq account has this model live, lower priority from 99 and add to routing candidates.

2. **Row 92** (`ci-failure-autofix` red) — `IN_PROGRESS` on `claude/cleanup-open-prs-issues-kdzv7g`. Check if PR was raised and merged.

3. **Row 94** (portfolio drain / idle agents) — `IN_PROGRESS` on `fix/portfolio-drain-idle-agents`. Check if merged.

4. **Row 95** (SAM NL actions) — `IN_PROGRESS` on `feat/sam-natural-language-actions`. Verify final status; should be merged by the time this runs.

5. **GPT model deprecations (Oct 23, 2026)**: `gpt-3.5-turbo-0125`, `gpt-4-0613`, `gpt-4-1106-preview` are being retired by OpenAI on 2026-10-23. Check if these IDs are in the repo's routing candidates and add a deprecation comment if so.

6. **Claude Code 2.1.287 "You Should Know" plugin** — A built-in side-agent plugin that flags things the user might miss. Consider whether there's a repo-applicable analogy (e.g., a pre-commit check that flags common mistakes). Low priority; assess against next run's candidate list.

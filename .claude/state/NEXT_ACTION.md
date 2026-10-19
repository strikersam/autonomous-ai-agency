# NEXT_ACTION — updated 2026-10-19 (branch `claude/amazing-sagan-3qwd7b`)

Repo restructure: `harness/` now holds the reusable, open-source-ready agent harness (86 generic
skills merged from `.claude/skills` + `.agents/skills`, subagents, commands, rules template,
connectors, loop guide, `sol-advisor` plugin). `.claude/agents`, `.claude/commands`,
`.claude/skills/<generic>` and `.agents/skills` are symlinks into it. README rewritten shorter.

## Open items

1. **Root launchers** (`*.sh`, `*.ps1`, `*.bat`, tunnel `.py` scripts) still sit at the repo root.
   Moving them to `scripts/local/` needs each one's root-path resolution rewritten and a test on
   Windows; not done because it could not be tested here.
2. **docs/** has overlapping folders (`adr/` vs `adrs/`, many one-off audit files). Consolidate.
3. **Open-sourcing the harness**: `harness/` is self-contained (own README, LICENSE, installer).
   Publishing = copy the folder to a new repo (dereference symlinks: none exist inside it).
4. Some harness skills still reference this repo's paths (e.g. `graphify`, `modularity-review`);
   generalise their wording before publishing.

---

# NEXT_ACTION — updated 2026-10-18 (daily automation, branch `claude/intelligent-gates-6bf3ev`)

NVIDIA Nemotron 3.5 Super VL (`nvidia/nemotron-3.5-super-vl:free`) added to model catalogue via OpenRouter free tier. PR [#1780](https://github.com/strikersam/autonomous-ai-agency/pull/1780) open. 13 tests verified; compileall clean; changelog parity OK.

## Open items for next daily run

1. **Check CI on PR #1780** — if green, merge. If red, investigate.

2. **Nemotron 3.5 Super VL tool-call probe** — declared `false` conservatively. Once PR merges, the router's health check cycle will test it. If it returns a valid `tool_calls` response, raise a PR to set `supports_tools: true` and `supports_function_calling: true`.

3. **Muse Spark Open live probe** (`meta-models/muse-spark-open`, priority 99) — still at priority 99. Once its PR is merged and deployed, check if the Groq account now has access (otherwise keep explicit-only).

4. **GPT model deprecations (Oct 23, 2026)**: `gpt-3.5-turbo-0125`, `gpt-4-0613`, `gpt-4-1106-preview` retire on 2026-10-23. Confirmed not in routing candidates as of today — re-verify after Oct 23.

5. **Groq Llama 4 Scout probe** (`meta-llama/llama-4-scout-17b-16e-instruct`, priority 99) — still pending a live probe.

---

# NEXT_ACTION — updated 2026-10-17 (daily automation, branch `claude/intelligent-gates-n8443c`)

Meta Muse Spark Open (`meta-models/muse-spark-open`) added to model catalogue. PR [#1777](https://github.com/strikersam/autonomous-ai-agency/pull/1777) open, auto-merge armed (squash). 18 tests pass; compileall clean; changelog parity OK.

## Open items for next daily run

1. **Check CI on PR #1777** — if green, should have auto-merged. If red, investigate.

2. **Muse Spark Open live probe** — priority 99 (explicit-only). Once the PR merges, the router's health check will test it. If a "contact sales" 403/401 comes back, add a note to the YAML and keep priority 99. Lower priority only after a live HTTP 200 completion.

3. **Groq Llama 4 Scout probe** (`meta-llama/llama-4-scout-17b-16e-instruct`) — still at priority 99 from 2026-10-04. Check if the Groq account now has this model and lower priority if it answers.

4. **GPT model deprecations (Oct 23, 2026)**: `gpt-3.5-turbo-0125`, `gpt-4-0613`, `gpt-4-1106-preview` retire on 2026-10-23. Confirmed not in routing candidates or cost tracker as of today — no action needed; re-verify after Oct 23.

---

# NEXT_ACTION — updated 2026-10-15 (review lane + judge evidence)

Shipped: #1761/#1762/#1763 (failed verification goes to FAILED, never Review; review autopilot moved 136 stuck tasks out at 10:49 UTC). Branch `claude/judge-diff-and-stubs`: the judge gets a real working-tree diff on host runs, and stubs named after a task id are rejected.

1. Root cause of the empty diff (found after #1768 shipped): `/app` has no `.git`, so task copies had no baseline and the E2B seed failed. Branch `claude/workspace-git-baseline` gives the copy a baseline commit. After deploy, Render logs should show "E2B sandbox seeded from /tmp/llm-task-copy-…" and "Judge brief: … git diff N chars" with N > 0 for host runs that changed tracked or new files (ignored files such as logs are still shown as content).
2. Many runs change nothing (0 changed files) and fail honestly; Failed will grow rather than Done. If that persists, the next lever is the planner/executor, not the verifier.
3. Operator: rotate the Browserbase key that was shared in chat on 2026-10-15.

# NEXT_ACTION — updated 2026-10-15 (evidence-driven verification)

#1765 merged 2026-10-15. Follow-up PR from the same branch carries the CodeRabbit fixes and restores the Bandit baseline (303).

1. After deploy, watch for tasks held with review reason "High-risk change verified; a person must approve it" (tag `risk:high-change`): verified agent changes to auth, secrets, governance, deploy, CI or migration paths no longer complete on their own. `VERIFICATION_POLICY_ENFORCED=false` restores the old verdicts while keeping the reports.
2. Follow-ups: produce an `EvidenceReport` from `tasks/independent_verifier.py` (non-loop runtimes) and from `_maybe_run_parallel`; record per-run token cost in the report.
3. Local runs without MongoDB: use `SKIP_DB_TESTS=1` (the pre-push hook sets it automatically).

# NEXT_ACTION — updated 2026-10-11 (durable state on SQLite)

Merged: #1719 (durable token ledger, sticky grants, tool-output offload on MongoDB), #1722 (docs), #1724 (same three stores on `STORAGE_BACKEND=sqlite`: numeric `expires_at_ts`, atomic single-statement increment, purge on write, `_id` primary-key lookups). This closes the "ledgers are in-memory per process" item in the 2026-10-10 Octop entry below. Follow-up branch `fix/sqlite-atomic-bandit-nosec` restores the Bandit count to 303 (the Security Gate is not a required check, so #1724 merged with 305).

## Open items

1. Consider making "Security Gate — No New Alerts" a required check in branch protection; auto-merge skipped it on #1724 (and on #1535 earlier, for Playwright).
2. `AGENT_DELEGATION_ENABLED=true` and `AGENT_USER_TOKENS_PER_DAY=2000000` are set on Render (`srv-d7cb43beo5us73e1leug`).

# NEXT_ACTION — updated 2026-10-11 (UI revamp + rule 49 in code)

Branch `claude/ui-revamp` → PR to master. Merge when CI is green (squash).

1. Rule 49 is now enforced for agency tasks (`TASK_VERIFICATION_REQUIRED`, default on). Watch "Needs you" on Home after deploy: tasks whose run has no judge verdict (analysis-only tasks, non-internal runtimes) now wait for a person. Follow-up worth doing: have the agency run its verifier role automatically on those so a person is not the only fallback.
2. Apper MCP connector is connected but has no projects; it cannot audit this repo or the live site.
# NEXT_ACTION — updated 2026-10-10 (Octop-inspired features)

Shipped from the Octop (TencentCloud/Octop) review, all merged: #1710 pre-push hook no longer leaks GIT_DIR into tests; #1711 per-user daily agent token cap (`AGENT_USER_TOKENS_PER_DAY`, off by default); #1712 lossless tool-output offload (`read_tool_output`); #1713 async specialist delegation (`AGENT_DELEGATION_ENABLED`, off by default); #1714 sticky session approval grants + runner identity. Follow-up branch `chore/finish-octop-followups` wires owner into the remaining runners.

## Open items

1. Token cap and offload ledgers are in-memory per process: on a multi-worker deploy, caps can overshoot by ~worker count. Persist if that matters.
2. Delegation and the token cap are off by default — turn on under Settings → Platform controls when wanted.
3. Local `pytest -x` cannot pass in cloud sessions without DNS (`tests/test_web_reach.py`); CI is the gate there.

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

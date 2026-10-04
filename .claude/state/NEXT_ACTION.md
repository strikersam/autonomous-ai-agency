# NEXT_ACTION — updated 2026-10-04

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

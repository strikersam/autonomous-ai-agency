# Agency Core — Operational Knowledge (verified live, 2026-06-10/11)

Everything below was verified against the running Cloudflare deployment, not inferred. This page is the durable copy; a wiki page mirrors it in the Knowledge screen.

## Architecture truths

**Execution brain.** `services/workflow_orchestrator.py` resolves the agent LLM endpoint via `_resolve_brain_provider()`: `AGENT_LLM_BASE_URL/API_KEY/MODEL` env override first, then the highest-priority configured provider record (lowest `priority` number wins; the same store the Providers screen shows), then local Ollama. Switching the brain = changing a provider priority. No redeploy.

**Provider records.** Anthropic works through its OpenAI-compatible layer: type `openai-compatible`, base `https://api.anthropic.com/v1/`, Bearer key. Current order: ClaudeCode (-30) > nvidia-nim-deepseek `deepseek-ai/deepseek-v4-pro` (-20) > nvidia-nim nemotron (-10). Free NIM tier ≈ 40 req/min/model; concurrent runs throttle each other.

**Ephemeral state (root of most "mystery" failures).** Orchestrator run history, scheduler jobs, and any in-flight agent work are lost on every backend restart/redeploy. Durable: GitHub (issues/PRs), the company graph store. Fix tracked in issue #505; until merged, the `post-deploy-verify` cadence self-recreates the supervision schedules, and definitions live as a comment on epic #504.

**Tokens.** User-initiated orchestrator runs have no GitHub token unless the execute payload carries `github_token`; only system runs (no user_id) use the server token. Issue #506 adds per-user stored tokens. Without a token, agents change workspace files but cannot open PRs — work silently evaporates on restart.

**Truthful status.** A run whose verification fails ends `failed` with issues in `run.error` (fixed in PR #503). Before this, runs reported `done` with zero changed files — treat any pre-2026-06-10 "success" metrics as unverified.

**Alerts.** The top-right AlertsBell polls `/api/activity` every 30 s. It appeared dummy because the endpoint returned `{logs,events,activity}` while the bell reads `items`/`activities` (fixed in PR #516). Alerts are now also DERIVED on read — failed runs (P1), runs awaiting approval (P2), empty scheduler = wipe warning — so the alert system itself cannot be wiped.

## Pros of linking the GitHub repo (vs running unlinked)

1. **Durability.** GitHub is the only store that survives restarts: issues are the backlog, PRs are the work, comments are the audit trail. Unlinked, agent output lives in an ephemeral workspace and dies with the container.
2. **Real HITL.** Approval moves to the merge button — agents propose, CI verifies, a human merges. Unlinked, "approval" gates an action whose result nobody can review.
3. **Self-improvement loop.** Quick Notes → auto-filed issues (#511, #513) → context PRs (#512, #514) → implementation PRs. The pipeline's every stage is repo-native.
4. **Evidence.** "34 specialists" or "autonomy KPIs" become checkable claims only when each maps to commits, PRs, and CI runs.
Label convention: tag issues whose value depends on the repo link as `repo-linked` so unlinked deployments know which features degrade.

## Runbooks

**After any redeploy:** check Schedules; if empty, recreate `agency-supervisor` (0 */4 * * *), `post-deploy-verify` (30 7 * * *), `tech-debt-marker-burndown` (0 6 * * 1,4) from the definitions comment on issue #504.

**Brain swap:** Providers screen (or `PUT /api/providers/{id}`) → change `priority`. Verify with a smoke run: file an orchestrator run to append a comment line to docs/changelog.md, approve, expect `done` + 1 changed file.

**Chronic CI:** Playwright job fails on Docker Hub pull timeouts (add registry auth or mirror); a workflow literally named `.devcontainer/devcontainer.json` and Security Scan fail on master — tracked in epic #504.

## Open backlog (epic #504)

#505 durable schedules/runs · #506 per-user GH tokens · #507 worktree isolation (concurrent runs share one workspace) · #508 providers edit UI · orchestrator runs board UI · doctor truth split · onboarding idempotency (duplicate companies) · scanner stall · skill library 0-loaded · 230 code markers (104 BUG / 71 TODO / 13 FIXME) burned down 3/run by schedule.

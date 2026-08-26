# Active Task Tracker

> **Living document** — updated by every agent session across all tools (Claude Code, Codex, Cursor, Aider, etc.)
> Rules: mark IN_PROGRESS when you start a task, DONE when verified, BUG_FOUND when you discover an issue,
> BUG_FIXED when resolved. Never delete rows — when a row closes, move it to
> `.claude/state/archive/` rather than deleting it.
>
> Only open work lives here. 63 closed rows and the full session log were moved to
> [`archive/completed-2026-06-to-08.md`](archive/completed-2026-06-to-08.md) on 2026-08-10 —
> the SessionStart hook injects the top of this file into every session, so finished work
> was being paid for on every task.
>
> **The six `IN_PROGRESS` rows below were last touched between 2026-06-05 and 2026-07-03.**
> Their branches may already be merged. Verify status before picking one up; none of them
> was re-verified during the archive split.

## Status Key

| Status | Meaning |
|--------|---------|
| `TODO` | Planned but not started |
| `IN_PROGRESS` | Being worked on this session |
| `DONE` | Implemented, tested, merged |
| `BLOCKED` | Waiting on external dependency |
| `BUG_FOUND` | Bug discovered during implementation |
| `BUG_FIXED` | Bug confirmed fixed (link the PR) |
| `DEFERRED` | Deprioritised — see Notes for why |

---

## Current Sprint Tasks

| # | Task | Status | PR / Branch | Notes | Updated |
|---|------|--------|-------------|-------|---------|
| 2 | Dynamic Session Planning Workflow (this task) | `IN_PROGRESS` | [#406](https://github.com/strikersam/local-llm-server/pull/406) | hooks + tracker + AGENTS.md update | 2026-06-05 |
| 6 | Portfolio refresh workflow → reuse RENDER_BACKEND_URL secret | `IN_PROGRESS` | claude/portfolio-refresh-backend-url | point cron ping at existing secret | 2026-06-06 |
| 8 | FreeBuff always-on Telegram bot (24×7 Render/Docker, embedded mode) | `IN_PROGRESS` | `claude/freebuff-telegram-deploy` | embedded in-process agent + launcher + Dockerfile.telegram + render worker + deploy docs | 2026-06-06 |
| 11 | SEO audit: browser-use fetch (Akamai bypass), honest revenue model, demoable UI tab + downloads | `IN_PROGRESS` | `claude/cool-davinci-494siy` | services/seo_fetch.py (httpx/Playwright/auto-escalate), diminishing-returns revenue curve, CompanyScreen SEO tab + CSV/JSON/MD downloads; 13 new fetch tests. Live Akamai bypass needs Playwright browsers in deploy | 2026-06-13 |
| 27 | Adversarial autonomy-paths audit + hardening | `IN_PROGRESS` | #694 | 2 `agent/`-local fixes (self-heal re-dispatch stranding; broken Hermes dispatch) + 3 tests. Deferred orchestrator-zone findings → Bug Log #9-#12. | 2026-06-19 |
| 32 | Move heavy voice deps out of the web image → standalone Dockerfile.voice (slim web image, fast cold starts) | `IN_PROGRESS` | `claude/sam-voice-livekit-xjow4g` (PR #935 pending) | Dockerfile.backend no longer installs requirements-livekit (~600MB); new Dockerfile.voice (slim+libgomp1, backend deps, CMD worker start); docs/render.yaml/tests updated | 2026-07-03 |
| 33 | Daily automation 2026-08-21: Claude 5 YAML catalog + workspace-id observability | `DONE` | `claude/nifty-pasteur-4zlcyu` | claude-sonnet-5/opus-5/haiku-4-5-20251001 added to models.yaml; default promoted to sonnet-5; anthropic-workspace-id header captured; 20 tests; changelogs updated | 2026-08-21 |
| 34 | Add TokenIn (tokenin.my.id) as a free rotatable brain provider | `DONE` (code) / `BLOCKED` (Render+live check) | `claude/tokenin-provider-integration-57v8k6` | Provider wired across models.yaml, brain_config Literal+fallbacks, brain_failover registry+opus alias, router from_env+free classification; 10 free `myt/` models as failover rotation; 6 new tests + count-assertion fixes across 4 suites. **BLOCKED:** Render env-var add refused — service `local-llm-server` suspended for billing (`cannot deploy suspended service`); live opus check not possible from this sandbox (egress policy blocks `tokenin.my.id`, 403 CONNECT). | 2026-08-22 |
| 35 | Frontend UX redesign: 20→6 IA, retire legacy UI, unify tokens | `DONE` (merged) | `claude/agency-ui-ux-redesign-yjvb85` (PR #1325 → master 67bd7f8) | Design canvas (Artifact) + implemented: 6 goal-based hubs w/ back-compat alias map for old /v5/* deep links; legacy /legacy dashboard + 21 pages + 6 dead components removed (~23k LOC); tokens unified to index.css (Tailwind Outfit→Manrope fix); new StatusPill/Spinner/HubTabs primitives. Fixed test_frontend_deployment_guards OAuth-origin guard (repointed from deleted SettingsPage.js → api.js — the one CI failure, unrelated to render). Squash-merged to master 2026-08-22 after governance #1324 landed first. | 2026-08-22 |
| 36 | Governance enforcement GA: policy+budget on every execution path, matrix STABLE | `DONE` (merged) | `feat/governance-enforcement-ga` (PR #1324 → master 9605f67) | GovernanceGate.charge feeds tokens/cost/depth; runtime dispatch runs the session budget; Surface.AGENT for spawn depth; all six ceilings fire independently; approvals fail-closed (TTL+restart); policies_governance→STABLE + policy_authoring_ui BETA; matrix-guard test. Squash-merged to master 2026-08-22. | 2026-08-22 |
| 37 | Policy Authoring UI GA: propose-via-PR editor, matrix STABLE | `DONE` (merged) | `feat/policy-authoring-ui-ga` (PR #1329 → master ff6ecd5) | New `packages/governance/authoring.py` validates a proposed policy against the real PolicyEngine + org baseline, diffs it, and opens a PR (never writes the live file). Router adds admin-only `GET /policy/raw`, `POST /policy/validate`, `POST /policy/propose` (needs GH_PAT); Governance screen gains a load→validate→propose editor. Org baseline can be tightened from the dashboard but never loosened (refused before any PR). `policy_authoring_ui`→STABLE + matrix-guard test; 30 authoring tests; docs + both changelogs. One CI fix (mounted the editor component — CRA no-unused-vars). Squash-merged to master 2026-08-23. | 2026-08-23 |
| 38 | Unblock the autonomous loop: real failing-test node IDs + a database for the loop workflows | `DONE` (merged) | [#1358](https://github.com/strikersam/autonomous-ai-agency/pull/1358) → master `cfea9ff` | Four root causes, each masked by the previous one. (a) `agency-cycle.yml`'s `grep -E '^(FAILED\|ERROR) '` matched pytest captured log records (`LEVEL logger:file.py:lineno`), emitting bogus IDs like `qwen-proxy:app_settings.py:70` that no pytest run resolves — the agent never converged and escalated every run (#1354). (b) `continuous-improvement.yml`'s `grep '^FAILED '` dropped ERROR summary lines, so error-only runs reported nothing (#1352). Both now call new unit-tested `scripts/parse_pytest_failures.py`. (c) Those two workflows declared no `mongo:7` service while `ci.yml` always had one, so only they saw `ServerSelectionTimeoutError` — the PR gate stayed green while the loop failed daily. Both now declare it. (d) Six modules set `ADMIN_EMAIL` at import after `backend/server.py` had captured a different value → seed 200 then login 401; conftest pins it. Plus `MEMORY_KERNEL_DIR` per-session temp dir. **Recorded trap:** pinning `STORAGE_BACKEND=sqlite` clears the error but hangs the suite — a non-daemon aiosqlite `_connection_worker_thread` stops interpreter exit (51+ min vs master's 3m27s, on a job with no `timeout-minutes`); tried, caught pre-merge, reverted. 30 new tests. | 2026-08-26 |

---

## Bug Log

| # | Bug Description | Found | Fixed | PR | Status |
|---|----------------|-------|-------|----|--------|
| 9 | Agent `write_file` workspace-isolation leak: `tests/test_e2e_agent_chat.py::TestAgentFullPRWorkflow::test_agent_full_pr_workflow` monkeypatches `_CHAT_AGENT_WORKSPACE_ROOT` to `tmp_path` and mocks an executor `write_file("src/main.py", "def hello(): return 'Hello Agent'")` step. Running the full suite (`pytest -q --ignore=tests/e2e`, 2026-06-14) left a real `src/main.py` with that exact content at the repo root — the agent write escaped the isolated `tmp_path` workspace into the live checkout. Root cause not yet isolated (suspects: `agent/loop.py` MCP-first `write_file` dispatch ~line 1051, or `WorkspaceTools` default-root fallback in `agent/tools.py`). Needs `risky-module-review`. | 2026-06-14 | — | — | `BUG_FOUND` |
| 16 | **GATE BYPASS (P0, DEFERRED):** `requires_approval` only redirects the final DONE→IN_REVIEW transition (`tasks/service.py:755`; `tasks/store.py:194` `list_pending` has no `requires_approval` filter), so the dispatcher runs the agent to completion BEFORE any approval. Mitigated by the agent's own autonomy gate (no merge/push to protected branches), but the charter's "gate risky/outward-facing BEFORE executing" needs a pre-EXECUTE gate. Architecturally significant + in the active orchestrator/telegram zone → needs an explicit decision. | 2026-06-19 | — | — | `BUG_FOUND` |
| 17 | **DEFERRED (orchestrator zone):** (a) `workflow_orchestrator.py` first-merge gate is coupled to `run.approved` not "this merge consented", so a restored/auto-approved run can skip it; (b) `services/repo_connection.py::decide_merge` returns `awaiting_repo_connection` with `requires_approval=False`, letting an auto-approved no-repo run execute-and-discard; (c) 16-hex signatures over `[:120]`-truncated inputs can collide and drop distinct heals/trends; (d) untracked `asyncio.create_task(ensure_self_company())` in `services/background.py` swallows exceptions. | 2026-06-19 | — | — | `BUG_FOUND` |
| 18 | **DEFERRED (P2, pre-existing, low severity):** Stale-company-ID recovery in both `CompanyScreen.jsx` (PR #962) and `CompanyGraphPanel` in `KnowledgeScreen.jsx` (PR #1110) validates the persisted `COMPANY_ID_KEY` against only the first page of `api.listCompanies()` (`limit=100` default, `backend/company_api.py:390`). An admin/owner with >100 accessible companies whose stored ID falls outside that first page gets wrongly treated as stale — cleared and silently replaced with `list[0]`. Flagged by Codex review on #1110 (https://github.com/strikersam/autonomous-ai-agency/pull/1110#discussion_r3633223301). Needs either full pagination until the stored ID is found, or a direct per-ID company/graph lookup before treating it as stale — should fix both screens together to avoid the two staying inconsistent again. | 2026-07-22 | — | — | `BUG_FOUND` |

---

## Roadmap Items (from `docs/roadmap-killer-todos.md`)

| # | Item | Priority | Status | PR |
|---|------|----------|--------|-----|
| ★2 | Specialized Sub-Agents with Per-Role Models | P0 | `TODO` | — |
| A1 | Hermes ChatML Prompt Format | P0 | `TODO` | — |
| A2 | Multi-Hop ReAct Loop | P0 | `TODO` | — |
| B1 | Nemotron Reward Model Scoring | P0 | `TODO` | — |
| C2 | Function Calling (OpenAI-compatible) | P0 | `TODO` | — |
| ★5 | Sandboxed Agent Execution | P1 | `TODO` | — |
| ★6 | Cost Analytics + FTS5 Memory + Constitution | P1 | `TODO` | — |
| A3 | Capability Registry + Dynamic Tool Discovery | P1 | `TODO` | — |
| A4 | Async Task Queue | P1 | `TODO` | — |
| A5 | Inter-Agent Message Bus | P1 | `TODO` | — |
| B2 | SteerLM Steering Tokens | P1 | `TODO` | — |
| B3 | Synthetic Training Data Pipeline | P1 | `TODO` | — |
| B4 | NeMo Guardrails | P1 | `TODO` | — |
| B5 | NIM Connection Pooling + Circuit Breaker | P1 | `TODO` | — |
| C3 | Streaming Delta Reconstruction | P1 | `TODO` | — |
| C4 | Chat History Persistence | P1 | `TODO` | — |
| C5 | Context Window Management | P1 | `TODO` | — |
| C6 | Prompt Caching | P1 | `TODO` | — |
| D1 | Helm Chart | P1 | `TODO` | — |
| D2 | Docker Compose Production Stack | P1 | `TODO` | — |
| D3 | OpenTelemetry Distributed Tracing | P1 | `TODO` | — |
| E1 | Cross-Harness Routing | P1 | `TODO` | — |
| E2 | Self-Healing Agent Doctor | P1 | `TODO` | — |
| F2 | MCP Server | P1 | `TODO` | — |
| G1 | Per-Model Cost Attribution | P1 | `TODO` | — |

---

# Active Task Tracker

> **Living document** — updated by every agent session across all tools (Claude Code, Codex, Cursor, Aider, etc.)
> Rules: mark IN_PROGRESS when you start a task, DONE when verified, BUG_FOUND when you discover an issue,
> BUG_FIXED when resolved. Never delete rows — append new rows for re-attempts.

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
| 1 | Killer TODO Roadmap (docs only — 33-item backlog from 6 OSS repos) | `DONE` | [#406](https://github.com/strikersam/local-llm-server/pull/406) | Draft PR created, CI running | 2026-06-05 |
| 2 | Dynamic Session Planning Workflow (this task) | `IN_PROGRESS` | [#406](https://github.com/strikersam/local-llm-server/pull/406) | hooks + tracker + AGENTS.md update | 2026-06-05 |
| 3 | Agentic Portfolio Management (WSJF) + v5 Portfolio screen | `DONE` | #423, #426 | portfolio.py, agile health/retro, v5 board | 2026-06-06 |
| 4 | Autonomous Portfolio Intelligence (signals → initiatives, 6h cron) | `DONE` | [#427](https://github.com/strikersam/local-llm-server/pull/427) | portfolio_intelligence.py + refresh workflow + UI provenance | 2026-06-06 |
| 5 | Fix social login (Google & GitHub OAuth) | `DONE` | `claude/social-login-google-github-BBGoT` | 3 bugs fixed in backend/server.py — see bug log #4-6 | 2026-06-06 |
| 6 | Portfolio refresh workflow → reuse RENDER_BACKEND_URL secret | `IN_PROGRESS` | claude/portfolio-refresh-backend-url | point cron ping at existing secret | 2026-06-06 |
| 7 | FreeBuff agent (free NVIDIA models) + Telegram phone control (#416) | `DONE` | [#431](https://github.com/strikersam/local-llm-server/pull/431) merged | FreeBuffAgent + /freebuff/* endpoints + Telegram inline buttons + unlimited rate limit; tests + docs | 2026-06-06 |
| 8 | FreeBuff always-on Telegram bot (24×7 Render/Docker, embedded mode) | `IN_PROGRESS` | `claude/freebuff-telegram-deploy` | embedded in-process agent + launcher + Dockerfile.telegram + render worker + deploy docs | 2026-06-06 |
| 9 | SEO/GEO/AEO/AIO audit engine + repo fixer + revenue portfolio (#533, PR #534 plan) | `DONE` | `claude/cool-davinci-494siy` | 97-check engine, WSJF delegation, auto-fixer, API, 124 tests — see docs/seo-audit.md | 2026-06-12 |
| 10 | Autonomous agile ceremonies (standup/retro/sprint-planning) + Delivery Manager role (35th specialist family) | `DONE` | `claude/agentic-agile-workflows-8ymf4d` | agents/agile_ceremonies.py (standup/sprint-retro/backlog-retro/sprint-plan, 17 tests) + agile-ceremonies.yml cron (standup/retro/plan) + `delivery` specialist family (35th) bound to agentic-agile/agentic-portfolio, matrix + docs regenerated | 2026-06-14 |
| 11 | SEO audit: browser-use fetch (Akamai bypass), honest revenue model, demoable UI tab + downloads | `IN_PROGRESS` | `claude/cool-davinci-494siy` | services/seo_fetch.py (httpx/Playwright/auto-escalate), diminishing-returns revenue curve, CompanyScreen SEO tab + CSV/JSON/MD downloads; 13 new fetch tests. Live Akamai bypass needs Playwright browsers in deploy | 2026-06-13 |
| 12 | Fix specialist provisioning timeout + masked "something went wrong" errors (onboarding/SEO/gucci.com scan) | `DONE` | `claude/specialist-seo-scan-errors-pov08i` | onboarding.py Step 8 now backgrounded via asyncio.create_task; runtimes/control.py uses asyncio.to_thread for docker compose; api.js fmtErr() no longer masks e.message, added default/long-call axios timeouts; 1 new regression test | 2026-06-14 |
| 13 | Unblock PR #638 CI (4 pre-existing master bugs found while making #12 mergeable) | `DONE` | `claude/specialist-seo-scan-errors-pov08i` | (1) `.github/scripts/implement_agent.py` had 2968 trailing NUL bytes breaking py_compile; (2) `CompanyScreen.jsx` truncated `exp` instead of `export default CompanyScreen;`, broke npm build; (3) `proxy.py` alias `owned_by` was `llm-relay-alias` vs test's `autonomous-ai-agency-alias`; (4) `test_brain_priority_scanner.py::test_scanner_imports_cleanly` did `sys.modules.pop("services.scanner")` creating a duplicate WebsiteScanner class, breaking monkeypatch in all 9 `test_onboarding_provisioning.py` tests when run in full suite. Full `pytest -x` (2823 tests) now green | 2026-06-14 |
| 14 | Fix orchestrator P1 error-cascade (AttributeError 'dict'/'NoneType' has no attribute 'passed'/'company_id' + "Future exception was never retrieved" + stall-requeue loop flooding the activity feed) | `DONE` | `claude/agency-error-cascade-d2eoaw` | Root cause: `restore_in_flight()` rehydrated phase outputs as raw dicts (not Pydantic models) and left runs with no reconstructable `_request` as queued/running, so `execute(None, resume_run_id=...)` crashed on `req.company_id`/`req.user_id`, and the post-loop `run.verification.passed` check crashed on a dict. Fixed via `_PHASE_OUTPUT_MODELS` reconstruction + fail-fast on missing `_request` (workflow_orchestrator.py, orchestrator_supervisor.py), and `_QueueEntry.wait` flag so fire-and-forget `enqueue()` never calls `set_exception()` (orchestrator_queue.py). 5 new regression tests; full `pytest -x` (2868 tests) green | 2026-06-15 |
| 15 | Autonomy Charter + Master Goal Prompt (full-autonomy spec, Telegram-gated) | `DONE` | [#652](https://github.com/strikersam/autonomous-ai-agency/pull/652) | `docs/autonomy/AUTONOMY_CHARTER.md` (Gate Matrix, brain policy, 5 autonomous loops, G1-G5 gap table, acceptance criteria) + `docs/autonomy/MASTER_PROMPT.md` (CEO operating prompt) | 2026-06-15 |
| 16 | G1 — Proactive Telegram approval-gate push (`awaiting_approval` → inline Approve/Reject) + `TELEGRAM_CHAT_ID` single-operator convention | `DONE` | [#652](https://github.com/strikersam/autonomous-ai-agency/pull/652) | `WorkflowOrchestrator._notify_approval_gate()` → `NotificationDispatcher.send_approval_gate()`; `telegram_bot.py` `wfo:approve\|reject:<run_id>` callbacks (`approve_async`/`cancel_run`, not-found/already-resolved handling); `TELEGRAM_CHAT_ID` fallback for ALLOWED/ADMIN/NOTIFY chat IDs via `_resolve_bot_user_ids()`. New tests: `test_telegram_approval_gate.py`, `TestApprovalGateNotification`, `wfo:` callback tests in `test_telegram_freebuff.py`. Full `pytest -x` (2898 tests) green | 2026-06-15 |
| 17 | G2 — Closed-loop self-heal feedback (confirm error signature gone post-fix) | `DONE` | merged | `agent/self_healing.py` detected→fixing→verifying→resolved/regressed/awaiting_human + `note_recurrence`; bootstrapped in `services/background.py`. See `docs/changelog.md` [Unreleased]. Hardened in #694 (re-dispatch no longer strands a heal). | 2026-06-19 |
| 18 | G3 — Auto issue→task intake (GitHub issues → Task records) | `DONE` | merged | `POST /api/webhooks/github` + `tasks/issue_intake.py` (HMAC, `autonomy:intake` label gate, idempotent by `source_id`). See `docs/changelog.md` [Unreleased]. | 2026-06-19 |
| 19 | G4 — Per-company trend scoping (score trends vs each company's detected stack) | `DONE` | merged | `agent/trend_scoping.py` + `TrendWatcher.scope_trends_to_companies()`; per-company fan-out gated via Gate Matrix. See `docs/changelog.md` [Unreleased]. | 2026-06-19 |
| 20 | G5 — `RepoConnection` + `DeliveryPolicy` + orchestrator land-step | `DONE` | #685 | `models/company_graph.py` + `services/repo_connection.py` (`detect_delivery_policy`/`decide_merge`/consent) wired into `WorkflowOrchestrator` ApprovalGate (first-merge → Telegram gate). | 2026-06-19 |
| 21 | P0 unblockers (issue #656): brain hard-blocked on paid-Anthropic 400 + Telegram getUpdates 409/429/502 dual-poller storm | `BUG_FIXED` | [#652](https://github.com/strikersam/autonomous-ai-agency/pull/652) | `_resolve_brain_provider` no longer silently escalates to paid Anthropic (gated behind `ALLOW_PAID_BRAIN`, default off) → free NVIDIA NIM is the brain once `NVIDIA_API_KEY` is set, else falls to Ollama with an actionable log. Telegram poll loop honours `retry_after`/exp-backoff + `TELEGRAM_POLLER_DISABLED` single-poller guard (set on freebuff worker in render.yaml). Stale `NVIDIA_DEFAULT_MODEL` corrected. Tests in `test_brain_priority_scanner.py` + `test_telegram_freebuff.py`. **Operator must set `NVIDIA_API_KEY` in Render to fully unblock.** | 2026-06-17 |
| 22 | Slowness hotfix + free-brain headroom (storm guard, 150s→300s timeout) | `DONE` | #686 | `agent/log_monitor.py` operational-error skip + hourly cap; `tasks/service.py` timeout 300s. | 2026-06-19 |
| 23 | Default free brain → `nvidia/nemotron-3-super-120b-a12b` (faster reasoning MoE, ~12B active) | `DONE` | #687 | `brain_policy.py`/`agent/loop.py`/`render.yaml`/`.env.example`. **Live Render env var `NVIDIA_DEFAULT_MODEL` must be re-applied (Blueprint sync) to take effect — still shows 550b until then.** | 2026-06-19 |
| 24 | Public `GET /api/autonomy/status` readiness probe (brain/secrets/loops, no auth) | `DONE` | #688 | one-URL "is this deploy autonomous right now". | 2026-06-19 |
| 25 | Flaky `Test (Python 3.13)` root fix (background loops started under e2e TestClient) | `DONE` | #689 | `tests/conftest.py` defaults `RUN_BACKGROUND_IN_WEB=false`; ended the per-PR CI thrash. | 2026-06-19 |
| 26 | Keep-alive workflow (free-tier 24/7 autonomy, no paid worker) | `DONE` | #690 | `.github/workflows/keepalive.yml` pings `/api/health` every 10m (loops run in web via `RUN_BACKGROUND_IN_WEB=true`). | 2026-06-19 |
| 27 | Adversarial autonomy-paths audit + hardening | `IN_PROGRESS` | #694 | 2 `agent/`-local fixes (self-heal re-dispatch stranding; broken Hermes dispatch) + 3 tests. Deferred orchestrator-zone findings → Bug Log #9-#12. | 2026-06-19 |
| 29 | SAM voice worker in-process (fully hands-off) + ship voice/ in Docker image (pre-existing prod gap: /agent/sam/speak silently failed on Render) | `DONE` | `claude/sam-voice-livekit-xjow4g` (follow-up to #930) | `start_in_process()` daemon thread in backend lifespan (SAM_VOICE_IN_PROCESS, off under TESTING), Dockerfile installs voice/requirements-livekit.txt + `COPY voice/`, gTTS in backend reqs, 7 new tests + Dockerfile guard | 2026-07-02 |
| 28 | SAM realtime voice over LiveKit (taskmaster-style full-duplex: talk to SAM, SAM talks back, agency tools by voice) | `DONE` | `claude/sam-voice-livekit-xjow4g` | `voice/livekit_config.py` + `voice/livekit_token.py` (PyJWT room tokens, no new backend deps), `voice/sam_livekit_worker.py` (LiveKit Agents: Silero VAD → Deepgram/Groq STT → SAM LLM w/ get_agency_status·list_pending_tasks·create_task tools → ElevenLabs/Groq TTS; brain via `SAM_LLM_BASE_URL` → NVIDIA NIM/Hermes/proxy), backend `GET/POST /agent/sam/livekit/{status,token}`, SamVoiceScreen live mode (`livekit-client`, dynamic import, captions), `docs/SAM_VOICE_LIVEKIT.md`, 17 tests in `tests/test_sam_livekit.py`. Needs `LIVEKIT_URL/API_KEY/API_SECRET` + `GROQ_API_KEY` in Render to go live. | 2026-07-02 |
| 33 | BUG_FIXED: post-login 120s Proxy Read Timeout — /api/autonomy/status ran full self-onboarding inline (re-triggered every restart on ephemeral sqlite) + Chromium RAM on 512MB dyno | `BUG_FIXED` | `claude/sam-voice-livekit-xjow4g` (fix PR pending) | ensure_self_company now a guarded background task (bootstrap_scheduled/bootstrapping), SCANNER_HEADLESS_RENDER=off in render.yaml (static-tier fallback), regression test drives handler on one loop | 2026-07-03 |
| 32 | Move heavy voice deps out of the web image → standalone Dockerfile.voice (slim web image, fast cold starts) | `IN_PROGRESS` | `claude/sam-voice-livekit-xjow4g` (PR #935 pending) | Dockerfile.backend no longer installs requirements-livekit (~600MB); new Dockerfile.voice (slim+libgomp1, backend deps, CMD worker start); docs/render.yaml/tests updated | 2026-07-03 |
| 31 | BUG_FIXED: post-#931 Render deploy crash-loop — in-process voice worker OOM-killed the 512MB instance at boot | `BUG_FIXED` | `claude/sam-voice-livekit-xjow4g` (fix PR pending) | SAM_VOICE_IN_PROCESS now defaults to false (livekit_config.py + render.yaml); image still ships deps so flag-flip enables it on >=2GB instances; regression test pins default OFF; docs sizing guidance | 2026-07-03 |
| 30 | OpenHands-inspired hardening: StuckDetector (tool-loop no-progress abort) + microagents (`.openhands/microagents/` keyword-triggered planner knowledge) | `DONE` | [#932](https://github.com/strikersam/autonomous-ai-agency/pull/932) merged (`2b45a8e`) | `agent/stuck_detector.py` + `agent/microagents.py` wired into AgentRunner; 4 starter microagents; 22 new tests; all 28 CI checks green | 2026-07-03 |

---

## Bug Log

| # | Bug Description | Found | Fixed | PR | Status |
|---|----------------|-------|-------|----|--------|
| 1 | NVIDIA NIM double `/v1` URL in `agent/loop.py` line 911 | 2026-06-03 | 2026-06-03 | #397 | `BUG_FIXED` |
| 2 | ProviderManager vs ProviderRouter type mismatch in `direct_chat.py` | 2026-06-03 | 2026-06-03 | #399 | `BUG_FIXED` |
| 3 | TaskBoardScreen create-task modal silently swallowed API errors | 2026-06-05 | 2026-06-05 | #406 parent | `BUG_FIXED` |
| 4 | GitHub+Google share `session["oauth_state"]` — CSRF check always fails on multi-tab/provider-switch | 2026-06-06 | 2026-06-06 | `claude/social-login-google-github-BBGoT` | `BUG_FIXED` |
| 5 | Google redirect_uri via `url_for` breaks behind proxy — token exchange rejected by Google | 2026-06-06 | 2026-06-06 | `claude/social-login-google-github-BBGoT` | `BUG_FIXED` |
| 6 | GitHub OAuth URL missing `redirect_uri`; no timeout on httpx clients in login flows | 2026-06-06 | 2026-06-06 | `claude/social-login-google-github-BBGoT` | `BUG_FIXED` |
| 7 | Google login still "Invalid OAuth state" — session cookie doesn't survive Cloudflare↔Render hop + Render cold-start SESSION_SECRET rotation. Moved login state to server-side `oauth_states` collection | 2026-06-06 | 2026-06-06 | `claude/social-login-oauth-state-store` | `BUG_FIXED` |
| 8 | Social login 500 "Internal server error" — `_valid_login_state` subtracted naive MongoDB `created_at` from aware `now()` → TypeError (unhandled). Normalised naive datetime to tz-aware | 2026-06-06 | 2026-06-06 | `claude/social-login-naive-datetime-fix` | `BUG_FIXED` |
| 9 | Agent `write_file` workspace-isolation leak: `tests/test_e2e_agent_chat.py::TestAgentFullPRWorkflow::test_agent_full_pr_workflow` monkeypatches `_CHAT_AGENT_WORKSPACE_ROOT` to `tmp_path` and mocks an executor `write_file("src/main.py", "def hello(): return 'Hello Agent'")` step. Running the full suite (`pytest -q --ignore=tests/e2e`, 2026-06-14) left a real `src/main.py` with that exact content at the repo root — the agent write escaped the isolated `tmp_path` workspace into the live checkout. Root cause not yet isolated (suspects: `agent/loop.py` MCP-first `write_file` dispatch ~line 1051, or `WorkspaceTools` default-root fallback in `agent/tools.py`). Needs `risky-module-review`. | 2026-06-14 | — | — | `BUG_FOUND` |
| 10 | `.github/workflows/ci-failure-autofix.yml` called Anthropic API with `claude-sonnet-4-20250514` (original Claude Sonnet 4) — Anthropic retires this model on the Claude API 2026-06-15, would break the autofix workflow starting tomorrow. Updated to `claude-sonnet-4-6` to match the workflow's own header comment | 2026-06-14 | 2026-06-14 | `claude/nifty-pasteur-hvjqzn` | `BUG_FIXED` |
| 11 | `tests/test_onboarding_provisioning.py` (9 tests) fail with `['Blocked: target URL is not a safe public address (SSRF protection)']` ONLY in full/large-batch runs — the `wired` fixture's `monkeypatch.setattr(scanner_mod.WebsiteScanner, "scan_website", fake_scan_website)` stops taking effect once enough other test modules have run first, so `services.onboarding._scan_website` invokes the real (SSRF-blocked, headless-render-attempting) `WebsiteScanner.scan_website` for `*.example-*.com` hosts. Passes in isolation and in every small pairwise combination tried. **Reproduced identically on `origin/master` (`f34c5b3`)** with the same 53-file batch (`9 failed, 628 passed`) — confirmed pre-existing on master, independent of this branch's 8 changed files. Needs `risky-module-review` (touches `services/scanner.py` SSRF guard + async event-loop/CompanyAgency activation interplay, also logs `CompanyAgency: activation failed ...: Event loop is closed`, possibly related to bug #9). | 2026-06-14 | 2026-06-14 | `c6b7520` (#638), merged into `claude/agentic-agile-workflows-8ymf4d` via `c339ac4` | `BUG_FIXED` |
| 12 | CI "Test (Python 3.13)" jobs on `claude/agentic-agile-workflows-8ymf4d` hung 30+ min (vs master's ~2.5 min) on commit `4e6b087` — branch lacked master's `c6b7520`/#638 fix for the blocking `subprocess.run(["docker","compose",...])` call in `runtimes/control.py` reached via `services/onboarding.py`'s synchronous `await agency.activate_company(...)`. Resolved by merging `origin/master` (`c6b7520`) into the branch (merge commit `c339ac4`). | 2026-06-14 | 2026-06-14 | `c339ac4` | `BUG_FIXED` |
| 13 | Orchestrator P1 error-cascade flooding activity feed: `restore_in_flight()` rehydrated checkpointed phase outputs as raw dicts, so the post-execute `run.verification.passed` check raised `AttributeError: 'dict' object has no attribute 'passed'`; runs restored with no persisted `_request` stayed `queued`/`running` and were re-enqueued by the supervisor as `execute(None, resume_run_id=...)`, raising `AttributeError: 'NoneType' object has no attribute 'company_id'`. Both exceptions were `set_exception()`'d onto fire-and-forget `OrchestratorQueue.enqueue()` futures nobody awaits, so asyncio logged "Future exception was never retrieved" on GC for every retry — an endless stall→requeue→crash loop spamming P1 alerts for run IDs `wfo_2595df77ed1f`, `wfo_9f2a3ee2b1da`, `wfo_841a0518c956`, `wfo_a5151d808fa4`, `wfo_e6a9f78caf4e`, `wfo_bcea91a8ce81`, `wfo_23faf405831a`, `wfo_bf62ba125f00`, `wfo_ba879e94a168`. | 2026-06-15 | 2026-06-15 | `claude/agency-error-cascade-d2eoaw` | `BUG_FIXED` |
| 14 | Self-heal re-dispatch stranded a regressed heal forever: `agent/self_healing.py::_regress()` scheduled `_redispatch` fire-and-forget with no exception handling while zeroing `_verify_deadline`, so a re-dispatch failure left the heal in `REGRESSED` permanently (never retried/escalated/swept) — broke G2 closed-loop self-heal. | 2026-06-19 | 2026-06-19 | #694 (escalates to `AWAITING_HUMAN` on failure + done-callback) | `BUG_FIXED` |
| 15 | `agent/trend_watcher.py::dispatch_high_relevance_to_hermes()` called `asyncio.run()` from inside the running fetch loop (always `RuntimeError`) and leaked an `AsyncClient` via mangled indentation — the whole Hermes auto-dispatch arm was dead/broken. | 2026-06-19 | 2026-06-19 | #694 (now `async`/`async with`; left un-wired pending gated routing) | `BUG_FIXED` |
| 16 | **GATE BYPASS (P0, DEFERRED):** `requires_approval` only redirects the final DONE→IN_REVIEW transition (`tasks/service.py:755`; `tasks/store.py:194` `list_pending` has no `requires_approval` filter), so the dispatcher runs the agent to completion BEFORE any approval. Mitigated by the agent's own autonomy gate (no merge/push to protected branches), but the charter's "gate risky/outward-facing BEFORE executing" needs a pre-EXECUTE gate. Architecturally significant + in the active orchestrator/telegram zone → needs an explicit decision. | 2026-06-19 | — | — | `BUG_FOUND` |
| 17 | **DEFERRED (orchestrator zone):** (a) `workflow_orchestrator.py` first-merge gate is coupled to `run.approved` not "this merge consented", so a restored/auto-approved run can skip it; (b) `services/repo_connection.py::decide_merge` returns `awaiting_repo_connection` with `requires_approval=False`, letting an auto-approved no-repo run execute-and-discard; (c) 16-hex signatures over `[:120]`-truncated inputs can collide and drop distinct heals/trends; (d) untracked `asyncio.create_task(ensure_self_company())` in `services/background.py` swallows exceptions. | 2026-06-19 | — | — | `BUG_FOUND` |
| 18 | **DEFERRED (P2, pre-existing, low severity):** Stale-company-ID recovery in both `CompanyScreen.jsx` (PR #962) and `CompanyGraphPanel` in `KnowledgeScreen.jsx` (PR #1110) validates the persisted `COMPANY_ID_KEY` against only the first page of `api.listCompanies()` (`limit=100` default, `backend/company_api.py:390`). An admin/owner with >100 accessible companies whose stored ID falls outside that first page gets wrongly treated as stale — cleared and silently replaced with `list[0]`. Flagged by Codex review on #1110 (https://github.com/strikersam/autonomous-ai-agency/pull/1110#discussion_r3633223301). Needs either full pagination until the stored ID is found, or a direct per-ID company/graph lookup before treating it as stale — should fix both screens together to avoid the two staying inconsistent again. | 2026-07-22 | — | — | `BUG_FOUND` |

---

## Roadmap Items (from `docs/roadmap-killer-todos.md`)

| # | Item | Priority | Status | PR |
|---|------|----------|--------|-----|
| ★1 | 3-Phase Context-Pruner Middleware | P0 | `DONE` | agent/context_pruner.py integrated; 15 tests added (2026-07-06) |
| ★2 | Specialized Sub-Agents with Per-Role Models | P0 | `TODO` | — |
| ★3 | Reasoning Token Budget + Toggle | P0 | `DONE` | TokenBudget wired into AgentRunner._chat_text; set_token_budget(); 12 integration tests (2026-07-06) |
| A1 | Hermes ChatML Prompt Format | P0 | `TODO` | — |
| A2 | Multi-Hop ReAct Loop | P0 | `TODO` | — |
| B1 | Nemotron Reward Model Scoring | P0 | `TODO` | — |
| C1 | Structured Output / JSON Mode | P0 | `TODO` | — |
| C2 | Function Calling (OpenAI-compatible) | P0 | `TODO` | — |
| F1 | Precise Diff Application (Codebuff-style) | P0 | `TODO` | — |
| ★4 | Skill/Procedural Memory | P1 | `TODO` | — |
| ★5 | Sandboxed Agent Execution | P1 | `TODO` | — |
| ★6 | Cost Analytics + FTS5 Memory + Constitution | P1 | `TODO` | — |
| ★7 | Adaptive Loop Halting | P1 | `DONE` | `agent/adaptive_halting.py` AdaptiveHalter (velocity + consecutive-fail gates), wired into AgentRunner.run(); 14 tests (2026-07-13) |
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

## Session Log

| Date | Agent/Tool | Branch | Action |
|------|------------|--------|--------|
| 2026-06-05 | claude-sonnet-4-6 (Opus agent) | claude/llm-server-roadmap-pr-COcKN | Created roadmap TODO from 6 OSS repos research |
| 2026-06-05 | claude-sonnet-4-6 | claude/llm-server-roadmap-pr-COcKN | Built dynamic session planning workflow |
| 2026-06-14 | claude-sonnet-4-6 | claude/agentic-agile-workflows-8ymf4d | Implemented autonomous agile ceremonies (agents/agile_ceremonies.py + agile-ceremonies.yml cron) and added `delivery` (Delivery Manager) as the 35th specialist family |
| 2026-06-14 | claude-sonnet-4-6 | claude/nifty-pasteur-hvjqzn | Daily automation: researched Anthropic/Claude Code/Codex 2026-06 industry news; found Claude Sonnet 4 / Opus 4 retire on the Claude API 2026-06-15 — fixed `.github/workflows/ci-failure-autofix.yml` (`claude-sonnet-4-20250514` → `claude-sonnet-4-6`), added `tests/test_daily_2026_06_14.py` regression guard |
| 2026-07-06 | claude-sonnet-4-6 | claude/nifty-pasteur-ixksyh | Daily automation: researched Claude Code July 2026 (context compaction, subagent extended-thinking inheritance) + Codex July 2026 (configurable rollout token budgets, abort-on-exhaust). Implemented: (1) ★1 DONE — 15 tests for agent/context_pruner.py 3-phase pruner; (2) ★3 DONE — TokenBudget wired into AgentRunner._chat_text + set_token_budget() + _record_tokens() + 12 integration tests. 38/38 new tests pass, 54/54 related agent tests pass. |
| 2026-07-13 | claude-sonnet-4-6 | claude/nifty-pasteur-nwl1bt | Daily automation: researched Claude Code July 2026 (smarter auto-mode halting, /doctor, transcript protection) + Codex July 2026 (MCP tool search by default) + MCP spec 2025-11-25 (structuredContent + outputSchema). Implemented: (1) ★7 DONE — agent/adaptive_halting.py AdaptiveHalter (velocity + consecutive-failure gates) wired into AgentRunner.run(); (2) MCP structured output — MCPToolResult dataclass + call_tool_structured() for MCP spec 2025-11-25 structuredContent extraction. 28/28 new tests pass, 30/30 agent runner tests pass, 76/76 MCP tests pass. |

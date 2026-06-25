# 467 Final Acceptance Criteria

> Issue #467 §6 required: "Final acceptance criteria"

---

## Definition of Done

A spec section (A–K) is **DONE** when:

1. Code is written following AGENTS.md coding standards
2. All new functionality has tests in `tests/`
3. `pytest -x` passes with zero failures
4. No regression in existing test coverage
5. `docs/changelog.md` updated under `[Unreleased]`
6. If applicable: feature matrix updated to reflect new tier
7. If applicable: Pydantic models updated with `extra="forbid"`
8. If new env vars: `.env.example` and `docs/configuration-reference.md` updated

---

## Section-by-Section Acceptance Criteria

### §A — Company Graph + Onboarding

**Acceptance criteria:**
- [ ] `backend/company_onboarding.py` or similar exists with `onboard_company(url: str) -> Company` method
- [ ] Multi-pass scan: tech stack detection (Playwright), team structure inference, artifact inventory
- [ ] Company stored in `services/company_graph_store.py`
- [ ] `AgentRun.list_available_fixes()` includes onboarding fix
- [ ] Tests: `tests/test_company_onboarding.py` with mocked scan
- [ ] E2E test for full URL → Company Graph flow

### §B — 34 Specialist Families

**Acceptance criteria:**
- [ ] Engineering specialists built: Quality, Finance, Research, Agile (existing)
- [ ] Business specialists built: SEO, PIM, OMS, DAM, Analytics, Trading, Support/CRM
- [ ] Each specialist has `run(task: Task) -> Result` method
- [ ] Each specialist has tests in `tests/test_<specialist>.py`
- [ ] Specialists registered in `agent/skill_registry.py`
- [ ] Documented in `docs/architecture/agency-core-audit-2026-05-22.md`

### §C — ECC, Obsidian, Graphify, Council Review Wiring

**Acceptance criteria:**
- [ ] `ECCErrorCorrectionLoop` skill exists in `.agents/skills/ecc/`
- [ ] `ObsidianKnowledgeGraph` skill exists in `.agents/skills/obsidian/`
- [ ] `graphify` skill is wired to workflow phase (agent crafts phase calls graphify)
- [ ] `council-review` skill is wired to review phase
- [ ] `agent-browser` skill is wired for browser-needed tasks
- [ ] End-to-end test: task enters workflow → all four skills invoked in correct phase

### §D — Direct Chat as Control Center

**Acceptance criteria:**
- [ ] Intent classification: `direct_chat.py:classify_intent()` maps user message to action
- [ ] Sticky context: conversation history maintained across turns within session
- [ ] No metadata leakage: LLM responses do not expose internal state, API keys, or session IDs
- [ ] Unified control plane: direct_chat is the primary interface for all agent operations
- [ ] Tests: `tests/test_direct_chat_control_center.py` covering intent classification, sticky context, metadata leakage prevention

### §E — Workflow Engine as Canonical Backbone + Worktree Isolation

**Acceptance criteria:**
- [ ] All agent executions go through `workflow/engine.py`
- [ ] Phase sequence enforced: plan → execute → verify → judge (no phase skipping)
- [ ] Worktree isolation: each task runs in isolated git worktree, cleaned after completion
- [ ] Worktree root configurable via `AGENT_WORKSPACE_ROOT` env var
- [ ] Tests: `tests/test_workflow_engine.py` phase sequence tests, `tests/test_workspace_isolation.py`

### §F — Doctor Full Check List

**Acceptance criteria:**
- [ ] `GET /api/doctor/public` — providers, Ollama health (no auth required)
- [ ] `GET /api/doctor/diagnostics` — runtimes, workspaces, GitHub readiness, company graph integrity, feature matrix sanity, CI parity, background liveness (JWT required)
- [ ] `POST /api/doctor/fix/{check_name}` — real one-click fix (not just returning fix suggestions)
- [ ] `GET /api/doctor/list_available_fixes` — enumerate all available fixes
- [ ] `POST /api/doctor/run_deep_diagnostics` — full diagnostic run
- [ ] Tests: `tests/test_doctor_endpoints.py` covering all 8 checks + fix execution

### §G — CEO Autonomous Loop

**Acceptance criteria:**
- [ ] CEO agent executes on schedule (workflow dispatch or cron)
- [ ] Branch-protection-safe: uses GH_PAT with repo scope, respects branch protection
- [ ] Deduplication: same issue/PR not acted on twice
- [ ] Verified close: PR merged only after CI green + review approval
- [ ] `agent/agency.py` CEO loop has explicit dedupe and verified-close logic
- [ ] Tests: `tests/test_ceo_autonomous_loop.py` covering dedupe and verified-close

### §H — Public Site Truth

**Acceptance criteria:**
- [ ] `index.html` and docs reflect only WORKING/STABLE features
- [ ] FLAKY features labeled as DEVELOPMENT
- [ ] ADVERTISED-BUT-NOT-BUILT features labeled as PLANNED or removed
- [ ] Feature matrix in docs matches public site claims
- [ ] telegram_bot moved to DEVELOPMENT tier or opt-in (per spec directive)
- [ ] Tests: `tests/test_public_site_truth.py` — scrapes public site, verifies feature claims against test suite

### §I — Feature Matrix Discipline

**Acceptance criteria:**
- [ ] `docs/architecture/feature-matrix.md` updated with demotions for: async_agent_jobs, crispy_workflow, task_harness_runtime, multi_agent_swarm, openhands_runtime, sidecar_runtimes, openclaw_integration, quick_actions_ios, machine_peer_sync, jcode_runtime, tunnels, telegram_bot
- [ ] Public site updated to reflect demotions
- [ ] `tests/test_feature_matrix.py` exists and passes with new tiers

### §J — Contract Discipline

**Acceptance criteria:**
- [ ] `AgentRunner` Pydantic model has `model_config = {"extra": "forbid"}`
- [ ] `ModelRouter` Pydantic model has `model_config = {"extra": "forbid"}`
- [ ] `JobManager` Pydantic model has `model_config = {"extra": "forbid"}`
- [ ] `WorkflowOrchestrator` Pydantic model has `model_config = {"extra": "forbid"}`
- [ ] `SkillRegistry` Pydantic model has `model_config = {"extra": "forbid"}`
- [ ] All method signatures are locked (no `**kwargs` in public interfaces)
- [ ] Tests: `tests/test_contracts_agency.py` has explicit schema enforcement tests

### §K — CI Parity + E2E Coverage

**Acceptance criteria:**
- [ ] E2E test for onboarding: `tests/e2e/test_onboarding.py`
- [ ] E2E test for specialist provisioning: `tests/e2e/test_specialist_provisioning.py`
- [ ] E2E test for skill exec: `tests/e2e/test_skill_exec.py`
- [ ] E2E test for direct chat control center: `tests/e2e/test_direct_chat_control_center.py`
- [ ] E2E test for workflow engine backbone: `tests/e2e/test_workflow_backbone.py`
- [ ] E2E test for Doctor checks: `tests/e2e/test_doctor_checks.py`
- [ ] E2E test for CEO loop: `tests/e2e/test_ceo_loop.py`
- [ ] E2E test for HITL: `tests/e2e/test_hitl.py`
- [ ] E2E test for issue/PR lifecycle: `tests/e2e/test_issue_pr_lifecycle.py`
- [ ] All E2E tests run in CI (`pytest -x tests/e2e/`)
- [ ] Coverage report generated: `pytest --cov=. --cov-report=term-missing --cov-fail-under=80`

---

## Pre-Code Deliverables Checklist

Before any code is written for sections A–K, these must exist as artifacts:

- [x] `docs/audits/467-inventory.md` — state + PR inventory ✅
- [x] `docs/audits/467-skill-inventory.md` — every skill's load/wire/test status ✅
- [x] `docs/audits/467-brutal-audit.md` — file references with WORKING/FLAKY/ADVERTISED-BUT-NOT-BUILT/MOCKED ✅
- [x] `docs/architecture/golden-path.md` — golden path defined and locked ✅
- [x] `docs/public-site-truth-spec.md` — public site truth spec ✅
- [x] `docs/audits/467-acceptance-criteria.md` — final acceptance criteria ✅

---

## PR Sequencing (8 PRs for A–K)

| PR | Sections | Focus | Test Focus |
|----|----------|-------|------------|
| PR-1 | §J (contract) | Pydantic extra="forbid" on 5 core models | `tests/test_contracts_agency.py` |
| PR-2 | §I (feature matrix) | Demote 12 features in feature-matrix.md + public site | `tests/test_feature_matrix.py` |
| PR-3 | §F (Doctor deep) | All 8 checks + run_fix + list_available_fixes | `tests/test_doctor_endpoints.py` |
| PR-4 | §D (direct chat) | Control center + intent classification + sticky context | `tests/test_direct_chat_control_center.py` |
| PR-5 | §E (workflow) | Worktree isolation enforced + phase sequence | `tests/test_workspace_isolation.py`, `tests/test_workflow_engine.py` |
| PR-6 | §G (CEO loop) | Branch-protection-safe + dedupe + verified close | `tests/test_ceo_autonomous_loop.py` |
| PR-7 | §A (onboarding) | Company Graph + URL scan + list_available_fixes | `tests/test_company_onboarding.py` |
| PR-8 | §B + §C + §H + §K | Specialists + skill wiring + public site + E2E coverage | 9 E2E tests |

---

*Last updated: 2026-06-08. Pre-code deliverables complete. Code implementation pending.*
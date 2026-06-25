# Issue #467 — Section 1: Pulled State + PR Inventory

**Produced:** 2026-06-08
**Status:** PRE-CODE DELIVERABLE — must precede any code work

---

## 1. Current Git State

### Branch: `consolidate/maturation-stable`
- tip: Latest consolidated work (retry logic, trend watcher expansion, background agent heartbeat, Telegram service)
- NOT merged to master — master is at PR #462 (RTK output filtering)

### Master branch
- tip: PR #462 — RTK output filtering fix
- Does NOT include any of the #467 work
- Does NOT include autonomous agency hardening from consolidate/maturation-stable

### Other active branches
- `claude/context-issue-467` — agency core autonomy hardening (merged to consolidate)
- Various skill branches under `.claude/` — skills and agents definitions

---

## 2. Open PRs (as of 2026-06-08)

| PR | Title | Status | Maps to #467 |
|----|-------|--------|-------------|
| #487 | agency core observability hardening | Open (consolidate) | Partial G, F |
| #462 | fix: resolve direct chat issues when agent mode is ON | Merged to master | Partial D |
| #469 | fix(dispatcher): use module-level time import | Merged | Minor |
| #472 | feat: workspace isolation + feature maturity tiers + structured errors | Merged | E (partial) |
| #463 | feat: implement RTK-style output filtering | Merged | Proxy hardening |
| #461 | security: remove all hardcoded credential fallbacks | Merged | Security |
| #460 | fix: suppress Bandit false positives | Merged | CI |

---

## 3. Files Modified on consolidate/maturation-stable (vs master)

| File | Lines ± | Purpose | #467 Coverage |
|------|---------|---------|---------------|
| `agent/background.py` | +103 | Retry logic, heartbeat updates | G (partial) |
| `agent/loop.py` | +minor | Tool call retry | G (partial) |
| `agent/trend_watcher.py` | +major | 13-source trend intelligence | G (orthogonal) |
| `telegram_service.py` | +276 | REVERTED — issue says telegram must be gated/removed | Violated spec |
| `log_watcher.py` | +437 | REVERTED — not in #467 spec | Violated spec |
| `handlers/diagnostics.py` | +242 | Doctor public/auth split | F (partial) |
| `agent/kpi.py` | +180 | KPI counters for autonomy | G |
| `tests/test_contracts_agency.py` | +335 | Contract discipline tests | J (partial) |

---

## 4. What Master Has (that consolidate doesn't)

- `agent/loop.py` — original AgentRunner with plan→execute→verify
- `direct_chat.py` — DirectChatHandler with `_BYPASS` for internal callers
- `runtimes/adapters/internal_agent.py` — InternalAgentAdapter
- `workflow/engine.py` — WorkflowEngine (minor hardening only)
- `services/company_graph.py` — CompanyGraphStore (partially implemented)
- `agents/agile_sprints.py` — AgileSprintAgent (partially implemented)
- `agents/portfolio.py` — PortfolioManager (partially implemented)
- `services/workflow_orchestrator.py` — WorkflowOrchestrator
- `agent/agency.py` — CEO agency with GitHub Actions cycle
- `runtimes/adapters/hermes.py` — HermesAdapter (first-class, with Kimi bridge)
- `agent/trend_watcher.py` — original 10-source version (pre-expansion)

---

## 5. What Is MISSING from master (0% delivered in #467)

- `frontend/` — public site is still a sign-in shell
- `webui/` — no real public content
- `docs/` — no architectural docs matching #467 scope
- Company onboarding endpoint (multi-pass URL scan → Company Graph)
- 34 specialist families fully wired
- Feature matrix discipline (demotions not done)
- Pydantic extra="forbid" enforcement
- E2E test coverage for autonomy
- Contract tests for AgentRunner/ModelRouter/JobManager/WorkflowOrchestrator/SkillRegistry

---

## 6. Required Action Before Code

**Do NOT merge PR #487 as "fixes #467"** — it covers ~15-20% of the mandate.
The telegram_service.py and log_watcher.py additions directly contradict the spec.

All 6 pre-code deliverables (Sections 1-6) must be produced before opening any code PR claiming to fix #467.
# 467 Skill Inventory — load / wire / test status

> Issue #467 §3 required: "Skill inventory with each skill's load/wire/test status"

## Skill Registry

All skills live in `.agents/skills/` and are indexed in `agent/skill_registry.py`.

Legend:
- **LOAD** — Does `skill(name)` return the skill descriptor without error?
- **WIRE** — Is the skill invoked by any live code path (not test-only)?
- **TEST** — Does `pytest tests/test_skill_registry.py` pass for this skill?

---

## Core Agency Skills (load/wire/test)

| Skill | File | Load | Wire | Test | Notes |
|-------|------|------|------|------|-------|
| `risky-module-review` | `.agents/skills/risky-module-review/SKILL.md` | ✅ | ✅ | ✅ | admin_auth, key_store, agent/tools, handlers/v3_auth, rbac, social_auth |
| `test-first-executor` | `.agents/skills/test-first-executor/SKILL.md` | ✅ | ✅ | ✅ | Used by Bug Fix Agent; referenced in AGENTS.md |
| `docs-sync` | `.agents/skills/docs-sync/SKILL.md` | ✅ | ✅ | ❌ | No test coverage |
| `changelog-enforcer` | `.agents/skills/changelog-enforcer/SKILL.md` | ✅ | ✅ | ❌ | No test coverage |
| `graphify` | `.agents/skills/graphify/SKILL.md` | ✅ | ❌ | ❌ | Not wired to any live code path |
| `implementation-planner` | `.agents/skills/implementation-planner/SKILL.md` | ✅ | ✅ | ❌ | Referenced in AGENTS.md but no pytest coverage |
| `branch-cleanup` | `.agents/skills/branch-cleanup/SKILL.md` | ✅ | ✅ | ❌ | No test coverage |
| `dependency-audit` | `.agents/skills/dependency-audit/SKILL.md` | ✅ | ✅ | ❌ | No test coverage |
| `council-review` | `.agents/skills/council-review/SKILL.md` | ✅ | ❌ | ❌ | Not wired to any live code path; spec §C demands end-to-end binding |
| `release-readiness` | `.agents/skills/release-readiness/SKILL.md` | ✅ | ✅ | ❌ | No test coverage |
| `repo-memory-updater` | `.agents/skills/repo-memory-updater/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `modularity-review` | `.agents/skills/modularity-review/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `platform-setup` | `.agents/skills/platform-setup/SKILL.md` | ✅ | ❌ | ❌ | Not wired; manual skill only |
| `session-handoff` | `.agents/skills/session-handoff/SKILL.md` | ✅ | ✅ | ❌ | Referenced in wrap-up skill |
| `wrap-up` | `.agents/skills/wrap-up/SKILL.md` | ✅ | ✅ | ❌ | End-of-session ritual |
| `smart-commit` | `.agents/skills/smart-commit/SKILL.md` | ✅ | ❌ | ❌ | Not wired; referenced in AGENTS.md |
| `self-improve` | `.agents/skills/self-improve/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `learn-rule` | `.agents/skills/learn-rule/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `replay-learnings` | `.agents/skills/replay-learnings/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `memory-consolidation` | `.agents/skills/memory-consolidation/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `parallel-worktrees` | `.agents/skills/parallel-worktrees/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `pro-workflow` | `.agents/skills/pro-workflow/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `cooldown-resume` | `.agents/skills/cooldown-resume/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `deslop` | `.agents/skills/deslop/SKILL.md` | ✅ | ✅ | ❌ | Referenced in coding standards; no pytest |
| `insights` | `.agents/skills/insights/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `fabric-patterns` | `.agents/skills/fabric-patterns/SKILL.md` | ✅ | ✅ | ❌ | Referenced in AGENTS.md |
| `repowise-intelligence` | `.agents/skills/repowise-intelligence/SKILL.md` | ✅ | ✅ | ❌ | repowise.py imports and wires it |
| `ticket-to-pr` | `.agents/skills/ticket-to-pr/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `scope-guard` | `.agents/skills/scope-guard/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `sandboxed-exec` | `.agents/skills/sandboxed-exec/SKILL.md` | ✅ | ✅ | ❌ | Used in agent/tools.py |
| `task-scoper` | `.agents/skills/task-scoper/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `task-alive-updates` | `.agents/skills/task-alive-updates/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `system-prompt-audit` | `.agents/skills/system-prompt-audit/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `stitch-skill` | `.agents/skills/stitch-skill/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `soft-skill` | `.agents/skills/soft-skill/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `smart-commit` | `.agents/skills/smart-commit/SKILL.md` | ✅ | ❌ | ❌ | Duplicate entry above |
| `skill-composer` | `.agents/skills/skill-composer/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `taste-skill` | `.agents/skills/taste-skill/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `tokenizer-diagnostics` | `.agents/skills/tokenizer-diagnostics/SKILL.md` | ✅ | ❌ | ❌ | Not wired |
| `training-stability-monitor` | `.agents/skills/training-stability-monitor/SKILL.md` | ✅ | ❌ | ❌ | Not wired |

---

## Named Skills Referenced in Spec §C

| Spec Reference | Skill | Status | Gap |
|----------------|-------|--------|-----|
| §C | `council-review` | NOT WIRED | Must bind to workflow phase |
| §C | `graphify` | NOT WIRED | Must bind to workflow phase |
| §C | `ECC` (error-correction-loop) | **ADVERTISED-BUT-NOT-BUILT** | No .agents/skills/ecc/ directory |
| §C | `Obsidian` (knowledge graph) | **ADVERTISED-BUT-NOT-BUILT** as skill | `agent/knowledge_sync.py` exists; not exposed as skill |
| §C | browser-based skills | **MOCKED** | No browser automation skill wired to live paths (agent-browser skill exists but not invoked) |
| §C | `agent-browser` | LOAD ✅ WIRE ❌ | Not wired to any live agent execution path |

---

## Agent Specialties (not skills per se, but referenced in spec §B)

| Agent | File | Status | Notes |
|-------|------|--------|-------|
| `QualityAgent` | `agent/quality.py` | WORKING | Has run() method; not tested in suite |
| `FinanceAgent` | `agent/finance.py` | WORKING | Has run() method; not tested |
| `ResearchAgent` | `agent/research.py` | WORKING | Has run() method; not tested |
| `AgileAgent` | `agent/agile.py` | WORKING | Has run() method; not tested |
| Portfolio specialist | `agents/portfolio_intelligence.py` | WORKING | Has WSJF scoring; not tested end-to-end |
| SEO specialist | `services/seo_agent.py` | ADVERTISED-BUT-NOT-BUILT | File does not exist |
| PIM specialist | `services/pim_agent.py` | ADVERTISED-BUT-NOT-BUILT | File does not exist |
| OMS specialist | `services/oms_agent.py` | ADVERTISED-BUT-NOT-BUILT | File does not exist |
| DAM specialist | `services/dam_agent.py` | ADVERTISED-BUT-NOT-BUILT | File does not exist |
| Analytics specialist | `services/analytics_agent.py` | ADVERTISED-BUT-NOT-BUILD | File does not exist |
| Agentic Agile | `agent/agile.py` | PARTIAL | Only basic sprint tracking; no full autonomy |
| Agentic Portfolio | `agents/portfolio_intelligence.py` | PARTIAL | WSJF exists; full autonomous loop not built |
| Trading specialist | `services/trading_agent.py` | ADVERTISED-BUT-NOT-BUILT | File does not exist |
| Support/CRM specialist | `services/crm_agent.py` | ADVERTISED-BUT-NOT-BUILT | File does not exist |
| CEO agent | `agent/agency.py` | PARTIAL | Has execute() but no branch-protection-safe loop, no dedupe, no verified close |

---

## Test Coverage Summary

```
tests/test_skill_registry.py        — exists, passes
tests/test_skills.py                — exists, partial (some skills)
tests/test_agents.py                — agent runner, passes
tests/test_agent_runner.py          — exists, passes
tests/test_agent_coordinate.py      — exists, passes
tests/test_agent_tools.py           — workspace tools, passes
tests/test_contracts_agency.py      — contract tests, 21 cases, passes
tests/test_direct_chat_async.py     — passes
tests/test_workflow_engine.py       — passes
```

**Coverage gap:** 0 E2E tests for onboarding, specialist provisioning, skill exec, direct chat as control center, workflow engine backbone, Doctor checks, CEO loop, HITL, or issue/PR lifecycle — as noted in spec §K.

---

## Gaps Summary

| Gap | Count | Severity |
|-----|-------|----------|
| Skills not wired to live paths | 25 | HIGH |
| Named skills from spec §C not built (ECC, Obsidian as skill) | 2 | HIGH |
| Specialist families from spec §B not built (SEO, PIM, OMS, DAM, Analytics, Trading, CRM) | 7 | HIGH |
| No E2E coverage for spec §K outcomes | 9 areas | HIGH |
| Skills without pytest coverage | 30 | MEDIUM |
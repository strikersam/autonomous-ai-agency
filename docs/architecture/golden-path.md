# 467 Golden Path — Locked Implementation Order

> Issue #467 §4 required: "Golden Path defined and locked"

---

## What Is the Golden Path

The Golden Path is the single, correct sequence of operations for any AI-coded task in this repo. It eliminates arbitrary choices and ensures every task goes through the same quality gates.

**Principle:** Every task — bug fix, feature, refactor, config change — follows the same 8-step path. No shortcuts, no "I'll do it later", no "this is just a small change".

---

## The 8-Step Golden Path

### Step 1: Scout — Understand the territory

Before writing any code:
- Read `AGENTS.md` for the relevant module's section
- Run `graphify query "<task description>"` to query the knowledge graph (70x cheaper than reading source)
- Read the relevant `CLAUDE.md` files for module contracts
- List the files that will change: `glob "**/<module>*.py"`

**No code is written before this step is complete.**

### Step 2: Plan — Define the change

- Use `implementation-planner` skill for multi-file or multi-step implementations
- Write a `NEXT_ACTION.md` at `.claude/state/NEXT_ACTION.md`
- Identify which spec section this maps to (A–K from #467)
- If the change touches RISKY MODULES (admin_auth, key_store, agent/tools, handlers/v3_auth, rbac, social_auth), invoke `risky-module-review` skill **before** writing any code

### Step 3: Write tests first

- Write failing tests that reproduce the bug or define the new behavior
- Tests must be runnable with `pytest -x tests/test_<module>.py`
- No PR is opened without test coverage for the new code path

### Step 4: Implement

- Write the code following AGENTS.md coding standards:
  - Type annotations on all public functions
  - `async` for all I/O operations
  - Pydantic v2 models for all API shapes
  - `logging` not `print`
  - No hardcoded secrets
- Keep files under 800 lines
- If a file exceeds 800 lines, create a decomposition issue first

### Step 5: Validate

```bash
pytest -x                                           # Fast fail — all tests green
pytest --cov=. --cov-report=term-missing           # Coverage must not decrease
bandit -r .                                         # Security scan
```

### Step 6: Review

- Invoke `council-review` skill for any change touching >2 files or any RISKY MODULE
- Fix all issues raised before proceeding

### Step 7: Document

- Update `docs/changelog.md` under `[Unreleased]`
- If new env vars added, update `docs/configuration-reference.md`
- If new API endpoint added, update `docs/api-surfaces.md`
- If module contract changed, update the module's `CLAUDE.md`

### Step 8: Commit and propose

- Use `smart-commit` skill for commit message formatting
- Push branch and open PR with link to relevant issue (#467, etc.)
- PR body must reference the spec section (A–K) being addressed
- CI must be green before merge

---

## Golden Path Exceptions

| Exception | When Allowed | Who Can Authorize |
|-----------|-------------|-------------------|
| P0 security vulnerability | Before writing tests | Human escalation required |
| Hotfix in production | After verbal approval | Human on-call |
| Documentation-only change | Always | Any agent |

---

## Module-Specific Golden Paths

### Agent Code (agent/ directory)
1. Scout: Read `agent/CLAUDE.md` if it exists; check `agent/__init__.py` imports
2. Plan: Identify if this is a Tool, an Agent, or a Coordinator
3. Tools → follow `agent/tools.py` patterns (sync file I/O, `_resolve_path()` sandbox)
4. Agents → follow `agent/loop.py` AgentRunner patterns (plan→execute→verify→judge)
5. Coordinators → follow `agent/agency.py` CEO patterns
6. Always add KPI counters in `agent/kpi.py` for new execution paths

### Backend Code (backend/, handlers/)
1. Scout: Read `backend/server.py` to understand routing
2. Plan: Add Pydantic request/response models in `workflow/models.py` or `backend/models.py`
3. Implement: All endpoints must have auth guards (`verify_api_key` or `_get_admin_identity_from_request`)
4. Validate: `pytest -x tests/test_backend_server_features.py`

### Workflow Code (workflow/)
1. Scout: Read `workflow/engine.py` phase sequence
2. Plan: Phase sequence is enforced — cannot skip phases
3. Implement: New phases must be registered in `workflow/phases.py`
4. Validate: `pytest -x tests/test_workflow_engine.py`

### Skill Code (.agents/skills/)
1. Scout: Read `.agents/skills/skill-composer/SKILL.md` for authoring conventions
2. Plan: Skills must have `SKILL.md` with name, description, tools, parameters
3. Implement: Follow skill manifest schema
4. Validate: `pytest -x tests/test_skill_registry.py`

---

## What Breaks the Golden Path

Any of the following triggers an automatic stop and human review:
- Commit to `master` without CI green
- Change to a RISKY MODULE without `risky-module-review`
- New endpoint without auth guard
- Decrease in test coverage
- Hardcoded secret or API key
- `print()` statement added
- File exceeds 800 lines without justification
- PR body doesn't reference spec section (A–K)

---

## Verification

Run `pytest -x` after every golden path step. The path is not complete until tests are green.
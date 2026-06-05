# Skill: session-planning — Mandatory Planning Workflow for All AI Agents

> **When to use:** At the start of EVERY non-trivial agentic session, before writing any code.
> This skill is universal — it works with Claude Code, Codex, Cursor, Aider, and any other AI tool
> that reads AGENTS.md or CLAUDE.md.

---

## The 10-Step Workflow

Run these steps **in order**. Do not skip steps 6 (draft PR) or 7 (user confirmation).

### Step 1 — Orient (free)
```bash
cat AGENTS.md                                    # cross-tool ground truth
cat CLAUDE.md                                    # project-specific rules
cat graphify-out/GRAPH_REPORT.md                 # codebase map (no token cost)
cat .claude/state/active-tasks.md               # what's already in flight
cat docs/changelog.md | head -40                # what recently changed
```

### Step 2 — Understand the Task
- If from a GitHub issue: read the issue body, comments, linked PRs
- If from a user message: restate the task in one sentence to confirm understanding
- If resuming: read `.claude/state/NEXT_ACTION.md` and `active-tasks.md`

### Step 3 — Load Relevant Skills
```bash
ls .claude/skills/                               # see all available skills
# Load skills matching the task type:
# Multi-file change       → implementation-planner
# Tests needed            → test-first-executor
# Auth/key/agent-tools    → risky-module-review
# Pre-merge review        → council-review
# Adding deps             → dependency-audit
# Codebase exploration    → graphify
# Cross-harness routing   → ecc-harness-patterns
```

### Step 4 — Research (if novel task)
- If the task involves techniques not in the codebase, search OSS reference projects
- Use web search or GitHub MCP to read relevant repos
- Cite sources in the plan

### Step 5 — Write the Plan
Use the `implementation-planner` skill or write directly:
```markdown
## Plan: <task name>

**Goal:** one sentence

**Files to change:**
- `path/to/file.py` — what changes and why
- `path/to/other.py` — what changes and why

**Steps:**
1. Write tests first (test-first-executor)
2. Implement step A
3. Implement step B
4. Run pytest -x
5. Update changelog
6. Update active-tasks.md

**Risks:** list risky modules requiring risky-module-review

**Acceptance criteria:** how to verify it works
```

### Step 6 — Update active-tasks.md
Add rows to `.claude/state/active-tasks.md`:
```markdown
| N | <task description> | `TODO` | — | <brief note> | <date> |
```

### Step 7 — Create Draft PR with Plan
```bash
git checkout -b <descriptive-branch-name>
# Create PR immediately as DRAFT with the plan as description
# PR body = Step 5 plan + TODO checklist
# Title format: "feat/fix/docs(<scope>): <what it does>"
```

**PR body must include:**
- The prompt/task description
- The plan from Step 5
- A `## TODO` checklist that matches `active-tasks.md` rows
- `## Test plan` section

### Step 8 — Confirm with User
**STOP. Do not write any code until the user confirms.**

Say exactly:
> "Here's the plan: [summary]. I've created draft PR #N with the full details.
> Shall I proceed with implementation? (yes/no, or let me know what to change)"

### Step 9 — Execute (after confirmation)
- Work through the plan step by step
- Update `active-tasks.md` status as you go:
  - Start a task → `IN_PROGRESS`
  - Find a bug → `BUG_FOUND` (add to Bug Log)
  - Fix a bug → `BUG_FIXED`
  - Complete a task → `DONE`
- Commit after each meaningful unit of work (not after each file)
- Run `pytest -x` before every commit

### Step 10 — Close Out
- Update all `IN_PROGRESS` tasks to `DONE` in `active-tasks.md`
- Update PR body with outcomes and any bugs discovered/fixed
- Update `docs/changelog.md`
- Update `.claude/state/NEXT_ACTION.md` if work continues next session
- Push and request review

---

## Updating active-tasks.md During Execution

The tracker at `.claude/state/active-tasks.md` is the living record. Update it continuously:

```python
# Pattern for updating status (Python pseudo-code):
# 1. Read the file
# 2. Find the row by task number
# 3. Update Status column
# 4. Update Notes column with brief outcome
# 5. Update Updated column with today's date
```

**Always log bugs:**
```markdown
## Bug Log
| # | Bug Description | Found | Fixed | PR | Status |
|---|----------------|-------|-------|----|--------|
| N | <description> | <date> | <date or —> | <PR or —> | BUG_FOUND / BUG_FIXED |
```

---

## Cross-Tool Compatibility

This workflow is designed to work with any AI coding tool:

| Tool | How it reads this workflow |
|------|--------------------------|
| Claude Code | CLAUDE.md + this skill via `/session-planning` |
| Codex / OpenCode | AGENTS.md mandatory workflow section |
| Cursor | AGENTS.md (Cursor reads project-level AGENTS.md) |
| Aider | AGENTS.md via `--read AGENTS.md` or auto-detection |
| GitHub Actions (AI) | AGENTS.md + `.github/workflows/` context |
| Any other agent | AGENTS.md is the universal contract |

---

## Quick Reference Card

```
READ   → AGENTS.md + CLAUDE.md + GRAPH_REPORT.md + active-tasks.md
SKILLS → load relevant skills for this task type  
PLAN   → write implementation plan (files, steps, risks, acceptance)
TRACK  → add tasks to active-tasks.md as TODO
PR     → create DRAFT PR with plan as body + TODO checklist
CONFIRM → ask user before writing any code
EXECUTE → implement step by step, updating tracker status live
BUGS   → log BUG_FOUND immediately, BUG_FIXED when resolved
DONE   → update active-tasks.md + changelog + NEXT_ACTION.md
```

# Agent Orchestration Design

## Overview

The agent system in `agent/` implements a **clean-room multi-agent orchestration pattern**
inspired by generator/reviewer/council separation used in modern AI engineering systems.

## Four-Agent Structure

| Agent | Role | Model | Handoff |
|-------|------|-------|---------|
| Planner | Decompose instruction into ordered steps | deepseek-r1:32b | → Implementer |
| Implementer | Execute each step via tool loop + LLM | qwen3-coder:30b | → Reviewer |
| Reviewer (Verifier) | Verify each file change before apply | deepseek-r1:32b | pass→apply, fail→retry |
| Judge | Release gate after session completes | deepseek-r1:32b | → done/blocked |

## Shared State

All agents share state through:
1. `.claude/state/agent-state.json` — full session plan and status
2. `.claude/state/checkpoint.jsonl` — append-only completed-step log
3. The filesystem — applied changes are visible immediately to all agents

## Plan-First Pathway

```
POST /v1/agent/run {instruction, auto_commit, max_steps}
    │
    ▼
AgentRunner.run()
    │
    ├─ _generate_plan()      ← Planner agent call
    │    Uses: build_planning_prompt() → LLM → AgentPlan.model_validate()
    │
    └─ for step in plan.steps[:max_steps]:
           _execute_step()   ← Implementer + Reviewer agents
```

## Tool Loop (Implementer)

The implementer uses a bounded tool loop before generating file content.
This ensures it has sufficient context to make accurate changes:

```
for remaining in range(4, 0, -1):
    tool_call = LLM(goal, step, observations, remaining)
    if tool_call.tool == "finish": break
    result = run_tool(tool_call.tool, tool_call.args)
    observations.append(result)
```

Available tools: `read_file`, `list_files`, `search_code`, `finish`.

## Execution Pathway

```
For each target_file:
    original = read(target_file)
    retries = 0
    while retries <= 2:
        new_content = Implementer(goal, step, context)
        syntax_issues = local_syntax_check(new_content)
        safety_issues = local_safety_check(new_content)
        verdict = Reviewer(original, new_content, syntax_issues + safety_issues)
        if verdict.status == "pass":
            apply_diff(target_file, new_content)
            break
        retries += 1
        feedback_issues = syntax_issues + verdict.issues
```

## Review Pathway (Council Mode)

For pre-merge review, the `council-review` skill runs four sequential reviewer roles:
1. Security (auth, key exposure, path traversal)
2. Correctness (logic, edge cases, type safety)
3. Performance (async paths, caching, loops per request)
4. Maintainability (coupling, naming, abstraction level)

This is implemented as a skill (`.claude/skills/council-review/SKILL.md`) rather than
a live agent call, since it runs on diffs rather than during the generation loop.

## Release-Readiness Pathway

The Judge agent (`.claude/agents/judge.md`) runs the release-readiness skill at session end:
- Verifies all steps completed
- Runs `pytest -x`
- Checks changelog
- Produces `judge-verdict.json` with APPROVED / APPROVED_WITH_CONDITIONS / BLOCKED

## Worktree Isolation & Concurrency

Per-task git worktree isolation **is implemented** (not a future capability).

- **Concurrent dispatch.** `tasks/dispatcher.py` pulls up to
  `TASK_DISPATCH_CONCURRENCY` (default 5) pending tasks and runs them together
  via `asyncio.gather(*(self._execute_task(t.task_id) for t in tasks))`.
- **Per-task isolation.** Before executing, `runtimes/adapters/internal_agent.py`
  calls `_create_worktree(workspace, task_id)`, which runs
  `git worktree add --detach <path> HEAD` so each concurrent task edits its own
  working tree off the shared object store and cannot clobber another task's
  in-flight changes. When the workspace is not a git repo (or worktree creation
  fails) it falls back to a `tempfile.TemporaryDirectory` copy of the workspace.
- **Cleanup.** `_remove_worktree(...)` removes the worktree (`git worktree remove
  --force`, then `rmtree` as a safety net) in a `finally` block when the task ends.
- **Claim lock.** A shared per-task claim (`task:active:<id>`, TTL 1h) prevents two
  workers from executing the same task concurrently.

```bash
# Effectively, per task:
git worktree add --detach <workspace>/.worktrees/<task-slug> HEAD
# … agent edits, commits, opens PR from inside the worktree …
git worktree remove --force <path>
```

**Caveats / known limits.** Isolation is per *task*, keyed off `task_id`; ad-hoc
runs without a task id share an `"adhoc"` slug. The fallback temp-copy path does
not carry git history, so git-dependent steps degrade in non-repo workspaces.
The Judge does not yet auto-merge results across worktrees — each task is expected
to land its own branch/PR.

## OSS Inspirations (Clean-Room)

This design was inspired by:
- open-multi-agent patterns (generator/reviewer separation)
- openclaw council/ultraplan/ultrareview patterns
- Microsoft AutoGen-style role separation

No proprietary code was copied. Architecture was re-implemented independently.

## Key Invariants

1. Planner runs before any Implementer call — no execution without a plan.
2. Verifier approves before any `apply_diff` — no writes bypass review.
3. `max_steps` is always respected — no unbounded loops.
4. Retry limit per file is 3 — agents don't loop forever on failures.
5. All state changes are written to disk before the next LLM call.

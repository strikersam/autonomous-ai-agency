# Intent: agent pull requests that are right before a human sees them

Author: repository owner, written up by Claude Code. Status: accepted 2026-10-08.

## Problem

Agent-opened PRs reached GitHub in a state no reviewer should have to see.

- #1694 (task `agent/task-29c4c115`): an `llms.txt` full of invented domains,
  e-mail and social handles, at a path the site never serves. The title
  promised semantic landmarks that were not in the diff.
- #1696 (task `agent/task-a4b12bb4`): asked to "add internal links", it
  replaced `frontend/src/App.js` with a static placeholder (removing routing,
  auth and the whole dashboard) and cut 1,490 lines from the root
  `index.html`. CI was red on seven checks.
- #1695 / #1697 (daily model automation): each re-added a model id that is on
  the retired list, so the catalogue tests went red.

Three causes, all verified in the code on 2026-10-08:

1. `agent/pr_gate.py` only inspects `.py` files. A change made only of JS,
   HTML or text passes with zero blockers.
2. The judge in `agent/loop.py` is shown the goal, a step count and whether
   all steps applied — never the diff — and its verdict does not stop the PR.
3. Nothing compares what changed with what the plan said would change, or
   notices a change that deletes far more than it adds.

## Proposed outcome

An agent PR opens only when deterministic checks have passed in the agent's
own clone, and the PR body carries the evidence: the plan, which checks ran
and their result, the judge's verdict on the real diff. A human reviewer
judges intent and risk, not whether the build works.

## Affected users and systems

Repository owner (reviewer), every agent task with `AGENT_AUTO_PR_ENABLED`.
`agent/pr_gate.py`, `agent/loop.py` (judge input, PR body), tests.

## Constraints

- No new provider calls; the judge call already exists.
- Fail closed: if a check cannot run, the PR does not open.
- Backward compatible: `pr_blockers(root, changed_files)` keeps working.
- Protected paths (CLAUDE.md rule 15 modules, the app shell, deploy and CI
  config) are never changed by an agent PR; a human makes those changes.

## Open questions

- Frontend checks need `node_modules` in the agent clone. Where it is absent
  the PR states that frontend tests were not run instead of claiming a pass.

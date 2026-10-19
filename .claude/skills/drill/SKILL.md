---
name: drill
description: >
  "Do the drill": clear every open PR and issue in this repo. Inventory them,
  implement what is pending, merge each one only with CI green, then sweep for
  anything else left to fix, until nothing is open and master is green. Use when
  the operator types /drill, "do the drill", "you know the drill", or "take care
  of open PRs and issues".
triggers:
  - /drill
  - "do the drill"
  - "you know the drill"
  - "take care of open PRs and bugs"
  - "close and merge all PRs and issues"
references:
  - CLAUDE.md
  - REVIEW.md
  - scripts/drill_inventory.py
  - .claude/skills/model-catalogue-update/SKILL.md
  - .claude/skills/risky-module-review/SKILL.md
---

# /drill — clear the board, keep master green

**Done means:** every open PR is merged or closed with a reason, and every open
issue is fixed, verified as already fixed, or closed with a reason. Master CI is
green on its latest commit, no workflow's latest run on master is red, and a
final report says which of these were checked. Nothing about it is a judgement
call left in your head: each item ends in a merge, a close comment, or a line in
the report that says why it is still open.

The drill is four phases. Work them in order and loop phases 2–3 until the
inventory is empty. A merge moves master, which puts other PRs behind, and a
long-running workflow can reopen an issue you just closed. So phase 4 always
re-runs the inventory instead of trusting phase 1.

---

## Phase 1 — Inventory (read-only)

```bash
git fetch origin master && git checkout -B <your-branch> origin/master
python scripts/drill_inventory.py          # add --json for a machine-readable copy
```

The script lists every open PR and issue with its category, CI state on the PR
head, merge state, master CI, and every workflow whose latest run on master
failed. It never writes. A merge state of `unknown` means GitHub has not
computed it yet: query that PR again before acting on it.

Post the inventory table to the operator before changing anything. Then make a
task per item; a long list goes into the task tracker, not your memory.

## Phase 2 — Decide and implement, per category

Read the item before deciding: the body, the comments, and for a PR the diff
and the failing job's log (`get_job_logs`, tail ≈ 80 lines). The title and the
bot's own summary are claims, not evidence.

| Category | What to do |
|---|---|
| `own` | Your branch's PR (the script takes the checked-out branch, or `--own-branch`). Drive it through phase 3 like any fix. |
| `dependabot` | Check the new version exists on the registry. For a **major** bump, find the API we call (`grep -rn "from <pkg>"`), install the new version into a scratch dir (`pip install --target <scratch> <pkg>==X`) and run the tests that touch it with `PYTHONPATH=<scratch>`. A breaking change that affects us needs the operator (rule 40); none means it is safe to take. Branch protection requires PRs to be up to date, so each merge puts the rest behind. With **more than three** green bumps waiting, cherry-pick their commits into one PR from your branch and close the originals pointing at it. That is one CI round instead of one per bump. With fewer, `PUT pulls/{n}/update-branch` and merge them one at a time. Close a bump whose package another PR removes, saying which PR. |
| `agent` (`agent/*`) | Hold it to `REVIEW.md`. Close, with the reason, any PR that adds root-level report files, fabricated dates, retired model ids, removed tests or assertions, or a rewrite far larger than the plan. Otherwise fix it up on its branch and drive it like your own. |
| `automation` (`claude/daily-automation-*`, `claude/harness-scan-*`, `claude/context-issue-*`) | Daily model PRs follow `.claude/skills/model-catalogue-update/SKILL.md`. Resolve conflicts by merging master in, never by rebasing. A draft context PR whose issue closed should be closed too. A harness-scan draft is a report: merge it if it is docs-only and green, close it if superseded. |
| `session` (`claude/*`) | If the inventory marks it **IN FLIGHT** (pushed in the last 2 h), another session is likely still on it. Report it and leave it. Older than that, treat it as abandoned work and drive it to green. |
| `human` | Reviewers' small asks: implement. Larger asks or design questions: comment with a proposal and put the call to the operator. |
| `bug`, `automation-bug` | Reproduce or find the evidence first (failing run log, traceback). Check whether master already fixed it (`git log -S`, the latest scheduled run). If fixed, close with the commit and the green run as proof. If not, fix it with a regression test that fails first. |
| `quick-note`, `quick-note-rejected` | Read the linked source and the context PR. Build it if it is a real, scoped feature; otherwise close as `not_planned` and name what in the repo already covers it. |
| `routine` | Do each checkbox that is actionable from code. Close the issue when every box is done or has a written reason. |

**Implementing a fix:**
- One coherent change per PR, on your own branch, from fresh master.
- A bug fix needs a regression test that fails before the fix. Show it failing.
- Entries under `## [Unreleased]` in both `CHANGELOG.md` and `docs/changelog.md`
  (`python scripts/check_changelog_parity.py`). `chore:`, `docs:`, `ci:`,
  `test:` commits are exempt.
- A changed workflow needs `python agent/loop_registry.py audit --check` green.
- `graphify update .` and commit `graphify-out/GRAPH_REPORT.md` with the change.
- Run the touched tests, then the full suite, before pushing. A test that also
  fails on clean master is pre-existing: prove it by running it on master, and
  say so in the PR.

## Phase 3 — Merge with CI green

For every PR you opened or are driving:

1. Open it with the template's sections, enable squash auto-merge, and subscribe to its activity.
2. Schedule a check-in about 50 minutes out (`send_later`) as the safety net. Cancel it when the PR merges.
3. **Red CI:** root-cause it from the job log, then push a fix. Before calling it
   "not this PR's", check whether the same check is red on master. A check that
   fails on an old head commit after you pushed a new one is stale: ignore it.
4. **Conflict:** merge master into the branch, keep both sides' changelog
   entries, regenerate lockfiles with the tool (`npm install`), never by hand.
5. **Behind:** update the branch. After any merge, the other PRs go behind; update them in turn.
6. Review bots: a finding with a real path to failure gets fixed. A
   rate-limit or usage-limit notice from CodeRabbit or Codex is not a finding.

After each merge, confirm it landed: the merge commit is on master, and for a
backend change, exactly one Render deploy went live. Check that through the
Render connector (`mcp__Render__*`, workspace `tea-d7car44p3tds739qdrs0`,
service `srv-d7cb43beo5us73e1leug`), because the `render` MCP server often
reports CONNECTION_CLOSED.

## Phase 4 — Prove nothing is left

Re-run `python scripts/drill_inventory.py`. It must show:
- **0 open items**, except IN FLIGHT session PRs and anything you reported as blocked with a reason;
- master CI **green**;
- red workflows on master: **none**. A red one is an item: open its log and go back to phase 2.

Then:
- Look for anything an in-flight run did after you closed an issue, such as a
  reopen or a retry label.
- Check `.claude/state/active-tasks.md` for rows the drill closed and move them
  to the archive (rule 44).
- Reset your branch to master and push, so the stop hook has nothing to flag.
- Cancel every check-in you scheduled.

**Final report** — one table: item, what was done (merged / closed / fixed in
#N / left open), and the evidence (commit, run id, deploy id). Then a list of
what was not checked and why, for example "Render deploy not checked: connector
unavailable".

---

## Do

- Verify a bot's claim against primary data before acting. A "500/503 server
  error" issue turned out to be a regex counting Playwright's `waiting 500ms`
  lines, and a "tests failing" escalation was a missing git identity in a temp repo.
- Check whether master already fixed something before writing a fix for it.
- Close with a comment that names the evidence (commit SHA, run id). End every
  GitHub comment with the Claude Code footer.
- Fix the root cause in code when automation keeps failing the same way, such
  as a retry loop that hammers a model returning 404, rather than only closing
  the symptom issue.
- Keep tracking an item until it is merged or closed. "Auto-merge is on" is not the end.
- Re-inventory after merging. A drill is a loop, not a pass.

## Don't

- Don't merge with any required check red, pending, or skipped for the wrong reason.
  Never force-push master, never pass `--no-verify`, never bypass branch protection.
- Don't skip, disable, `xfail` or delete a test to get green, and don't weaken an
  assertion. Don't push an empty commit or close and reopen a PR to re-trigger CI.
- Don't call a failure a flake without proof: same commit green earlier, or the
  job died before any test ran. At most one re-run.
- Don't rebase or force-push someone else's branch. Merge master into it instead.
- Don't touch an IN FLIGHT session PR, and don't close another session's work
  without the operator's say-so.
- Don't modify a rule-15 risky module, add a migration, change Actions permissions,
  or take a breaking dependency upgrade without asking first (rule 40).
- Don't widen a PR beyond its fix. A separate problem gets its own PR or a reported follow-up.
- Don't put a model identifier in commits, PR text or code comments. Don't paste
  a token anywhere (rule 42).
- Don't report "done" from your own summary. The phase 4 inventory output is the evidence.

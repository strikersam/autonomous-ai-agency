# Autonomous SDLC Loop (Agency Core, repo-agnostic)

> **Status:** Design / phased build. This document is the blueprint for moving the
> *entire* autonomous software-delivery loop out of this repo's GitHub Actions and
> into Agency Core, so **any repo connected by URL + token gets the whole loop** —
> not just `strikersam/local-llm-server`.

---

## The gap this closes

Today the loop is **half a pipeline** (verified live 2026-06-10):

```
issue ──► issue-context-generator.yml ──► docs: draft PR (plan + todos + prompt) ──► ⛔ STOP
```

The draft PRs (`#509`, `#512`, `#514` on `claude/context-issue-N`) are **plans, not
implementations**. Nothing autonomously turns a plan into code, resolves review
comments, or merges. And because the trigger is a **GitHub Action in *this* repo**,
none of it applies to a customer repo onboarded via URL.

The target loop, running **server-side in Agency Core**:

```
issue / signal
   └► CONTEXT      (plan + todos + prompt)            [exists: generate_context.py]
        └► IMPLEMENT  (agent writes code on the branch) [MISSING — Phase 1]
             └► VERIFY  (tests + bandit + lint)         [partial: workflow VERIFY phase]
                  └► REVIEW-RESOLVE (Codex/CodeRabbit)   [MISSING — Phase 2]
                       └► GATE (green + approved)        [partial: ApprovalGate, JUDGE]
                            └► MERGE to master           [MISSING — Phase 3]
                                 └► MONITOR (regressions)[exists: kpi + reconciler]
```

---

## Design principle: repo-agnostic, not GitHub-Actions-bound

Every step must be driven by a **`RepoConnection`** value object, never by ambient
`GITHUB_REPOSITORY` / workflow context:

```python
@dataclass(frozen=True)
class RepoConnection:
    url: str                 # https://github.com/<owner>/<repo>
    token: str               # per-connection PAT/OAuth (NOT the server token)
    default_branch: str = "main"
    provider: str = "github" # github | gitlab | … (future)
```

- The connection is created at **onboarding** (the user already supplies the repo
  URL + token there) and persisted with the Company in `CompanyGraphStore`.
- The loop clones/fetches into a **per-task worktree** (already implemented:
  `runtimes/adapters/internal_agent.py::_create_worktree`) so concurrent repos and
  tasks never collide.
- All GitHub calls go through a thin `GitHubClient(connection)` (REST), so the same
  code path works for `local-llm-server` and any onboarded repo. **No `.github/`
  workflow is required on the target repo.**

---

## Reuse map (what already exists)

| Capability | Existing component | Status |
|------------|--------------------|--------|
| Golden-path state machine | `services/workflow_orchestrator.py` (CLASSIFY→…→MONITOR) | ✅ live |
| Code-writing agent | `agent/loop.py::AgentRunner` | ✅ live |
| Per-task git worktree isolation | `runtimes/adapters/internal_agent.py::_create_worktree` | ✅ live |
| Concurrent task pickup | `tasks/dispatcher.py` (`asyncio.gather`, claim lock) | ✅ live |
| Push/PR token resolution (per-conn) | `workflow_orchestrator._resolve_push_token` | ✅ live (#506) |
| Signals → initiatives → tasks | `agents/portfolio_intelligence.py` | ✅ live |
| Context/plan generation | `.github/scripts/generate_context.py` | ⚠️ in CI — **port into core** |
| Approval / HITL gate | `workflow_orchestrator` `ApprovalGate` | ✅ live |
| Quality judge | workflow `JUDGE` phase | ✅ live |
| Autonomy metrics | `agent/kpi.py` + `/api/kpi/public` | ✅ live |
| Stranded-task recovery | `tasks/store.py::reconcile_stranded_tasks` | ✅ live |

The orchestrator **already is** the place this belongs. The work is adding the three
missing transitions and making the I/O `RepoConnection`-driven.

---

## Phases

### Phase 0 — `RepoConnection` plumbing
- Add the `RepoConnection` model + persistence on Company; populate at onboarding.
- `GitHubClient(connection)` REST wrapper (issues, PRs, comments, merge, checks).
- **Exit:** an onboarded repo can be listed, its open issues/PRs read, server-side.

### Phase 1 — Plan-PR → Implementation  *(highest leverage; closes the live gap)*
- New trigger: a task of type `implement_pr` carrying `{connection, pr_number,
  context_path}`. The dispatcher (already concurrent + worktree-isolated) runs
  `AgentRunner` against the context doc, commits real code to the PR branch, pushes
  with the connection token, and flips the PR from draft → ready.
- Wire `portfolio_intelligence` so an open `docs:` plan-PR becomes an `implement_pr`
  initiative — *"a portfolio task picks it up and drives it to close."*
- **Exit:** an open plan-PR gains a real implementation commit autonomously.

### Phase 2 — Review-comment resolution (Codex / CodeRabbit)
- Ingest review threads via `GitHubClient` (and the existing PR-activity webhook).
- For each actionable comment, enqueue a `resolve_review` sub-task → AgentRunner
  patches → push → resolve thread / reply. Bounded retries; escalate to HITL on
  ambiguity (reuse the `AskUserQuestion`-style gate).
- **Exit:** CodeRabbit's actionable comments get addressed without a human.

### Phase 3 — Quality gate + auto-merge
- Before merge, run the target repo's tests + **bandit** + lint **inside the
  worktree** (server-side, not the repo's Actions); extend tests where coverage drops.
- Merge only when: checks green **and** JUDGE = APPROVED **and** required approvals
  satisfied. Use `GitHubClient.merge` with the connection token.
- **Exit:** a green, approved PR merges to the target's default branch autonomously.

### Phase 4 — Monitor & regression guard
- After merge, watch for regressions; increment a `regressions_after_auto_merge`
  KPI (currently surfaced as `null` in `/api/kpi/public`) and raise a Doctor warning
  on any non-zero — the auto-merge safety net the brief requires.

---

## Safety invariants (carry over from `agent/CLAUDE.md`)
1. Verifier/JUDGE must pass before merge — no bypass.
2. Bounded retries on implement/resolve loops (reuse the loop's retry≤3).
3. Per-connection token only; never borrow the server token for a customer repo
   unless the operator explicitly opts in (`_resolve_push_token` already enforces this).
4. Every autonomous merge is logged to KPIs + the audit trail; HITL gate is mandatory
   for repos flagged `requires_approval`.

---

## Why not keep it in GitHub Actions?
Actions are bound to one repo, can't be applied to a customer's repo without
installing workflows there, can't share the Company Graph / specialist / skill
context, and can't be observed by the Doctor/KPIs. Moving the loop into Agency Core
makes it **universal, observable, and HITL-gated** — the platform becomes the
autonomous SDLC engine for any repo you point it at.

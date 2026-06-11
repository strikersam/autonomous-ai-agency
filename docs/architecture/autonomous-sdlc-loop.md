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
    provider: str = "github" # github | gitlab | bitbucket | … (provider-abstracted)
    delivery: "DeliveryPolicy | None" = None  # detected per repo (see below)
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

## Detect & respect each repo's delivery policy

**No assumed delivery model.** Every repo is different — some take PRs into the
default branch, some allow direct pushes to `main`, some use a release/integration
branch (gitflow), some gate on required reviews/checks/CODEOWNERS. The loop must
**discover** the convention and **conform** to it; it must never force a PR where
direct push is the norm, never direct-push where protection forbids it, and never
land on the wrong base branch.

```python
class MergeStyle(str, Enum):
    DIRECT_PUSH = "direct_push"      # push commits straight onto the target branch
    PR_MERGE    = "pr_merge"         # open a PR and merge it (merge/squash/rebase)

@dataclass(frozen=True)
class DeliveryPolicy:
    deployment_branch: str           # the FINAL branch changes must reach (e.g. main, release)
    work_base: str                   # branch to base work on (often == deployment_branch)
    merge_style: MergeStyle
    branch_prefix: str | None        # e.g. "feature/", "claude/" — match existing convention
    pr_required: bool                # branch protection requires a PR
    required_approvals: int          # min approving reviews before merge
    required_checks: list[str]       # status checks that must be green
    enforce_codeowners: bool         # CODEOWNERS review required
    merge_method: str                # "merge" | "squash" | "rebase" (repo's allowed setting)
    auto_merge_allowed: bool         # operator opt-in AND policy permits unattended merge
```

**Detection inputs (all read-only, per connection):**
- `GET /repos/{o}/{r}` → `default_branch`, allowed merge methods (`allow_squash_merge`…).
- `GET /repos/{o}/{r}/branches/{branch}/protection` → `pr_required`,
  `required_approving_review_count`, `required_status_checks`, `enforce_admins`,
  `require_code_owner_reviews`. (403/empty ⇒ unprotected ⇒ direct push *possible*.)
- Existing branch names (`GET /branches`) → infer `branch_prefix` and whether a
  release/integration branch exists.
- `CONTRIBUTING.md` / `.github/` conventions and recent merged-PR history → tie-break
  the style (PR vs direct, squash vs merge).

**Conform at GATE/MERGE:**
1. Base work on `work_base`, create `${branch_prefix}<task-slug>` if a branch flow is used.
2. If `merge_style == DIRECT_PUSH` **and** protection allows it → push commits to
   `deployment_branch` directly. Otherwise open a PR into the correct base.
3. Block the merge until `required_approvals`, `required_checks`, and CODEOWNERS are
   satisfied — using the repo's *own* rules, not ours.
4. Use the repo's allowed `merge_method`.

**Safe defaults & HITL:** when detection is ambiguous or protection can't be read,
fall back to the **safest** path (open a PR, never auto-merge) and surface the
detected `DeliveryPolicy` for operator confirmation before the first unattended
merge on that repo. `auto_merge_allowed` is opt-in per connection.

---

## Companies without a connected repo (URL-only onboarding)

Many companies onboard with **only a website URL** — no repo, no PAT, sometimes no
codebase at all. The agency must still be useful, and code work must **wait, not fail**.

**Split work by capability, not by company.** Every task declares what it needs:

```python
class TaskCapability(str, Enum):
    NONE        = "none"          # research, SEO, content, portfolio, monitoring, drafts
    REPO_READ   = "repo_read"     # scan/analyse code (clone only)
    REPO_WRITE  = "repo_write"    # implement / push / open PR / merge  → needs a connection
```

- **`NONE` tasks run regardless of any repo** — a URL-only company gets its full
  non-code agency (the content/SEO/research/marketing/portfolio/support specialists,
  which already exist and are now skill-bound for all 34 families). Value is delivered
  on day one without a repo.
- **`REPO_WRITE` (and `REPO_READ`) tasks** check the company's `RepoConnection` before
  execution. If none exists, the task is **created and paused**, not dropped:
  `status = BLOCKED`, `blocked_reason = "awaiting_repo_connection"` (a typed reason),
  surfaced on the board with a **“Connect a repository”** CTA (GitHub / GitLab /
  **Bitbucket**). The work item is visible and queued — the operator sees *exactly*
  what the agency would do the moment a repo is connected.

**Auto-resume on connect.** Adding a `RepoConnection` for a company emits a
`repo_connected` event that re-queues every task `BLOCKED` on
`awaiting_repo_connection` for that company (reuse `tasks/dispatcher._auto_retry_blocked`
+ the permissive `retry()` already on master in #515). No manual re-trigger.

**Provider-abstracted.** A repo connection can be GitHub, GitLab, or Bitbucket; the
`GitHubClient` generalises to a `RepoClient(connection)` interface so detection,
push, PR/MR, comments, and merge work across providers. A company may connect a repo
*after* months of URL-only operation — the queued code tasks then flow through the
normal loop.

**No fabricated code work.** If a company genuinely has no codebase, the loop never
invents `REPO_WRITE` tasks for it; the agency focuses on the domains it *can* serve.

---

## Universality: case-coverage matrix

To be truly universal the loop must have a defined behaviour for every combination
of connection, provider, policy, CI, review, state, stack, and governance. Each axis
below lists the cases and the handling; the **golden rule** across all of them:
*when uncertain or unsafe, stop at a reviewable artifact (PR/draft) + HITL — never
force, never silently drop, never land on the deployment branch.*

### A. Connection & credentials
| Case | Handling |
|------|----------|
| No repo + no token (URL-only) | Non-code work runs; code tasks paused `awaiting_repo_connection`. |
| Repo URL, no token (public) | `REPO_READ` (clone/scan) ok; `REPO_WRITE` paused `awaiting_token`. |
| Token, no repo URL | List repos the token can access; ask operator to pick (HITL). |
| Token with insufficient scope (no push/PR) | Detect via API probe; pause writes with `insufficient_scope` + re-auth CTA. |
| Token expired / revoked mid-flow | 401/403 ⇒ pause affected tasks, emit re-auth CTA, keep work queued. |
| Org SSO-gated token | Detect SSO requirement; surface "authorize token for org" CTA. |
| Fine-grained PAT vs classic vs OAuth vs GitHub App | Capability probe, not assumptions — store detected permissions on the connection. |
| Multiple repos per company (poly-repo) | A company has *N* `RepoConnection`s; tasks bind to a specific repo; route by path/signal. |
| Monorepo | One connection; path-scoped CODEOWNERS + path-scoped tests/scope. |

### B. Provider & host
| Case | Handling |
|------|----------|
| GitHub.com / GitHub Enterprise | `RepoClient(github, base_url)`; PR terminology. |
| GitLab.com / self-managed | MR terminology, GitLab CI checks, approvers rules. |
| Bitbucket Cloud / Server | PR + Bitbucket pipelines + reviewers. |
| Self-hosted / custom base URL | `base_url` on the connection; never hardcode api.github.com. |
| Unsupported provider | Degrade to clone+push over git only (no PR API); or pause with "provider unsupported". |

### C. Delivery / branch policy  *(detected — see DeliveryPolicy)*
| Case | Handling |
|------|----------|
| Direct push to default allowed | Push commits straight to deployment branch. |
| PR/MR required into default | Open PR into correct base; merge per repo rules. |
| Gitflow (feature→develop→release→main) | Base work on the integration branch, not `main`; respect promotion chain. |
| Protected branch: required reviews/checks/CODEOWNERS | Block landing until satisfied with the repo's own thresholds. |
| Required signed commits (GPG/S/MIME) | Sign with a configured key; if unavailable ⇒ pause `cannot_sign` + HITL. |
| Linear history / "up-to-date before merge" | Rebase/merge base, re-run checks, then land. |
| Squash-only / merge-only / rebase-only | Use the repo's single allowed `merge_method`. |
| Fork-only contribution (no upstream branch) | Fork → branch → PR from fork. |
| Ambiguous / unreadable protection | Safest path: PR, no auto-merge, surface policy for confirmation. |

### D. CI / checks
| Case | Handling |
|------|----------|
| Repo has CI (Actions/GitLab CI/Jenkins/external) | Wait for required checks; land only when green. |
| Repo has **no** CI | Run tests + bandit/lint **in our worktree** as the gate. |
| Required check we can't trigger (external) | Async wait w/ timeout ⇒ escalate, don't force-merge. |
| Flaky / transient failure | Bounded re-run; if persistent ⇒ real failure, escalate. |
| Long-running checks | Async wait off the worker; resume on webhook/poll. |
| Non-Python stack | Language-aware tooling (jest/go test/cargo/…); scanner detects stack. |

### E. Review automation & humans
| Case | Handling |
|------|----------|
| CodeRabbit / Codex bot reviews | Ingest threads; classify actionable vs nit vs question. |
| Actionable comment | Sub-task → patch → push → resolve thread. |
| Nit / question / "won't fix" | Reply with rationale; resolve or leave per convention. |
| Required **human** approval | Wait; never self-approve; notify the reviewer; timeout ⇒ escalate. |
| Conflicting / ambiguous feedback | HITL — do not guess. |
| Review loop (changes requested N×) | Bounded retries (≤3), then escalate with a diff of what was tried. |
| No reviewers at all | Our JUDGE + council-review skill act as the gating reviewer. |

### F. Repo state & conflicts
| Case | Handling |
|------|----------|
| Base moved / merge conflict | Rebase/merge base in the worktree, re-verify; unresolvable ⇒ HITL. |
| Existing draft/plan PR for the issue | Continue it in place; never open a duplicate. |
| Branch name collision | Detect + reuse or suffix; idempotent. |
| Concurrent tasks touching same files | Per-repo **merge queue** / serialize landings to avoid conflict storms. |
| Someone force-pushed the PR branch | Detect divergence; re-sync or escalate. |
| Repo deleted / access lost mid-flow | Pause, notify, keep artifacts. |

### G. Task origin
| Source | Handling |
|--------|----------|
| Issue (this or customer repo) | Context → implement → land. |
| Scanner signal (security/stack/trend) | Synthesized task, no issue required. |
| Operator / dashboard / Quick Note / Telegram | Normal task intake. |
| Portfolio initiative | Decomposed into capability-tagged tasks (WSJF-ranked). |
| Scheduled cadence | Recurring task; dedupe against open work. |

### H. Governance / safety / HITL
| Case | Handling |
|------|----------|
| Auto-merge opt-in vs off | Per connection; off ⇒ always stop at PR. |
| Production / high-risk repo | Stricter: mandatory HITL even if auto-merge on. |
| Sensitive paths (auth, payments, infra, secrets) | Mandatory HITL regardless of policy. |
| Spend / rate-limit budget per company | Enforce budget; pause `budget_exceeded` when hit. |
| Provider API rate-limited | Exponential backoff; resume. |
| Push rejected by secret-scanning / push protection | Treat as a hard stop; strip secret, never bypass protection. |
| Compliance (license, no-secrets, audit) | License check + `_local_safety_check`; every action audited + KPI'd. |

### I. Idempotency & dedupe (cross-cutting)
- One open PR per issue/initiative; one reply per review thread; reusing existing
  branches/PRs — keyed on `(connection, issue_id|initiative_id)`. CEO-style dedupe
  prevents two agents implementing the same thing.

### J. Concurrency & fairness (cross-cutting)
- Per-company and per-repo concurrency caps; fair scheduling across companies; a
  per-repo landing queue so concurrent merges don't thrash. Worktree isolation
  (already built) keeps task working trees independent.

### K. Stuck / dead-letter (cross-cutting)
- Any task that can't progress lands in a typed paused state (`awaiting_*`,
  `needs_human`, `budget_exceeded`, `cannot_sign`, …) — visible on the board, never
  lost. The reconciler (`reconcile_stranded_tasks`) is the last-resort net, observable
  and rate-warned (Doctor warning if it fires > N/24h).

---

## Integrations & intake sources (honest tiers)

Two distinct integration kinds — keep them separate and **never advertise what isn't
wired** (the docs-consistency gate applies):

**Code hosts (read + write: branch/PR/merge)**
- **GitHub / GitHub Enterprise** — supported.
- **GitLab**, **Bitbucket** — planned (provider-abstracted `RepoClient`).

**Intake sources (issues / tickets / signals → tasks)**
- **GitHub Issues** — supported.
- **Jira (API token)** — *planned, first-class.* High-value: poll/JQL the project,
  turn tickets into capability-tagged tasks, push status/comment back, link the PR to
  the ticket. (An Atlassian connector is already reachable in-session, so this is a
  natural near-term add — auth via Jira **API token + email + site URL**.)
- **Scanner signals / Quick Note / Telegram / operator dashboard** — supported.

**Coming soon (surface as a disabled option with a "Coming soon" badge — do NOT
implement a fake path):** AWS CodeCommit, Azure DevOps (Repos + Boards), Gitea,
Linear, Asana, Trello. These appear in the connect UI so users see the roadmap, but
selecting one says "coming soon" rather than pretending to integrate.

> Rule: an integration is either **wired + tested** (shown active) or **"Coming
> soon"** (shown disabled). Nothing in between — same anti-drift discipline as the
> feature matrix.

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

### Phase 0 — `RepoConnection` plumbing + delivery-policy detection
- Add the `RepoConnection` + `DeliveryPolicy` models + persistence on Company; populate at onboarding.
- `GitHubClient(connection)` REST wrapper (repo meta, branch protection, branches,
  issues, PRs, comments, checks, merge).
- `detect_delivery_policy(connection)` reads repo meta + branch protection + branch
  names + CONTRIBUTING to produce a `DeliveryPolicy`; cache on the connection.
- **Exit:** for any onboarded repo we can read its issues/PRs **and** report exactly
  how changes are expected to reach its deployment branch (PR vs direct, base branch,
  required approvals/checks) — server-side, with safe fallback when protection is unreadable.

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

### Phase 3 — Quality gate + policy-conformant landing
- Before landing, run the target repo's tests + **bandit** + lint **inside the
  worktree** (server-side, not the repo's Actions); extend tests where coverage drops.
- **Land per the detected `DeliveryPolicy`** (never a hardcoded model):
  - `DIRECT_PUSH` + protection permits → push to `deployment_branch`.
  - otherwise → open a PR into the correct base, using the repo's allowed `merge_method`.
- Merge/push only when the repo's *own* rules are satisfied: local checks green **and**
  JUDGE = APPROVED **and** `required_approvals`/`required_checks`/CODEOWNERS met **and**
  `auto_merge_allowed` (operator opt-in). Ambiguous policy ⇒ stop at an open PR + HITL.
- **Exit:** changes reach each repo's deployment branch *the way that repo expects*,
  with its protections respected.

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
5. **The repo's delivery policy is authoritative.** Never force a PR where direct push
   is the convention, never direct-push where branch protection forbids it, never land
   on a branch other than the detected base. Protection rules, required reviews/checks,
   and CODEOWNERS are obeyed as the repo defines them; unknown/unreadable policy ⇒
   safest path (PR, no auto-merge) + operator confirmation.

---

## Why not keep it in GitHub Actions?
Actions are bound to one repo, can't be applied to a customer's repo without
installing workflows there, can't share the Company Graph / specialist / skill
context, and can't be observed by the Doctor/KPIs. Moving the loop into Agency Core
makes it **universal, observable, and HITL-gated** — the platform becomes the
autonomous SDLC engine for any repo you point it at.

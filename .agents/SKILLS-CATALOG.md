# Autonomous AI Agency Skills Catalog

This is the authoritative index for the Autonomous AI Agency's skill ecosystem. It
provides per-task mapping so any future agent session can rapidly load the right
local file-based skills (from `.agents/skills/<name>/SKILL.md`), the runtime tools
the assistant tool surface exposes, and "best-in-class" external patterns. When a
new session opens, scan the **Quick Reference** table first.

> **Three layers per skill:**
> **[L]** = Local file-based skill in `.agents/skills/<name>/SKILL.md`
> **[R]** = Runtime assistant tool (loaded into this session's tool surface)
> **[E]** = Public-repo complement (citation by maintainer reputation, not URL)
>
> Local and runtime layers are first-party. External complements are *patterns of
> thought* — reasoning, prompts, checklists — never unauthenticated downloads.

---

## Quick Reference: Use Case → Skills

| Use case                                             | Local skills ([L])                                                          | Runtime layer ([R])                                            | External pattern ([E])                              |
| ----------------------------------------------------- | --------------------------------------------------------------------------- | -------------------------------------------------------------- | ---------------------------------------------------- |
| Feature implementation (design → code → tests → PR)   | `implementation-planner`, `test-first-executor`, `scope-guard`, `task-scoper` | `implementation-planner`, `test-first-executor`                 | Anthropic Claude Code, Aider                         |
| Code review & audit (security, quality, modularity)   | `council-review`, `modularity-review`, `risky-module-review`, `deslop`, `system-prompt-audit`, `dependency-audit` | `modularity-review`, `risky-module-review`, `council-review`, `deslop` | Obra/superpowers (architectural review templates)   |
| Git / PR operations (commit, branch, release, merge) | `smart-commit`, `release-readiness`, `changelog-enforcer`, `parallel-worktrees`, `git-hygiene` | `smart-commit`, `release-readiness`, `changelog-enforcer`, `branch-cleanup` | Conventional Commits standard                        |
| Memory and rule learning (long-term context)          | `repo-memory-updater`, `learn-rule`, `replay-learnings`, `self-improve`, `memory-consolidation` | `repo-memory-updater`, `learn-rule`, `replay-learnings`        | AutoGPT memory patterns                              |
| Research and docs (web, papers, library APIs)         | `research`, `docs-sync`, `graphify`, `repo-memory-updater`, `repowise-intelligence`, `fabric-patterns` | `perplexity`, `agent-browser`, `dev-browser`, `browserbase-search`, `graphify`, `repo-memory-updater` | Fabric (Daniel Miessler's pattern library)           |
| Multi-agent orchestration / swarm / handoffs          | `pro-workflow`, `session-handoff`, `wrap-up`, `parallel-agents`, `cooldown-resume` | `pro-workflow`, `cowork-session`, `hybrid-reasoning`, `session-handoff`, `wrap-up` | Anthropic Model Context Protocol (MCP)               |
| Risks / secrets / production-safety                   | `risky-module-review`, `git-hygiene`, `session-handoff`                       | `risky-module-review`                                           | OWASP LLM Top 10                                     |
| Auto-fix and regression handling                      | `self-improve`, `ticket-to-pr`, `auto-fix`, `issue-resolver`, `cooldown-resume`, `wrap-up` | `cooldown-resume`, `smart-commit`, `release-readiness`         | Anthropic Claude Code self-edit loop, Aider          |
| Live platform audit / e2e browser tests               | `release-readiness`, `risky-module-review`, `ticket-to-pr`                    | `agent-browser`, `browserbase-ui-test`, `browserbase-fetch`    | Playwright Pythonic bindings                         |
| Style and craft polish (UI / docs / prompt tone)      | `minimalist-skill`, `brutalist-skill`, `taste-skill`, `stitch-skill`, `soft-skill`, `redesign-skill`, `output-skill` | `deslop`, `prompt-transparency`                                  | Stripe Press, refactoring UI patterns (linear / vercel) |
| Trend learning / competitive intelligence (G4 / Autonomy Charter) | None direct — covered by TrendWatcher runtime + `agent/trend_watcher.py` | `perplexity`, `graphify`, `research`                            | Every.to, Stratechery (qualitative patterns)         |

---

## Best-in-Class External Skill Catalogs (Popular Git Repos, Reputational Citations)

These are the recognized public skill catalogs that influenced (or should influence)
our local skills. Citations are by maintainer reputation — DO NOT add unauthenticated
downloads from these; treat them as thought-pattern references to cross-check.

| Repo / Maintainer                                     | Why it's best-in-class                                  | How it maps into our skill set                              |
| ----------------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------ |
| Anthropic-maintained public skills catalog            | Reference implementation of agent skills for Claude Code | `pro-workflow`, `test-first-executor`, `implementation-planner`, `risky-module-review` patterns |
| Anthropic claude-code repo                            | Source of the canonical plan→execute→verify loop + permissions + MCP | `sessions/orchestrator.py` Golden Path, `auto-fix`, `ticket-to-pr` |
| obra/superpowers (community-recognised)               | Aggressive architectural review and "challenger" prompt bank | `council-review`, `modularity-review`, `system-prompt-audit` |
| Fabric (Daniel Miessler's prompt library)             | Wide catalogue of curated "extract the X from this" patterns | `fabric-patterns` (verbatim, well-tested)                    |
| OWASP LLM Top 10                                      | Industry-maintained threat catalog for LLM apps          | `risky-module-review` checklist inputs                       |
| Stripe Press / Refactoring UI patterns                | Calm design-language references for UI polish           | `minimalist-skill`, `soft-skill`, `stitch-skill`             |
| Conventional Commits standard                         | Community-maintained commit-message schema              | `smart-commit` formatter                                    |
| AutoGPT memory patterns                               | Battle-tested session-mem prompts                        | `memory-consolidation`, `repo-memory-updater`                |
| Aider maintainer cohort                               | Git-to-AST to-commit loop reference implementation       | `ticket-to-pr`, `auto-fix` patterns                         |
| MCP (Model Context Protocol) specification            | Tool-integration contract                                        | `parallel-agents`, `webui/commands.py`, `webui/providers.py` |

We deliberately do **NOT** auto-pull skills or fragments from these — pulls could
inject prompt-injection or be silently repointed. Pull only by hand, review diffs,
lock the SHAs in `.agents/skills/<x>/PIN.md` (one we add per imported skill).

---

## Comprehensive Skill Index (By Category)

### 1. Planning and Implementation
For scoping work, designing before coding, executing tightly.
- `implementation-planner` **[L][R]** — multi-file step-by-step plan generation
- `test-first-executor` **[L][R]** — TDD workflow enforcement
- `scope-guard` **[L]** — anti-creep belt-and-braces
- `task-scoper` **[L]** — task decomposition
- `ticket-to-pr` **[L]** — end-to-end GitHub-ticket → PR

### 2. Code Quality, Architecture, and Audits
For deep inspection and adversarial review.
- `council-review` **[L][R]** — multi-persona simulated review
- `modularity-review` **[L][R]** — boundary and coupling check
- `risky-module-review` **[L][R]** — privileged-module guard
- `deslop` **[L][R]** — remove AI slop
- `dependency-audit` **[L][R]** — third-party-package safety
- `system-prompt-audit` **[L]** — agent sub-prompts audit
- `data-quality-audit` **[L]** — dataset/output quality scoring

### 3. State Management and Git Flow
For wrangling version control and session state.
- `smart-commit` **[L][R]** — conventional-commit formatter
- `changelog-enforcer` **[L][R]** — keep docs/changelog.md honest
- `release-readiness` **[L][R]** — pre-tag gate
- `parallel-worktrees` **[L][R]** — concurrent isolated branches
- `branch-cleanup` **[R]** — delete merged branches
- `git-hygiene` **[L]** — keep the tree clean
- `checkpoint-strategy` **[L]** — runtime save-points
- `task-alive-updates` **[L]** — long-running task liveness

### 4. Memory, Knowledge, and Context Tuning
For carrying learnings across sessions.
- `repo-memory-updater` **[L][R]** — sync AGENTS.md / CLAUDE.md from reality
- `learn-rule` **[L][R]** — persist rules to long-term memory
- `replay-learnings` **[L][R]** — surface past patterns before acting
- `self-improve` **[L]** — pattern extraction from session outcomes
- `memory-consolidation` **[R]** — large-context distillation

### 5. Research, Browsing, and External Intel
For fetching non-local answers.
- `browserbase-search` / `browserbase-fetch` / `browserbase-ui-test` **[R]** — remote headless-browser stack
- `agent-browser` / `dev-browser` **[R]** — local CDP driving
- `perplexity` **[R]** — cited deep web research
- `research` **[L]** — research-output contract
- `docs-sync` **[L][R]** — keep code/docs in lockstep
- `graphify` **[L][R]** — repo knowledge graph
- `repowise-intelligence` **[L][R]** — dependency / git intelligence
- `fabric-patterns` **[L][R]** — Daniel Miessler's prompt library port
- `local-ai-query` **[L]** — local LLM-only query path

### 6. Session Lifecycle and Workflow
For the meta: how sessions start, run, hand off, end.
- `pro-workflow` **[L][R]** — Scout → Plan → Implement → Review discipline
- `session-handoff` **[L][R]** — next-session continuity
- `wrap-up` **[L][R]** — closing ritual
- `cooldown-resume` **[L][R]** — pause / resume across rate limits
- `cowork-session` **[R]** — shared pairing context
- `parallel-agents` **[L]** — multi-agent fan-out
- `context-prime` **[L]** — pre-task context injection
- `brain-dump` **[L]** — operator free-form ingestion

### 7. Style and Craft Polish (UI / Docs / Tone)
For "feel right" work — design, docs, prompts.
- `minimalist-skill` **[L]**, `brutalist-skill` **[L]**, `taste-skill` **[L]**, `stitch-skill` **[L]**, `soft-skill` **[L]**, `redesign-skill` **[L]**, `output-skill` **[L]**
- `prompt-library` **[L]** — curated prompt snippets
- `prompt-transparency` **[L]** — surface prompt-component provenance
- `llms.txt` **[L]** — site-level LLM-accessibility contract
- `resource-panel` **[L]** — presentation-component kit

### 8. Diagnostics and Debugging
For when things go wrong.
- `debug-tracer` **[L]** — narrow-down output
- `sandboxed-exec` **[L]** — run untrusted scripts safely
- `duplicate-thread` **[L]** — detect and merge parallel sessions
- `email-triage` **[L]** — sort inbound by urgency
- `feature-flag` **[L]** — risk-reduce new features
- `fabric-patterns` (also doubles here, classification patterns)

### 9. Self-Fixing and Regressions
For closing the loop on detected breakage.
- `auto-fix` **[L]** — small PRs from observed reproductions
- `issue-resolver` **[L]** — bug → fix workflow
- `ticket-to-pr` **[L]** — issue → branch → PR
- `cooldown-resume` **[L][R]** — handle transient failures
- `self-improve` **[L]** — meta-loop

### 10. Domain (Modelling, Training, Infra)
For ML/data/science stack.
- `lr-schedule-advisor` **[L]**
- `tokenizer-diagnostics` **[L]**
- `training-stability-monitor` **[L]**
- `data-quality-audit` **[L]**

---

## Known Gaps (Be Honest: What This Catalog Does NOT Cover)

- **Live IaC (Terraform, AWS CDK, Pulumi) deployments.** No skill attempts to mutate
  cloud resources from the agent loop. Operator-driven via `gh` / `wrangler` / `tf` CLI.
- **Database migration sandbox.** Code generation for SQL exists via the regular
  workflow, but destructive `migrate down` / schema-blast verification has no
  isolation harness. Operator reviews SQL changes before merge.
- **Active secret rotation.** We *audit* secrets via `dependency-audit`. We do
  *not* rotate AWS IAM keys, GitHub PATs, or Vault tokens from a skill — that is
  a privileged operation the operator must perform manually with the audit trail.
- **Hardware emulation / GPU kernel benchmarks.** Pure software only.
- **Live Pay / PCI patterns.** Out of scope; triggers `risky-module-review` and
  routes to the operator's compliance team.
- **Production deploy and master automation (no auto-merge-to-master skill).** PRs
  are the contract. No agent output flows directly to `master`; the Autonomy
  Charter G5 keeps first-merge / outbound pushes under Telegram-gated Repo
  Connection + Delivery Policy.

---

## How to Add a New Skill (Appendix — for the Next Operator)

1. Create `.agents/skills/<skill-name>/SKILL.md` following the existing structure
   (YAML frontmatter triggers, top description, full body).
2. Reference this catalog in the SKILL.md frontmatter so a future session can find
   the closest neighbours via `find .agents/skills -name '*.md' | xargs grep <skill-name>`.
3. Add a one-line entry to the **Comprehensive Skill Index** above.
4. If the skill depends on an external pattern repo, add a `PIN.md` file capturing
   the exact SHA / version reviewed and the date so drift is detectable.
5. If the skill outputs persistent state, document whether it lives in
   `.claude/state/sessions/` (gitignored) or `.claude/state/` (candidate commit,
   decide per file).
6. Do NOT bundle a `.env.example` rewrite here — that's its own skill
   (`changelog-enforcer`, with a `docs/configuration-reference.md` update path).

---

## Sources of Truth (Per AGENTS.md)

- Skill behaviour: `.agents/skills/<name>/SKILL.md` (the single canonical doc)
- Index / catalogue: `.agents/SKILLS-CATALOG.md` (this file)
- Per-session resumption: `.claude/state/sessions/<session-id>/STATE.json` (machine) / `SESSION.md` (human)
- Team-shared state files: `.claude/state/NEXT_ACTION.md`, `.claude/state/agent-state.json`,
  `checkpoint.jsonl` — decision per case whether to commit (see top-level ignore
  for session-private subtree; this section is intentionally tracked).
- Codebase contract (autonomy charter): `AGENTS.md`
- Architecture decisions: `docs/adrs/`
- Changelog: `docs/changelog.md`

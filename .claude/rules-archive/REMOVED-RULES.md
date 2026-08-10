# Removal Ledger — 308 normative statements cut, and why

Nothing has actually been deleted from the repo. This is the case for each cut, so
you can overrule any of it. Reason codes:

| Code | Meaning |
|------|---------|
| **DEFAULT** | I would already do this without being told. Generic good engineering, or behaviour I follow by matching surrounding code. |
| **HARNESS** | Already mandated by the Claude Code system prompt I run under. The repo copy adds context cost and zero behaviour. |
| **DUPE** | States something another rule in this repo already states. Kept once, cut here. |
| **GATE** | Already enforced mechanically by a git hook or a CI check. Prose restating an enforced gate cannot change an outcome. |
| **REFERENCE** | Not a rule — a fact, table, diagram, or command list. Belongs in docs, not in a ruleset. Retained where it lives. |
| **STALE** | Describes a state of the repo that is no longer true. Evidence in `CONFLICTS.md`. |
| **UNENFORCEABLE** | An aspiration with no check behind it and no way for an agent to comply or fail. |

---

## CLAUDE.md — 86 cut

| § | What | n | Code | Note |
|---|------|---|------|------|
| 2 | Architectural Principles | 10 | DEFAULT | "Never duplicate logic", "Composition over inheritance", "Dependency inversion", "Feature modules", "Configuration over code", "Event-driven communication", "Incremental migration", "No hidden coupling", "Everything observable", "Everything testable". Design maxims, not repo facts. The two with teeth (backward compatibility, secrets-env-only) survive as kept rules 41 and 6. |
| 3 | "No circular imports" | 1 | DEFAULT | Python basics. |
| 3 | "No `os.environ.get()` outside config modules" | 1 | DUPE | Same rule as the row two above it; merged into kept rule 5. |
| 7 | "Known issues (fixed)" — schedule multiplication | 1 | REFERENCE | A changelog entry living in the constitution. |
| 9 | "No `import *`", "No commented-out code" | 2 | DEFAULT | |
| 11 | Rewrite Strategy — 6 phases and their 5 rules | 5 | REFERENCE | A project plan. `REWRITE_PLAN.md` already holds it. "Phase 1 ← YOU ARE HERE" has been true since the file was written. |
| 13 | Autonomous Development Policy items 1–6 | 6 | DUPE/GATE | Each item restates §3, §10, or a CI check. Item 7 (squash-merge) survives inside kept rule 38. |
| 14 | **Standing Instructions, §14.1–§14.11** | **60** | **HARNESS/DUPE** | See the note below — this is the single largest cut. |

### The §14 cut, in detail

§14 is 2,908 words — 54% of `CLAUDE.md` — and it is genuinely well-written. It is
also the clearest case in the audit, because it is aimed at a general weakness in
LLM behaviour rather than at anything about this repository, and the Claude Code
harness already instructs the same behaviour before any repo file is read.

| §14 subsection | Directives | Verdict |
|----------------|-----------|---------|
| 14.1 Reading Intent | 4 | HARNESS — the system prompt already says to interpret ambiguity as a careful colleague would and to check in only when readings diverge materially. |
| 14.2 Breaking Problems Down | 4 | DEFAULT — decomposition before multi-file work. |
| 14.3 Effort Placement | 4 | DEFAULT |
| 14.4 Verification | 5 | DEFAULT — re-deriving counts is the highest-value item here. It is what caught the stale figures in `CONFLICTS.md`. It is also what I did in this audit without consulting §14. |
| 14.5 Known vs Guessed | 6 | DEFAULT — the three-marker syntax is house style, not a failure-preventer. |
| 14.6 Self-Attack | 3 | DEFAULT |
| 14.7 Completeness | 4 | HARNESS — "Finish the whole task… say explicitly what you left out and why." |
| 14.8 Refusing to Guess | 6 | DUPE of 14.5 plus DEFAULT. |
| 14.9 Delivery (answer/reasoning/risks) | 6 | HARNESS — the system prompt requires the outcome first and no throat-clearing. **This is the one block you may want back as a house style preference**, which is a different justification from "I would fail without it". |
| 14.10 Ten fake-competence patterns | 10 | DEFAULT — with one exception: pattern 7, phantom verification ("never write *I tested this* when no test ran"), is a real live failure mode. It is also verbatim harness policy: *"Report outcomes faithfully: if tests fail, say so with the output; if a step was skipped, say that."* HARNESS. |
| 14.11 Final Gate | 8 | DUPE — re-runs the eight preceding subsections. It also **conflicts** with 14.9: an 8-item re-pass "on every answer, no exceptions" is disproportionate for the one-line questions 14.9 tells you to answer in one line. |

Honest summary: about four of these 60 directives target failure modes that are
still live. All four are already carried by the harness. The other 56 are
restatements of ordinary careful work. The cost is 2,908 words in every session's
context, on every task, including the ones that touch no code at all.

---

## AGENTS.md — 107 cut

| Section | n | Code | Note |
|---------|---|------|------|
| Coding Standards §1–§8 (24 bullets) | 18 | DUPE | Duplicates `ENGINEERING_STANDARDS.md` §1–§3 and `CLAUDE.md` §9. Six survive as kept rules 24–29 — the ones naming a specific string or exception (`getLogger("qwen-proxy")`, the `WorkspaceTools` sync-I/O carve-out, `from __future__ import annotations`). |
| Git & Credentials prose | 3 | DUPE | Four bullets elaborating one rule; kept as rule 42. |
| Testing: "coverage must not decrease, baseline ~65%, target 80%" | 1 | UNENFORCEABLE | No coverage gate exists in the CI check list. An agent cannot tell whether it complied. |
| Testing: "Running Tests" command block | 1 | REFERENCE | |
| Documentation Requirements 1–5 | 3 | DUPE | Two survive as kept rules 34 and 37. |
| Deployment Process, Release Process, Monitoring Standards, Alerts | 20 | REFERENCE + STALE | Ops runbook content. Two entries are factually wrong — see `CONFLICTS.md` C4 (Vercel). |
| Bug Triage Process 1–7 | 7 | DEFAULT | Reproduce → isolate → fix → test → PR. Item 7 also **conflicts** with the `commit-msg` hook — see `CONFLICTS.md` C5. |
| PR Review Checklist (20 boxes) | 20 | GATE/DUPE | Every box is either a CI check or a rule already kept. A checklist of things a machine is already checking changes no outcome. |
| Definition of Done (8) | 8 | DUPE | |
| Autonomous Maintenance items 1, 3, 5, 7 | 4 | DEFAULT/DUPE | "Read before modifying" (default); "verify time-sensitive facts" (stated three times across `CLAUDE.md` §6, this list, and the Internet Access section); "scope changes tightly" (= golden rule); "commit incrementally" (default). Items 2, 4, 6, 8, 9, 10 survive as kept rules 39, 30, 44, 38, 40. |
| Agent Escalation Rules 1–8 | 7 | DUPE | Merged into one rule (kept rule 40). |
| Production Safety Rules — "never merge without CI", "never deploy without local test", "feature flags for risky features", "secrets never in code" | 4 | DUPE/UNENFORCEABLE | The remaining four merge into kept rule 41. "Never deploy to production without testing locally first" is untestable for an agent working in a container against auto-deploy branches. |
| Subagent Roles & Responsibilities table | 6 | REFERENCE | An org chart for six named agent personas. Useful orientation; not an instruction. |
| State Persistence file table | 5 | REFERENCE | The tracked-vs-gitignored convention below it is a real safety rule and survives as kept rule 43. |

---

## ENGINEERING_STANDARDS.md — 80 cut

| Section | n | Code | Note |
|---------|---|------|------|
| Naming conventions (13 rows) | 13 | DEFAULT | `snake_case.py`, `PascalCase` classes, `kebab-case` CSS. I match the surrounding code. |
| Import order (Python + JS blocks) | 2 | DEFAULT | |
| Function rules: single responsibility, docstrings, no `import *` | 3 | DEFAULT | Max-50-lines and type hints survive as kept rules 28 and 24. |
| File rules: max 300 lines JSX, no commented-out code, no `print()` | 3 | DEFAULT/DUPE | |
| Error handling JS block | 1 | DEFAULT | |
| Logging: 5 level definitions, 3 format examples | 7 | DEFAULT/REFERENCE | "Never log secrets" and `%s` formatting survive inside kept rules 6 and 26. |
| Security: secrets 4, auth 4, authz 2, rate limits 3 | 13 | DUPE | All already covered by kept rules 5, 6, 8, 41. The four security-header requirements are folded into kept rule 41 rather than cut. |
| Testing rules 3–6, fixture blocks, frontend blocks | 6 | DEFAULT/REFERENCE | Includes "tests must run in < 5 seconds each" — UNENFORCEABLE, no per-test timing gate exists. |
| CI/CD: PR requirement list, branch naming | 8 | GATE/DUPE | Conventional-commit prefixes survive inside kept rule 34, because the `commit-msg` hook parses exactly those prefixes. |
| Performance table (7), caching (4), DB indexes (5) | 16 | REFERENCE + STALE | Targets and current values with no measurement date. Several are contradicted by the `CLAUDE.md` bill of materials — see `CONFLICTS.md` C1. |
| Documentation standards (3) + arch doc list (5) | 8 | DUPE | Kept rule 37 covers the part with a consequence. |

---

## Module-level `CLAUDE.md` — 13 cut

| File | n | Code | Note |
|------|---|------|------|
| `agent/CLAUDE.md` | 10 | REFERENCE | Package description, model table, "skills to use" list, and the two 4-step tool-registration recipes. The recipes' one non-obvious fact — registering a tool is silent unless `build_tool_prompt()` also lists it — survives as kept rule 19. The invariants and the SSRF pattern survive as kept rules 16–20 and 14. |
| `router/CLAUDE.md` | 3 | REFERENCE | Selection-priority ladder, passthrough behaviour, env var table. The three invariants survive as kept rules 21–23. |

---

## `.openhands/microagents/` — 21 duplicated

Four files, 21 bullets, targeting OpenHands rather than Claude. Every bullet
restates `CLAUDE.md` or `AGENTS.md`. **Not cut** — they serve a different tool —
but flagged, because `repo.md` names `brain_policy.py` as a config module and that
file does not exist in the repo (`CONFLICTS.md` C2). A duplicated rule set drifts;
this one already has.

---

## Hooks — 1 cut, 6 kept

All six hook scripts stay. They are the reason a large part of the prose above is
redundant: `pre-commit` blocks staged `.env`/`keys.json` and hardcoded secrets,
`commit-msg` blocks a missing changelog entry, `pre-push` runs `pytest -x`,
`post-commit`/`graphify-refresh` keep the graph current.

One directive is cut: `session-plan-bootstrap` injects "Before writing any code
this session, FIRST produce a short PLAN + TODO list" into every session
(DEFAULT/HARNESS — I plan before multi-file work anyway, and the harness sends its
own task-tracking reminder). The hook itself should stay for the active-task
context it surfaces, though see the memory note below.

---

## Memory — `.claude/state/`

Not rules, but part of what loads every session, so audited:

- **`learnings.md`** — a template instructing "append one entry per session… each
  entry compounds into a growing knowledge base." It contains **zero entries**. An
  instruction that has never once been followed is not a rule, it is a decoration.
  Recommend deleting the file or actually using it.
- **`active-tasks.md`** — 4,789 words, of which the `session-plan-bootstrap` hook
  injects the first 60 lines into every session. The newest rows are dated
  2026-06-06 and link PRs in `strikersam/local-llm-server`, a repository name the
  remote no longer uses. Recommend trimming to open tasks only; the hook's context
  budget is currently spent on `DONE` rows from two months ago.
- **`NEXT_ACTION.md`** (1,496 words) and five session artifacts —
  `quick-notes-summary.md`, `quick-notes-processing-summary.md`,
  `twitter-228-insights.md`, `twitter-231-insights.md`, `issue-230-duplicate.md`
  (2,523 words combined) — are finished session output, not live state. Recommend
  moving to `docs/` or deleting.

---

## Skills — audited, not cut

45 skills in `.claude/skills/` (20,503 words) and 59 in `.agents/skills/` (35,868
words). These load on demand, not every session, so they do not carry the standing
context cost that motivated this audit, and cutting them would remove capability
rather than instruction. Two observations for a future pass:

- **17 skills exist in both trees** under the same name — `changelog-enforcer`,
  `cooldown-resume`, `council-review`, `dependency-audit`, `docs-sync`,
  `fabric-patterns`, `graphify`, `implementation-planner`, `modularity-review`,
  `release-readiness`, `repo-memory-updater`, `repowise-intelligence`,
  `risky-module-review`, `test-first-executor`, and others. Two copies of a
  behavioural instruction is the same drift risk as the microagents above.
- Several `.claude/skills/` entries carry an `ADAPTED FROM` preamble describing
  what a third-party original did before the rewrite. That is provenance for a
  reviewer, and it is being paid for in the model's context on every invocation.

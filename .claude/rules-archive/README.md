# Rules Audit — 352 rules in, 44 out

An audit of every standing instruction this repository gives an AI agent:
`CLAUDE.md`, `AGENTS.md`, `ENGINEERING_STANDARDS.md`, the module-level
`CLAUDE.md` files, `.openhands/microagents/`, the `.claude/hooks/` scripts,
`.claude/settings.json`, `.claude/state/` memory, and the two skill trees.

**Status: applied 2026-08-10.** `CLAUDE.md` §1 is now the single source of the 44
rules; `AGENTS.md` and `ENGINEERING_STANDARDS.md` were rewritten as reference-only
and point back to it. This folder is the record of what changed and why — keep it,
it is the argument for every rule that is missing.

A ninth conflict surfaced while applying: **the risky-module list gated three files
that no longer exist.** `admin_auth.py`, `rbac.py`, and `social_auth.py` moved into
`packages/auth/` (`admin.py`, `rbac.py`, `oauth.py`), so rule 15's review gate named
paths that could never match. Fixed in `CLAUDE.md` rule 15 and the `AGENTS.md` risky
table. Recorded as C9 in `CONFLICTS.md`.

**The §14 cut was partly wrong, and is partly reversed.** The audit judged §14
removable because the Claude Code harness already mandates it. That is true for
Claude Code and false for this repo's own agents: `.github/scripts/generate_context.py`
fed §14 to the autonomous issue-context agent, and `agents/profiles.py` bound all five
CRISPY roles to it. Those run on `nvidia/llama-3.3-nemotron-super-49b-v1` with no
harness behind them. CI caught it — the two tests guarding those paths failed.

Resolution: §14's four load-bearing directives are restored as `CLAUDE.md` §2, rules
45–48, at 250 words against the original 2,908. Both consumers now carve out §1 + §2
whole (~1,350 words) instead of a flat 4,000-char excerpt that cut mid-ruleset, so
those agents get *more* of the binding rules than before, not less. The 56 cut
directives stay cut. Ruleset total: **48 rules**, not 44.

One recommendation in `REMOVED-RULES.md` was withdrawn on inspection:
`.claude/state/learnings.md` is written by five skills (`learn-rule`,
`replay-learnings`, `session-handoff`, `wrap-up`, `insights`), so deleting it would
break them. It stays. That it has zero entries is a skill-adoption problem, not a
file problem.

| | Before | After | Change |
|---|---|---|---|
| Normative statements | 352 | **44** | −308 |
| Words of binding rules | 11,880 | **1,055** | −91% |
| Words across the whole always-on layer | 11,880 | **5,566** | −53% |

Two numbers because the old files interleaved rules with reference material, so all
11,880 words read as instruction. The 44 rules are 1,055 words; the remaining ~4,500
are the reference tables — architecture, codebase map, env vars, fixtures — kept,
corrected, and now clearly marked as *not* rules.

## Read in this order

1. **[`KEPT-RULES.md`](KEPT-RULES.md)** — the 44 surviving rules, rewritten. This is
   the deliverable.
2. **[`REMOVED-RULES.md`](REMOVED-RULES.md)** — the 308 cuts, grouped by source, each
   with a reason code. Overrule anything here.
3. **[`CONFLICTS.md`](CONFLICTS.md)** — eight contradictions and stale facts found
   while auditing, each with the command that proves it. Worth reading even if you
   reject the rest of the audit; several are live defects in the current rules.

## Method

You asked three questions of each rule: would I already do this untold, is it
correcting a weakness I no longer have, does it conflict with anything else. You
then said to mark for removal on a *no* to any of them — but that inverts against
your closing instruction, "keep only the rules you would actually fail without."
Answering *no* to the first question means the rule teaches me something, which is
exactly the rule to keep. I used the closing instruction as the intent, so a rule
survived only if:

- an agent that had never read it would get this repo **wrong**, and
- nothing else in the repo already says it, and
- no hook or CI check already enforces it mechanically.

That is why `packages/ai/router.py` is the only path to a provider (kept — 
unguessable) and "never duplicate logic" is not (cut — I do that anyway).

The counting unit is a *normative statement*: a numbered item, a directive bullet,
or a requirement table row. Reference tables — env var lists, the codebase map,
deployment topology, secrets inventory, performance targets — were excluded from
the 352, since they are facts rather than instructions. Mechanical cross-check:
`grep -cE '^\s*([0-9]+\.|[-*]|\|)\s'` across those files returns 622 total
bullets and rows, of which 352 carry an imperative.

## What the cut was actually made of

Three things dominate the 308:

1. **`CLAUDE.md` §14, Standing Instructions — 60 directives, 2,908 words, 54% of
   the file.** Well-written, and aimed at general LLM failure modes rather than at
   this repository. Roughly four of the 60 address something still live; all four
   are already mandated by the Claude Code system prompt I run under before I read
   any repo file. The rest is a description of ordinary careful work, paid for in
   context on every task including the ones that touch no code.
2. **Duplication — the same rule stated up to seven times.** "Every bug fix needs a
   regression test" appears seven times across four files — `CLAUDE.md` lines 358
   and 420, `AGENTS.md` lines 222, 358, 385, `ENGINEERING_STANDARDS.md` line 156,
   and `.openhands/microagents/repo.md` line 13
   (`grep -rn 'regression test'`). The changelog rule appears in eight files,
   counting the hook and skill that enforce it. Duplicated rules drift, and these
   already have — see `CONFLICTS.md` C1–C4.
3. **Prose restating an enforced gate.** The 20-box PR Review Checklist and the
   8-item Definition of Done list things that `pre-commit`, `commit-msg`,
   `pre-push`, and 22 CI checks already block on. A rule a machine is already
   enforcing cannot change an agent's outcome; it can only cost context.

## What was applied

- **`CLAUDE.md`** — §1 is the 44 rules; §2–§7 are reference (what the repo is,
  architecture, a re-measured bill of materials, commands, env vars, pointers).
  5,384 → 2,216 words.
- **`AGENTS.md`** — reference only: codebase map with re-measured line counts, risky
  modules, file-size exceptions, deployment, monitoring, agent roles, session state,
  git hooks. States no rule. 3,873 → 1,522 words.
- **`ENGINEERING_STANDARDS.md`** — worked examples and lookup tables only: log levels,
  error handling, authorization patterns, fixtures, commit format, performance
  targets, indexes, ADRs. 1,229 → 683 words.
- **`agent/CLAUDE.md`, `router/CLAUDE.md`** — package reference plus a pointer to the
  invariants (rules 16–23), instead of a second copy of them.
- **`.openhands/microagents/`** — four files reduced to pointers at `CLAUDE.md` §1.
  The `brain_policy.py` reference (C2) is gone.
- **`.claude/state/`** — 63 closed rows and the session log moved to
  `archive/completed-2026-06-to-08.md`; the live tracker now carries only open work,
  with a note that its six `IN_PROGRESS` rows have not been re-verified since July.
- **All nine conflicts** in `CONFLICTS.md` resolved in the files themselves.

Every path named in the 44 rules was checked to exist before this was committed.

# Rules Audit — 352 rules in, 44 out

An audit of every standing instruction this repository gives an AI agent:
`CLAUDE.md`, `AGENTS.md`, `ENGINEERING_STANDARDS.md`, the module-level
`CLAUDE.md` files, `.openhands/microagents/`, the `.claude/hooks/` scripts,
`.claude/settings.json`, `.claude/state/` memory, and the two skill trees.

**Nothing in this audit has been applied.** `CLAUDE.md`, `AGENTS.md`, and
`ENGINEERING_STANDARDS.md` are byte-identical to what they were before. This
folder is the proposal.

| | Before | After | Change |
|---|---|---|---|
| Normative statements | 352 | **44** | −308 |
| Words of standing instruction | 11,880 | **1,055** | −91% |

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

## If you approve

Applying this means: replace `CLAUDE.md` §0–§14 and the normative half of
`AGENTS.md` and `ENGINEERING_STANDARDS.md` with `KEPT-RULES.md`, keep the reference
tables where they are (they are useful; they are just not rules), and fix the eight
items in `CONFLICTS.md` — four of which are wrong regardless of what happens to the
rest of this audit.

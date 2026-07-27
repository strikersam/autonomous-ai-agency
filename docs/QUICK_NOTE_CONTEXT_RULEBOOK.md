# Quick-Note Context Rulebook

> **The quality standard for every context document generated from a quick-note issue.**
> Enforced programmatically by `.github/scripts/context_rules.py`, which runs inside
> `.github/scripts/generate_context.py` before any draft PR is opened.
> Read this before changing the generator, the prompt, or the gate.

---

## What this document is for

A quick-note issue is a URL and one line of intent. Something has to turn that into a
plan an implementing agent can act on without re-reading the source. That translation is
where the value is, and it is also where the whole pipeline used to fail: the generator
would restate the issue title in more words, hedge every noun, flag risky modules it had
no intention of touching, and ship a "plan" whose first TODO was *"Review the linked
repository"* — handing the actual work back to the reader.

The rules below exist to make that specific failure mode impossible. Each one names the
defect it prevents, states the rule, and says whether a machine or a human enforces it.

Rules marked **[gate]** are checked by `context_rules.validate()` and reported inline in the
generated document. Rules marked **[review]** are for the human or agent reviewing the
draft PR.

---

## The rules

### R1 — Ground the plan in the source before planning anything **[gate]**

The generator must fetch the linked URL and base the plan on what was actually retrieved.
If the fetch failed, the document must say so in its Source Grounding block, and the plan
must be marked as unverified throughout.

*Prevents:* a confident plan derived from nothing but the URL slug.

**Check:** when the fetch returned nothing, the document renders a `⚠️ NOT FETCHED`
grounding row and the gate records R1 as unmet. (Whether the summary itself is
substantive is R2's job, not R1's.)

---

### R2 — Say what the artifact actually is **[gate]**

Before proposing anything, the document must state in plain sentences what the source *is*
(a skill file, a library, a blog post, a spec, a paper) and what it *does*. This is the one
section a reader uses to decide whether the rest is worth reading.

*Prevents:* a plan about "the linked repository" that never establishes what the linked
repository contains.

**Check:** `source_summary` is at least 120 characters and is not merely the issue title or
the URL echoed back.

---

### R3 — Reach a verdict, and let that verdict be "reject" **[gate]**

Every document must record one of three verdicts:

| Verdict | Meaning |
|---------|---------|
| `adopt` | The source describes something this repo should build largely as-is. |
| `adapt` | The underlying idea is useful; the specific implementation is not a fit and is reworked. |
| `reject` | Nothing here belongs in this repo. |

`reject` is a first-class, valuable outcome and must come with a reason. Most linked
artifacts are genuinely not applicable to this codebase, and inventing a feature to justify
the issue is worse than closing it.

*Prevents:* random features bolted on because the pipeline assumed every issue must yield a
plan.

**Check:** `verdict` is one of the three values and `verdict_reason` is non-empty. A `reject`
verdict skips the TODO-shaped rules — there is no plan to check.

---

### R4 — Every TODO carries a done-condition **[gate]**

Each TODO must state what is observably true once it is finished, in terms someone could
check without doing the other TODOs. "Endpoint returns 200 with the `served_models` field"
is a done-condition. "Improve the endpoint" is not.

This is CLAUDE.md §14.2 applied to generated plans.

*Prevents:* a checklist that cannot be checked.

**Check:** every TODO has a `done_when` of at least 20 characters.

---

### R5 — No exploration masquerading as a task **[gate]**

A TODO may not open with `Review`, `Investigate`, `Explore`, `Research`, `Understand`,
`Consider`, `Look into`, `Analyze`, `Study`, `Familiarize`, `Determine`, or `Identify`
unless it names a target file and a done-condition that is not a restatement of the verb.
Reading the source is the generator's job, and it already happened; a plan that defers it
has done nothing.

*Prevents:* the "Step 1: read the thing I was supposed to read for you" plan.

**Check:** filler openers are matched against the ban list; a match with no `file`, or with a
`done_when` that repeats the same verb, is a violation.

---

### R6 — No hedged guesses **[gate]**

The prompt and notes may not contain `such as`, `e.g.`, `if necessary`, `if applicable`,
`may need to`, `might need`, `potentially`, `as appropriate`, `various`, `and so on`, or
`etc.`. Every one of these is the linguistic signature of a writer who did not check.
Where something genuinely is not known, say so with CLAUDE.md §14.5 marking — an explicit
`Assuming X (unverified) — if wrong, Y changes` — rather than a hedge that reads like a fact.

*Prevents:* "integrate features such as improved model routing or enhanced observability",
which names nothing and commits to nothing.

**Check:** case-insensitive substring scan of `prompt` and `notes`. `source_summary` is
exempt, since it describes someone else's writing.

---

### R7 — Risk flags must be earned **[gate]**

A module belongs in `risk_flags` only if a TODO actually modifies it. Flagging
`key_store.py` "in case" trains every reader to ignore the risk section, which is precisely
when a real risk gets missed.

*Prevents:* risk-flag inflation.

**Check:** every entry in `risk_flags` appears in the `file` field of at least one TODO.

---

### R8 — Named files must exist **[gate]**

Every path in `relevant_files` must resolve in the repository. A file the plan intends to
create is written with a trailing ` (new)` marker and is exempt.

*Prevents:* fabricated-but-plausible paths — the single most common way a generated plan
sends an implementing agent to a file that was never there.

**Check:** filesystem existence relative to `REPO_ROOT`.

---

### R9 — Do not restate the repository constitution **[gate]**

The prompt may not re-teach rules that every agent already loads from `CLAUDE.md`: run
`pytest -x`, add type hints, use Pydantic, log instead of print, update the changelog, keep
secrets out of source. Repeating them consumes the prompt budget that should be spent on
what is specific to *this* change, and it pads a thin plan until it looks thorough.

*Prevents:* coverage theater (CLAUDE.md §14.10 pattern 4).

**Check:** ban list of constitution phrases scanned against `prompt`.

---

### R10 — Use the repository's real identity **[gate]**

The project is `autonomous-ai-agency`. The former name `local-llm-server` must not appear in
generated text.

*Prevents:* plans addressed to a repository that no longer exists under that name.

**Check:** substring scan of `prompt`, `notes`, and `source_summary`.

---

### R11 — Name a real integration point **[gate]**

The plan must identify at least one existing module it hooks into. A change that touches
nothing that already exists is either a new subsystem — which needs an architecture note,
not a quick-note plan — or a fabrication.

*Prevents:* free-floating plans with no attachment to the codebase.

**Check:** at least one entry in `relevant_files` exists on disk without a `(new)` marker.

---

### R12 — Mark epistemic status at the claim **[review]**

Claims drawn from the fetched source are stated flat. Claims inferred about this repo's
internals are marked `Likely … based on …`. Anything unverified is marked
`Assuming … — if wrong, …`. This is CLAUDE.md §14.5, and it is the difference between a
document a reader can act on and one they have to re-derive.

*Prevents:* a guess inheriting the credibility of the verified facts around it.

**Enforcement:** human review of the draft PR. Not machine-checkable without judging meaning.

---

## How the gate behaves

`generate_context.py` runs the gate after the model returns:

1. **First pass fails** → the violations are fed back to the same model as a repair
   instruction, and it gets exactly one more attempt.
2. **Repair pass still fails** → the document ships anyway, with a **Quality Gate** section
   listing every unmet rule by ID.

Slop is never shipped silently. A document that violates rules says so at the top, which
means a reviewer can triage it in seconds instead of reading a plausible-looking plan to
the end before discovering it is empty.

A `reject` verdict is not a failure. It short-circuits R4, R5, R7, R8, and R11, since there is
no plan to check.

---

## Changing these rules

The rulebook and the gate are one artifact in two files. Changing
`.github/scripts/context_rules.py` without changing this document, or the reverse, is a
defect — `tests/test_context_rulebook.py` asserts that every rule ID in the gate is
documented here and vice versa.

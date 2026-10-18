# Continual Harness (`agent/harness_spec.py`)

A durable, cited document of *how to work in this repo*, refined as evidence
arrives — the idea borrowed from Prime Agent's "Continual Harness". Lessons in
`agent/lessons.py` already record why a step failed; the harness spec is what
turns a **repeated** failure into a standing instruction the planner reads
before it plans.

Lessons alone decay: `recent_lessons_block()` shows the most recent N, so a
failure that stops recurring for a while falls out of the window and is
re-learned the hard way. The spec is the part that sticks.

## The two rules that keep it honest

**Every entry cites its evidence.** An entry carries the signature of the lesson
that produced it and the hit count when it was written:

```markdown
## Standing instructions

- [lesson:9f2c1a4b8e hits=3] During execute: Executor did not produce an applicable file update.
```

A proposal with no traceable lesson is discarded, never written. Without that
rule a self-editing prompt accumulates plausible-sounding advice nobody can
trace to a real failure — the difference between learning and drift.

**Refinement is deterministic, not model-generated.** A lesson promotes once it
has been seen `HARNESS_SPEC_MIN_HITS` times (default 2). No LLM decides what
goes in the file, so it cannot hallucinate a rule, costs zero tokens, and is
fully testable. A failure seen once is an incident; seen twice, it is a pattern.

**Retirement and history.** Evidence works both ways. When later successes
contradict a lesson, the next refinement removes its entry instead of leaving it
to hold a slot; each addition or removal is appended to
`.agency/harness-history.jsonl` (signatures only). An unreadable lesson store
retires nothing. The idea comes from Google Research's Harness² (arXiv
2610.14224); its propose-probe-compose step was not adopted because it needs K
extra model runs per task.

## Where it lives

`.agency/harness.md` inside the workspace — plain Markdown, so it is readable,
hand-editable, diffable in review, and greppable when a prompt starts behaving
oddly. Hand-written prose above the `## Standing instructions` heading is
preserved across refinements; only the generated block is rewritten.

## Flow

```
run fails → agent/lessons.py records it (hits += 1)
          → harness_spec.refine() promotes lessons at/over the threshold
          → HarnessEnrichment.build_spec_block() injects them
          → AgentRunner._inject_enrichment() puts them in the next system prompt
```

The refine call sits in `AgentRunner.run()` immediately after
`record_step_failures`, and the injection reuses the existing enrichment path —
no second prompt-assembly route was added.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `HARNESS_SPEC_ENABLED` | `true` | Kill switch for reading/injecting |
| `HARNESS_SPEC_AUTO_REFINE` | `true` | Let runs append and retire entries |
| `HARNESS_SPEC_MIN_HITS` | `2` | Repeats before a lesson promotes |
| `HARNESS_SPEC_MAX_ENTRIES` | `40` | Entries retained in the file |
| `HARNESS_SPEC_MAX_CHARS` | `1200` | Cap on the injected block |

**Writing is on by default** (since 2026-10-18). All five settings are admin-panel
controls (Settings → Platform controls, group "Agent loop") and take effect without
a restart. Set `HARNESS_SPEC_AUTO_REFINE=false` to stop runs writing; on a workspace
with no `.agency/harness.md`, `build_block()` returns `""` and prompts are unchanged.
A spec that already exists — generated earlier, or committed by hand — is injected
while `HARNESS_SPEC_ENABLED` is true.

**Only cited entries are injected.** The spec lives inside the workspace, which
for agent work is often a third-party repository. An entry is injected only when
its citation matches a lesson this platform actually recorded, so a
`.agency/harness.md` committed by someone else cannot smuggle instructions into
the system prompt. Hand-written *prose* is preserved in the file but never
injected — only `- [lesson:…]` entries are.

When the block is truncated by `HARNESS_SPEC_MAX_CHARS`, the most-repeated
entries survive — if something has to go, keep the lessons that cost the most.

## Trying it

```bash
# auto-refine is already on; run the tasks below
# ...run agent tasks that fail the same way twice...
cat .agency/harness.md
```

Or drive it directly:

```python
from agent.harness_spec import refine, build_block
refine(".", lessons=[{"signature": "abc123", "hits": 2,
                      "lesson": "Run pytest before committing", "phase": "verify"}], force=True)
print(build_block("."))
```

## Reviewing what it wrote

The spec is a tracked file in the workspace, so a refinement shows up in
`git diff` like any other change. Read it the way you would read a PR: every
line names the lesson behind it, so an entry that looks wrong can be traced to
the run that produced it — and deleted, since hand edits are preserved.

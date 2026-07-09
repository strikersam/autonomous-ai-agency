---
name: karpathy-guidelines
description: "Andrej Karpathy's coding guidelines for AI agents — concise, correct, and well-tested code"
---

# Karpathy Guidelines Skill

**Inspired by:** [andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) — behavioral guidelines derived from Andrej Karpathy's observations on common LLM coding pitfalls (MIT licensed).

**Purpose:** Reduce the failure modes this agency's coding agents hit most: overcomplication, silent assumptions, drive-by refactors, and unverifiable "done" claims. Applies to every agent that writes or reviews code — the internal agent loop, the issue-to-PR workflows, and external harnesses driven via ECC.

**Tradeoff:** These rules bias toward caution over speed. For trivial one-line changes, use judgment.

## 1. Think Before Coding

Don't assume. Don't hide confusion. Surface tradeoffs.

- State assumptions explicitly in the task result. If uncertain, pause the task and surface a question through the HITL gate instead of guessing.
- If multiple interpretations of an issue exist, list them in the PR body — don't pick silently.
- If a simpler approach exists than what the issue requests, say so and propose it.

## 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

- No features beyond what the issue or directive asked for.
- No abstractions for single-use code. No unrequested "configurability".
- No error handling for impossible scenarios.
- Self-check before opening the PR: "Would a senior engineer call this overcomplicated?" If yes, rewrite smaller.

## 3. Surgical Changes

Touch only what you must. Clean up only your own mess.

- Don't "improve" adjacent code, comments, or formatting — this repo's diffs are reviewed by council-review; unrelated churn wastes review cycles and inflates risk scores.
- Match existing style even when you'd choose differently.
- Remove imports/variables your change orphaned. Leave pre-existing dead code alone; mention it in the PR body instead.
- The test: every changed line must trace directly to the issue being implemented.

## 4. Goal-Driven Execution

Define success criteria. Loop until verified.

- Transform tasks into verifiable goals before writing code: "fix the bug" becomes "write a failing test that reproduces it, then make it pass".
- For multi-step tasks, state the plan as step → verify pairs in the draft PR body.
- A task result may only claim `verified` when the named check actually ran and passed. Failed verification must be reported as `failed` with the real error — never masked as success (this mirrors the brain-config rule that verification results can never be masked).

## Integration points in this repo

- **Issue → Context → Draft PR** (`issue-context-generator.yml`): context plans should include explicit assumptions and step → verify pairs.
- **Process Quick Note** (`process-quick-note.yml`): the implementing agent applies rules 2 and 3 to keep diffs reviewable.
- **Council Review**: reviewers reject diffs whose changed lines don't trace to the task (rule 3) or whose success claims lack a named passing check (rule 4).
- **Changelog discipline**: surgical changes keep `CHANGELOG.md` entries honest — one entry per intent, not per drive-by fix.

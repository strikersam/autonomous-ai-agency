# Intent: adopt the rest of the AI-native SDLC playbook

Author: repository owner, written up by Claude Code. Status: accepted 2026-10-08.

## Problem

#1699 applied the build and gate plays. Six were still missing: CLAUDE.md was 412 lines of
mostly reference material read every session; the agency's own agents kept their plan in
memory instead of committing it; there was no REVIEW.md; nothing re-tested the agents'
configuration when it changed; an agent could weaken the tests that judge it; and no loop
turned a drifting production metric into new work.

## Proposed outcome

CLAUDE.md holds the rules and the verification commands, with reference moved out. Agent
PRs commit their plan. REVIEW.md defines the passes, and the agency's judge reads it.
Incidents become evals that run on config changes. The gate blocks weakened tests. A
deterministic control-band loop files an intent issue when master CI drifts.

## Affected users and systems

Every agent session (CLAUDE.md), every agent PR (gate, judge, plan file), CI (two new
workflows), the issue queue (control-band intents).

## Constraints

- §1–§2 of CLAUDE.md are extracted verbatim into production prompts; their text and
  markers must not change.
- Detection in the control-band loop is deterministic; no model decides a breach.
- No new secrets; workflows use `github.token` with the narrowest permissions.

## Open questions

- Model-graded evals (real agent runs scored in CI) need a provider budget; the evals here
  are deterministic replays and config checks.

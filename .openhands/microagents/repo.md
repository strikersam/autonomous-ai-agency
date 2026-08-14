---
name: repo
type: repo
version: 2.0.0
---

The binding rules for this repository are in `CLAUDE.md` §1 — 44 numbered rules,
authoritative for every agent regardless of tool. Read that section before changing
code; do not rely on a summary.

`AGENTS.md` holds the codebase map, the risky-module list, and the deployment and
monitoring reference. `ENGINEERING_STANDARDS.md` holds worked examples — fixtures,
log levels, error-handling patterns.

The rules were deliberately deduplicated in 2026-08. Earlier versions of this file
carried its own copy, which drifted: it named `brain_policy.py` as a config module,
and no such file exists. Do not reintroduce a local copy here.

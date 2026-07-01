# ADR-001: Adopt packages/ directory structure

## Status
Accepted

## Context
The repository has 628 Python files across 48 top-level directories with no
clear separation between applications, libraries, and infrastructure. Root
level contains 38 .py files that should be in packages.

## Decision
Adopt a `packages/` directory for shared libraries and `apps/` for deployable
applications, as defined in ARCHITECTURE.md.

## Consequences
- New code goes in packages/
- Existing code stays in place until migrated (Strangler Fig pattern)
- Migration is incremental — one subsystem at a time
- Old code deleted only after new code verified in production for 7 days

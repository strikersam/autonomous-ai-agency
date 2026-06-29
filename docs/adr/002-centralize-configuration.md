# ADR-002: Centralize configuration in packages/config/

## Status
Accepted

## Context
Environment variables are read via os.environ.get() in 30+ files across the
codebase. This makes it impossible to audit, validate, or document all config
in one place.

## Decision
Create packages/config/settings.py as the single source of truth. Every module
imports `from packages.config import settings`. No module reads os.environ
directly (except settings.py).

## Consequences
- All env vars documented in one file
- Type safety via typed Settings class
- Easy to audit (grep for os.environ should only find settings.py)
- Migration is incremental — existing code keeps working

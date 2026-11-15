"""packages/runs — durable runs: records, events, lease with fencing, side effect ledger.

A persistence and lifecycle layer, not an orchestration engine: the existing
engines decide what to do and record here that it happened. See
``docs/plans/2026-11-14-enterprise-reliability-durable-execution-plan.md``.
"""
from __future__ import annotations

"""tests/test_loops_api.py — contract test for GET /api/loops.

The Loops screen (Loop Engineering UI surface) reads this endpoint. It must:
  * return the full catalogued fleet (one entry per loop in loops/registry.yaml),
  * include the loop-audit readiness (score/grade/dimensions) + drift status +
    loop-cost estimate,
  * never raise — a registry problem degrades to ok=False with an empty fleet.
"""
from __future__ import annotations

import asyncio


def test_loops_overview_returns_fleet_and_readiness():
    from backend.server import loops_overview

    body = asyncio.run(loops_overview())

    assert body["ok"] is True
    assert isinstance(body["loops"], list)
    assert len(body["loops"]) > 0, "registry.yaml should catalogue at least one loop"

    # Readiness block shape (powers the score dial + dimension tiles).
    r = body["readiness"]
    assert 0 <= r["score"] <= 100
    assert r["grade"] in {"A", "B", "C", "D", "F"}
    assert r["total_loops"] == len(body["loops"])
    assert set(r["by_level"]) == {"L1", "L2", "L3"}
    assert {"maturity", "self_heal", "governance", "safety"} <= set(r["dimensions"])

    # Drift + cost.
    assert "ok" in body["drift"]
    assert isinstance(body["est_monthly_tokens"], int)

    # Each loop row carries the fields the table renders.
    sample = body["loops"][0]
    for key in ("id", "name", "pattern", "level", "cadence", "cost", "self_heal", "gate", "source"):
        assert key in sample, f"loop row missing {key!r}"

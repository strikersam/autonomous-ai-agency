"""tests/test_loop_registry.py — Loop Engineering governance layer.

Pins the contract of agent/loop_registry.py (loop-audit / loop-cost / drift
self-heal) and proves the committed loops/registry.yaml is valid and in sync
with the cron-scheduled workflows on disk.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from agent.loop_registry import (
    DEFAULT_REGISTRY_PATH,
    DEFAULT_WORKFLOWS_DIR,
    DriftReport,
    LoopRegistry,
    LoopSpec,
    ReadinessReport,
    audit_drift,
    load_registry,
    load_registry_sync,
    loop_readiness,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _spec(**over) -> LoopSpec:
    base = dict(
        id="x", name="X", pattern="self-heal", level="L2", trigger="daemon",
        cadence="continuous", runs_per_day=1, cost="low", source="agent/loop_registry.py",
        self_heal=True, gate="telegram", purpose="p",
    )
    base.update(over)
    return LoopSpec(**base)


# ── Model validation ────────────────────────────────────────────────────────

def test_loop_id_must_be_kebab():
    with pytest.raises(ValueError):
        _spec(id="Bad Id")


def test_duplicate_ids_rejected():
    with pytest.raises(ValueError):
        LoopRegistry(loops=[_spec(id="dup"), _spec(id="dup")])


def test_by_id_lookup():
    reg = LoopRegistry(loops=[_spec(id="a"), _spec(id="b")])
    assert reg.by_id("a").id == "a"
    assert reg.by_id("missing") is None


# ── loop-cost ───────────────────────────────────────────────────────────────

def test_cost_scales_with_tier_and_cadence():
    low = _spec(cost="low", runs_per_day=1)
    high = _spec(cost="high", runs_per_day=1)
    assert high.estimate_monthly_tokens() > low.estimate_monthly_tokens()
    # event-driven loops (runs_per_day=0) are modelled as zero standing cost
    assert _spec(cost="very_high", runs_per_day=0).estimate_monthly_tokens() == 0


def test_fleet_cost_is_sum_of_loops():
    reg = LoopRegistry(loops=[_spec(id="a", cost="low", runs_per_day=2),
                              _spec(id="b", cost="medium", runs_per_day=3)])
    assert reg.estimate_monthly_tokens() == sum(l.estimate_monthly_tokens() for l in reg.loops)


# ── loop-audit ──────────────────────────────────────────────────────────────

def test_readiness_empty_registry_is_zero():
    report = loop_readiness(LoopRegistry(loops=[]))
    assert report.score == 0 and report.grade == "F"


def test_readiness_is_bounded_and_graded():
    reg = LoopRegistry(loops=[
        _spec(id="a", level="L3", self_heal=True, cost="high", gate="telegram"),
        _spec(id="b", level="L2", self_heal=True),
        _spec(id="c", level="L1", self_heal=False, gate="none"),
    ])
    report = loop_readiness(reg)
    assert isinstance(report, ReadinessReport)
    assert 0 <= report.score <= 100
    assert report.grade in {"A", "B", "C", "D", "F"}
    assert set(report.dimensions) == {"maturity", "self_heal", "governance", "safety"}
    assert report.by_level == {"L1": 1, "L2": 1, "L3": 1}


def test_higher_maturity_scores_higher():
    low = LoopRegistry(loops=[_spec(id="a", level="L1", self_heal=False, gate="none")])
    high = LoopRegistry(loops=[_spec(id="a", level="L3", self_heal=True, gate="telegram")])
    assert loop_readiness(high).score > loop_readiness(low).score


def test_ungated_risky_loop_dings_safety():
    reg = LoopRegistry(loops=[_spec(id="a", level="L3", cost="very_high", gate="none")])
    report = loop_readiness(reg)
    assert report.dimensions["safety"] == 0
    assert any("gate" in n for n in report.notes)


# ── drift self-heal ─────────────────────────────────────────────────────────

def test_drift_flags_stale_source(tmp_path):
    reg = LoopRegistry(loops=[_spec(id="ghost", trigger="daemon",
                                    source="agent/does_not_exist.py")])
    # empty workflows dir → no "missing", but the bogus source is stale
    drift = audit_drift(reg, workflows_dir=tmp_path, repo_root=REPO_ROOT)
    assert isinstance(drift, DriftReport)
    assert "agent/does_not_exist.py" in drift.stale_sources
    assert drift.ok is False


def test_drift_flags_missing_scheduled_workflow(tmp_path):
    wf = tmp_path / "new-loop.yml"
    wf.write_text("on:\n  schedule:\n    - cron: '0 0 * * *'\n", encoding="utf-8")
    reg = LoopRegistry(loops=[])
    drift = audit_drift(reg, workflows_dir=tmp_path, repo_root=REPO_ROOT)
    assert ".github/workflows/new-loop.yml" in drift.missing_from_registry
    assert drift.ok is False


# ── Committed registry must be real and in sync ─────────────────────────────

def test_committed_registry_loads_and_validates():
    reg = load_registry_sync()
    assert reg.version >= 1
    assert len(reg.loops) >= 20
    # core autonomy loops are catalogued
    assert reg.by_id("autonomous-cycle") is not None
    assert reg.by_id("autonomous-cycle").level == "L3"


def test_committed_registry_has_no_drift():
    """Every cron-scheduled workflow is catalogued and every source exists."""
    reg = load_registry_sync()
    drift = audit_drift(reg)
    assert drift.ok, (
        f"loop registry drift — missing: {drift.missing_from_registry}, "
        f"stale: {drift.stale_sources}"
    )


def test_async_loader_matches_sync():
    sync = load_registry_sync()
    rid = sorted(l.id for l in sync.loops)
    a = asyncio.run(load_registry())
    assert sorted(l.id for l in a.loops) == rid


def test_default_paths_exist():
    assert DEFAULT_REGISTRY_PATH.exists()
    assert DEFAULT_WORKFLOWS_DIR.is_dir()

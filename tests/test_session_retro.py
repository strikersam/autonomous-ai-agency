"""Tests for services/session_retro.py — session retrospective mining."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from agent.improvement_loop import ImprovementLoop
from agent.state import AgentSessionStore
from services import session_retro


def test_retro_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SESSION_RETRO_ENABLED", raising=False)
    assert session_retro.retro_enabled() is False


@pytest.fixture
def store(tmp_path: Path) -> AgentSessionStore:
    return AgentSessionStore(db_path=tmp_path / "sessions.db")


def _seed_friction(store: AgentSessionStore, n_sessions: int, issue_text: str) -> None:
    for i in range(n_sessions):
        session = store.create(title=f"session-{i}")
        store.append_event(session.session_id, "empirical_verify_failed", {"issues": [issue_text]})


def test_collect_friction_events_reads_matching_event_types(store: AgentSessionStore):
    _seed_friction(store, 2, "byte-compile failure in mod.py")
    session = store.create(title="clean")
    store.append_event(session.session_id, "tool_call", {"tool": "read_file"})  # not friction

    events = session_retro.collect_friction_events(store, lookback=50)
    assert len(events) == 2
    assert all(e.event_type == "empirical_verify_failed" for e in events)


def test_cluster_friction_groups_by_signature(store: AgentSessionStore):
    _seed_friction(store, 3, "byte-compile failure in mod.py")
    events = session_retro.collect_friction_events(store, lookback=50)
    clusters = session_retro.cluster_friction(events)
    assert len(clusters) == 1
    assert clusters[0].count == 3
    assert len(clusters[0].sessions) == 3


def test_judge_cluster_falls_back_without_judge_fn():
    cluster = session_retro.FrictionCluster(
        signature="x", event_type="empirical_verify_failed", count=4, sessions=["a", "b"]
    )
    text = session_retro.judge_cluster(cluster)
    assert "occurred 4 times" in text


def test_judge_cluster_uses_judge_fn_when_provided():
    cluster = session_retro.FrictionCluster(signature="x", event_type="t", count=1, sessions=["a"])
    result = session_retro.judge_cluster(cluster, judge_fn=lambda c: "LLM verdict")
    assert result == "LLM verdict"


def test_clusters_to_issues_respects_min_count(store: AgentSessionStore):
    _seed_friction(store, 2, "rare failure")
    events = session_retro.collect_friction_events(store, lookback=50)
    clusters = session_retro.cluster_friction(events)
    assert session_retro.clusters_to_issues(clusters, min_count=3) == []
    assert len(session_retro.clusters_to_issues(clusters, min_count=2)) == 1


def test_run_retro_cycle_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SESSION_RETRO_ENABLED", raising=False)
    result = asyncio.run(session_retro.run_retro_cycle())
    assert result == {"scanned": 0, "clusters": 0, "routed": 0, "reason": "disabled"}


def test_run_retro_cycle_routes_recurring_friction(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SESSION_RETRO_ENABLED", "true")
    monkeypatch.setenv("SESSION_RETRO_MIN_CLUSTER", "3")
    db_path = tmp_path / "sessions.db"
    monkeypatch.setenv("AGENT_DB_PATH", str(db_path))

    seed_store = AgentSessionStore(db_path=db_path)
    _seed_friction(seed_store, 4, "recurring parse error")

    loop = ImprovementLoop(repo_root=tmp_path, on_task=None)
    import agent.improvement_loop as improvement_loop_mod
    monkeypatch.setattr(improvement_loop_mod, "_loop_instance", loop)

    result = asyncio.run(session_retro.run_retro_cycle())
    assert result["scanned"] == 4
    assert result["clusters"] == 1
    assert result["routed"] == 1
    assert loop.get_status()["issues_detected"] == 1

"""Tests for agents/portfolio_intelligence.py — autonomous signal → initiative.

Loads modules with a stubbed ``agents`` package so the heavy ``agents/__init__``
chain is bypassed. All signals (GitHub, research) are injected — no network.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


if "agents" not in sys.modules or not hasattr(sys.modules.get("agents"), "__path__"):
    pkg = types.ModuleType("agents")
    pkg.__path__ = [str(ROOT / "agents")]
    sys.modules["agents"] = pkg
_load("agents.agile_sprints", "agents/agile_sprints.py")
_load("agents.portfolio", "agents/portfolio.py")
pi = _load("agents.portfolio_intelligence", "agents/portfolio_intelligence.py")

InitiativeStatus = sys.modules["agents.portfolio"].InitiativeStatus

SAMPLE_TASKS = """# Active Task Tracker

## Current Sprint Tasks

| # | Task | Status | PR / Branch | Notes | Updated |
|---|------|--------|-------------|-------|---------|
| 1 | Old shipped thing | `DONE` | [#1](http://x) | done | 2026-06-05 |
| 2 | Build the message bus | `IN_PROGRESS` | — | wip | 2026-06-05 |

## Bug Log

| # | Bug Description | Found | Fixed | PR | Status |
|---|----------------|-------|-------|----|--------|
| 1 | Already fixed leak | 2026-06-03 | 2026-06-03 | #1 | `BUG_FIXED` |
| 2 | Token refresh crashes on expiry | 2026-06-05 | — | — | `BUG_FOUND` |

## Roadmap Items (from `docs/roadmap-killer-todos.md`)

| # | Item | Priority | Status | PR |
|---|------|----------|--------|-----|
| ★1 | 3-Phase Context-Pruner Middleware | P0 | `TODO` | — |
| C4 | Chat History Persistence | P1 | `TODO` | — |
| Z9 | Shipped roadmap item | P1 | `DONE` | #2 |
"""


class TestParsing:
    def test_roadmap_items_skip_done_and_score_priority(self):
        inits = pi.initiatives_from_roadmap(SAMPLE_TASKS)
        titles = {i.title for i in inits}
        assert "3-Phase Context-Pruner Middleware" in titles
        assert "Chat History Persistence" in titles
        assert "Build the message bus" in titles          # open sprint task
        assert "Old shipped thing" not in titles           # DONE skipped
        assert "Shipped roadmap item" not in titles        # DONE skipped
        p0 = next(i for i in inits if i.title.startswith("3-Phase"))
        p1 = next(i for i in inits if i.title == "Chat History Persistence")
        assert p0.business_value == 13 and p0.source == "roadmap"
        # P0 carries higher cost of delay (priority signal, size-independent).
        # NB WSJF itself favours shorter jobs, so a big P0 can rank below a small P1.
        assert p0.cost_of_delay > p1.cost_of_delay

    def test_in_progress_status_mapped(self):
        inits = pi.initiatives_from_roadmap(SAMPLE_TASKS)
        bus = next(i for i in inits if "message bus" in i.title)
        assert bus.status == InitiativeStatus.IN_PROGRESS
        assert bus.source == "sprint"

    def test_bug_log_only_open(self):
        inits = pi.initiatives_from_bug_log(SAMPLE_TASKS)
        titles = [i.title for i in inits]
        assert titles == ["Fix: Token refresh crashes on expiry"]
        assert inits[0].source == "bug"
        assert inits[0].status == InitiativeStatus.APPROVED
        assert inits[0].time_criticality == 8

    def test_estimate_job_size(self):
        assert pi.estimate_job_size("Middleware refactor") == 13   # big hint
        assert pi.estimate_job_size("Tweak label") == 5            # small
        assert pi.estimate_job_size("x" * 70) == 8                 # long title


class TestGithubAndResearch:
    def test_github_signals_filter_prs_from_issues(self):
        class FakeResp:
            def __init__(self, data): self._d = data
            def json(self): return self._d

        def fake_get(url, headers):
            if "/pulls" in url:
                return FakeResp([{"title": "Refactor router", "number": 12}])
            return FakeResp([
                {"title": "Crash on startup", "number": 30},
                {"title": "Actually a PR", "number": 31, "pull_request": {"url": "x"}},
            ])

        payload = pi.fetch_github_signals("owner/repo", "tok", http_get=fake_get)
        assert payload["pulls"] == [{"title": "Refactor router", "number": 12}]
        assert payload["bug_issues"] == [{"title": "Crash on startup", "number": 30}]

    def test_github_no_token_returns_empty(self):
        assert pi.fetch_github_signals("owner/repo", None) == {}

    def test_initiatives_from_github(self):
        inits = pi.initiatives_from_github({
            "pulls": [{"title": "Add caching", "number": 9}],
            "bug_issues": [{"title": "NPE in parser", "number": 10}],
        })
        by_source = {i.source: i for i in inits}
        assert by_source["pr"].status == InitiativeStatus.IN_PROGRESS
        assert by_source["bug"].title == "Fix: NPE in parser"

    def test_initiatives_from_research_scales_relevance(self):
        inits = pi.initiatives_from_research([
            {"title": "New reranker model", "source": "arxiv", "relevance_score": 0.9},
        ])
        assert inits[0].source == "research"
        assert inits[0].title.startswith("Evaluate:")
        assert inits[0].business_value >= 10   # high relevance → high BV


class TestBuild:
    def _intel(self, tmp_path):
        state = tmp_path / ".claude" / "state"
        state.mkdir(parents=True)
        (state / "active-tasks.md").write_text(SAMPLE_TASKS, encoding="utf-8")
        return pi.PortfolioIntelligence(repo="owner/repo", root=tmp_path, github_token=None)

    def test_build_combines_sources_and_counts(self, tmp_path):
        intel = self._intel(tmp_path)
        mgr = intel.build(
            github_payload={"pulls": [{"title": "Add caching", "number": 9}], "bug_issues": []},
            research_alerts=[{"title": "New model", "source": "hn", "relevance_score": 0.8}],
        )
        ranked = mgr.prioritized()
        sources = {i.source for i in ranked}
        assert {"roadmap", "sprint", "bug", "pr", "research"} <= sources
        # WSJF descending
        wsjfs = [i.wsjf for i in ranked]
        assert wsjfs == sorted(wsjfs, reverse=True)
        # build counts recorded
        assert intel.last_build.get("bug", 0) >= 1
        assert intel.last_build.get("pr", 0) == 1

    def test_build_dedupes_by_title(self, tmp_path):
        intel = self._intel(tmp_path)
        # A PR whose title matches the open bug should not double-count.
        mgr = intel.build(
            github_payload={"pulls": [], "bug_issues": [
                {"title": "Token refresh crashes on expiry", "number": 5}]},
            research_alerts=[],
        )
        titles = [i.title for i in mgr.prioritized()]
        assert titles.count("Fix: Token refresh crashes on expiry") == 1

    def test_build_offline_still_has_backlog(self, tmp_path):
        intel = self._intel(tmp_path)
        mgr = intel.build(github_payload={}, research_alerts=[])
        assert mgr.initiative_count >= 3   # roadmap + sprint + bug from local files

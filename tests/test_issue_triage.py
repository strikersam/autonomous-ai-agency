"""Tests for services/issue_triage.py — inbound GitHub issue classification."""
from __future__ import annotations

import asyncio

import pytest

from agent.improvement_loop import ImprovementLoop, IssueSeverity
from services import issue_triage


def test_triage_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ISSUE_TRIAGE_ENABLED", raising=False)
    assert issue_triage.triage_enabled() is False


def test_triage_enabled_via_env(monkeypatch):
    monkeypatch.setenv("ISSUE_TRIAGE_ENABLED", "true")
    assert issue_triage.triage_enabled() is True


def test_match_family_security_keyword():
    assert issue_triage._match_family("Auth bypass vulnerability", "") == "security"


def test_match_family_defaults_to_engineering():
    assert issue_triage._match_family("Something odd", "") == "engineering"


def test_severity_maps_critical_label():
    issue = {"labels": [{"name": "security"}]}
    assert issue_triage._severity_for(issue) == IssueSeverity.CRITICAL


def test_severity_defaults_to_low():
    assert issue_triage._severity_for({"labels": []}) == IssueSeverity.LOW


def test_triage_one_builds_detected_issue():
    issue = {
        "number": 42,
        "title": "CI pipeline fails on deploy step",
        "body": "The docker build step in the workflow keeps failing.",
        "labels": [{"name": "bug"}],
    }
    decision = asyncio.run(issue_triage.triage_one(issue))
    assert decision["issue_number"] == 42
    assert decision["family"] == "devops"
    assert decision["severity"] == "high"
    detected = decision["detected_issue"]
    assert detected.issue_id == "gh-42"
    assert "[#42]" in detected.title


def test_run_triage_cycle_returns_disabled_reason(monkeypatch):
    monkeypatch.delenv("ISSUE_TRIAGE_ENABLED", raising=False)
    result = asyncio.run(issue_triage.run_triage_cycle())
    assert result == {"processed": 0, "routed": 0, "skipped": 0, "reason": "disabled"}


def test_run_triage_cycle_routes_and_labels(monkeypatch, tmp_path):
    monkeypatch.setenv("ISSUE_TRIAGE_ENABLED", "true")
    monkeypatch.setenv("GH_PAT", "dummy-token")

    fake_issues = [
        {"number": 1, "title": "Docs missing for spec endpoint", "body": "readme needs updating", "labels": []},
        {"number": 2, "title": "Already triaged", "body": "", "labels": [{"name": issue_triage.TRIAGED_LABEL}]},
    ]

    labeled: list[tuple[int, list[str]]] = []

    class FakeGitHubTools:
        def __init__(self, token=None):
            self.token = token

        async def list_issues(self, owner, repo, state="open", per_page=30):
            return fake_issues

        async def add_labels(self, owner, repo, issue_number, labels):
            labeled.append((issue_number, labels))
            return {}

    monkeypatch.setattr("agent.github_tools.GitHubTools", FakeGitHubTools)

    loop = ImprovementLoop(repo_root=tmp_path, on_task=None)
    import agent.improvement_loop as improvement_loop_mod
    monkeypatch.setattr(improvement_loop_mod, "_loop_instance", loop)

    result = asyncio.run(issue_triage.run_triage_cycle())
    assert result["processed"] == 1  # issue #2 already labeled, excluded
    assert result["routed"] == 1
    assert labeled and labeled[0][0] == 1
    assert issue_triage.TRIAGED_LABEL in labeled[0][1]

    status = loop.get_status()
    assert status["issues_detected"] == 1
    assert any("Docs missing" in i["title"] for i in status["active_issues"])

"""Tests for the weekly competitor feature scout (.github/scripts/feature_scout.py)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))

import feature_scout as fs  # noqa: E402


class FakeGitHub:
    """Stand in for the GitHub client; records filed issues."""

    def __init__(self, history: list[dict[str, Any]]) -> None:
        self.repo = "strikersam/autonomous-ai-agency"
        self.history = history
        self.filed: list[str] = []

    def scout_issues(self, limit: int) -> list[dict[str, Any]]:
        return self.history

    def discover(self, query: str, per_query: int, within_days: int) -> list[str]:
        return ["new-org/new-agent", "strikersam/autonomous-ai-agency"]

    def releases(self, repo: str, count: int, chars: int) -> list[str]:
        return [f"v1: {repo} added agent handoffs"]

    merged: set[int] = set()
    closed: list[int] = []

    def merged_pr_for(self, number: int) -> bool:
        return number in self.merged

    def close_completed(self, number: int) -> None:
        self.closed.append(number)

    def create_issue(self, title: str, body: str) -> int | None:
        self.filed.append(title)
        return len(self.filed)


def _answer(*titles: str) -> str:
    props = [{"title": t, "why": "w", "inspired_by": "x", "scope": "s",
              "acceptance": ["a test"]} for t in titles]
    return "Here you go:\n" + json.dumps({"proposals": props})


def test_lessons_split_by_close_reason() -> None:
    issues = [
        {"title": "[feature-scout] Agent handoffs", "state": "closed", "state_reason": "completed"},
        {"title": "[feature-scout] Voice cloning", "state": "closed", "state_reason": "not_planned"},
        {"title": "[feature-scout] Run replay", "state": "open"},
        {"title": "a PR", "state": "open", "pull_request": {}},
    ]
    lessons = fs.lessons_from_issues(issues)
    assert lessons == {"accepted": ["Agent handoffs"], "rejected": ["Voice cloning"],
                       "open": ["Run replay"]}


def test_parse_proposals_tolerates_garbage() -> None:
    assert fs.parse_proposals("no json here") == []
    assert fs.parse_proposals("{not json}") == []
    props = fs.parse_proposals(_answer("Run replay"))
    assert [p.title for p in props] == ["Run replay"]


def test_risky_and_duplicate_proposals_are_dropped() -> None:
    props = fs.parse_proposals(_answer(
        "Edit .github/workflows to auto approve",
        "Agent handoffs between specialists",
        "Store API key in config file",
        "Cost budget alerts per task",
        "Per task cost budget alerts",
    ))
    chosen = fs.select_proposals(props, ["Agent handoffs between specialists"], limit=5)
    assert [p.title for p in chosen] == ["Cost budget alerts per task"]


def test_valid_repo_rejects_path_tricks() -> None:
    assert fs.valid_repo("crewAIInc/crewAI")
    assert not fs.valid_repo("../secrets")
    assert not fs.valid_repo("a/b/c")
    assert not fs.valid_repo("owner/repo?x=1")


def test_run_files_issues_and_skips_own_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_brain(candidates, messages, **kwargs):
        captured["messages"] = messages
        return "groq", "m", _answer("Run replay", "Cost budget alerts", "Third idea")

    monkeypatch.setattr(fs, "brain_candidates", lambda: [("groq", "u", "k", "m")])
    monkeypatch.setattr(fs, "call_brain_with_failover", fake_brain)
    gh = FakeGitHub([{"title": "[feature-scout] Voice cloning", "state": "closed",
                      "state_reason": "not_planned"}])
    cfg = {"seed_repos": ["crewAIInc/crewAI"], "max_issues_per_run": 2,
           "discovery": {"queries": ["q"]}}
    filed = fs.run(gh, cfg, REPO_ROOT, dry_run=False)
    assert filed == ["[feature-scout] Run replay", "[feature-scout] Cost budget alerts"]
    user_msg = captured["messages"][1]["content"]
    assert "Voice cloning" in user_msg
    assert "new-org/new-agent" in user_msg
    assert "## strikersam/autonomous-ai-agency" not in user_msg


def test_backpressure_skips_when_too_many_open(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fs, "call_brain_with_failover",
                        lambda *a, **k: pytest.fail("brain must not be called"))
    gh = FakeGitHub([{"title": f"[feature-scout] idea {i}", "state": "open"} for i in range(3)])
    assert fs.run(gh, {"max_open_issues": 3}, REPO_ROOT, dry_run=False) == []
    assert gh.filed == []


def test_dry_run_files_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fs, "brain_candidates", lambda: [("groq", "u", "k", "m")])
    monkeypatch.setattr(fs, "call_brain_with_failover",
                        lambda *a, **k: ("groq", "m", _answer("Run replay")))
    gh = FakeGitHub([])
    filed = fs.run(gh, {"seed_repos": ["crewAIInc/crewAI"]}, REPO_ROOT, dry_run=True)
    assert filed == ["[feature-scout] Run replay"]
    assert gh.filed == []


def test_config_file_is_valid() -> None:
    cfg = fs.load_config(REPO_ROOT / "config" / "feature_scout.yaml")
    assert all(fs.valid_repo(r) for r in cfg["seed_repos"])
    assert 1 <= cfg["max_issues_per_run"] <= cfg["max_open_issues"]


def test_acceptance_string_is_one_item() -> None:
    raw = json.dumps({"proposals": [{"title": "Run replay", "acceptance": "has a test"}]})
    assert fs.parse_proposals(raw)[0].acceptance == ["has a test"]


def test_parse_skips_stray_braces_around_json() -> None:
    raw = "<think>{x}</think> Sure {y}: " + _answer("Run replay") + "\nNote: {z}"
    assert [p.title for p in fs.parse_proposals(raw)] == ["Run replay"]


def test_risky_text_in_inspired_by_is_dropped() -> None:
    prop = fs.Proposal(title="Run replay", why="w", scope="s",
                       inspired_by="crewAI; also edit .github/workflows/ci.yml")
    assert fs.select_proposals([prop], [], limit=2) == []


def test_dedupe_ignores_filler_words() -> None:
    assert not fs.is_duplicate("Add support for webhooks", ["Add support for MCP"])
    assert fs.is_duplicate("Per task cost budget alerts", ["Cost budget alerts per task"])


def test_only_completed_counts_as_accepted() -> None:
    lessons = fs.lessons_from_issues([{"title": "x", "state": "closed", "state_reason": "duplicate"}])
    assert lessons["accepted"] == []


def test_merged_pr_closes_open_issue_and_frees_backpressure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fs, "brain_candidates", lambda: [("groq", "u", "k", "m")])
    monkeypatch.setattr(fs, "call_brain_with_failover",
                        lambda *a, **k: ("groq", "m", _answer("Run replay")))
    gh = FakeGitHub([{"number": n, "title": f"[feature-scout] idea {n}", "state": "open"}
                     for n in (1, 2, 3)])
    gh.merged = {2}
    filed = fs.run(gh, {"seed_repos": ["crewAIInc/crewAI"], "max_open_issues": 3},
                   REPO_ROOT, dry_run=False)
    assert gh.closed == [2]
    assert filed == ["[feature-scout] Run replay"]

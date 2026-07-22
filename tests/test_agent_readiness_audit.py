"""Tests for scripts/agent_readiness_audit.py — the 8-pillar readiness scorer."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "agent_readiness_audit.py"
_spec = importlib.util.spec_from_file_location("agent_readiness_audit", _SCRIPT_PATH)
audit = importlib.util.module_from_spec(_spec)
sys.modules["agent_readiness_audit"] = audit
_spec.loader.exec_module(audit)


def test_grade_boundaries():
    assert audit._grade(95) == "A"
    assert audit._grade(80) == "B"
    assert audit._grade(65) == "C"
    assert audit._grade(50) == "D"
    assert audit._grade(10) == "F"


def test_all_pillars_scored_and_bounded():
    report = audit.run_audit()
    names = {p.name for p in report.pillars}
    assert names == set(audit.PILLARS)
    for pillar in report.pillars:
        assert 0 <= pillar.score <= 100


def test_overall_score_is_mean_of_pillars():
    report = audit.run_audit()
    expected = round(sum(p.score for p in report.pillars) / len(report.pillars))
    assert report.score == expected
    assert report.grade == audit._grade(report.score)


def test_repo_scores_reasonably_high():
    """This repo ships pre-commit config, tests, docs, and the intake/retro
    loops added alongside this scorer — a sane floor catches real regressions
    (e.g. someone deleting CLAUDE.md) without being a brittle exact-match."""
    report = audit.run_audit()
    assert report.score >= 60


def test_as_markdown_includes_all_pillars_and_caveat():
    report = audit.run_audit()
    md = report.as_markdown()
    assert "Agent Readiness Report" in md
    assert "floor, not a ceiling" in md
    for pillar in report.pillars:
        assert pillar.name.replace("_", " ").title() in md


def test_score_testing_flags_missing_empirical_verify(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "loop.py").write_text("# no empirical verify here\n")
    result = audit.score_testing()
    assert any("Add tests" in f for f in result.fixes)


def test_score_documentation_all_missing_scores_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    result = audit.score_documentation()
    assert result.score == 0
    assert len(result.fixes) == 6


def test_main_check_flag_fails_below_threshold(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["agent_readiness_audit.py", "--check", "--threshold", "50"])
    exit_code = audit.main()
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "FAIL" in captured.err

"""tests/test_changelog_parity_guard.py — corruption guard for the changelog gate.

`scripts/check_changelog_parity.py::_blocks` keys sections by version and lets
the LAST ``## [X]`` win, so a duplicate ``## [Unreleased]`` heading (plus any
leftover git-conflict/stash markers below it) used to ride through parity
silently — the recurring drift that forced manual conflict resolutions on
PRs #1071 and #1076. `scan_corruption` now rejects that at the source; these
tests lock the behaviour in and assert the live changelogs are clean.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _ROOT / "scripts" / "check_changelog_parity.py"

_spec = importlib.util.spec_from_file_location("check_changelog_parity", _SCRIPT)
ccp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ccp)  # type: ignore[union-attr]


def test_clean_changelog_has_no_issues():
    clean = "## [Unreleased]\n### Added\n- something\n\n## [1.0.0]\n- initial\n"
    assert ccp.scan_corruption("x", clean) == []


def test_flags_conflict_marker():
    corrupt = "## [Unreleased]\n<<<<<<< HEAD\n- a\n=======\n- b\n>>>>>>> origin/master\n"
    issues = ccp.scan_corruption("x", corrupt)
    assert issues and any("conflict" in i for i in issues)


def test_flags_stash_marker():
    corrupt = "## [Unreleased]\n<<<<<<< Updated upstream\n- a\n=======\n- b\n>>>>>>> Stashed changes\n"
    issues = ccp.scan_corruption("x", corrupt)
    assert issues and any("conflict" in i for i in issues)


def test_flags_duplicate_version_heading():
    corrupt = "## [Unreleased]\n- a\n\n## [Unreleased]\n- b\n"
    issues = ccp.scan_corruption("x", corrupt)
    assert issues and any("duplicate version heading" in i for i in issues)


def test_setext_heading_underline_is_not_flagged():
    """A 7-equals line under a title (Markdown setext H1) must not false-positive."""
    ok = "Title\n=======\n\n## [Unreleased]\n- a\n"
    assert ccp.scan_corruption("x", ok) == []


def test_live_changelogs_are_clean():
    for name in ("CHANGELOG.md", "docs/changelog.md"):
        text = (_ROOT / name).read_text(encoding="utf-8")
        assert ccp.scan_corruption(name, text) == [], (
            f"{name} has changelog corruption: {ccp.scan_corruption(name, text)}"
        )

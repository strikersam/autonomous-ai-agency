"""Tests for ``.github/workflows/changelog-check.yml``'s PR-title exemption.

The gate skips the changelog requirement for chore/docs/style/ci/test/revert/
build-only PRs, detected by a shell ``case`` match on the PR title. Only the
``chore`` entry had a scoped-prefix variant (``chore(x):`` as well as
``chore:``), so a PR titled e.g. ``docs(state): ...`` fell through to the
changelog requirement the exemption exists to skip (observed on PR #1476,
which is exactly that kind of PR). The fix adds the same scoped variant to
every other prefix, using a literal ``(...)`` so a title like
``docstring: ...`` or ``testing: ...`` is not swept in by accident.

These tests run the *actual* shell ``case`` pattern extracted from the
workflow file, not a reimplementation of it, so they fail if the pattern
regresses.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github/workflows/changelog-check.yml"

EXEMPT_PREFIXES = ["chore", "docs", "style", "ci", "test", "revert", "build"]


@pytest.fixture(scope="module")
def case_patterns() -> str:
    """Extract the exact `case "$PR_TITLE" in <patterns>)` clause."""
    text = WORKFLOW.read_text(encoding="utf-8")
    m = re.search(r'case "\$PR_TITLE" in\s*\n\s*(.+?)\)\n', text)
    assert m, "could not find the PR_TITLE case statement in changelog-check.yml"
    return m.group(1)


def _is_exempt(patterns: str, title: str) -> bool:
    script = f'case "$1" in\n{patterns}) exit 0 ;;\n*) exit 1 ;;\nesac\n'
    # nosec - constant argv, list form (no shell); title is a $1 arg, never
    # interpolated into the script text. Bare `nosec` rather than the
    # `nosec B603,B607` form used elsewhere in this repo (e.g. agent/loop.py):
    # bandit 1.9.4's NOSEC_COMMENT_TESTS regex only registers the *last* code
    # in a comma-separated nosec list (its `finditer` walks one greedy match,
    # and the capturing group inside a `+`-quantified group retains only its
    # final iteration) — `# nosec B603,B607` suppresses B607 but leaves B603
    # firing, verified directly against agent/loop.py's existing uses.
    result = subprocess.run(["bash", "-c", script, "bash", title])  # nosec
    return result.returncode == 0


class TestScopedPrefixesAreExempt:
    """Both `prefix:` and `prefix(scope):` must skip the changelog gate."""

    @pytest.mark.parametrize("prefix", EXEMPT_PREFIXES)
    def test_bare_prefix_is_exempt(self, case_patterns: str, prefix: str) -> None:
        assert _is_exempt(case_patterns, f"{prefix}: do a thing")

    @pytest.mark.parametrize("prefix", EXEMPT_PREFIXES)
    def test_scoped_prefix_is_exempt(self, case_patterns: str, prefix: str) -> None:
        assert _is_exempt(case_patterns, f"{prefix}(scope): do a thing")

    def test_the_pr_that_found_this_is_exempt(self, case_patterns: str) -> None:
        assert _is_exempt(
            case_patterns,
            "docs(state): record daily automation 2026-09-11 (PR #1474 rescue)",
        )


class TestUnrelatedPrefixesAreNotExempt:
    """The scoped match must require a literal `(...)`, not a bare wildcard,
    or words that merely start with an exempt prefix become exempt too."""

    @pytest.mark.parametrize(
        "title",
        [
            "docstring: not actually a docs-only PR",
            "testing: not actually a test-only PR",
            "stylesheet: not actually a style-only PR",
            "circus: not actually a ci-only PR",
            "buildup: not actually a build-only PR",
            "reverting: not actually a revert-only PR",
            "choreography: not actually a chore-only PR",
            "feat: add a new feature",
            "fix(auth): patch a real bug",
        ],
    )
    def test_lookalike_titles_still_require_a_changelog_entry(
        self, case_patterns: str, title: str
    ) -> None:
        assert not _is_exempt(case_patterns, title)

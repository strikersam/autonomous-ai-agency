"""Tests for ``scripts/classify_dependabot_update.py``.

Every case below is taken verbatim from one of the 14 Dependabot PRs that sat
stranded (#1333-#1346), because the classifier exists to make exactly those
merge — or not — correctly and unattended.

The rule worth guarding: a verdict the classifier could not actually reach is
``unknown``, and ``unknown`` is not auto-mergeable. Guessing permissively here
means merging a breaking dependency upgrade with nobody watching.
"""
from __future__ import annotations

import pytest

from scripts.classify_dependabot_update import (
    GROUP,
    MAJOR,
    MINOR,
    PATCH,
    UNKNOWN,
    classify,
    compare_versions,
    is_auto_mergeable,
    parse_version,
)


def _commit(compare_url: str) -> str:
    return (
        "chore(deps): update a requirement\n\n"
        "Updates the requirements on [pkg](https://example.com) to permit the latest version.\n"
        "- [Release notes](https://github.com/o/r/releases)\n"
        f"- [Commits]({compare_url})\n\n"
        "---\nupdated-dependencies:\n- dependency-name: pkg\n...\n"
    )


class TestRefParsing:
    @pytest.mark.parametrize("ref,expected", [
        ("v0.122.0", (0, 122, 0)),          # anthropic (#1336)
        ("1.43.71", (1, 43, 71)),           # boto3 (#1342) — bare, no prefix
        ("lxml-6.1.1", (6, 1, 1)),          # lxml (#1341) — name-dash prefix
        ("livekit-agents@1.7.0", (1, 7, 0)),  # livekit (#1344) — name@version
        ("v2.37.0", (2, 37, 0)),            # fakeredis (#1343)
    ])
    def test_extracts_version_from_every_tag_style_dependabot_uses(
        self, ref: str, expected: tuple[int, ...]
    ) -> None:
        assert parse_version(ref) == expected

    def test_returns_none_when_there_is_no_version(self) -> None:
        assert parse_version("main") is None


class TestSemverComparison:
    @pytest.mark.parametrize("old,new,expected", [
        ((1, 43, 71), (1, 43, 77), PATCH),
        ((6, 1, 1), (6, 1, 2), PATCH),
        ((1, 6, 10), (1, 7, 0), MINOR),
        ((0, 122, 0), (1, 0, 0), MAJOR),
        ((2, 0, 0), (3, 0, 0), MAJOR),
    ])
    def test_classifies_by_changed_component(self, old, new, expected) -> None:
        assert compare_versions(old, new) == expected

    def test_zero_x_minor_bump_counts_as_major(self) -> None:
        """Below 1.0.0 a minor bump is allowed to break, so it needs a human."""
        assert compare_versions((0, 16, 0), (0, 17, 0)) == MAJOR

    def test_zero_x_patch_bump_is_still_a_patch(self) -> None:
        """curl-cffi (#1335) and graphifyy (#1345) must not be over-flagged."""
        assert compare_versions((0, 16, 0), (0, 16, 1)) == PATCH
        assert compare_versions((0, 9, 45), (0, 9, 48)) == PATCH

    def test_missing_components_are_treated_as_zero(self) -> None:
        assert compare_versions((3, 17), (3, 19)) == MINOR


class TestRealStrandedPullRequests:
    @pytest.mark.parametrize("branch,compare_url,expected", [
        ("dependabot/pip/anthropic-gte-1.0.0",
         "https://github.com/anthropics/anthropic-sdk-python/compare/v0.122.0...v1.0.0",
         MAJOR),
        ("dependabot/pip/graphifyy-gte-0.9.48",
         "https://github.com/Graphify-Labs/graphify/compare/v0.9.45...v0.9.48",
         PATCH),
        ("dependabot/pip/livekit-agents-gte-1.7.0-and-lt-2",
         "https://github.com/livekit/agents/compare/livekit-agents@1.6.10...livekit-agents@1.7.0",
         MINOR),
        ("dependabot/pip/boto3-gte-1.43.77",
         "https://github.com/boto/boto3/compare/1.43.71...1.43.77",
         PATCH),
        ("dependabot/pip/lxml-gte-6.1.2",
         "https://github.com/lxml/lxml/compare/lxml-6.1.1...lxml-6.1.2",
         PATCH),
        ("dependabot/pip/fakeredis-gte-2.37.1",
         "https://github.com/cunla/fakeredis-py/compare/v2.37.0...v2.37.1",
         PATCH),
        ("dependabot/pip/curl-cffi-gte-0.16.1",
         "https://github.com/lexiforest/curl_cffi/compare/v0.16.0...v0.16.1",
         PATCH),
    ])
    def test_classifies_each_single_dependency_pr(
        self, branch: str, compare_url: str, expected: str
    ) -> None:
        assert classify(branch, _commit(compare_url)) == expected

    @pytest.mark.parametrize("branch", [
        "dependabot/npm_and_yarn/frontend/all-patches-e7322276ff",          # #1334
        "dependabot/npm_and_yarn/webui/frontend/all-patches-9580d84d75",    # #1333
    ])
    def test_grouped_prs_are_minor_or_patch_by_configuration(self, branch: str) -> None:
        """`.github/dependabot.yml` declares these groups minor/patch-only."""
        assert classify(branch, "bump the all-patches group with 4 updates") == GROUP

    def test_reportlab_has_no_compare_link_so_stays_unknown(self) -> None:
        """#1346: reportlab.com is not GitHub, so Dependabot writes no compare link.

        The honest answer is "I could not tell", and an untellable bump is not
        one to merge unattended.
        """
        message = (
            "chore(deps): update reportlab requirement from <6,>=5.0.0 to >=5.0.1,<6\n\n"
            "Updates the requirements on [reportlab](https://www.reportlab.com/) "
            "to permit the latest version.\n\n---\nupdated-dependencies:\n"
            "- dependency-name: reportlab\n  dependency-version: 5.0.1\n...\n"
        )
        assert classify("dependabot/pip/reportlab-gte-5.0.1-and-lt-6", message) == UNKNOWN


class TestAutoMergeGate:
    @pytest.mark.parametrize("update_type", [GROUP, MINOR, PATCH])
    def test_reached_and_safe_verdicts_may_merge(self, update_type: str) -> None:
        assert is_auto_mergeable(update_type) is True

    @pytest.mark.parametrize("update_type", [MAJOR, UNKNOWN])
    def test_breaking_and_undetermined_verdicts_may_not(self, update_type: str) -> None:
        assert is_auto_mergeable(update_type) is False


class TestWorkflowWiring:
    def test_sweep_uses_this_script(self) -> None:
        from pathlib import Path

        wf = (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/dependabot-auto-merge.yml"
        )
        assert "classify_dependabot_update.py" in wf.read_text(encoding="utf-8")

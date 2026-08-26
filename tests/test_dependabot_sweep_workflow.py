"""Guards on ``.github/workflows/dependabot-auto-merge.yml``.

Three separate gates have stranded this repo's Dependabot PRs, and each one
looked like success from the outside. The workflow is shell inside YAML, so
nothing else can catch a regression in it:

1. ``secrets.GH_PAT`` is always empty on a ``dependabot[bot]``-triggered event
   (GitHub withholds repository secrets from that actor), so the event-driven
   job died with an empty ``GH_TOKEN`` on every PR it ever saw.
2. Auto-merge was armed on PRs that were ``BEHIND`` their base. Branch
   protection refuses an out-of-date branch, so all 14 sat armed and idle.
3. Updating those branches with ``GITHUB_TOKEN`` produced merge commits
   attributed to ``github-actions[bot]``. GitHub will not run workflows for
   those automatically: all 10 resulting CI runs came back ``action_required``,
   which *replaced* the green checks the PRs already had with checks that need
   a human click.

The tokens therefore differ per job on purpose, and the asymmetry is the whole
fix — hence the tests below.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/dependabot-auto-merge.yml"
)


@pytest.fixture(scope="module")
def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def workflow(workflow_text: str) -> dict:
    return yaml.safe_load(workflow_text)


def _job_text(workflow: dict, job: str) -> str:
    """Flatten one job back to text so token/flag use can be asserted on it."""
    return yaml.safe_dump(workflow["jobs"][job])


class TestTokenChoice:
    def test_event_driven_job_never_uses_gh_pat(self, workflow: dict) -> None:
        """Root cause 1: GH_PAT is empty on dependabot-triggered events."""
        assert "GH_PAT" not in _job_text(workflow, "auto-merge")

    def test_sweep_prefers_gh_pat(self, workflow: dict) -> None:
        """Root cause 3: a GITHUB_TOKEN merge commit leaves CI action_required.

        The sweep runs on schedule/dispatch, never on a dependabot event, so
        repository secrets *are* available to it — unlike the job above.
        """
        assert "secrets.GH_PAT" in _job_text(workflow, "sweep-stranded")

    def test_sweep_falls_back_when_gh_pat_is_absent(self, workflow: dict) -> None:
        assert "secrets.GITHUB_TOKEN" in _job_text(workflow, "sweep-stranded")


class TestStaleBranchHandling:
    def test_sweep_updates_branches_that_are_behind(self, workflow: dict) -> None:
        """Root cause 2: auto-merge alone never lands an out-of-date branch."""
        text = _job_text(workflow, "sweep-stranded")
        assert "BEHIND" in text
        assert "gh pr update-branch" in text

    def test_unknown_mergeability_is_retried_not_skipped(self, workflow: dict) -> None:
        """GitHub computes mergeability lazily and answers UNKNOWN meanwhile.

        Four of the 14 PRs (#1334 #1335 #1336 #1346) answered UNKNOWN on the
        first poll and were skipped in silence — the same class of quiet no-op
        the sweep exists to remove.
        """
        text = _job_text(workflow, "sweep-stranded")
        assert "UNKNOWN" in text, "the sweep must handle an UNKNOWN merge state"
        assert "sleep" in text, "UNKNOWN must be re-polled, not skipped"


class TestMajorBumpsStayWithHumans:
    """Rule 40: a dependency upgrade with a breaking change needs a human.

    The event-driven job can classify (it has the PR payload fetch-metadata
    needs); the sweep cannot. So the sweep must not arm auto-merge on a PR the
    other job has already flagged, and the two halves are coupled by a literal
    string in a comment body — exactly the kind of coupling that rots silently.
    """

    MARKER = "Major version bump"

    def test_event_driven_job_flags_majors_rather_than_merging(
        self, workflow: dict
    ) -> None:
        text = _job_text(workflow, "auto-merge")
        assert "version-update:semver-major" in text
        assert self.MARKER in text

    def test_sweep_recognises_the_marker_the_other_job_writes(
        self, workflow: dict
    ) -> None:
        assert self.MARKER in _job_text(workflow, "sweep-stranded")


class TestSweepStillCannotForceAnything:
    def test_sweep_never_uses_admin_merge(self, workflow: dict) -> None:
        """--admin bypasses required checks. --auto waits for them."""
        text = _job_text(workflow, "sweep-stranded")
        assert "--admin" not in text
        assert "--auto" in text

    def test_sweep_only_runs_off_pull_request_events(self, workflow: dict) -> None:
        assert workflow["jobs"]["sweep-stranded"]["if"].strip() == (
            "github.event_name != 'pull_request'"
        )

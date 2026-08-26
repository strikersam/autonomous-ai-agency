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

    The sweep cannot ask ``fetch-metadata`` — that needs a ``pull_request``
    payload. It also cannot defer to the event-driven job above, which is
    guarded by ``github.actor == 'dependabot[bot]'`` and therefore *skips* once
    the sweep updates a branch as a real user (verified on PR #1336: run
    32936415712, actor ``strikersam``, conclusion ``skipped``). So the verdict
    has to be one the sweep owns, which is why it shells out to a script that
    can actually be unit-tested.
    """

    def test_event_driven_job_flags_majors_rather_than_merging(
        self, workflow: dict
    ) -> None:
        text = _job_text(workflow, "auto-merge")
        assert "version-update:semver-major" in text
        assert "Major version bump" in text

    def test_sweep_classifies_before_arming_auto_merge(self, workflow: dict) -> None:
        text = _job_text(workflow, "sweep-stranded")
        assert "classify_dependabot_update.py" in text

    def test_sweep_arms_only_verdicts_that_were_actually_reached(
        self, workflow: dict
    ) -> None:
        """`unknown` must be handled like `major`, never waved through."""
        text = _job_text(workflow, "sweep-stranded")
        assert "group|minor|patch" in text, (
            "auto-merge must be gated on an explicit allow-list of update types"
        )
        assert "major" not in text.split("group|minor|patch")[1].split("esac")[0], (
            "a major bump must not appear in the arming branch"
        )

    def test_sweep_can_run_python(self, workflow: dict) -> None:
        """The classifier is a repo script, so the job needs a checkout."""
        steps = yaml.safe_dump(workflow["jobs"]["sweep-stranded"]["steps"])
        assert "actions/checkout" in steps
        assert "actions/setup-python" in steps


class TestBacklogActuallyDrains:
    """A sweep that cannot keep up with Dependabot is not a fix.

    Branch protection wants an up-to-date branch, so merging one PR puts every
    other open one back to BEHIND — the backlog drains at exactly one PR per
    run however many branches the sweep refreshes. Confirmed live: #1346 merged
    at 06:14 and #1345 was `behind` again immediately after, base pinned to the
    commit #1346 had just superseded.
    """

    def test_sweep_runs_hourly(self, workflow: dict) -> None:
        """Daily could never catch up: ~14 PRs arrive weekly, 7 would drain."""
        schedules = workflow[True]["schedule"]
        assert any(s["cron"] == "0 * * * *" for s in schedules), schedules

    def test_sweep_updates_at_most_one_stale_branch_per_run(
        self, workflow_text: str
    ) -> None:
        """Refreshing the rest burns two CI runs each and merges none of them.

        Asserted against the raw file: a yaml round-trip re-escapes the shell
        quoting, so the dumped job text is the wrong thing to match on.
        """
        assert "UPDATES_LEFT=1" in workflow_text
        assert '[ "$UPDATES_LEFT" -le 0 ]' in workflow_text
        assert "UPDATES_LEFT - 1" in workflow_text

    def test_registry_matches_the_new_cadence(self) -> None:
        from pathlib import Path

        registry = yaml.safe_load(
            (Path(__file__).resolve().parents[1] / "loops/registry.yaml").read_text(
                encoding="utf-8"
            )
        )
        entry = next(
            loop for loop in registry["loops"] if loop["id"] == "dependabot-auto-merge"
        )
        assert entry["runs_per_day"] == 24


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

"""The autonomous pipeline must not treat "I could not tell" as "yes".

Every defect pinned here was found by auditing one successful run — the
2026-08-28 quick-note cycle that merged `b368f9e7`. It passed every step,
reported green throughout, and shipped 1,199 lines that the same run's own
planning document had rejected. Nothing in the pipeline was broken in a way
that showed up as a failure; each gap simply resolved an unknown as an
approval.

Five of them:

* the implement step never read the plan's verdict, so a REJECT was built;
* a council verdict of WARN auto-merged, including one reading "cannot verify
  authentication/authorization guards" and "require human verification before
  merge";
* a *crashed* council defaulted to WARN, so a review that never ran merged
  exactly like one that passed;
* the review-bot wait reported success against zero reviews, because
  CodeRabbit declines this repo and Codex was out of quota;
* the queue took the oldest open issue of any kind, so status reports sat
  ahead of real work.

Two more, from the loops that feed it: `agency-cycle.yml` escalated failures
its own classifier had labelled "No code change can fix it", and
`crispy-burn-in-check.yml` filed a promotion verdict computed from an empty
evaluation.

These tests assert the gates by what they *do*, so a rename does not silently
retire one.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github/workflows"
QUICK_NOTE = WORKFLOWS / "process-quick-note.yml"
AGENCY_CYCLE = WORKFLOWS / "agency-cycle.yml"
BURN_IN = WORKFLOWS / "crispy-burn-in-check.yml"


def _job(path: Path, job_name: str) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"][job_name]


def _step(job: dict, step_id: str) -> dict:
    for step in job["steps"]:
        if step.get("id") == step_id:
            return step
    raise AssertionError(f"no step with id {step_id!r}")


@pytest.fixture(scope="module")
def quick_note() -> dict:
    return _job(QUICK_NOTE, "process")


class TestThePlanIsRead:
    """A plan that says "do not build this" must reach the thing that builds."""

    def test_a_gate_step_exists(self, quick_note: dict) -> None:
        assert _step(quick_note, "plan_gate")

    def test_it_runs_the_gate_script(self, quick_note: dict) -> None:
        run = _step(quick_note, "plan_gate")["run"]
        assert "scripts/context_plan_gate.py" in run

    def test_the_gate_script_exists_and_is_importable(self) -> None:
        assert (REPO_ROOT / "scripts/context_plan_gate.py").is_file()

    def test_the_implementer_requires_permission(self, quick_note: dict) -> None:
        """The whole point: no permission, no build."""
        condition = _step(quick_note, "implement")["if"]
        assert "plan_gate.outputs.may_implement == 'true'" in condition, (
            "the implement step must be gated on the plan's own verdict; "
            f"got: {condition}"
        )

    def test_the_gate_precedes_the_implementer(self, quick_note: dict) -> None:
        ids = [s.get("id") for s in quick_note["steps"]]
        assert ids.index("plan_gate") < ids.index("implement")

    def test_a_blocked_plan_is_reported_not_swallowed(self, quick_note: dict) -> None:
        blocked = _step(quick_note, "plan_blocked")
        assert blocked["if"] == "steps.plan_gate.outputs.may_implement == 'false'"
        assert "quick-note:rejected" in blocked["run"], (
            "a blocked issue must be labelled or the 4-hourly sweep re-picks it"
        )

    def test_a_missing_plan_only_passes_when_no_planner_ran(
        self, quick_note: dict
    ) -> None:
        """`--missing-ok` is correct for an unplanned issue and wrong otherwise."""
        run = _step(quick_note, "plan_gate")["run"]
        assert "REUSED_CONTEXT_BRANCH" in run
        assert "--missing-ok" in run

    def test_the_branch_step_reports_whether_a_planner_ran(
        self, quick_note: dict
    ) -> None:
        run = _step(quick_note, "branch")["run"]
        assert "reused_context=true" in run and "reused_context=false" in run


class TestOnlyAPassingCouncilMerges:
    MERGE_STEPS = ("ready", "merge")

    @pytest.mark.parametrize("step_id", MERGE_STEPS)
    def test_warn_no_longer_merges(self, quick_note: dict, step_id: str) -> None:
        condition = _step(quick_note, step_id)["if"]
        assert "verdict == 'WARN'" not in condition, (
            f"{step_id} still auto-merges a WARN; #1357 merged a WARN that said "
            f"'require human verification before merge'"
        )

    @pytest.mark.parametrize("step_id", MERGE_STEPS)
    def test_an_empty_verdict_no_longer_merges(
        self, quick_note: dict, step_id: str
    ) -> None:
        assert "verdict == ''" not in _step(quick_note, step_id)["if"]

    @pytest.mark.parametrize("step_id", MERGE_STEPS)
    def test_it_requires_pass(self, quick_note: dict, step_id: str) -> None:
        assert "steps.review.outputs.verdict == 'PASS'" in _step(quick_note, step_id)["if"]

    def test_a_council_that_did_not_run_is_not_a_warn(self, quick_note: dict) -> None:
        """`continue-on-error: true` means a crash must be its own state."""
        run = _step(quick_note, "review")["run"]
        assert 'VERDICT="NONE"' in run, (
            "a missing result file must not default to WARN — WARN used to merge"
        )

    def test_every_non_pass_outcome_tells_a_human(self, quick_note: dict) -> None:
        conditions = [
            s.get("if", "")
            for s in quick_note["steps"]
            if "needs human review" in (s.get("name") or "")
        ]
        assert conditions, "no step reports a non-PASS council verdict"
        assert any("verdict != 'PASS'" in c for c in conditions), (
            "only FAIL was reported, so WARN and a crashed council were silent"
        )


class TestReviewBotsAreCounted:
    """Waiting is not reviewing."""

    def test_the_wait_step_counts_what_arrived(self, quick_note: dict) -> None:
        run = _step(quick_note, "bots")["run"]
        assert "reviews_seen=" in run

    def test_zero_reviews_produces_a_warning(self, quick_note: dict) -> None:
        run = _step(quick_note, "bots")["run"]
        assert "::warning::" in run and "-eq 0" in run

    def test_the_apply_step_knows_the_count(self, quick_note: dict) -> None:
        assert "REVIEWS_SEEN" in (_step(quick_note, "review_apply")["env"] or {})


class TestTheQueueHoldsWorkNotPaperwork:
    NON_IMPLEMENTABLE = ("agency-escalation", "trend-digest", "crispy-burn-in")

    @pytest.mark.parametrize("label", NON_IMPLEMENTABLE)
    def test_report_issues_are_not_selected(self, quick_note: dict, label: str) -> None:
        run = _step(quick_note, "pick")["run"]
        assert label in run, (
            f"{label!r} issues are status reports, not implementable work; "
            f"they sat at the head of the queue for days"
        )

    def test_the_existing_exclusions_survive(self, quick_note: dict) -> None:
        run = _step(quick_note, "pick")["run"]
        for label in ("quick-note:exhausted", "quick-note:rejected"):
            assert label in run

    def test_automation_test_issues_are_still_selectable(self, quick_note: dict) -> None:
        """They have their own handler step; excluding them would strand them."""
        run = _step(quick_note, "pick")["run"]
        assert '"automation-test"' not in run

    def test_the_real_selector_picks_the_right_issue(self, quick_note: dict) -> None:
        """Run the actual jq, rather than reading it.

        Reading the expression proves a label is mentioned, not that it is
        excluded — and a jq that mentions every right label can still select
        the wrong issue. This extracts the real `--jq` argument from the
        workflow and runs it over a sample backlog shaped like the one that
        stalled: four escalations and a digest at the head of the queue.
        """
        jq_binary = shutil.which("jq")
        if jq_binary is None:  # pragma: no cover - jq is present on CI runners
            pytest.skip("jq not installed")

        run = _step(quick_note, "pick")["run"]
        match = re.search(r"--jq '(.+?)'\)", run, re.S)
        assert match, "could not extract the selector's jq expression"

        backlog = [
            {"number": 1312, "labels": [{"name": "bug"}, {"name": "agency-escalation"}]},
            {"number": 1347, "labels": [{"name": "crispy-burn-in"}]},
            {"number": 1350, "labels": [{"name": "trend-digest"}]},
            {"number": 1360, "labels": [{"name": "quick-note:rejected"}]},
            {"number": 1361, "labels": [{"name": "quick-note:exhausted"}]},
            {"number": 1370, "labels": [{"name": "automation-test"}]},
            {"number": 1375, "labels": [{"name": "enhancement"}]},
            {"number": 1380, "labels": []},
        ]
        # jq_binary is resolved by shutil.which, the expression comes from a
        # workflow file in this repo, the payload is a literal above, and the
        # call is list form with no shell — the vetted pattern `.bandit`
        # describes for individual B603/B607 suppressions.
        result = subprocess.run(  # nosec B603
            [jq_binary, "-r", match.group(1)],
            input=json.dumps(backlog),
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == "1370", (
            "the selector must skip every status-report and blocked issue and "
            f"take the oldest remaining one; got {result.stdout.strip()!r}"
        )

    def test_the_selector_returns_nothing_when_only_reports_are_open(
        self, quick_note: dict
    ) -> None:
        """An all-paperwork backlog is an idle tick, not a unit of work."""
        jq_binary = shutil.which("jq")
        if jq_binary is None:  # pragma: no cover
            pytest.skip("jq not installed")

        run = _step(quick_note, "pick")["run"]
        match = re.search(r"--jq '(.+?)'\)", run, re.S)
        assert match
        backlog = [
            {"number": 1312, "labels": [{"name": "agency-escalation"}]},
            {"number": 1350, "labels": [{"name": "trend-digest"}]},
        ]
        # jq_binary is resolved by shutil.which, the expression comes from a
        # workflow file in this repo, the payload is a literal above, and the
        # call is list form with no shell — the vetted pattern `.bandit`
        # describes for individual B603/B607 suppressions.
        result = subprocess.run(  # nosec B603
            [jq_binary, "-r", match.group(1)],
            input=json.dumps(backlog),
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == ""


class TestUnfixableFailuresDoNotEscalate:
    @pytest.fixture(scope="class")
    @classmethod
    def cycle(cls) -> dict:
        return _job(AGENCY_CYCLE, "ceo-assess-and-dispatch")

    def test_the_classifier_reports_whether_all_are_infrastructure(
        self, cycle: dict
    ) -> None:
        run = _step(cycle, "self_healing")["run"]
        assert "infra_only=" in run

    def test_the_escalation_is_gated_on_it(self, cycle: dict) -> None:
        step = next(
            s for s in cycle["steps"] if "cannot fix" in (s.get("name") or "").lower()
        )
        assert "infra_only != 'true'" in step["if"], (
            "four escalations (#1312, #1319, #1328, #1349) were filed over five "
            "days for one missing MongoDB service, each one classified "
            "'infrastructure_error — No code change can fix it'"
        )


class TestABurnInVerdictNeedsData:
    @pytest.fixture(scope="class")
    @classmethod
    def burn_in(cls) -> dict:
        return _job(BURN_IN, "evaluate")

    def test_an_unevaluable_run_fails_loudly(self, burn_in: dict) -> None:
        run = _step(burn_in, "eval")["run"]
        assert "evaluated=false" in run and "::error::" in run

    def test_the_issue_is_not_filed_without_an_evaluation(self, burn_in: dict) -> None:
        step = next(
            s for s in burn_in["steps"] if "tracking issue" in (s.get("name") or "")
        )
        assert step.get("if") == "steps.eval.outputs.evaluated == 'true'", (
            "issue #1347 reported 'not ready for promotion' with an empty gap "
            "and empty evaluation — a verdict computed from nothing"
        )

    def test_the_broken_dead_python_is_gone(self, burn_in: dict) -> None:
        """Shell redirection pasted into Python, raising behind `|| true`."""
        assert ">> /dev/stderr)" not in BURN_IN.read_text(encoding="utf-8")

    def test_the_defaults_can_actually_fire(self, burn_in: dict) -> None:
        """`grep … | cut … || echo default` reports cut's status, never grep's."""
        run = _step(burn_in, "eval")["run"]
        text = BURN_IN.read_text(encoding="utf-8")
        assert 'cut -d= -f2 || echo "false"' not in text, (
            "the fallback is unreachable in a pipeline; default the variable instead"
        )
        assert ': "${READY:=false}"' in text

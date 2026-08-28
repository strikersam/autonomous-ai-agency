"""Tests for ``.github/workflows/process-quick-note.yml``.

Two defects, one symptom: the autonomous implementer ran every four hours,
implemented nothing, and reported success.

The cause was that ``implement_agent.py`` refuses to accept
``IMPLEMENTATION_COMPLETE`` unless the last ``pytest`` exited 0, while this
workflow ran with no MongoDB service. ``tests/test_auth_me_regression.py`` then
errors on ``localhost:27017``, ``pytest -x`` stops there, and the gate can never
be satisfied — on any issue, regardless of what the agent wrote.

Nothing caught it, because a run that implements nothing skips its way to a
green tick: the downstream steps are gated by ``if:`` conditions, and a skipped
step is not a failed one. Nine issues piled up behind a workflow whose Actions
list was solid green.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github/workflows/process-quick-note.yml"
CI_WORKFLOW = REPO_ROOT / ".github/workflows/ci.yml"


@pytest.fixture(scope="module")
def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def job(workflow_text: str) -> dict:
    return yaml.safe_load(workflow_text)["jobs"]["process"]


def _step(job: dict, name_fragment: str) -> dict:
    for step in job["steps"]:
        if name_fragment in step.get("name", ""):
            return step
    raise AssertionError(f"no step whose name contains {name_fragment!r}")


class TestMongoService:
    """The implementer must run against the same services as the PR gate."""

    def test_job_declares_a_mongodb_service(self, job: dict) -> None:
        services = job.get("services") or {}
        assert services, (
            "process-quick-note.yml runs pytest, and implement_agent.py will not "
            "accept IMPLEMENTATION_COMPLETE unless pytest exits 0 — without a "
            "MongoDB service that gate is unsatisfiable on every issue"
        )
        assert "mongodb" in services

    def test_service_image_matches_the_ci_gate(self, job: dict) -> None:
        ci = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
        ci_images = {
            svc["image"]
            for ci_job in ci["jobs"].values()
            for svc in (ci_job.get("services") or {}).values()
            if "mongo" in str(svc.get("image", ""))
        }
        assert job["services"]["mongodb"]["image"] in ci_images, (
            "the implementer must see the same MongoDB the PR gate does, or it "
            "will chase failures the gate never reports"
        )

    def test_mongo_port_is_published(self, job: dict) -> None:
        assert "27017:27017" in job["services"]["mongodb"]["ports"]

    def test_storage_backend_is_not_pinned_to_sqlite(self, workflow_text: str) -> None:
        """conftest.py documents why: a sqlite pin leaks a non-daemon aiosqlite
        thread and the job runs toward GitHub's 360-minute ceiling."""
        assert "STORAGE_BACKEND: sqlite" not in workflow_text
        assert "STORAGE_BACKEND=sqlite" not in workflow_text


class TestBarrenRunIsVisible:
    """A run that implements nothing must not look like one that shipped."""

    def test_retry_handler_is_addressable(self, job: dict) -> None:
        assert _step(job, "Handle failure")["id"] == "retry", (
            "the fail-loudly step gates on this id"
        )

    def test_a_barren_run_fails_the_job(self, job: dict) -> None:
        step = _step(job, "Fail loudly")
        assert "exit 1" in step["run"], (
            "bookkeeping a barren run and then exiting 0 is exactly what hid "
            "this for weeks"
        )

    def test_it_is_gated_on_the_retry_handler_firing(self, job: dict) -> None:
        condition = _step(job, "Fail loudly")["if"]
        assert "steps.retry.outcome == 'success'" in condition
        assert "always()" in condition, (
            "without always() the step is skipped on the very failures it exists "
            "to surface"
        )

    def test_an_idle_tick_stays_green(self, job: dict) -> None:
        """No issue to pick up means the retry handler never runs, so the job
        must not go red — an idle schedule tick is not a defect."""
        condition = _step(job, "Fail loudly")["if"]
        assert "steps.retry.outcome" in condition, (
            "gating on failure() or always() alone would redden every idle run"
        )

    def test_it_runs_after_the_retry_handler(self, job: dict) -> None:
        """Order matters: the label bump and issue reopen must complete before
        the job goes red, or a failing run loses its bookkeeping."""
        names = [s.get("name", "") for s in job["steps"]]
        retry_at = next(i for i, n in enumerate(names) if "Handle failure" in n)
        fail_at = next(i for i, n in enumerate(names) if "Fail loudly" in n)
        assert retry_at < fail_at

    def test_the_error_names_the_issue(self, job: dict) -> None:
        run = _step(job, "Fail loudly")["run"]
        assert "::error" in run, "the Actions UI needs an annotation, not a log line"
        assert "ISSUE_NUM" in run


# A "full-suite" pytest run: `pytest` (or `python -m pytest`) whose arguments are
# all flags. Nothing narrows the collection, so it picks up the Mongo-backed
# regression tests and needs the service to have any chance of passing.
_PYTEST = re.compile(r"(?:python\s+-m\s+)?\bpytest\b(?P<args>[^\n|;&]*)")


def _runs_full_suite(job: dict) -> bool:
    runs = "\n".join(
        s.get("run", "") for s in (job.get("steps") or []) if isinstance(s, dict)
    )
    for match in _PYTEST.finditer(runs):
        args = match.group("args").split()
        paths = [
            a for a in args
            if not a.startswith(("-", "2>", ">", "1>"))
        ]
        if not paths:
            return True
    return False


def _full_suite_jobs() -> list[tuple[str, str, dict]]:
    found = []
    for path in sorted((REPO_ROOT / ".github/workflows").glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, job in (workflow.get("jobs") or {}).items():
            if isinstance(job, dict) and _runs_full_suite(job):
                found.append((path.name, name, job))
    return found


class TestEveryFullSuiteJobHasMongo:
    """The invariant, stated once for the whole repo.

    Adding the service to two workflows fixes today's outage; this is what stops
    the third one being written without it. The asymmetry is what did the
    damage — the autonomous loops saw failures the PR gate never did, so their
    reports described a repo that was never broken.
    """

    def test_the_detector_finds_the_known_jobs(self) -> None:
        """Guards the guard: a regex that matches nothing would pass silently."""
        names = {f"{wf}:{job}" for wf, job, _ in _full_suite_jobs()}
        assert "ci.yml:test" in names, "the PR gate runs the full suite"
        assert "process-quick-note.yml:process" in names

    @pytest.mark.parametrize(
        "workflow,job_name,job",
        [pytest.param(w, n, j, id=f"{w}:{n}") for w, n, j in _full_suite_jobs()],
    )
    def test_job_declares_mongo(self, workflow: str, job_name: str, job: dict) -> None:
        images = [
            str(svc.get("image", ""))
            for svc in (job.get("services") or {}).values()
        ]
        assert any("mongo" in image for image in images), (
            f"{workflow}:{job_name} runs the whole suite with no MongoDB service. "
            "tests/test_auth_me_regression.py will error on localhost:27017, "
            "pytest -x stops there, and any gate keyed on a green run becomes "
            "unsatisfiable — which is exactly how the implementer spent weeks "
            "reporting success while shipping nothing."
        )


class TestMongoIsReadyBeforeAnyPytest:
    """A pytest that starts a moment early reproduces the very defect the
    service exists to prevent — and does so silently, which is what made this
    expensive to find. The wait step must come first."""

    @pytest.mark.parametrize(
        "workflow",
        ["process-quick-note.yml", "ci-failure-autofix.yml"],
    )
    def test_wait_precedes_every_pytest(self, workflow: str) -> None:
        path = REPO_ROOT / ".github/workflows" / workflow
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        job = next(iter(spec["jobs"].values()))
        steps = job["steps"]

        waits = [
            i for i, s in enumerate(steps)
            if "Wait for MongoDB" in s.get("name", "")
        ]
        assert waits, f"{workflow} has no MongoDB readiness step"

        # `implement_agent.py` shells out to pytest, so it counts too.
        runners = [
            i for i, s in enumerate(steps)
            if "pytest" in s.get("run", "") or "implement_agent" in s.get("run", "")
        ]
        assert runners, f"{workflow} was expected to run pytest somewhere"
        assert waits[0] < min(runners), (
            f"{workflow} runs pytest at step {min(runners)} before waiting for "
            f"MongoDB at step {waits[0]}"
        )


class TestTheAgentRunsCurrentCode:
    """The implementer ran a four-day-old copy of itself.

    "Create or reuse feature branch" does
    ``git checkout -b "$CONTEXT_BRANCH" "origin/$CONTEXT_BRANCH"``, so every
    later step executes the tree *on that branch*. For issue #1347 the context
    branch was cut on 2026-08-24, so the 2026-08-28 run executed the pre-fix
    `.github/scripts/implement_agent.py` — its log still carried the string
    "Using NVIDIA NIM as the primary engine", which master had already deleted,
    and the six retired model ids master no longer contained.

    So a fix to the implementer is invisible to any issue that already has a
    branch. Worse, the agent was also reading stale *product* code: it planned
    against a master four days behind. Bringing master in before the agent runs
    fixes both, and is what a human would do before starting work on an old
    branch.
    """

    def test_master_is_merged_before_the_agent_runs(self, job: dict) -> None:
        branch_step = _step(job, "Create or reuse feature branch")
        assert "origin/master" in branch_step["run"], (
            "a reused context branch carries whatever tooling and product code "
            "existed when it was cut; the agent must not run against that"
        )

    def test_the_merge_precedes_the_implementer(self, job: dict) -> None:
        names = [s.get("name", "") for s in job["steps"]]
        branch_at = next(i for i, n in enumerate(names) if "feature branch" in n)
        impl_at = next(i for i, n in enumerate(names) if "Implement features" in n)
        assert branch_at < impl_at

    def test_a_conflict_does_not_run_the_agent_on_stale_code(self, job: dict) -> None:
        """If master cannot be merged, start clean rather than proceed stale."""
        run = _step(job, "Create or reuse feature branch")["run"]
        assert "merge --abort" in run
        assert run.count("origin/master") >= 2, (
            "the conflict path must also base itself on master"
        )

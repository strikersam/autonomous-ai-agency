"""A shell variable a workflow never sets expands to empty, and says nothing.

On 2026-08-29 the quick-note implementer merged its work to master with the
squash subject ``feat: implement quick-note issue #`` — no number. The merge
step built that subject from ``$ISSUE_NUM``, but its ``env:`` block was the one
place in the whole workflow that never declared it. Under ``bash -e`` an unset
variable is not an error; it is an empty string. So the flag was passed, the
merge succeeded, the run was green, and the only evidence that anything had
gone wrong was in ``git log``.

That is the same shape as every other defect this repo has been unwinding: the
broken thing and the working thing are indistinguishable from the outside.

The rule here is derived from what a step *does*, not from a list of steps
somebody has to remember to update: for every ``run:`` block, every variable it
reads must have somewhere it could have come from.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github/workflows"

# Provided by the runner, or by the shell itself. Not a workflow's job to set.
AMBIENT = frozenset({
    "CI", "HOME", "IFS", "LANG", "LC_ALL", "PATH", "PWD", "PYTHONPATH",
    "SHELL", "TMPDIR", "USER",
    # ${PIPESTATUS[0]} is a bash builtin array, used here to read pytest's
    # exit code through a `| tee` pipeline.
    "PIPESTATUS",
    "RUNNER_OS", "RUNNER_TEMP", "RUNNER_TOOL_CACHE",
    "GITHUB_ACTOR", "GITHUB_API_URL", "GITHUB_BASE_REF", "GITHUB_ENV",
    "GITHUB_EVENT_NAME", "GITHUB_EVENT_PATH", "GITHUB_HEAD_REF", "GITHUB_JOB",
    "GITHUB_OUTPUT", "GITHUB_PATH", "GITHUB_REF", "GITHUB_REPOSITORY",
    "GITHUB_RUN_ID", "GITHUB_RUN_NUMBER", "GITHUB_SERVER_URL", "GITHUB_SHA",
    "GITHUB_STEP_SUMMARY", "GITHUB_TOKEN", "GITHUB_WORKSPACE",
})

# `$NAME` or `${NAME...}`. Three characters minimum: `$1`, `$?` and friends are
# positional/status, not environment.
_READ = re.compile(r"\$\{?([A-Z][A-Z0-9_]{2,})\}?")
# `${NAME:-default}`, `${NAME:=x}`, `${NAME:?msg}`, `${NAME:+x}` — a reference
# that carries its own answer for "what if this is unset" is safe by
# construction, which is exactly the property the bug lacked.
_DEFAULTED = re.compile(r"\$\{([A-Z][A-Z0-9_]*)(?::[-=?+]|[-=?+])")
_ASSIGNED = re.compile(r"^[ \t]*(?:export[ \t]+|local[ \t]+)?([A-Z][A-Z0-9_]*)=", re.M)
_LOOP_VAR = re.compile(r"^[ \t]*for[ \t]+([A-Z][A-Z0-9_]*)[ \t]+in\b", re.M)
_READ_INTO = re.compile(r"\bread[ \t]+(?:-\w+[ \t]+)*([A-Z][A-Z0-9_]*)")
# `echo "NAME=..." >> "$GITHUB_ENV"` exports to *later steps in the same job*.
# Matched on the quoted-string form rather than on `echo`, because heredoc'd
# Python does the same thing a different way:
# `f.write(f"ELIGIBLE_COUNT={len(eligible)}\n")`.
_EXPORTED = re.compile(r"""["'](?:\$?f?)?([A-Z][A-Z0-9_]*)=""")


def _workflows() -> list[Path]:
    return sorted(WORKFLOWS.glob("*.yml"))


def _undeclared(job: dict, workflow_env: set[str]) -> list[tuple[str, str]]:
    """(step name, variable) for every read with no possible source.

    Job scope, not step scope: ``$GITHUB_ENV`` writes and env-file writes reach
    later steps, so a name any step in the job produces counts as available.
    Over-permissive on purpose — a false pass costs nothing here, a false
    failure would get the test deleted.
    """
    available = set(AMBIENT) | workflow_env | set(job.get("env") or {})
    steps = [s for s in (job.get("steps") or []) if isinstance(s, dict)]
    for step in steps:
        script = step.get("run") or ""
        for pattern in (_ASSIGNED, _LOOP_VAR, _READ_INTO, _EXPORTED):
            available |= set(pattern.findall(script))

    found: list[tuple[str, str]] = []
    for step in steps:
        script = step.get("run") or ""
        if not script:
            continue
        scope = available | set(step.get("env") or {}) | set(_DEFAULTED.findall(script))
        for name in sorted(set(_READ.findall(script)) - scope):
            found.append((step.get("name") or "(unnamed)", name))
    return found


def _cases() -> list[tuple[str, str, dict, set[str]]]:
    cases = []
    for path in _workflows():
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            continue
        workflow_env = set(doc.get("env") or {})
        for job_name, job in (doc.get("jobs") or {}).items():
            if isinstance(job, dict) and job.get("steps"):
                cases.append((path.name, job_name, job, workflow_env))
    return cases


def test_the_scan_sees_the_workflow_fleet() -> None:
    """A selector that matched nothing would make every assertion vacuous."""
    cases = _cases()
    assert len(cases) >= 20, f"expected the whole workflow fleet, found {len(cases)}"


@pytest.mark.parametrize(
    "workflow,job_name,job,workflow_env", _cases(), ids=lambda v: v if isinstance(v, str) else ""
)
def test_every_shell_variable_has_a_source(
    workflow: str, job_name: str, job: dict, workflow_env: set[str]
) -> None:
    missing = _undeclared(job, workflow_env)
    assert not missing, (
        f"{workflow} :: {job_name} reads variables nothing sets: "
        + "; ".join(f"${name} in {step!r}" for step, name in missing)
        + ". Declare it in the step's env:, give the reference a ${VAR:-default}, "
        "or set it earlier in the job — an unset variable expands to empty and "
        "the step still succeeds."
    )


class TestTheDetectorActuallyDetects:
    """A guard that cannot fail is not a guard.

    These reconstruct the 2026-08-29 defect and its neighbours in miniature, so
    a later loosening of the regexes shows up here rather than as another
    silently-empty interpolation on master.
    """

    def test_it_catches_an_undeclared_read(self) -> None:
        job = {"steps": [{"name": "merge", "env": {"REPO": "x"}, "run": 'gh pr merge --subject "#$ISSUE_NUM"'}]}
        assert _undeclared(job, set()) == [("merge", "ISSUE_NUM")]

    def test_a_step_env_declaration_satisfies_it(self) -> None:
        job = {"steps": [{"name": "merge", "env": {"ISSUE_NUM": "1"}, "run": 'echo "$ISSUE_NUM"'}]}
        assert _undeclared(job, set()) == []

    def test_a_github_env_write_in_an_earlier_step_satisfies_it(self) -> None:
        job = {"steps": [
            {"name": "start", "run": 'echo "SERVER_PID=$!" >> "$GITHUB_ENV"'},
            {"name": "stop", "run": 'kill "$SERVER_PID"'},
        ]}
        assert _undeclared(job, set()) == []

    def test_an_explicit_default_satisfies_it(self) -> None:
        job = {"steps": [{"name": "policy", "run": 'if [ "${ALLOW_PAID:-false}" = "true" ]; then :; fi'}]}
        assert _undeclared(job, set()) == []

    def test_a_local_assignment_satisfies_it(self) -> None:
        job = {"steps": [{"name": "branch", "run": 'BRANCH="quick-note"\necho "$BRANCH"'}]}
        assert _undeclared(job, set()) == []

    def test_ambient_runner_variables_are_not_flagged(self) -> None:
        job = {"steps": [{"name": "out", "run": 'echo "x=1" >> "$GITHUB_OUTPUT"'}]}
        assert _undeclared(job, set()) == []


class TestTheMergeStepNamesTheIssue:
    """The specific regression: the squash subject that reached master."""

    @pytest.fixture(scope="class")
    @classmethod
    def merge_step(cls) -> dict:
        doc = yaml.safe_load(
            (WORKFLOWS / "process-quick-note.yml").read_text(encoding="utf-8")
        )
        for step in doc["jobs"]["process"]["steps"]:
            if step.get("id") == "merge":
                return step
        raise AssertionError("no step with id 'merge' in process-quick-note.yml")

    def test_it_declares_the_issue_number(self, merge_step: dict) -> None:
        assert "ISSUE_NUM" in (merge_step.get("env") or {}), (
            "the merge step builds the squash subject from $ISSUE_NUM; without "
            "the declaration every merged commit is titled 'issue #' with no number"
        )

    def test_the_declaration_reads_the_same_output_as_every_other_step(
        self, merge_step: dict
    ) -> None:
        assert merge_step["env"]["ISSUE_NUM"] == "${{ steps.issue.outputs.number }}"

    def test_an_empty_number_does_not_produce_a_dangling_hash(
        self, merge_step: dict
    ) -> None:
        """Declared is not the same as non-empty — `steps.issue` can be skipped."""
        run = merge_step["run"]
        assert '[ -n "$ISSUE_NUM" ]' in run, (
            "the subject must be omitted rather than written with a bare '#'"
        )

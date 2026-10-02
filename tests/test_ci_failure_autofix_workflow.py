"""CI Failure Auto-Fix must stand down cleanly when it has nothing to apply.

With paid providers off (the default), "Generate fix with Claude" is skipped
and writes no patch, but "Apply and verify patch" still ran ``cat`` on the
missing file. Every run after a failed PR CI went red with no fix and no issue
(e.g. run 36965134070 on 2026-10-02). The "Skip if master itself is broken"
step only logged, so a red master still went on to generate patches.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci-failure-autofix.yml"


@pytest.fixture(scope="module")
def steps() -> dict[str, dict]:
    wf = yaml.safe_load(WORKFLOW.read_text())
    return {s.get("name", ""): s for s in wf["jobs"]["autofix"]["steps"]}


def _policy_skip(env: dict[str, str]) -> str:
    """Run the policy step's script and return the `skip` it emits."""
    wf = yaml.safe_load(WORKFLOW.read_text())
    script = next(s for s in wf["jobs"]["autofix"]["steps"] if s.get("id") == "policy")["run"]
    out = Path("/dev/stdout")
    result = subprocess.run(
        ["bash", "-c", script],
        env={"PATH": "/usr/bin:/bin", "GITHUB_OUTPUT": str(out), **env},
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.split("skip=", 1)[1].split()[0]


def test_apply_and_issue_steps_are_gated_on_policy(steps: dict[str, dict]) -> None:
    gate = "steps.policy.outputs.skip != 'true'"
    assert gate in steps["Generate fix with Claude"]["if"]
    assert gate in steps["Apply and verify patch"]["if"]
    assert gate in steps["Open issue when fix is too complex or verification fails"]["if"]


def test_apply_tolerates_a_missing_patch(steps: dict[str, dict]) -> None:
    run = steps["Apply and verify patch"]["run"]
    assert run.index("[ ! -s /tmp/autofix.patch ]") < run.index("cat /tmp/autofix.patch")


@pytest.mark.parametrize("env,skip", [
    ({"MASTER_EXIT": "0"}, "true"),
    ({"MASTER_EXIT": "0", "PROVIDER_POLICY_ALLOW_PAID": "true"}, "false"),
    ({"MASTER_EXIT": "1", "PROVIDER_POLICY_ALLOW_PAID": "true"}, "true"),
])
def test_policy_skips_when_paid_off_or_master_red(env: dict[str, str], skip: str) -> None:
    assert _policy_skip(env) == skip

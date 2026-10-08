"""Replay every recorded agent-PR incident against the pre-PR gate (tests/agent_evals/gate_cases.yaml).

A change to the gate, the agents' prompts or CLAUDE.md that lets one of these
through is a regression, whatever else it improves.
"""
from __future__ import annotations

import subprocess  # nosec B404 - fixed git argv in a tmp repo
from pathlib import Path

import pytest
import yaml

from agent.pr_gate import run_pr_gate

CASES = yaml.safe_load((Path(__file__).parent / "gate_cases.yaml").read_text(encoding="utf-8"))["cases"]
_LINES200 = "".join(f"<p>line {i}</p>\n" for i in range(200))


def _git(root: Path, *args: str) -> str:
    return subprocess.run(  # nosec B603 B607 - fixed git argv
        ["git", "-c", "user.email=e@e", "-c", "user.name=e", *args],
        cwd=root, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _write(root: Path, files: dict[str, str | None]) -> None:
    for rel, body in files.items():
        path = root / rel
        if body is None:
            path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_LINES200 if body == "@LINES200" else body, encoding="utf-8")


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_incident_replay(tmp_path: Path, case: dict) -> None:
    _write(tmp_path, case["before"])
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    base = _git(tmp_path, "rev-parse", "HEAD")
    _write(tmp_path, case["after"])
    report = run_pr_gate(tmp_path, list(case["after"]), goal=case["goal"],
                         planned_files=case["planned"], base_ref=base)
    assert (not report.ok) is case["blocked"], report.blockers
    text = "\n".join(report.blockers)
    for needle in case["expect"]:
        assert needle in text, f"{case['id']}: expected {needle!r} in {text!r}"

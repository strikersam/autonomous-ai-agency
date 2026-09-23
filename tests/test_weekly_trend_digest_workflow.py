"""The weekly trend digest opens an issue only when an alert needs action.

#1557 was one of a weekly run of issues whose own triage text said "no action —
most weeks, this is the answer", each closed by hand. The digest now goes to the
job summary, and an issue is opened only for alerts tagged ``action-required``.
These tests execute the workflow's own ``github-script`` body under Node.
"""
from __future__ import annotations

import json
import shutil
import subprocess  # nosec B404 — fixed argv, test-only
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/weekly-trend-digest.yml"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

_HARNESS = """
const created = [];
const github = { rest: { issues: { create: async (a) => { created.push(a); } } } };
const core = { info: () => {} };
const context = { repo: { owner: 'o', repo: 'r' } };
(async () => {
%s
})().then(() => console.log(JSON.stringify(created)));
"""


def _script() -> str:
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["trend-digest"]["steps"]
    step = next(s for s in steps if s.get("name") == "Create weekly digest issue")
    return step["with"]["script"]


def _run(tmp_path: Path, alerts: list[dict]) -> list[dict]:
    trends = tmp_path / "trends.json"
    trends.write_text(json.dumps(alerts), encoding="utf-8")
    script = _script().replace("/tmp/trends.json", str(trends))
    js = tmp_path / "run.js"
    js.write_text(_HARNESS % script, encoding="utf-8")
    out = subprocess.run(  # nosec B603 — fixed argv
        ["node", str(js)], capture_output=True, text=True, check=True, timeout=30
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def _alert(title: str, tags: list[str]) -> dict:
    return {
        "source": "ollama", "title": title, "url": "https://example.invalid",
        "relevance_score": 0.8, "published": "2026-09-21", "tags": tags,
    }


def test_no_issue_when_nothing_is_action_required(tmp_path: Path) -> None:
    alerts = [_alert("Ollama v0.34.1 released", ["ollama", "release"])]
    assert _run(tmp_path, alerts) == []


def test_issue_lists_only_action_required_alerts(tmp_path: Path) -> None:
    alerts = [
        _alert("Ollama v0.34.1 released", ["ollama", "release"]),
        _alert("Ollama v0.35.0 adds new models", ["ollama", "release", "action-required"]),
    ]
    created = _run(tmp_path, alerts)
    assert len(created) == 1
    body = created[0]["body"]
    assert "v0.35.0" in body
    assert "v0.34.1" not in body

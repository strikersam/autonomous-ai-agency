"""Guards on ``.github/workflows/security-gate.yml``."""
from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/security-gate.yml"


def test_gate_reruns_when_a_draft_is_marked_ready() -> None:
    """The gate skips draft PRs, and a skipped required job counts as passing.
    Quick-note PRs get their code while draft and are then marked ready, so
    without ready_for_review the gate never scans them before --auto merges."""
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    on = data.get("on", data.get(True))  # PyYAML reads the bare key `on` as True
    job = data["jobs"]["security-gate"]
    assert "draft == false" in job["if"]
    assert "ready_for_review" in on["pull_request"]["types"]
    for kind in ("opened", "synchronize", "reopened"):
        assert kind in on["pull_request"]["types"], kind

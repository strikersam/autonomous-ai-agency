"""Each merge deploys the backend once.

Render auto-deploys local-llm-server on every push to master, and
deploy-backend.yml also POSTed the deploy hook on the same push, so every merge
built and deployed twice (Render events 2026-10-08: trigger new_commit, then
trigger deploy_hook, same commit). On push the workflow now only verifies that
Render's own deploy goes live; the hook fires only on a manual dispatch.
"""
from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "deploy-backend.yml"


def _steps() -> dict[str, dict]:
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return {s["name"]: s for s in wf["jobs"]["deploy"]["steps"]}


def test_the_deploy_hook_only_fires_on_manual_dispatch():
    steps = _steps()
    for name in ("Validate deploy hook secret is set", "Trigger Render deployment"):
        assert steps[name].get("if") == "github.event_name == 'workflow_dispatch'", name


def test_every_push_still_verifies_the_commit_goes_live():
    verify = _steps()["Verify the new build is actually live"]
    assert "if" not in verify
    assert "EXPECTED_SHA" in verify["env"]

"""Regression tests for daily-2026-06-14 improvements.

Anthropic retires the original Claude Sonnet 4 / Opus 4 models
(`claude-sonnet-4-20250514`, `claude-opus-4-20250514`) on the Claude API on
2026-06-15, recommending migration to Claude Sonnet 4.6 / Opus 4.8.

Covers:
- `.github/workflows/ci-failure-autofix.yml` calls the Anthropic API with a
  non-retired model ID (`claude-sonnet-4-6`), matching the workflow's own
  documentation comment ("calls Claude Sonnet 4.6").
- No GitHub Actions workflow or CI script references a retired dated Claude 4
  model ID as the `model` value for a direct Anthropic API call.
"""

from __future__ import annotations

import os
import re

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")

# Original Claude Sonnet 4 / Opus 4 — retired on the Claude API 2026-06-15.
RETIRED_MODEL_IDS = ("claude-sonnet-4-20250514", "claude-opus-4-20250514")


def _read(path: str) -> str:
    with open(os.path.join(REPO_ROOT, path), encoding="utf-8") as fh:
        return fh.read()


def test_ci_autofix_workflow_uses_sonnet_4_6():
    """ci-failure-autofix.yml must call the Anthropic API with claude-sonnet-4-6,
    as documented in the workflow's own header comment."""
    content = _read(".github/workflows/ci-failure-autofix.yml")
    assert '"model": "claude-sonnet-4-6"' in content
    for retired in RETIRED_MODEL_IDS:
        assert retired not in content, (
            f"{retired} is retired on the Claude API as of 2026-06-15 — "
            "this workflow would start failing"
        )


def test_no_retired_claude_4_model_ids_in_workflows_or_scripts():
    """No GitHub Actions workflow or CI script should reference a retired
    Claude 4 model ID."""
    offenders: list[str] = []
    for base in (".github/workflows", ".github/scripts"):
        base_path = os.path.join(REPO_ROOT, base)
        if not os.path.isdir(base_path):
            continue
        for name in os.listdir(base_path):
            if not name.endswith((".yml", ".yaml", ".py")):
                continue
            content = _read(os.path.join(base, name))
            for retired in RETIRED_MODEL_IDS:
                if re.search(re.escape(retired), content):
                    offenders.append(f"{base}/{name}: {retired}")

    assert not offenders, f"Retired Claude 4 model IDs found: {offenders}"

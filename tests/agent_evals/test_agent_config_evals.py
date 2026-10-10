"""Regression checks on the configuration that steers the agents.

CLAUDE.md, REVIEW.md, the skills and the prompts are code the agents run on
(playbook, Stage 4: continuous evals gate configuration changes). These run on
every PR and nightly via .github/workflows/agent-evals.yml.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
CLAUDE_MD = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
RULE_NUMBER = re.compile(r"^(\d+)\. \*\*|^(\d+)\. ", re.M)


def _rules_section() -> str:
    return CLAUDE_MD[CLAUDE_MD.index("## 1. The Rules"):CLAUDE_MD.index("## 3. What this repo is")]


def test_rules_are_numbered_without_gaps():
    numbers = [int(a or b) for a, b in RULE_NUMBER.findall(_rules_section())]
    assert numbers == list(range(1, 50)), numbers


def test_claude_md_stays_short():
    # The playbook's bar is "under a page"; the 49 binding rules alone are most of
    # this, so the ceiling stops reference material creeping back in.
    assert len(CLAUDE_MD.splitlines()) <= 300


def test_context_generator_receives_every_rule():
    spec = importlib.util.spec_from_file_location("gen_ctx_eval", REPO / ".github/scripts/generate_context.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["gen_ctx_eval"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    context = module._load_codebase_context()
    for n in (1, 14, 34, 39, 45, 48, 49):
        assert re.search(rf"^{n}\. ", context, re.M), f"rule {n} missing from the agent context"


def test_every_path_in_the_reference_table_exists():
    table = CLAUDE_MD[CLAUDE_MD.index("## 5. Reference"):]
    for path in re.findall(r"`([^`]+)`", table):
        assert (REPO / path.rstrip("/")).exists(), path


def test_review_policy_has_the_three_passes():
    review = (REPO / "REVIEW.md").read_text(encoding="utf-8")
    for heading in ("**Bugs**", "**Security**", "**Compliance**", "## Cap the nits", "## Do not report"):
        assert heading in review, heading


@pytest.mark.parametrize("skill", sorted((REPO / ".claude" / "skills").glob("*/SKILL.md")),
                         ids=lambda p: p.parent.name)
def test_skill_frontmatter_names_its_folder(skill: Path):
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md must open with YAML frontmatter"
    meta = yaml.safe_load(text.split("---\n", 2)[1])
    assert meta.get("name") == skill.parent.name
    assert len(str(meta.get("description", "")).strip()) >= 20

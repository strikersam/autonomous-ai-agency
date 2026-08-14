"""Regression test: autonomous issue-context generation must not truncate
CLAUDE.md's binding ruleset before it reaches the LLM.

`_load_codebase_context()` in `.github/scripts/generate_context.py` feeds
CLAUDE.md into the context used by the autonomous GitHub issue-driven agent
(issue-context-generator workflow). A flat first-N-chars excerpt cuts the file
mid-ruleset, so §1 (the 44 rules) and §2 (Standing Instructions) are carved out
and sent whole. Those agents run on open-weights models with no harness system
prompt behind them, so §2 is the only place that discipline reaches them.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULE_PATH = REPO_ROOT / ".github" / "scripts" / "generate_context.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("generate_context", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_context"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_claude_md_has_the_carved_out_sections() -> None:
    """Sanity check on the fixture assumption this test relies on."""
    claude_md = (REPO_ROOT / "CLAUDE.md").read_text()
    rules_idx = claude_md.find("## 1. The Rules")
    standing_idx = claude_md.find("## 2. Standing Instructions")
    ref_idx = claude_md.find("## 3. What this repo is")
    assert 0 <= rules_idx < standing_idx < ref_idx, (
        "CLAUDE.md section order changed — _load_codebase_context() carves "
        "§1 through §2 by these markers and would fall back to a flat excerpt."
    )


def test_load_codebase_context_includes_rules_and_standing_instructions() -> None:
    module = _load_module()
    context = module._load_codebase_context()

    assert "## 1. The Rules" in context
    assert "## 2. Standing Instructions" in context
    # A rule from the far end of §1 — proves the ruleset was not truncated.
    assert "graphify update" in context
    # A rule from §2 — proves the discipline block survived.
    assert "Never report a check you did not run" in context


def test_reference_sections_are_not_shipped() -> None:
    """§3 onward is architecture reference, not instruction — dropping it is
    what buys room to send the whole ruleset."""
    module = _load_module()
    context = module._load_codebase_context()
    assert "## 5. Bill of materials" not in context

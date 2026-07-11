"""Regression test: autonomous issue-context generation must not silently
truncate CLAUDE.md before it reaches §14 Standing Instructions.

`_load_codebase_context()` in `.github/scripts/generate_context.py` feeds
CLAUDE.md into the LLM context used by the autonomous GitHub issue-driven
agent (issue-context-generator workflow). It excerpts only the first 4000
chars for a general overview; §14 lives much further into the file, so
without an explicit carve-out the mandatory Standing Instructions never
reach that autonomous agent at all.
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


def test_claude_md_standing_instructions_present_past_4000_chars() -> None:
    """Sanity check on the fixture assumption this test relies on."""
    claude_md = (REPO_ROOT / "CLAUDE.md").read_text()
    marker_idx = claude_md.find("## 14. Standing Instructions")
    assert marker_idx >= 4000, (
        "CLAUDE.md §14 moved inside the 4000-char excerpt window — "
        "the carve-out in _load_codebase_context() may now be redundant "
        "but should still be verified, not silently dropped."
    )


def test_load_codebase_context_includes_standing_instructions() -> None:
    module = _load_module()
    context = module._load_codebase_context()

    assert "## 14. Standing Instructions" in context
    assert "Final Gate" in context or "14.11" in context

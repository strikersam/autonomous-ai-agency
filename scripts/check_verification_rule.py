"""Fail if any agent instruction file's copy of rule 49 differs from CLAUDE.md's.

Rule 49 (independent verification before "done") is the one rule mirrored into
every agent's instruction file. Duplicated rules drift; this keeps them equal.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
START = "<!-- pstack-verification:start -->"
END = "<!-- pstack-verification:end -->"
MIRRORS = (
    "AGENTS.md",
    "agent/CLAUDE.md",
    "router/CLAUDE.md",
    "docs/agents.md",
    "GEMINI.md",
    ".github/copilot-instructions.md",
    ".cursor/rules/verification.mdc",
)


def extract(path: pathlib.Path) -> str | None:
    """Return the marked rule block in ``path``, or None when it is missing."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if START not in text or END not in text:
        return None
    return text[text.index(START): text.index(END) + len(END)]


def main() -> int:
    """Compare every mirror against CLAUDE.md and report each mismatch."""
    canonical = extract(ROOT / "CLAUDE.md")
    if canonical is None:
        print("FAIL: CLAUDE.md has no rule 49 block")
        return 1
    bad = [m for m in MIRRORS if extract(ROOT / m) != canonical]
    for m in bad:
        print(f"FAIL: {m} is missing rule 49 or differs from CLAUDE.md")
    if bad:
        return 1
    print(f"RULE 49 PARITY OK: {len(MIRRORS)} mirrors match CLAUDE.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())

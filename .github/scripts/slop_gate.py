#!/usr/bin/env python3
"""Reusable slop-gate for the autonomous PR-generating scripts.

Auto-PR scripts call a model on a vague issue and write whatever comes back.
Without a guard, an empty/garbled model response silently overwrites working
code — e.g. PR #833 replaced an 892-line ``direct_chat.py`` with ``{}`` and
opened a PR. This module refuses destructive / low-quality changes *before* a
PR is created.

Three checks, all pure functions so they unit-test without git or network:

  * ``is_destructive_overwrite`` — emptying or truncating an existing file.
  * ``python_parses``            — generated Python must at least parse.
  * ``diff_is_sloppy``           — a net mass-deletion isn't an "implementation".
"""
from __future__ import annotations

import ast

# Content that, written over a real file, means "the model gave us nothing".
_TRIVIAL = {"", "{}", "[]", '""', "''", "null", "none", "{}\n", "[]\n", "{\n}"}


def is_destructive_overwrite(old_text: str, new_text: str) -> tuple[bool, str]:
    """Return (rejected, reason) when *new_text* destroys an existing file.

    Two failure modes, both seen in real slop PRs:
      1. trivial/empty content over a non-trivial file (the ``{}`` case), and
      2. truncation — replacing a substantial file with <25% of its lines.
    A brand-new file (empty *old_text*) is always allowed.
    """
    if not (old_text or "").strip():
        return False, ""  # new (or previously-empty) file — nothing to destroy
    old_lines = old_text.count("\n") + 1
    new_lines = new_text.count("\n") + 1 if new_text else 0
    if old_lines >= 15 and new_text.strip().lower() in _TRIVIAL:
        return True, f"empties a {old_lines}-line file (content is trivial: {new_text.strip()[:20]!r})"
    if old_lines >= 30 and new_lines < max(5, int(old_lines * 0.25)):
        return True, f"truncates a {old_lines}-line file to {new_lines} lines (<25% of the original)"
    return False, ""


def python_parses(text: str) -> bool:
    """True when *text* is syntactically valid Python (or trivially empty)."""
    if not text.strip():
        return True
    try:
        ast.parse(text)
        return True
    except SyntaxError:
        return False


def diff_is_sloppy(total_add: int, total_del: int) -> tuple[bool, str]:
    """Net mass-deletion guard — an implementation shouldn't be mostly deletions."""
    if total_del > 40 and total_del > total_add * 3:
        return (
            True,
            f"net mass deletion (+{total_add} / -{total_del}) — looks destructive, "
            "not an implementation",
        )
    return False, ""

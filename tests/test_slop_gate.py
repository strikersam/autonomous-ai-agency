"""tests/test_slop_gate.py — the auto-PR slop-gate.

Guards the exact failure that produced PR #833: an auto-generated change that
replaced an 892-line `direct_chat.py` with `{}` and opened a PR. The gate must
reject destructive / non-parsing / net-mass-deletion output before a PR exists.
"""
from __future__ import annotations

import os
import sys

# slop_gate lives next to the auto-PR scripts.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".github", "scripts"))

from slop_gate import diff_is_sloppy, is_destructive_overwrite, python_parses  # noqa: E402


def test_empty_dict_over_real_file_is_rejected():
    """The #833 case: '{}' written over a substantial file."""
    old = "\n".join(f"line {i}" for i in range(892))
    rejected, reason = is_destructive_overwrite(old, "{}")
    assert rejected
    assert "empties" in reason


def test_truncation_is_rejected():
    old = "\n".join(f"line {i}" for i in range(200))
    new = "line 0\nline 1\nline 2"  # 3 lines, way under 25%
    rejected, reason = is_destructive_overwrite(old, new)
    assert rejected
    assert "truncates" in reason


def test_new_file_is_allowed():
    rejected, _ = is_destructive_overwrite("", "anything at all\nmore")
    assert not rejected


def test_substantial_rewrite_is_allowed():
    old = "\n".join(f"line {i}" for i in range(40))
    new = "\n".join(f"new {i}" for i in range(38))  # similar size → legit edit
    rejected, _ = is_destructive_overwrite(old, new)
    assert not rejected


def test_small_file_edit_not_flagged_as_truncation():
    # A short existing file shrinking is not destructive (below the 15/30 thresholds).
    rejected, _ = is_destructive_overwrite("a\nb\nc\nd\ne", "a\nb")
    assert not rejected


def test_python_parses():
    assert python_parses("def f():\n    return 1\n")
    assert python_parses("")            # empty is fine (not our concern here)
    assert not python_parses("def f(:\n  pass")  # syntax error


def test_diff_mass_deletion_rejected():
    rejected, reason = diff_is_sloppy(total_add=2, total_del=892)
    assert rejected
    assert "deletion" in reason


def test_diff_balanced_change_allowed():
    rejected, _ = diff_is_sloppy(total_add=120, total_del=30)
    assert not rejected

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

from slop_gate import (  # noqa: E402
    diff_is_sloppy,
    is_doc_only_boilerplate,
    is_destructive_overwrite,
    looks_like_secret_file,
    python_parses,
)


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


# ── secrets-shaped file guard (the exact PR #842 footgun) ──────────────────────

def test_secrets_json_footgun_rejected():
    # The literal content PR #842 committed to .github/secrets.json (python-dict repr).
    rejected, reason = looks_like_secret_file(
        ".github/secrets.json",
        "{'ANTHROPIC_API_KEY': '${ANTHROPIC_API_KEY}', 'GH_PAT': '${GH_PAT}'}",
    )
    assert rejected
    assert "secret" in reason.lower()


def test_secrets_file_rejected_by_name_even_when_empty():
    rejected, _ = looks_like_secret_file("config/secrets.yaml", "")
    assert rejected


def test_credentials_content_rejected_regardless_of_filename():
    rejected, _ = looks_like_secret_file(
        "config/app.json", '{"DATABASE_PASSWORD": "hunter2", "API_TOKEN": "abc"}'
    )
    assert rejected


def test_bare_dotenv_rejected():
    rejected, _ = looks_like_secret_file(".env", "OPENAI_API_KEY=sk-real-value\n")
    assert rejected


def test_example_template_allowed():
    # Documenting variable NAMES in a template is the correct pattern — allowed.
    rejected, _ = looks_like_secret_file(
        ".env.example", "OPENAI_API_KEY=\nGH_PAT=\n"
    )
    assert not rejected
    rejected, _ = looks_like_secret_file(
        "secrets.json.sample", '{"API_KEY": "your-key-here"}'
    )
    assert not rejected


def test_ordinary_config_not_flagged():
    # A normal package.json / config map with no credential-named keys is fine.
    rejected, _ = looks_like_secret_file(
        "package.json", '{"name": "app", "version": "1.0.0", "scripts": {}}'
    )
    assert not rejected
    rejected, _ = looks_like_secret_file(
        "router/registry.py", "REGISTRY = {'model': 'x'}\n"
    )
    assert not rejected


# ── doc-only boilerplate guard (the #842/#843 additive slop) ───────────────────

def test_doc_only_pr_rejected():
    """The exact #842/#843 pattern: only markdown + changelog, no code."""
    rejected, reason = is_doc_only_boilerplate([
        "AUTONOMOUS_AGENCY_SETUP.md",
        "investigation.md",
        "CHANGELOG.md",
        "docs/changelog.md",
    ])
    assert rejected
    assert "documentation-only" in reason


def test_doc_only_single_markdown_rejected():
    rejected, _ = is_doc_only_boilerplate(["docs/new-feature.md"])
    assert rejected


def test_pr_with_code_file_allowed():
    """A PR that includes at least one code file is not boilerplate."""
    rejected, _ = is_doc_only_boilerplate([
        "agent/new_feature.py",
        "CHANGELOG.md",
        "docs/changelog.md",
    ])
    assert not rejected


def test_pr_with_js_code_allowed():
    rejected, _ = is_doc_only_boilerplate([
        "frontend/src/components/NewPanel.jsx",
        "CHANGELOG.md",
    ])
    assert not rejected


def test_pr_with_shell_script_allowed():
    rejected, _ = is_doc_only_boilerplate([
        "scripts/deploy.sh",
        "docs/deploy.md",
    ])
    assert not rejected


def test_empty_file_list_allowed():
    rejected, _ = is_doc_only_boilerplate([])
    assert not rejected

#!/usr/bin/env python3
"""Reusable slop-gate for the autonomous PR-generating scripts.

Auto-PR scripts call a model on a vague issue and write whatever comes back.
Without a guard, an empty/garbled model response silently overwrites working
code — e.g. PR #833 replaced an 892-line ``direct_chat.py`` with ``{}`` and
opened a PR. This module refuses destructive / low-quality changes *before* a
PR is created.

Five checks, all pure functions so they unit-test without git or network:

  * ``is_destructive_overwrite`` — emptying or truncating an existing file.
  * ``python_parses``            — generated Python must at least parse.
  * ``diff_is_sloppy``           — a net mass-deletion isn't an "implementation".
  * ``looks_like_secret_file``   — never commit a secrets-shaped file to source.
  * ``is_doc_only_boilerplate``  — pure-doc PRs from vague issues are slop.
"""
from __future__ import annotations

import ast
import json
import re

# Content that, written over a real file, means "the model gave us nothing".
_TRIVIAL = {"", "{}", "[]", '""', "''", "null", "none", "{}\n", "[]\n", "{\n}"}

# Keys whose presence in a flat map marks the file as a credentials store.
_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|secret|token|password|passwd|credential|access[_-]?key|"
    r"private[_-]?key|client[_-]?secret|\bpat\b|_pat\b)",
    re.I,
)
# Intentional documentation templates are allowed — they carry no real values.
_EXAMPLE_SUFFIXES = (".example", ".sample", ".template", ".dist")
# Structured-config extensions a committed secrets store typically uses.
_SECRET_FILE_EXTS = (".json", ".yaml", ".yml", ".env", ".ini", ".toml")


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


def looks_like_secret_file(path: str, content: str) -> tuple[bool, str]:
    """Return (rejected, reason) when *path*/*content* is a secrets-shaped file.

    The autonomous agency once auto-committed ``.github/secrets.json`` holding
    ``{'ANTHROPIC_API_KEY': '${ANTHROPIC_API_KEY}', 'GH_PAT': '${GH_PAT}'}``
    (PR #842). Even with placeholder values that's a footgun — a tracked file
    literally named ``secrets`` invites someone to paste *real* keys into it, and
    it violates CLAUDE.md rule #2 ("No secrets in source"). Secrets belong in env
    vars / repo secrets, never in committed source.

    Two triggers (either is enough):
      1. the filename is a structured secrets store (``secret*``/``credential*``
         with a config extension, or a bare ``.env``/``.netrc``/``.npmrc``), or
      2. the content is a flat map whose keys name credentials.
    ``*.example`` / ``*.sample`` / ``*.template`` files are always allowed —
    documenting variable *names* (not values) is the correct pattern.
    """
    base = path.rsplit("/", 1)[-1].lower()
    if base.endswith(_EXAMPLE_SUFFIXES):
        return False, ""

    dotenv_like = base == ".env" or base.startswith(".env.")
    name_is_secrets = (
        ("secret" in base or "credential" in base) and base.endswith(_SECRET_FILE_EXTS)
    ) or dotenv_like or base in {".netrc", ".npmrc"}

    content_is_secrets = False
    text = (content or "").strip()
    if text:
        data = None
        try:
            data = json.loads(text)
        except Exception:  # noqa: BLE001
            # Tolerate a Python-dict repr (single quotes) — the exact #842 shape.
            try:
                data = ast.literal_eval(text)
            except Exception:  # noqa: BLE001
                data = None
        if isinstance(data, dict) and data:
            secret_values = [
                v for k, v in data.items()
                if isinstance(k, str) and _SECRET_KEY_RE.search(k)
            ]
            content_is_secrets = bool(secret_values) and all(
                v is None or isinstance(v, (str, int, float, bool))
                for v in secret_values
            )

    if name_is_secrets or content_is_secrets:
        return True, (
            "commits a secrets-shaped file — credentials belong in environment "
            "variables or repo secrets, never in tracked source (CLAUDE.md rule #2). "
            "Document variable names in a *.example template instead."
        )
    return False, ""


def is_doc_only_boilerplate(file_paths: list[str]) -> tuple[bool, str]:
    """Return (rejected, reason) when every generated file is documentation-only.

    PRs #842 and #843 were auto-merged from vague issues and contained only new
    markdown files (``AUTONOMOUS_AGENCY_SETUP.md``, ``investigation.md``) plus
    changelog entries — zero code.  The slop-gate couldn't catch them because
    the changes were additive, not destructive.

    An autonomous agent implementing a real issue should produce at least one
    code file (.py, .js, .jsx, .ts, .tsx, .go, .rs, .java, .sh, .sql, etc.).
    A PR that only touches docs/markdown/changelog/text is either boilerplate
    hallucination from a vague issue or a planning doc that needs human review.
    """
    if not file_paths:
        return False, ""

    _DOC_EXTS = {
        ".md", ".txt", ".rst", ".adoc", ".csv", ".log",
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    }
    _CHANGELOG_STEMS = {"changelog", "changes", "history", "news"}

    for path in file_paths:
        base = path.rsplit("/", 1)[-1].lower()
        stem = base.rsplit(".", 1)[0] if "." in base else base
        ext = ("." + base.rsplit(".", 1)[1]) if "." in base else ""

        is_changelog = stem in _CHANGELOG_STEMS
        is_doc = ext in _DOC_EXTS

        if not is_changelog and not is_doc:
            return False, ""

    return True, (
        "all generated files are documentation-only (markdown, changelog, config) "
        "with no code changes — this is boilerplate from a vague issue, not a real "
        "implementation. The autonomous agent should produce at least one code file."
    )


def diff_is_sloppy(total_add: int, total_del: int) -> tuple[bool, str]:
    """Net mass-deletion guard — an implementation shouldn't be mostly deletions."""
    if total_del > 40 and total_del > total_add * 3:
        return (
            True,
            f"net mass deletion (+{total_add} / -{total_del}) — looks destructive, "
            "not an implementation",
        )
    return False, ""

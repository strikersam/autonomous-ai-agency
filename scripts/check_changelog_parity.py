"""scripts/check_changelog_parity.py

CI guard for the changelog mirror. Closes the medium-severity code-review item on
PR #692 — without this job, the root ``CHANGELOG.md`` (human-facing) and
``docs/changelog.md`` (the path ``changelog-check.yml`` keys on) can drift apart
silently across PRs.

Behaviour
---------
- Reads both files (UTF-8) and extracts the body of ``## [Unreleased]`` (text
  between the marker and the next ``## [`` or EOF).
- Normalises: line endings → LF (so Windows CRLF and Linux LF checkouts match
  cleanly), strips HTML comments, trailing whitespace per line, and collapses
  3+ consecutive newlines into 2.
- Exit codes:
    0 — bodies match (status: ``PARITY OK``); prints ``::warning::`` to stderr
        if BOTH bodies are non-empty-after-header but normalize to empty, so a
        contributor is not silently OK'd for a pull request that drops every
        bullet (the previous content gets the version header back).
    1 — bodies differ (prints unified-diff to stderr, status: ``PARITY DRIFT``)
    2 — either file missing, or neither file has a ``## [Unreleased]`` header
       (prints ``::error::`` annotation to stderr for GitHub Actions)

Usage
-----
::

    python scripts/check_changelog_parity.py
    python scripts/check_changelog_parity.py --root CHANGELOG.md --docs docs/changelog.md
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

_UNRELEASED_RE = re.compile(r"## \[Unreleased\](.*?)(?=## \[|\Z)", re.DOTALL)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_TRAILING_WS_RE = re.compile(r"[ \t]+$", re.MULTILINE)
_BLANK_RUN_RE = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    """Line-endings → LF, strip HTML comments, trim per-line, collapse blanks."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HTML_COMMENT_RE.sub("", text)
    text = _TRAILING_WS_RE.sub("", text)
    text = _BLANK_RUN_RE.sub("\n\n", text)
    return text.strip()


def extract_unreleased_body(content: str) -> str | None:
    """Return the normalised body of ``## [Unreleased]`` or ``None`` if absent."""
    match = _UNRELEASED_RE.search(content)
    if not match:
        return None
    return normalize_text(match.group(1))


def _to_compare_lines(body: str | None) -> list[str]:
    """Split a normalised body into lines with trailing ``\\n`` for difflib."""
    if not body:
        return []
    return [(line + "\n") for line in body.split("\n")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=Path("CHANGELOG.md"))
    parser.add_argument("--docs", type=Path, default=Path("docs/changelog.md"))
    args = parser.parse_args()

    root_path: Path = args.root
    docs_path: Path = args.docs

    if not root_path.exists() or not docs_path.exists():
        missing = [str(p) for p in (root_path, docs_path) if not p.exists()]
        print(
            f"::error::Missing changelog file(s): {', '.join(missing)}",
            file=sys.stderr,
        )
        return 2

    root_content = root_path.read_text(encoding="utf-8")
    docs_content = docs_path.read_text(encoding="utf-8")
    root_body = extract_unreleased_body(root_content)
    docs_body = extract_unreleased_body(docs_content)

    if root_body is None and docs_body is None:
        print(
            "::error::Neither changelog has a '## [Unreleased]' header "
            f"(checked {root_path} and {docs_path}).",
            file=sys.stderr,
        )
        return 2

    root_lines = _to_compare_lines(root_body)
    docs_lines = _to_compare_lines(docs_body)

    if root_lines == docs_lines:
        # M2: if both files HAD a [Unreleased] header but the body is empty after
        # normalisation (i.e. only whitespace / HTML comments / blank lines),
        # surface a warning so a regression that drops every bullet is not
        # silently OK'd by the parity check.
        if not root_body and not docs_body:
            print(
                "::warning::Both changelogs have a '## [Unreleased]' header "
                "but an empty body — add at least one bullet under "
                "'### Added'/'### Changed'/'### Fixed' before merging.",
                file=sys.stderr,
            )
        print("PARITY OK")
        return 0

    print("PARITY DRIFT")
    diff = difflib.unified_diff(
        root_lines,
        docs_lines,
        fromfile=str(root_path),
        tofile=str(docs_path),
        n=3,
    )
    sys.stderr.writelines(diff)
    return 1


if __name__ == "__main__":
    sys.exit(main())

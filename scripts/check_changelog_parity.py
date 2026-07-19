"""scripts/check_changelog_parity.py

CI guard for the changelog mirror. Closes the medium-severity code-review
item on PR #692 -- without this job, the root ``CHANGELOG.md``
(human-facing) and ``docs/changelog.md`` (the path
``changelog-check.yml`` keys on) can drift apart silently across PRs.

Behaviour
---------
- Reads both files (UTF-8) and extracts every ``## [X]`` version body
  (including ``## [Unreleased]``).
- Normalises: line endings -> LF, strip per-line trailing whitespace,
  collapse 3+ consecutive newlines into 2.
- Compares the bodies byte-exact per version key, sorted by key.
- Exit codes:
    0 -- bodies match (status: ``PARITY OK``).
    1 -- bodies differ (prints unified-diff to stderr, status:
        ``PARITY DRIFT``).
    2 -- either file missing, or neither file has any ``## [...]``
       header (prints ``::error::`` annotation to stderr for
       GitHub Actions).

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

_VERSION_RE = re.compile(r"^## \[(.+?)\]", re.MULTILINE)
_TRAILING_WS_RE = re.compile(r"[ \t]+$", re.MULTILINE)
_BLANK_RUN_RE = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _TRAILING_WS_RE.sub("", text)
    text = _BLANK_RUN_RE.sub("\n\n", text)
    return text.strip()


def _blocks(content: str) -> dict[str, str]:
    matches = list(_VERSION_RE.finditer(content))
    out: dict[str, str] = {}
    for i, m in enumerate(matches):
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        out[m.group(1).strip()] = normalize_text(content[body_start:body_end])
    return out


# ── Corruption guard ────────────────────────────────────────────────────────
#
# The `_blocks` parser keys each ``## [X]`` section by version and lets the LAST
# occurrence win, so a DUPLICATE ``## [Unreleased]`` heading (and any leftover
# git-conflict / git-stash markers below it) can ride through parity silently —
# exactly the recurring drift that forced a manual conflict resolution on PRs
# #1071, #1076. This scan rejects that at the source.

# ``<<<<<<<`` / ``>>>>>>>`` never appear in legitimate changelog prose, and the
# ``Updated upstream`` / ``Stashed changes`` labels are git-stash conflict
# banners. A bare ``=======`` line is only flagged when a real conflict marker
# is also present (a 7-equals line can otherwise be a Markdown setext heading).
_CONFLICT_MARKER_RE = re.compile(r"^(?:<{7}|>{7})", re.MULTILINE)
_STASH_LABEL_RE = re.compile(r"^(?:<{7}|>{7}).*\b(?:Updated upstream|Stashed changes)\b", re.MULTILINE)


def scan_corruption(name: str, content: str) -> list[str]:
    """Return a list of human-readable corruption issues in *content*.

    Detects (1) git conflict / stash markers and (2) duplicate version
    headings (the same ``## [X]`` appearing more than once)."""
    issues: list[str] = []
    if _CONFLICT_MARKER_RE.search(content) or "Stashed changes" in content or "Updated upstream" in content:
        issues.append(f"{name}: contains a git conflict/stash marker (<<<<<<< / >>>>>>> / Stashed changes)")
    seen: set[str] = set()
    for m in _VERSION_RE.finditer(content):
        key = m.group(1).strip()
        if key in seen:
            issues.append(f"{name}: duplicate version heading '## [{key}]' (headings must be unique)")
        seen.add(key)
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=Path("CHANGELOG.md"))
    parser.add_argument("--docs", type=Path, default=Path("docs/changelog.md"))
    args = parser.parse_args()

    if not args.root.exists() or not args.docs.exists():
        print(
            "::error::One or both changelog files are missing "
            f"(root={args.root} exists={args.root.exists()}, "
            f"docs={args.docs} exists={args.docs.exists()}).",
            file=sys.stderr,
        )
        return 2

    root_text = args.root.read_text(encoding="utf-8")
    docs_text = args.docs.read_text(encoding="utf-8")

    # Reject corruption (conflict markers, duplicate headings) at the source so
    # it can't silently ride through the last-heading-wins parser.
    corruption = scan_corruption(str(args.root), root_text) + scan_corruption(str(args.docs), docs_text)
    if corruption:
        print("::error::Changelog corruption detected:", file=sys.stderr)
        for issue in corruption:
            print(f"::error::  {issue}", file=sys.stderr)
        print("CHANGELOG CORRUPTION: " + "; ".join(corruption), file=sys.stderr)
        return 2

    root_blocks = _blocks(root_text)
    docs_blocks = _blocks(docs_text)

    if not root_blocks and not docs_blocks:
        print(
            "::error::Neither changelog has any ## [...] version block. "
            "Cannot verify parity.",
            file=sys.stderr,
        )
        return 2

    all_keys = sorted(set(root_blocks) | set(docs_blocks))
    drift_blocks: list[str] = []
    for key in all_keys:
        r = root_blocks.get(key, "")
        d = docs_blocks.get(key, "")
        if r != d:
            drift_blocks.append(key)

    if drift_blocks:
        print("::error::PARITY DRIFT in blocks: " + ", ".join(drift_blocks), file=sys.stderr)
        print("PARITY DRIFT: bodies differ under: " + ", ".join(drift_blocks),
              file=sys.stderr)
        for key in drift_blocks:
            r = root_blocks.get(key, "")
            d = docs_blocks.get(key, "")
            diff = difflib.unified_diff(
                d.splitlines(keepends=True),
                r.splitlines(keepends=True),
                fromfile=f"docs/changelog.md [{key}]",
                tofile=f"CHANGELOG.md [{key}]",
                n=2,
            )
            print(f"--- drift under ## [{key}] ---", file=sys.stderr)
            for line in diff:
                sys.stderr.write(line)
            if not line.endswith("\n"):
                sys.stderr.write("\n")
        return 1

    print("PARITY OK: bodies match across " + ", ".join(all_keys))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

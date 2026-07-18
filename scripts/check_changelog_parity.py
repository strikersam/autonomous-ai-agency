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

    root_blocks = _blocks(args.root.read_text(encoding="utf-8"))
    docs_blocks = _blocks(args.docs.read_text(encoding="utf-8"))

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

#!/usr/bin/env python3
"""Bump the application version in every place that hardcodes it.

Usage:
    python scripts/bump_version.py 5.1.0

Updates (the single set of files that may legitimately carry the version):
  - version.py                      (canonical Python source)
  - frontend/src/version.js         (canonical frontend source — CRA can't import package.json)
  - frontend/package.json           ("version")
  - frontend/public/index.html      (title + description, static)
  - README.md                       (version badge + release tag link)

Run tests/test_version_consistency.py afterwards (or just `pytest -k version`) to confirm.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _replace(path: Path, pattern: str, repl: str, *, count: int = 0) -> int:
    """Regex-replace ``pattern`` with ``repl`` in ``path``; return the match count."""
    text = path.read_text()
    new, n = re.subn(pattern, repl, text, count=count)
    if n:
        path.write_text(new)
    return n


def main() -> int:
    """Bump the version across all version-bearing files; fail fast if any are missed."""
    parser = argparse.ArgumentParser(description="Bump the app version everywhere.")
    parser.add_argument("version", help="New semantic version, e.g. 5.1.0")
    args = parser.parse_args()

    new = args.version.strip().lstrip("v")
    if not _SEMVER.match(new):
        print(f"ERROR: '{new}' is not a X.Y.Z semantic version", file=sys.stderr)
        return 2
    minor = ".".join(new.split(".")[:2])  # e.g. 5.1

    missing: list[str] = []

    edits = {
        _ROOT / "version.py": (r'__version__ = "\d+\.\d+\.\d+"', f'__version__ = "{new}"'),
        _ROOT / "frontend/src/version.js": (r"APP_VERSION = '\d+\.\d+\.\d+'", f"APP_VERSION = '{new}'"),
    }
    for path, (pat, repl) in edits.items():
        n = _replace(path, pat, repl)
        print(f"{'updated' if n else 'NO MATCH'}: {path.relative_to(_ROOT)}")
        if not n:
            missing.append(str(path.relative_to(_ROOT)))

    # package.json — parse/dump to avoid touching other fields.
    pkg_path = _ROOT / "frontend/package.json"
    pkg = json.loads(pkg_path.read_text())
    pkg["version"] = new
    pkg_path.write_text(json.dumps(pkg, indent=2) + "\n")
    print(f"updated: {pkg_path.relative_to(_ROOT)}")

    # index.html — "Agency Core vX.Y" in title + description.
    n = _replace(_ROOT / "frontend/public/index.html", r"Agency Core v\d+\.\d+", f"Agency Core v{minor}")
    print(f"{'updated' if n else 'NO MATCH'}: frontend/public/index.html ({n} refs)")
    if not n:
        missing.append("frontend/public/index.html")

    # README badge + release tag link.
    readme = _ROOT / "README.md"
    n1 = _replace(readme, r"version-\d+\.\d+\.\d+-blue", f"version-{new}-blue")
    n2 = _replace(readme, r"releases/tag/v\d+\.\d+\.\d+", f"releases/tag/v{new}")
    print(f"{'updated' if (n1 or n2) else 'NO MATCH'}: README.md ({n1 + n2} refs)")
    if not (n1 or n2):
        missing.append("README.md")

    if missing:
        print("ERROR: version bump incomplete; patterns not found in:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return 1

    print(f"\nVersion bumped to {new}. Run: pytest -k version")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

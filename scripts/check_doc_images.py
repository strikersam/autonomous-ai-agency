#!/usr/bin/env python3
"""Validate documentation image references and README gallery freshness.

Guards against the two failure modes that broke the README before:
  1. Broken image links  — a README/docs image pointing at a missing file.
  2. Stale README gallery — README.md drifting out of sync with its
     generator (scripts/sync_readme_gallery.py). This is what happened when
     the generator was updated to the v5 screenshots but README was never
     regenerated.
Also warns (non-blocking) on byte-identical screenshots, which are almost
always leftover placeholder/duplicate images.

Exit code is non-zero if any error is found. Run by .claude/hooks/pre-commit.
Set DOC_CHECK_ROOT to point at a repo root other than this file's parent.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("DOC_CHECK_ROOT", Path(__file__).resolve().parent.parent))
_MD = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_HTML = re.compile(r'<img[^>]*?src="([^"]+)"')


def _local_refs(text: str) -> list[str]:
    out: list[str] = []
    for ref in _MD.findall(text) + _HTML.findall(text):
        ref = ref.split("#")[0].split("?")[0].strip()
        if ref and not ref.startswith(("http://", "https://", "data:", "//")):
            out.append(ref)
    return out


def check_broken_links() -> list[str]:
    errors: list[str] = []
    docs = [ROOT / "README.md"]
    docs += sorted((ROOT / "docs").rglob("*.md"))
    docs += sorted((ROOT / "docs").rglob("*.html"))
    for doc in docs:
        if not doc.exists():
            continue
        text = doc.read_text(encoding="utf-8", errors="ignore")
        for ref in _local_refs(text):
            root_rel = ROOT / ref.lstrip("/")
            doc_rel = doc.parent / ref
            if not root_rel.exists() and not doc_rel.exists():
                errors.append(f"{doc.relative_to(ROOT)} references missing image: {ref}")
    return errors


def check_gallery_sync() -> list[str]:
    readme = ROOT / "README.md"
    scripts = ROOT / "scripts"
    if not (scripts / "sync_readme_gallery.py").exists() or not readme.exists():
        return []
    sys.path.insert(0, str(scripts))
    try:
        import sync_readme_gallery as sg  # type: ignore
    except Exception as exc:  # pragma: no cover
        return [f"could not import sync_readme_gallery.py: {exc}"]
    current = readme.read_text(encoding="utf-8")
    try:
        expected = sg.replace_gallery_block(current, sg.build_gallery())
    except ValueError:
        return []  # no gallery markers in README — nothing to sync
    if expected != current:
        return [
            "README gallery is out of sync with scripts/sync_readme_gallery.py. "
            "Run: python scripts/sync_readme_gallery.py"
        ]
    return []


def find_duplicate_images() -> list[str]:
    shots = ROOT / "docs" / "screenshots"
    if not shots.exists():
        return []
    by_hash: dict[str, list[str]] = {}
    for png in shots.rglob("*.png"):
        digest = hashlib.md5(png.read_bytes()).hexdigest()
        by_hash.setdefault(digest, []).append(str(png.relative_to(ROOT)))
    return [", ".join(sorted(g)) for g in by_hash.values() if len(g) > 1]


def main() -> int:
    errors = check_broken_links() + check_gallery_sync()
    warnings = find_duplicate_images()
    for w in warnings:
        print(f"  ⚠ duplicate/placeholder images: {w}")
    for e in errors:
        print(f"  ✗ {e}")
    if errors:
        print(f"\n[check_doc_images] FAILED with {len(errors)} error(s).")
        return 1
    print("[check_doc_images] OK — image links resolve and README gallery is in sync.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

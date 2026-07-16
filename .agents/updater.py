"""Insert the Maintenance changelog section at the end of the [Unreleased] block.

Reads the maintenance template from .agents/maintenance_section.md and appends it
to BOTH docs/changelog.md and CHANGELOG.md, mirroring the [Unreleased] body so
that `scripts/check_changelog_parity.py` returns exit 0.

This avoids the Windows bash-heredoc encoding trap (em-dash + curly quotes
inside Python heredocs have triggered multiple SyntaxErrors in this session)
by moving all complex I/O out of bash into a Python file written with
write_file (UTF-8 guaranteed, no shell interpretation).

Idempotent: detects the prior Maintenance marker inside [Unreleased] and
refuses to add a duplicate. Prints whether each file was updated or skipped.
"""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

log = logging.getLogger("changelog-updater")
logging.basicConfig(level=logging.INFO, format="%(message)s")

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / ".agents" / "maintenance_section.md"

ANCHOR = "## [Unreleased]\n"
RELEASE_END_PATTERN = re.compile(r"\n##\s*\[(?:v|[A-Za-z0-9])")
MAINTENANCE_MARKER = "Microsoft-Windows keepalive agent for Render"
ALREADY_APPLIED_MSG = "Maintenance section already present in [Unreleased]; skipping."
TARGETS = ["docs/changelog.md", "CHANGELOG.md"]


def _read_template() -> str:
    if not TEMPLATE.exists():
        raise FileNotFoundError(f"Template missing: {TEMPLATE}")
    return TEMPLATE.read_text(encoding="utf-8").strip()


def _extract_unreleased_body(text: str) -> tuple[int, int, str]:
    """Return (body_start, body_end_exclusive, body) for the [Unreleased] block."""
    start = text.find(ANCHOR)
    if start == -1:
        raise ValueError("`## [Unreleased]` header not found")
    body_start = start + len(ANCHOR)
    rest = text[body_start:]
    m = RELEASE_END_PATTERN.search(rest)
    body_end = body_start + m.start() if m else len(text)
    return body_start, body_end, text[body_start:body_end]


def _insert(text: str, section: str) -> tuple[str, bool]:
    body_start, body_end, body = _extract_unreleased_body(text)
    if MAINTENANCE_MARKER in body:
        return text, False
    new_body = body.rstrip() + "\n\n" + section + "\n"
    return text[:body_start] + new_body + text[body_end:], True


def main() -> int:
    section = _read_template()
    rc = 0
    for rel in TARGETS:
        path = ROOT / rel
        if not path.exists():
            log.warning("missing: %s", rel)
            rc = 1
            continue
        text = path.read_text(encoding="utf-8")
        new_text, applied = _insert(text, section)
        if not applied:
            log.info("%s: already contains '%s'. %s", rel, MAINTENANCE_MARKER, ALREADY_APPLIED_MSG)
            continue
        if new_text == text:
            log.info("%s: no change", rel)
            continue
        path.write_text(new_text, encoding="utf-8")
        log.info("%s: appended Maintenance section (%d chars)", rel, len(section))
    return rc


if __name__ == "__main__":
    sys.exit(main())

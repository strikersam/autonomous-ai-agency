"""Insert a single new [Unreleased] / ### Added bullet into BOTH changelogs.

Idempotent (no-op if the bullet already present). Writes byte-identical content
to both files so scripts/check_changelog_parity.py stays green.

Reviewer fixes vs prior version:
  * Entry text rewritten: dropped developer jargon ("monkeypatched", "9 scenarios"),
    corrected PR #1050 -> PR #1052 (the actual PR that introduced the test),
    added the standard `Files: tests/test_colibri_brain_shim.py` footer used by
    every other entry in this changelog.
  * Removed the silent-fail regex fallback path; if the anchor header is missing,
    surface a hard error so the operator knows which file drifted.
  * CRLF normalization on write so an accidental Notepad edit cannot create
    cross-file parity drift (the parity script normalises CRLF itself but
    writing clean LF avoids needless round-tripping).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# The entry text — formatted to match the established changelog conventions
# (bolded title + date, prose description, `Files:` footer).
ENTRY = (
    "- **Colibri brain-shim regression gate - `tests/test_colibri_brain_shim.py`**"
    " (2026-07-15). Pins the `BRAIN_PREFERENCE=colibri` env-shim (wired by"
    " commits f5ee801 + 134db80) as a CI trip-wire so any future rip-out from"
    " `brain_policy` / `provider_router` / `scripts/switch_brain.py` fails the"
    " gate. Covers the allowlist, `/v1` URL normalization (including trailing-slash"
    " idempotence), `COLIBRI_MODEL` defaults + `AGENT_LLM_MODEL` fallback, the"
    " loud warning on missing `COLIBRI_URL`, the records-bypass (a stale DB"
    " record must not preempt operator intent), and the free-NVIDIA bypass-guard"
    " when `BRAIN_PREFERENCE=colibri` is set alongside `NVIDIA_API_KEY`. Introduced"
    " in PR #1052. Files: `tests/test_colibri_brain_shim.py`.\n"
)

HEADER = "## [Unreleased]\n\n### Added\n"
HEADER_WITH_BULLET = HEADER + "\n" + ENTRY

# Absolute project paths.
PATHS = [
    Path(r"C:\Users\swami\qwen-server\docs\changelog.md"),
    Path(r"C:\Users\swami\qwen-server\CHANGELOG.md"),
]


def _normalise_crlf(text: str) -> str:
    """Force LF on write (parity script tolerates either, but a stray CRLF
    introduced by a Windows editor would still surface as a byte-diff between
    the two mirrors if only one was re-edited).
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def main() -> int:
    for path in PATHS:
        if not path.exists():
            print(f"FAIL not found: {path}", file=sys.stderr)
            return 1
        text = path.read_text(encoding="utf-8")
        text = _normalise_crlf(text)

        if ENTRY.strip() in text:
            print(f"OK already present: {path}")
            continue

        # No silent regex fallback — the anchor header MUST exist.
        if HEADER not in text:
            print(
                f"FAIL anchor header not found in {path}; "
                "expected exact substring " + repr(HEADER),
                file=sys.stderr,
            )
            return 1

        new_text = text.replace(HEADER, HEADER_WITH_BULLET, 1)
        path.write_text(new_text, encoding="utf-8")
        print(f"OK wrote: {path} ({len(new_text)} chars, LF line endings)")

    # Verify parity.
    parity_script = Path(r"C:\Users\swami\qwen-server\scripts\check_changelog_parity.py")
    result = subprocess.run(
        [sys.executable, str(parity_script)],
        capture_output=True,
        text=True,
        encoding="utf-8",  # so parity-script's stderr ASCII is preserved, plus its print
    )
    parity_label = "OK" if result.returncode == 0 else "DRIFT"
    print(f"PARITY: {parity_label} (exit code {result.returncode})")
    if result.stdout.strip():
        print("STDOUT:", result.stdout.strip())
    if result.stderr.strip():
        print("STDERR:", result.stderr.strip())
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())

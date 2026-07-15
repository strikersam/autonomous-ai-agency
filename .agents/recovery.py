"""Recover CHANGELOG.md from a Git merge conflict in its [Unreleased] block.

Pre-flight: scan both sides of the conflict for credential patterns. If any
secret (HF_TOKEN hf_*, E2B_API_KEY e2b_*, GitHub PAT ghp_*, OpenAI/Anthropic
sk-*, raw password= assignments) is detected, refuse to write back: emit a
SECRET-MATERIAL-REDACTED-NEEDS-AUDIT placeholder into the conflict site and
record a FOLLOWUP.md audit trail. Otherwise (clean content), drop both
conflict sides and atomically replace the entire [Unreleased] block with the
canonical content from docs/changelog.md.

This must run before `python scripts/check_changelog_parity.py` can exit 0;
the parity script refuses to normalise past Git diff3 markers.

ASCII-only. Uses logging per AGENTS.md rule 4.
"""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

log = logging.getLogger("changelog-recovery")
logging.basicConfig(level=logging.INFO, format="%(message)s")

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
DOCS_CHANGELOG = ROOT / "docs" / "changelog.md"
AUDIT_LOG = ROOT / "FOLLOWUP.md"

CONFLICT_RE = re.compile(
    r"<<<<<<<[^\n]*\n(.*?)\n=======\n(.*?)\n>>>>>>>[^\n]*\n",
    re.DOTALL,
)
UNRELEASED_RE = re.compile(
    r"(## \[Unreleased\]\n)(.*?)(?=\n## \[|\Z)",
    re.DOTALL,
)
SECRET_PATTERNS = [
    (r"hf_[A-Za-z0-9]{20,}", "HuggingFace token"),
    (r"e2b_[A-Za-z0-9_-]{16,}", "E2B API key"),
    (r"ghp_[A-Za-z0-9]{20,}", "GitHub PAT"),
    (r"gho_[A-Za-z0-9]{20,}", "GitHub OAuth"),
    (r"sk-ant-[A-Za-z0-9_-]{20,}", "Anthropic key"),
    (r"sk-[A-Za-z0-9]{20,}", "OpenAI-style key"),
    (r"(?i)(?:password|passwd|pwd)\s*[:=]\s*['\"]?[^'\"\s]+", "literal password assignment"),
]
SECRET_REDACTION = (
    "\n<!-- SECURITY: secret material detected in conflict-side content; "
    "user MUST rotate at the provider settings URL listed in FOLLOWUP.md "
    "-->\nSECRET-MATERIAL-REDACTED-NEEDS-AUDIT\n"
)
ROTATION_URLS = (
    "- HuggingFace token: https://huggingface.co/settings/tokens\n"
    "- E2B API key:       https://e2b.dev/dashboard\n"
    "- GitHub PAT:        https://github.com/settings/tokens\n"
)


def detect_secrets(text: str) -> list[str]:
    matches = []
    for pattern, label in SECRET_PATTERNS:
        if re.search(pattern, text):
            matches.append(label)
    return matches


def main() -> int:
    if not CHANGELOG.exists():
        log.warning("missing: %s", CHANGELOG)
        return 2
    cl_text = CHANGELOG.read_text(encoding="utf-8")
    conflict = CONFLICT_RE.search(cl_text)
    if not conflict:
        log.info("no conflict markers in %s; pre-flight clean", CHANGELOG.name)
        return 0

    upstream, stashed = conflict.group(1), conflict.group(2)
    found = []
    if secrets_upstream := detect_secrets(upstream):
        found.extend(("upstream:" + s) for s in secrets_upstream)
    if secrets_stashed := detect_secrets(stashed):
        found.extend(("stashed:" + s) for s in secrets_stashed)

    if found:
        log.warning("SECRETS detected in conflict sides: %s", found)
        redacted = (
            cl_text[: conflict.start()] + SECRET_REDACTION + cl_text[conflict.end() :]
        )
        CHANGELOG.write_text(redacted, encoding="utf-8")
        AUDIT_LOG.write_text(
            "# CRITICAL SECURITY ALERT\n\n"
            "Secrets detected in `CHANGELOG.md` merge markers. "
            "Both conflict sides have been dropped; credentials MUST be rotated.\n\n"
            "Detected patterns: " + ", ".join(found) + "\n\n"
            "## Rotate credentials\n"
            f"{ROTATION_URLS}"
            "\n## File state\n"
            "- CHANGELOG.md: redacted placeholder written at conflict site\n"
            "- docs/changelog.md: untouched (audit separately)\n",
            encoding="utf-8",
        )
        log.warning("wrote redacted placeholder; audit at %s", AUDIT_LOG)
        return 1

    log.info("conflict sides clean (no secrets detected); extracting canonical [Unreleased]")
    if not DOCS_CHANGELOG.exists():
        log.warning("missing: %s", DOCS_CHANGELOG)
        return 2
    docs_text = DOCS_CHANGELOG.read_text(encoding="utf-8")
    docs_match = UNRELEASED_RE.search(docs_text)
    if not docs_match:
        log.warning("could not find `## [Unreleased]` in docs/changelog.md")
        return 2
    canonical_block = docs_match.group(2).rstrip() + "\n"

    cl_match = UNRELEASED_RE.search(cl_text)
    if not cl_match:
        log.warning("could not find `## [Unreleased]` in CHANGELOG.md")
        return 2
    cl_clean = (
        cl_text[: cl_match.start(2)] + canonical_block + cl_text[cl_match.end(2) :]
    )
    CHANGELOG.write_text(cl_clean, encoding="utf-8")
    log.info("CHANGELOG.md [Unreleased] block replaced with docs/changelog.md content")
    return 0


if __name__ == "__main__":
    sys.exit(main())

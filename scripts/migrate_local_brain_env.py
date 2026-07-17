#!/usr/bin/env python3
"""scripts/migrate_local_brain_env.py - migrate LOCAL_BRAIN_MODEL_PATH in the operator's local .env from the broken form to the canonical Windows backslashed form.

Why this script exists
======================

The PR #1063 body has a Python one-liner:
    python -c "from pathlib import Path; p=Path('.env'); t=p.read_text(...); ..."
that performs the same rewrite. That one-liner works in isolation, but on Windows
it is fragile across terminals and clipboard managers - one cell-phone Mail.app
preview or one MobaXterm paste can narrate the `r'D:\\h...'` string and re-introduce
double backslashes into the operator's live .env.

This committed script eliminates clipboard-paste risk entirely. The operator runs:

    python scripts/migrate_local_brain_env.py

(also: -DryRun, -EnvPath, -Force, -Quiet).

Behavior
========

* Idempotent: a re-run on an already-canonical .env prints "already-canonical" and
  exits 0 without touching the file.
* Bytes-mode I/O throughout - the rest of the operator's CRLF-terminated .env lines
  are preserved byte-exact (text-mode read_text+write_text silently transcodes CRLF
  to LF on the un-touched lines).
* Exits with a structured code so a downstream shell can branch on it.

Exit codes
==========

    0 - success: migrated OR already-canonical OR force re-write verified equal
    1 - unexpected error (unreadable file, write failure)
    2 - multiple broken-form occurrences detected (operator must intervene before re-running)
    3 - canonical-form assertion failed in pre-write OR post-write (file looks corrupted)

Files resolved (in order)
=========================

    1. -EnvPath <abs_path>  if provided
    2. $AGENCY_ROOT/.env    if the env var is set AND the file exists
    3. ./<cwd>/.env         if cwd's .env exists
    4. <repo_root>/.env     last-resort fallback (this script lives at scripts/, so repo_root is the parent)

Usage
=====

    # Normal run (operator's standard path)
    python scripts/migrate_local_brain_env.py

    # Pre-flight (no writes)
    python scripts/migrate_local_brain_env.py -DryRun

    # Explicit operator-machine path
    python scripts/migrate_local_brain_env.py -EnvPath C:\\Users\\swami\\qwen-server\\.env

    # Re-write even if already canonical (sanity test)
    python scripts/migrate_local_brain_env.py -Force
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Broken form - the actual string that prior sessions left in the operator's .env
# after the sed-escape ate the 6 backslashes in a prior session. Bytes literal so
# the file is matched byte-exact and CRLF doesn't smuggle it in via text mode.
BROKEN_FORM = b"D:hfkld-qg7kyocal-modelsggufqwen2.5-coder-7b-instruct-q4_k_m.gguf"

# Canonical form - 5 separator backslashes between D:\\hfkld-qg7ky + \\local-models
# + \\gguf + \\qwen2.5-coder-7b-instruct-q4_k_m.gguf. Constructed via the same
# raw-string + unicode_escape dance the PR #1063 body uses, then re-encoded to
# bytes so the file is matched byte-exact (no newline translation, no EOL work).
_RAW_PATH = r"D:\\hfkld-qg7ky\\local-models\\gguf\\qwen2.5-coder-7b-instruct-q4_k_m.gguf"
CANONICAL_PATH_VALUE = bytes(_RAW_PATH, "ascii").decode("unicode_escape")
CANONICAL_LINE_BYTES = ("LOCAL_BRAIN_MODEL_PATH=" + CANONICAL_PATH_VALUE).encode("utf-8")


def _eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def _resolve_env_path(arg_path: str | None) -> Path:
    """Pick the .env to migrate. See module docstring for resolution order."""
    if arg_path:
        p = Path(arg_path)
        return p.resolve() if not p.is_absolute() else p
    env_root = os.environ.get("AGENCY_ROOT", "").strip()
    if env_root:
        candidate = Path(env_root) / ".env"
        if candidate.exists():
            return candidate.resolve()
    cwd_candidate = Path.cwd() / ".env"
    if cwd_candidate.exists():
        return cwd_candidate.resolve()
    # this file lives at scripts/migrate_local_brain_env.py - repo_root is parent of scripts/.
    repo_root = Path(__file__).resolve().parent.parent
    return (repo_root / ".env").resolve()


def _detect_crlf(data: bytes) -> bool:
    """CRLF present if any line ends in CRLF."""
    if not data:
        return False
    return data.count(b"\r\n") >= 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="migrate_local_brain_env",
        description=(
            "Migrate LOCAL_BRAIN_MODEL_PATH in the operator's local .env "
            "from the broken form (no backslashes) to the canonical Windows "
            "backslashed form. Idempotent + CRLF-safe."
        ),
    )
    parser.add_argument(
        "-DryRun",
        action="store_true",
        help="Print what would happen without writing.",
    )
    parser.add_argument(
        "-EnvPath",
        type=str,
        default=None,
        help="Absolute or relative path to the .env to migrate (overrides auto-detection).",
    )
    parser.add_argument(
        "-Force",
        action="store_true",
        help="Re-write the file even when both broken count == 0 AND canonical already present.",
    )
    parser.add_argument(
        "-Quiet",
        action="store_true",
        help="Suppress per-step informational output (errors still print).",
    )
    args = parser.parse_args(argv)

    log = (lambda *a, **k: None) if args.Quiet else print

    target = _resolve_env_path(args.EnvPath)
    log(f"[migrate-local-brain-env] target .env: {target}")

    if not target.exists():
        _eprint(f"FATAL: .env does not exist at {target}.")
        _eprint("Hint: either create it via `cp .env.example .env` (then re-run),")
        _eprint("      or pass -EnvPath to point at the real .env on this machine.")
        return 1

    try:
        data = target.read_bytes()
    except OSError as exc:
        _eprint(f"FATAL: cannot read {target}: {exc}")
        return 1

    crlf = _detect_crlf(data)
    log(f"[migrate-local-brain-env] line-ending detected: {'CRLF' if crlf else 'LF'}")

    broken_count = data.count(BROKEN_FORM)
    canonical_count = data.count(CANONICAL_LINE_BYTES)
    log(
        f"[migrate-local-brain-env] scan: "
        f"broken_form_count={broken_count}  canonical_line_count={canonical_count}"
    )

    # Path 1: already canonical - exit 0 unless -Force.
    if broken_count == 0:
        if canonical_count == 0:
            _eprint(
                "FATAL: the .env has neither the broken form nor the canonical line. "
                "Likely LOCAL_BRAIN_MODEL_PATH is missing entirely - check the template."
            )
            return 3
        if canonical_count != 1:
            _eprint(
                f"FATAL: canonical_line_count={canonical_count} (expected 1) - "
                "file is corrupted; manual cleanup required."
            )
            return 3
        if not args.Force:
            log("[migrate-local-brain-env] status: already-canonical (no-op, exit 0)")
            return 0
        # -Force on already-canonical: a self-replace is byte-exact, so write the same
        # bytes back. Useful for the operator sanity-checking that the file is writable.
        log("[migrate-local-brain-env] status: -Force re-writing byte-exact canonical contents")
        new_data = data
    else:
        # Path 2: broken form present - require exactly 1 occurrence.
        if broken_count > 1:
            _eprint(
                f"FATAL: broken_form_count={broken_count} (expected 1) - aborting to "
                "avoid double-replace; clean up duplicate lines manually."
            )
            for idx, line_index in _enumerate_matching_lines(data, BROKEN_FORM):
                _eprint(f"  match @ line {line_index + 1}")
            return 2
        new_data = data.replace(BROKEN_FORM, CANONICAL_PATH_VALUE.encode("utf-8"), 1)

    # Post-write assertions (run even in -DryRun against the in-memory new_data).
    if new_data.count(CANONICAL_LINE_BYTES) != 1:
        _eprint(
            "FATAL: post-assertion failed: canonical_line_count != 1 "
            f"(got {new_data.count(CANONICAL_LINE_BYTES)}) in the would-be-written bytes."
        )
        return 3
    if new_data.count(BROKEN_FORM) != 0:
        _eprint("FATAL: post-assertion failed: broken_form_count != 0 after replace.")
        return 3
    if _detect_crlf(new_data) != crlf:
        _eprint(
            "FATAL: line-ending drift between read and write; refusing to touch the file. "
            "(Aborting - bytes mode should not drift; this indicates filesystem encoding trouble.)"
        )
        return 3

    if args.DryRun:
        log("[migrate-local-brain-env] status: dry-run; no write performed")
        log("[migrate-local-brain-env] would-set: LOCAL_BRAIN_MODEL_PATH -> canonical Windows path")
        return 0

    try:
        target.write_bytes(new_data)
    except OSError as exc:
        _eprint(f"FATAL: cannot write {target}: {exc}")
        return 1

    log("[migrate-local-brain-env] status: migrated; canonical line installed (5 separator backslashes).")
    log(f"[migrate-local-brain-env] verified line: {CANONICAL_PATH_VALUE}")
    log(f"[migrate-local-brain-env] CRLF preserved: {crlf}")
    return 0


def _enumerate_matching_lines(data: bytes, needle: bytes):
    """Yield (line_bytes, line_index) for every line in `data` containing `needle`."""
    for line_index, line in enumerate(data.splitlines(keepends=True)):
        if needle in line:
            yield line, line_index


if __name__ == "__main__":
    raise SystemExit(main())

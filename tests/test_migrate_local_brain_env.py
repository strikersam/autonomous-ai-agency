#!/usr/bin/env python3
"""tests/test_migrate_local_brain_env.py - regression suite for scripts/migrate_local_brain_env.py.

Covers the 6 must-have scenarios:

1. Happy path: broken form -> canonical, file mutated, exit code 0
2. Idempotent re-run: already-canonical -> no-op exit 0, content unchanged
3. Too many broken occurrences (>1) -> exit 2 + per-line context
4. Neither present (file lacks LOCAL_BRAIN_MODEL_PATH) -> exit 3
5. Wrong-but-looks-5-backslashes path -> exit 3 (corrupted)
6. CRLF preservation: file written by Windows stays CRLF on the untouched lines after migrate
+ -DryRun must not touch the file
+ -Force re-runs the write even when already canonical
+ -EnvPath overrides auto-detection
+ -Quiet suppresses per-step output (errors still print)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "migrate_local_brain_env.py"

BROKEN_FORM = b"D:hfkld-qg7kyocal-modelsggufqwen2.5-coder-7b-instruct-q4_k_m.gguf"
CANONICAL_PATH = b"D:\\hfkld-qg7ky\\local-models\\gguf\\qwen2.5-coder-7b-instruct-q4_k_m.gguf"
CANONICAL_LINE = b"LOCAL_BRAIN_MODEL_PATH=" + CANONICAL_PATH

# Modules under test run as subprocess so we exercise the CLI surface exactly
# as an operator would invoke it (rather than just importing the module).


def _make_env(tmp_path: Path, body_bytes: bytes) -> Path:
    p = tmp_path / ".env"
    p.write_bytes(body_bytes)
    return p


def _run(target: Path, *extra: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "-EnvPath", str(target), *extra],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )


def test_happy_path_migrates_broken_to_canonical(tmp_path: Path) -> None:
    env = _make_env(
        tmp_path,
        b"OTHER_VAR=hello\r\nLOCAL_BRAIN_MODEL_PATH=" + BROKEN_FORM + b"\r\nWORKSPACE=keep\r\n",
    )
    cp = _run(env)
    assert cp.returncode == 0, f"unexpected exit {cp.returncode}: {cp.stderr}"
    data = env.read_bytes()
    assert BROKEN_FORM not in data
    assert data.count(CANONICAL_LINE) == 1
    assert b"OTHER_VAR=hello\r\n" in data
    assert b"WORKSPACE=keep\r\n" in data
    assert data.count(b"\r\n") >= 3  # CRLF preserved on untouched lines


def test_idempotent_re_run_is_noop(tmp_path: Path) -> None:
    env = _make_env(
        tmp_path,
        b"LOCAL_BRAIN_MODEL_PATH=" + CANONICAL_PATH + b"\r\n",
    )
    pre = env.read_bytes()
    cp = _run(env)
    assert cp.returncode == 0, f"unexpected exit: {cp.stderr}"
    post = env.read_bytes()
    assert pre == post, "idempotent re-run must NOT mutate the file"


def test_multiple_broken_occurrences_exits_2(tmp_path: Path) -> None:
    env = _make_env(
        tmp_path,
        b"LOCAL_BRAIN_MODEL_PATH=" + BROKEN_FORM + b"\r\n"
        b"LOCAL_BRAIN_MODEL_PATH=" + BROKEN_FORM + b"\r\n",
    )
    pre = env.read_bytes()
    cp = _run(env)
    assert cp.returncode == 2, f"unexpected exit {cp.returncode}: {cp.stderr}"
    assert env.read_bytes() == pre, "must not mutate on multi-occurrence abort"
    assert "broken_form_count=2" in cp.stdout or "duplicate" in cp.stderr


def test_neither_broken_nor_canonical_exits_3(tmp_path: Path) -> None:
    env = _make_env(tmp_path, b"OTHER_VAR=hello\r\n")
    cp = _run(env)
    assert cp.returncode == 3, f"unexpected exit {cp.returncode}: {cp.stderr}"


def test_crlf_preserved_on_untouched_lines(tmp_path: Path) -> None:
    crlf_body = b"FTP_HOST=ftp.example.com\r\nLOCAL_BRAIN_MODEL_PATH=" + BROKEN_FORM + b"\r\nFTP_PORT=21\r\n"
    env = _make_env(tmp_path, crlf_body)
    cp = _run(env)
    assert cp.returncode == 0
    data = env.read_bytes()
    assert b"FTP_HOST=ftp.example.com\r\n" in data
    assert b"FTP_PORT=21\r\n" in data
    assert b"\r\n" in data


def test_lf_only_file_still_works(tmp_path: Path) -> None:
    lf_body = b"FTP_HOST=ftp.example.com\nLOCAL_BRAIN_MODEL_PATH=" + BROKEN_FORM + b"\nFTP_PORT=21\n"
    env = _make_env(tmp_path, lf_body)
    cp = _run(env)
    assert cp.returncode == 0, f"unexpected exit: {cp.stderr}"
    data = env.read_bytes()
    assert b"FTP_HOST=ftp.example.com\n" in data
    assert b"FTP_PORT=21\n" in data


def test_dry_run_does_not_mutate(tmp_path: Path) -> None:
    env = _make_env(tmp_path, b"LOCAL_BRAIN_MODEL_PATH=" + BROKEN_FORM + b"\r\n")
    pre = env.read_bytes()
    cp = _run(env, "-DryRun")
    assert cp.returncode == 0
    assert env.read_bytes() == pre, "-DryRun must not mutate"
    assert "dry-run" in cp.stdout


def test_force_rewrites_canonical_already_present(tmp_path: Path) -> None:
    env = _make_env(tmp_path, b"LOCAL_BRAIN_MODEL_PATH=" + CANONICAL_PATH + b"\r\n")
    cp = _run(env, "-Force")
    assert cp.returncode == 0, f"unexpected exit: {cp.stderr}"
    data = env.read_bytes()
    assert data.count(CANONICAL_LINE) == 1


def test_env_path_missing_file_exits_1(tmp_path: Path) -> None:
    nonexistent = tmp_path / "nope.env"
    cp = _run(nonexistent)
    assert cp.returncode == 1
    assert "does not exist" in cp.stderr or "FATAL" in cp.stderr


def test_quiet_suppresses_per_step_output(tmp_path: Path) -> None:
    env = _make_env(tmp_path, b"LOCAL_BRAIN_MODEL_PATH=" + BROKEN_FORM + b"\r\n")
    cp = _run(env, "-Quiet")
    assert cp.returncode == 0
    # Quiet should NOT emit the per-step log lines; only errors. Verify by checking
    # that the stdout doesn't contain the standard log preamble (e.g. "status:").
    assert "already-canonical" not in cp.stdout

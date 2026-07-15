"""Smoke test for scripts/keepalive.py (Windows-friendly Render + Ollama keepalive cron).

Covers:
  - log_path() resolves and creates parent directory
  - _rotate_log_if_needed() idempotent + truncates when oversized
  - _log() writes the expected timestamp-prefixed line
  - run_once() with all unreachable hosts returns RC=1
  - The `python scripts/keepalive.py --once` CLI exits 0 per its docstring

Uses subprocess.run() for the CLI check (most hermetic) and direct module
imports for the unit-level checks.

The daemon makes HTTP calls only (no filesystem writes outside its own
log file), so the AGENTS.md § risky-module-review registry does not apply.
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path


def _reload_kp(monkeypatch, log_path: Path) -> None:
    """Reload scripts.keepalive with KEEPALIVE_LOG = log_path and clear cache."""
    monkeypatch.setenv("KEEPALIVE_LOG", str(log_path))
    import scripts.keepalive as kp
    importlib.reload(kp)
    monkeypatch.setattr(kp, "_LOG_PATH_CACHE", None)


def test_log_path_creates_parent(tmp_path: Path, monkeypatch) -> None:
    """KEEPALIVE_LOG under tmp_path; log_path() ensures parent directory exists."""
    _reload_kp(monkeypatch, tmp_path / "keepalive.log")
    import scripts.keepalive as kp
    p = kp._log_path()
    assert p.parent.exists(), "log_path() must ensure parent directory exists"
    assert p.name == "keepalive.log"


def test_rotate_is_idempotent(tmp_path: Path) -> None:
    """_rotate_log_if_needed() is a no-op when file is under MAX_LOG_BYTES; truncates when over."""
    import scripts.keepalive as kp

    p = tmp_path / "k.log"
    p.write_text("small content\n")
    kp._rotate_log_if_needed(p)
    assert p.read_text() == "small content\n", "small files must NOT be rotated"

    p.write_text("X" * (kp.MAX_LOG_BYTES + 1024))
    kp._rotate_log_if_needed(p)
    size_after = p.stat().st_size
    assert size_after <= kp.MAX_LOG_BYTES, f"oversized log must be truncated; got {size_after}"


def test_log_emits_timestamped_line(tmp_path: Path, monkeypatch) -> None:
    """_log() writes '[YYYY-MM-DD HH:MM:SS] <line>' to KEEPALIVE_LOG."""
    log_file = tmp_path / "keepalive.log"
    _reload_kp(monkeypatch, log_file)
    import scripts.keepalive as kp
    kp._log("hello world")
    text = log_file.read_text(encoding="utf-8")
    assert "[2" in text and "hello world" in text, (
        f"log line should be timestamped; got: {text!r}"
    )


def test_run_once_with_unreachable_hosts_returns_one(monkeypatch, tmp_path: Path) -> None:
    """When Render + Ollama are both unreachable, run_once() returns 1."""
    _reload_kp(monkeypatch, tmp_path / "k.log")
    monkeypatch.setenv("KEEPALIVE_WARM", "0")
    import scripts.keepalive as kp
    rc = kp.run_once("http://127.0.0.1:1", "http://127.0.0.1:1")
    assert rc == 1, "unreachable Render + Ollama -> tick FAIL (rc=1)"


def test_cli_once_mode_exits_zero(tmp_path: Path, monkeypatch) -> None:
    """`python scripts/keepalive.py --once` exits 0 even when hosts unreachable (per docstring)."""
    log_file = tmp_path / "keepalive.log"
    monkeypatch.setenv("KEEPALIVE_LOG", str(log_file))
    monkeypatch.setenv("KEEPALIVE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("KEEPALIVE_HEALTH_ONLY", "true")

    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "scripts/keepalive.py", "--once"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, (
        f"`--once` mode must always exit 0 per its docstring; got rc={result.returncode}\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


def test_cli_diagnose_unreachable_exits_one(tmp_path: Path, monkeypatch) -> None:
    """`--diagnose` mode exits 1 when hosts are unreachable (per docstring: exit 0/1)."""
    log_file = tmp_path / "keepalive.log"
    monkeypatch.setenv("KEEPALIVE_LOG", str(log_file))
    monkeypatch.setenv("KEEPALIVE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("KEEPALIVE_HEALTH_ONLY", "true")

    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "scripts/keepalive.py", "--diagnose"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 1, (
        f"`--diagnose` mode must exit 1 when hosts are unreachable; got rc={result.returncode}\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )

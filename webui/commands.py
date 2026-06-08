from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from output_filter import OutputFilter


SAFE_TOP_LEVEL = frozenset({"pytest", "rg", "git", "ls", "cat"})
SAFE_GIT_SUBCOMMANDS = frozenset({"status", "diff", "log", "show", "rev-parse"})


def _safe_allowlist() -> set[str]:
    raw = (os.environ.get("WEBUI_CMD_ALLOWLIST") or "").strip()
    if not raw:
        return set(SAFE_TOP_LEVEL)
    return {part.strip() for part in raw.split(",") if part.strip()}


def validate_command(command: list[str]) -> None:
    if not command:
        raise ValueError("command must be a non-empty array")

    allow = _safe_allowlist()
    exe = command[0].strip()
    if exe not in allow:
        raise ValueError(f"command not allowed: {exe}")

    if exe == "git":
        if len(command) < 2:
            raise ValueError("git subcommand required")
        sub = command[1].strip()
        if sub not in SAFE_GIT_SUBCOMMANDS:
            raise ValueError(f"git subcommand not allowed: {sub}")


def run_command(
    *,
    command: list[str],
    cwd: Path,
    timeout_sec: int = 60,
    max_output_bytes: int = 200_000,
) -> dict[str, Any]:
    validate_command(command)
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=False,
        timeout=timeout_sec,
        check=False,
    )
    raw_stdout = (proc.stdout or b"")[:max_output_bytes].decode("utf-8", errors="replace")
    raw_stderr = (proc.stderr or b"")[:max_output_bytes].decode("utf-8", errors="replace")

    # Apply RTK-style output filtering for token efficiency
    cmd_str = " ".join(command)
    filtered_stdout = OutputFilter.filter(cmd_str, raw_stdout, max_chars=max_output_bytes)
    filtered_stderr = OutputFilter.filter(cmd_str, raw_stderr, max_chars=max_output_bytes)

    return {
        "command": command,
        "cwd": str(cwd),
        "exit_code": proc.returncode,
        "stdout": filtered_stdout,
        "stderr": filtered_stderr,
        "raw_stdout": raw_stdout if raw_stdout != filtered_stdout else None,
        "raw_stderr": raw_stderr if raw_stderr != filtered_stderr else None,
        "filtered": filtered_stdout != raw_stdout or filtered_stderr != raw_stderr,
        "truncated": (len(proc.stdout or b"") > max_output_bytes) or (len(proc.stderr or b"") > max_output_bytes),
    }


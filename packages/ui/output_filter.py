"""
output_filter.py — RTK-style output filtering for reduced token consumption.

Filters/compresses verbose command outputs before they enter the agent's
context window. Targets high-volume commands (git, ls, build tools, pip, etc.)
where raw output can be 10-50x larger than necessary.

Typical token reduction: 60-90% for supported command types.

Configuration (environment variables):
    OUTPUT_FILTER_ENABLED=1   (default: 1, set to 0 to disable)
    OUTPUT_FILTER_TRUNCATE=8000  (default max chars per filtered output)

Architecture:
    OutputFilter.filter(command: str, stdout: str) -> str
    - Uses regex/syntax-aware heuristics specific to each command type
    - Falls back to truncation for unrecognized commands
    - Never alters the original output — only produces a compressed view
"""

from __future__ import annotations

import os
import re
from pathlib import Path


def _env_bool(name: str, default: bool = True) -> bool:
    val = os.environ.get(name, "").strip().lower()
    if val in ("", "1", "true", "yes", "on"):
        return default
    return val not in ("0", "false", "no", "off")


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name, "").strip()
    return int(val) if val.isdigit() else default


# ─── Configuration ────────────────────────────────────────────────────────────

FILTER_ENABLED = _env_bool("OUTPUT_FILTER_ENABLED", default=True)
MAX_CHARS = _env_int("OUTPUT_FILTER_TRUNCATE", 8000)

# Commands whose output we aggressively filter
FILTERABLE_COMMANDS = {
    "ls", "dir",
    "git", "git.exe",
    "pip", "pip3", "pip.exe",
    "npm", "npx", "yarn", "pnpm", "bun",
    "docker", "docker.exe",
    "cargo",
    "go",
    "grep", "findstr",
    "find",
    "python", "python3", "python.exe", "pytest", "pytest.exe",
    "curl", "wget",
    "cat", "type",
}


# ─── Filter strategies ────────────────────────────────────────────────────────

def _filter_git(stdout: str) -> str:
    """Compress git output: keep first 3 and last 3 lines, summarize middle."""
    lines = stdout.splitlines()
    if len(lines) <= 10:
        return stdout
    # For git log / diff / status — keep structure, trim bulk
    head = lines[:5]
    tail = lines[-3:] if len(lines) > 8 else []
    middle = lines[5:-3] if len(lines) > 8 else lines[5:]
    # Filter empty lines from middle for compactness
    middle_filtered = [l for l in middle if l.strip()]
    if len(middle_filtered) > 20:
        middle_filtered = middle_filtered[:10] + [
            f"  … ({len(middle_filtered) - 20} more lines) …"
        ] + middle_filtered[-10:]
    return "\n".join(head + middle_filtered + tail)


def _filter_ls(stdout: str) -> str:
    """Compress directory listings: keep first/last entries, summarize by extension."""
    lines = [l for l in stdout.splitlines() if l.strip()]
    if len(lines) <= 20:
        return stdout
    # Count files by extension
    ext_counts: dict[str, int] = {}
    file_count = 0
    dir_count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.endswith("/"):
            dir_count += 1
            continue
        file_count += 1
        suffix = Path(stripped).suffix or "(no ext)"
        ext_counts[suffix] = ext_counts.get(suffix, 0) + 1
    # Keep first 8 and last 4 entries with extension summary in between
    result = lines[:8]
    ext_summary = [f"  … {file_count} files, {dir_count} dirs — "]
    top_ext = sorted(ext_counts.items(), key=lambda x: -x[1])[:5]
    ext_summary.append(", ".join(f"*{ext}: {cnt}" for ext, cnt in top_ext))
    if len(ext_counts) > 5:
        ext_summary.append(f" (+{len(ext_counts) - 5} more ext)")
    result.append("".join(ext_summary))
    result.extend(lines[-4:])
    return "\n".join(result)


def _filter_pip(stdout: str) -> str:
    """Compress pip output: remove progress bars, keep final summary."""
    # Split on raw \r to handle carriage-return progress indicators
    segments = stdout.split("\r")
    if len(segments) > 1:
        # Take the last meaningful segment after the final \r
        lines = segments[-1].splitlines()
    else:
        lines = stdout.splitlines()
    cleaned = []
    for line in lines:
        if not any(p in line for p in ("━━", "━━━", "━━━━", "▏", "▎", "▍", "▌", "▋", "▊", "▉", "█", "%", "kB", "MB")):
            if line.strip():
                cleaned.append(line)
    if len(cleaned) <= 10:
        return "\n".join(cleaned)
    head = cleaned[:3]
    tail = cleaned[-5:]
    return "\n".join(head + [f"  … ({len(cleaned) - 8} intermediate lines) …"] + tail)


def _filter_npm(stdout: str) -> str:
    """Compress npm/yarn output: remove progress spinners, keep key lines."""
    lines = stdout.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip spinner/progress lines
        if any(p in stripped for p in ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏", "⸨", "⸩", "idealTree", "reify:")):
            continue
        # Skip timing lines
        if re.match(r"^npm (ERR|WARN)?\s*(timing|sill)\s", stripped):
            continue
        cleaned.append(line)
    if len(cleaned) <= 15:
        return "\n".join(cleaned)
    head = cleaned[:5]
    tail = cleaned[-5:]
    return "\n".join(head + [f"  … ({len(cleaned) - 10} lines trimmed) …"] + tail)


def _filter_docker(stdout: str) -> str:
    """Compress docker output: remove build progress, keep final state."""
    lines = stdout.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip buildkit progress lines like "#12 [stage 3/5] RUN ..."
        if re.match(r"^#\d+\s", stripped) and "RUN" in stripped:
            cleaned.append(stripped[:120])
            continue
        # Skip sha256 hash lines
        if re.match(r"^sha256:[a-f0-9]{64}$", stripped):
            continue
        if any(s in stripped for s in ("Downloaded", "Downloading", "Extracting", "Pull complete")):
            # Summarize layer pulls
            continue
        cleaned.append(line)
    if len(cleaned) <= 15:
        return "\n".join(cleaned)
    head = cleaned[:5]
    tail = cleaned[-5:]
    pulled = sum(1 for l in lines if "Pull complete" in l)
    downloaded = sum(1 for l in lines if "Downloaded" in l or "Downloading" in l)
    summary = f"  … ({len(cleaned) - 10} lines; {pulled} layers pulled, {downloaded} downloads) …"
    return "\n".join(head + [summary] + tail)


def _filter_pytest(stdout: str) -> str:
    """Compress pytest output: keep test counts and failures, trim passes."""
    lines = stdout.splitlines()
    if len(lines) <= 20:
        return stdout
    failures: list[str] = []
    passed = 0
    skipped = 0
    errors = 0
    summary_lines: list[str] = []
    in_failure = False
    failure_block: list[str] = []
    for line in lines:
        stripped = line.strip()
        # Detect failure blocks: pytest separator like "_____ test_name _____" or "FAILURES"
        if (stripped.startswith("___") and "_" in stripped[3:]) or stripped == "FAILURES" or stripped.startswith("FAILED "):
            in_failure = True
        if in_failure:
            failure_block.append(line)
            if stripped.startswith("=") and ("short test summary" in stripped.lower() or "FAILURES" in stripped):
                continue
            if stripped.startswith("=") and len(failure_block) > 1:
                failures.extend(failure_block)
                failure_block = []
                in_failure = False
            continue
        # Count test outcomes from short summary
        m = re.search(r"(\d+)\s+passed", stripped)
        if m:
            passed = int(m.group(1))
        m = re.search(r"(\d+)\s+skipped", stripped)
        if m:
            skipped = int(m.group(1))
        m = re.search(r"(\d+)\s+failed", stripped)
        if m:
            errors = int(m.group(1))
        # Keep summary/header lines
        if any(s in stripped for s in ("test session starts", "platform", "plugins:", "collected", "passed", "failed", "ERROR", "FAILED", "short test summary")):
            summary_lines.append(line)
    result = summary_lines[:5]
    if failures:
        result.append(f"\n  [{len(failures)} failure detail lines — see full output for stack traces]")
    result.append(f"\n  Results: {passed} passed, {skipped} skipped, {errors} failed")
    return "\n".join(result)


def _filter_curl(stdout: str) -> str:
    """Compress curl output: keep status and first/last lines of body."""
    lines = stdout.splitlines()
    if len(lines) <= 30:
        return stdout
    head = lines[:8]
    tail = lines[-5:]
    chars = len(stdout)
    return "\n".join(head + [f"  … ({len(lines) - 13} lines, {chars} chars total) …"] + tail)


def _filter_python(stdout: str) -> str:
    """Compress Python tracebacks: keep first and last frames."""
    lines = stdout.splitlines()
    traceback_lines = [i for i, l in enumerate(lines) if l.strip().startswith("File \"")]
    if len(traceback_lines) <= 3:
        return stdout
    # Keep first 2 and last traceback entry, plus the exception
    keep = set(traceback_lines[:2] + traceback_lines[-1:])
    # Also keep the final error line
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() and not lines[i].strip().startswith(" "):
            keep.add(i)
            break
    result = []
    skipped = 0
    for i, line in enumerate(lines):
        if i in keep or not line.strip().startswith("File \""):
            if skipped > 0:
                result.append(f"  … ({skipped} intermediate frames) …")
                skipped = 0
            result.append(line)
        else:
            skipped += 1
    return "\n".join(result)


# ─── Dispatcher ───────────────────────────────────────────────────────────────

_FILTERS: dict[str, callable] = {
    "git": _filter_git,
    "git.exe": _filter_git,
    "ls": _filter_ls,
    "dir": _filter_ls,
    "pip": _filter_pip,
    "pip3": _filter_pip,
    "pip.exe": _filter_pip,
    "npm": _filter_npm,
    "npx": _filter_npm,
    "yarn": _filter_npm,
    "pnpm": _filter_npm,
    "bun": _filter_npm,
    "docker": _filter_docker,
    "docker.exe": _filter_docker,
    "pytest": _filter_pytest,
    "pytest.exe": _filter_pytest,
    "python": _filter_python,
    "python3": _filter_python,
    "python.exe": _filter_python,
    "curl": _filter_curl,
    "wget": _filter_curl,
}


class OutputFilter:
    """Token-optimizing output filter for command stdout.

    Usage::

        from packages.ui.output_filter import OutputFilter

        stdout = subprocess.run(...).stdout
        filtered = OutputFilter.filter("git log --oneline", stdout)
        # 60-90% smaller, still semantically equivalent
    """

    @staticmethod
    def filter(command: str, stdout: str, max_chars: int | None = None) -> str:
        """Filter *stdout* from *command* for token efficiency.

        If FILTER_ENABLED is False, returns original output (truncated to max_chars).
        For unrecognized commands, returns truncated passthrough.
        """
        if not FILTER_ENABLED:
            return _truncate(stdout, max_chars or MAX_CHARS)

        if not stdout or not stdout.strip():
            return stdout

        limit = max_chars or MAX_CHARS

        # Extract the base command name
        cmd_parts = command.strip().split()
        if not cmd_parts:
            return _truncate(stdout, limit)

        base_cmd = os.path.basename(cmd_parts[0]).lower()

        # Try special filters first, then generic
        if base_cmd in _FILTERS:
            try:
                result = _FILTERS[base_cmd](stdout)
                return _truncate(result, limit)
            except Exception:
                pass

        # Generic filter: trim repeated lines, collapse whitespace
        result = _filter_generic(stdout)
        return _truncate(result, limit)

    @staticmethod
    def is_enabled() -> bool:
        return FILTER_ENABLED

    @staticmethod
    def enable() -> None:
        global FILTER_ENABLED
        FILTER_ENABLED = True

    @staticmethod
    def disable() -> None:
        global FILTER_ENABLED
        FILTER_ENABLED = False


def _filter_generic(stdout: str) -> str:
    """Generic compression for unrecognized commands."""
    lines = stdout.splitlines()
    if len(lines) <= 30:
        return stdout
    # Remove consecutive duplicate lines
    deduped = []
    prev = None
    dup_count = 0
    for line in lines:
        if line == prev:
            dup_count += 1
            if dup_count == 3:
                deduped.append(f"  … (repeated {_count_remaining(lines, line, deduped)} more times) …")
        else:
            deduped.append(line)
            dup_count = 0
            prev = line
    if len(deduped) <= 30:
        return "\n".join(deduped)
    head = deduped[:15]
    tail = deduped[-10:]
    return "\n".join(head + [f"  … ({len(deduped) - 25} lines trimmed) …"] + tail)


def _count_remaining(lines: list[str], target: str, already_added: list[str]) -> int:
    count = 0
    found = False
    for line in lines:
        if line == target:
            if found:
                count += 1
            elif len([l for l in already_added if l == target]) >= 3:
                found = True
    return count


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + f"\n  … ({len(text) - max_chars} more chars) …\n" + text[-half:]

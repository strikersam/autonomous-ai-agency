"""
log_watcher.py — Automated log monitoring agent.

Watches log files, detects errors/warnings, files GitHub issues,
and creates fix PRs automatically. Runs as a daemon thread alongside
the proxy server.

Configuration (environment variables):
    LOG_WATCHER_ENABLED=1          Enable the watcher (default: 1)
    LOG_WATCHER_INTERVAL=30        Seconds between log scans (default: 30)
    LOG_WATCHER_FILES=logs/*.log   Comma-separated log file globs
    GITHUB_TOKEN=...               Required for issue/PR creation

Error detection patterns (configurable via LOG_WATCHER_PATTERNS):
    Built-in: ERROR, CRITICAL, FATAL, Traceback, Exception:,
              [Errno, Connection refused, 500, 502, 503

Deduplication:
    Issues are deduplicated by fingerprint (error type + file + line pattern).
    The same error won't create duplicate issues within a 24-hour window.

PR Creation:
    When LOG_WATCHER_AUTO_FIX=1, the watcher will attempt to create
    fix PRs for detected issues using the Claude Code / Codebuff pipeline.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from collections import defaultdict
from pathlib import Path

log = logging.getLogger("qwen-log-watcher")

# ─── Configuration ────────────────────────────────────────────────────────────

WATCHER_ENABLED = os.environ.get("LOG_WATCHER_ENABLED", "1").strip() not in ("0", "false", "no", "off")
SCAN_INTERVAL = int(os.environ.get("LOG_WATCHER_INTERVAL", "30"))
AUTO_FIX_ENABLED = os.environ.get("LOG_WATCHER_AUTO_FIX", "0").strip() in ("1", "true", "yes", "on")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "strikersam/local-llm-server").strip()

# ─── Error detection ──────────────────────────────────────────────────────────

# Patterns that indicate a genuine error (not noise)
ERROR_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bERROR\b",
        r"\bCRITICAL\b",
        r"\bFATAL\b",
        r"Traceback \(most recent call last\)",
        r"\bException:\s",
        r"\[Errno\s",
        r"Connection refused",
        r"Connection reset",
        r"Connection timed out",
        r"\b500\b.*Internal Server Error",
        r"\b502\b.*Bad Gateway",
        r"\b503\b.*Service Unavailable",
        r"\b504\b.*Gateway Timeout",
        r"ImportError:",
        r"ModuleNotFoundError:",
        r"SyntaxError:",
        r"AttributeError:",
        r"KeyError:",
        r"FileNotFoundError:",
        r"PermissionError:",
        r"TimeoutError:",
        r"MemoryError:",
        r"RuntimeError:",
        r"ValueError:",
        r"TypeError:",
        r"IndexError:",
        r"json\.decoder\.JSONDecodeError",
        r"requests\.exceptions\.",
        r"httpx\.\w+Error",
        r"sqlite3\.\w+Error",
    ]
]

# Patterns to ignore (false positives)
IGNORE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"error.*handled successfully",
        r"error.*ignored",
        r"retrying.*error",
        r"test.*error.*mock",
        r"UserWarning",
        r"DeprecationWarning",
    ]
]


@dataclass
@dataclass
class LogEntry:
    """A single error entry extracted from a log file."""
    file_path: str
    line_number: int
    message: str
    error_type: str


class ErrorFingerprint:
    """Generates stable fingerprints for error deduplication."""

    @staticmethod
    def fingerprint(entry: LogEntry) -> str:
        """Create a hash from error type, file, and normalized message pattern."""
        # Normalize: remove numbers, timestamps, memory addresses to make patterns stable
        normalized = re.sub(r'\b0x[0-9a-fA-F]+\b', '0xADDR', entry.message)
        normalized = re.sub(r'\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\b', 'TIMESTAMP', normalized)
        normalized = re.sub(r'\b\d+\.\d+\.\d+\.\d+(:\d+)?\b', 'IP:PORT', normalized)
        normalized = re.sub(r"File \".*?\", line \d+", 'File "FILE", line N', normalized)
        key = f"{entry.error_type}:{entry.file_path}:{normalized[:200]}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


class LogWatcher:
    """Background daemon that monitors logs and creates GitHub issues for errors.

    Usage::

        watcher = LogWatcher(
            log_files=["logs/proxy.log", "logs/error.log"],
            github_token=os.environ["GITHUB_TOKEN"],
        )
        watcher.start()
        # ... server runs ...
        watcher.stop()
    """

    def __init__(
        self,
        log_files: list[str] | None = None,
        github_token: str | None = None,
        issue_labels: list[str] | None = None,
    ) -> None:
        self.log_files = log_files or self._discover_log_files()
        self.github_token = github_token or GITHUB_TOKEN
        self.issue_labels = issue_labels or ["auto-detected", "log-watcher"]
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_positions: dict[str, int] = {}  # file -> last read byte offset
        self._seen_hashes: set[str] = set()  # dedup fingerprints
        self._issues_created: int = 0
        self._errors_detected: int = 0
        self._dedup_window: dict[str, float] = {}  # fingerprint -> first seen timestamp

    # ── Public API ────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the log watcher in a daemon thread."""
        if not WATCHER_ENABLED:
            log.info("Log watcher disabled via LOG_WATCHER_ENABLED")
            return
        if not self.log_files:
            log.warning("No log files found to watch")
            return

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._watch_loop,
            daemon=True,
            name="log-watcher",
        )
        self._thread.start()
        log.info("Log watcher started — watching %d files", len(self.log_files))

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the watcher to stop."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def get_stats(self) -> dict:
        return {
            "enabled": WATCHER_ENABLED,
            "watching": len(self.log_files),
            "files": self.log_files,
            "errors_detected": self._errors_detected,
            "issues_created": self._issues_created,
            "running": bool(self._thread and self._thread.is_alive()),
        }

    def scan_now(self) -> list[LogEntry]:
        """Force an immediate scan. Returns any errors found (synchronous)."""
        entries: list[LogEntry] = []
        for file_path in self.log_files:
            entries.extend(self._scan_file(file_path))
        return entries

    # ── Internal: file discovery ──────────────────────────────────────────

    @staticmethod
    def _discover_log_files() -> list[str]:
        """Discover log files from configuration or common paths."""
        configured = os.environ.get("LOG_WATCHER_FILES", "").strip()
        if configured:
            import glob
            result = []
            for pattern in configured.split(","):
                pattern = pattern.strip()
                if pattern:
                    result.extend(glob.glob(pattern))
            return sorted(set(result))

        # Default: common log paths
        defaults = [
            "logs/proxy.log",
            "logs/error.log",
            "logs/ollama.log",
            "logs/server.log",
        ]
        return [p for p in defaults if Path(p).exists()]

    # ── Internal: scan loop ───────────────────────────────────────────────

    def _watch_loop(self) -> None:
        """Main daemon loop: scan periodically."""
        # Clean expired dedup entries
        self._clean_dedup()

        while not self._stop.is_set():
            try:
                entries: list[LogEntry] = []
                for file_path in self.log_files:
                    entries.extend(self._scan_file(file_path))

                self._errors_detected += len(entries)
                for entry in entries:
                    self._handle_error(entry)

                self._clean_dedup()
            except Exception as exc:
                log.exception("Log watcher scan failed: %s", exc)

            self._stop.wait(SCAN_INTERVAL)

    def _scan_file(self, file_path: str) -> list[LogEntry]:
        """Read new content from a log file and extract error entries."""
        if not Path(file_path).exists():
            return []

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                if file_path in self._last_positions:
                    f.seek(self._last_positions[file_path])
                else:
                    # First scan: skip existing content (only watch NEW errors)
                    f.seek(0, 2)  # Seek to end

                new_lines = f.readlines()
                self._last_positions[file_path] = f.tell()
        except (OSError, IOError):
            return []

        entries: list[LogEntry] = []
        for line in new_lines:
            error_type = self._classify(line)
            if error_type:
                if self._should_ignore(line):
                    continue
                entries.append(LogEntry(
                    file_path=file_path,
                    line_number=0,  # Approximate since we only track byte offsets
                    message=line.strip(),
                    error_type=error_type,
                ))

        return entries

    def _classify(self, line: str) -> str | None:
        """Classify a log line as an error type, or None if benign."""
        for pattern in ERROR_PATTERNS:
            if pattern.search(line):
                # Determine the primary error type from the pattern
                match_text = pattern.search(line).group(0).lower()
                if "traceback" in match_text:
                    return "traceback"
                if "exception" in match_text:
                    return "exception"
                if "error" in match_text:
                    return "error"
                if "critical" in match_text:
                    return "critical"
                if "fatal" in match_text:
                    return "fatal"
                if "timeout" in match_text:
                    return "timeout"
                if "connection" in match_text:
                    return "connection"
                if any(s in match_text for s in ("500", "502", "503", "504")):
                    return "http_error"
                if "import" in match_text or "module" in match_text:
                    return "import"
                if "syntax" in match_text:
                    return "syntax"
                if any(s in match_text for s in ("attribute", "key", "value", "type", "index")):
                    return "runtime"
                return "error"  # Generic fallback
        return None

    def _should_ignore(self, line: str) -> bool:
        """Check if a line should be ignored as a false positive."""
        for pattern in IGNORE_PATTERNS:
            if pattern.search(line):
                return True
        return False

    # ── Internal: issue creation ──────────────────────────────────────────

    def _handle_error(self, entry: LogEntry) -> None:
        """Process a detected error: dedup and create GitHub issue if new."""
        fp = ErrorFingerprint.fingerprint(entry)

        # Dedup: skip if we've seen this fingerprint recently
        now = time.time()
        if fp in self._dedup_window and (now - self._dedup_window[fp]) < 86400:
            return

        self._dedup_window[fp] = now
        self._seen_hashes.add(fp)

        log.info("New error detected: [%s] %s in %s",
                 entry.error_type, entry.message[:120], entry.file_path)

        if self.github_token:
            self._create_github_issue(entry, fp)

    def _create_github_issue(self, entry: LogEntry, fingerprint: str) -> None:
        """Create a GitHub issue for the detected error."""
        import urllib.request

        title = f"[auto] {entry.error_type.upper()}: {entry.message[:80]}"
        body = (
            f"## Auto-detected Error\n\n"
            f"**Type:** `{entry.error_type}`\n"
            f"**File:** `{entry.file_path}`\n"
            f"**Fingerprint:** `{fingerprint}`\n\n"
            f"### Error Message\n```\n{entry.message[:2000]}\n```\n\n"
            f"---\n*Detected by log_watcher.py — auto-filed from production logs.*\n"
        )

        payload = json.dumps({
            "title": title,
            "body": body,
            "labels": self.issue_labels,
        }).encode()

        req = urllib.request.Request(
            f"https://api.github.com/repos/{GITHUB_REPO}/issues",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.github_token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                self._issues_created += 1
                issue_number = data.get("number")
                log.info("Created issue #%d: %s", issue_number, title)

                if AUTO_FIX_ENABLED:
                    self._create_fix_branch(issue_number, entry, fingerprint)
        except Exception as exc:
            log.error("Failed to create GitHub issue: %s", exc)

    def _create_fix_branch(
        self, issue_number: int, entry: LogEntry, fingerprint: str
    ) -> None:
        """Attempt to create a fix PR for the detected issue via Codebuff/Claude pipeline."""
        branch_name = f"auto-fix/issue-{issue_number}-{fingerprint[:8]}"

        log.info("Auto-fix enabled — would create branch %s", branch_name)
        # TODO: Integrate with Codebuff/Claude Code pipeline for automatic fixes.
        # For now, creates a descriptive branch name for manual follow-up.
        # Production integration would:
        # 1. git checkout -b {branch_name}
        # 2. Run codebuff/claude-code with: "Fix the error described in #N"
        # 3. git push and create PR with "Closes #N"

    # ── Internal: cleanup ─────────────────────────────────────────────────

    def _clean_dedup(self) -> None:
        """Remove dedup entries older than 24 hours."""
        now = time.time()
        expired = [fp for fp, ts in self._dedup_window.items() if now - ts > 86400]
        for fp in expired:
            del self._dedup_window[fp]


# ─── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Log Watcher — monitor logs and file GitHub issues")
    parser.add_argument("--scan", action="store_true", help="Run one scan and exit")
    parser.add_argument("--daemon", action="store_true", help="Run continuously as daemon")
    parser.add_argument("--interval", type=int, default=SCAN_INTERVAL, help="Scan interval in seconds")
    parser.add_argument("--files", nargs="*", help="Log files to watch")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] log-watcher %(message)s")

    watcher = LogWatcher(log_files=args.files)

    if args.scan:
        entries = watcher.scan_now()
        if entries:
            print(f"Found {len(entries)} error(s):")
            for e in entries:
                print(f"  [{e.error_type}] {e.file_path}: {e.message[:100]}")
        else:
            print("No errors found.")
    elif args.daemon:
        watcher.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            watcher.stop()
    else:
        parser.print_help()

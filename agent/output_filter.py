"""agent/output_filter.py — LLM Output Compression & Token Savings

Inspired by rtk-ai/rtk — reduces LLM token consumption by filtering and
compressing command outputs before they reach the LLM context.

Strategies applied:
  - Smart Filtering — removes noise (comments, whitespace, boilerplate)
  - Grouping — aggregates similar items (files by directory, errors by type)
  - Truncation — keeps relevant context, cuts redundancy
  - Deduplication — collapses repeated lines with counts

Usage::

    from agent.output_filter import OutputFilter

    filt = OutputFilter()
    compact = filt.filter_git_status(raw_output)
    savings = filt.compute_savings(raw_output, compact)
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("qwen-output-filter")

# Rough heuristic: average tokens per character
_TOKENS_PER_CHAR = 1 / 4  # ~4 chars per token


@dataclass
class FilterResult:
    """Result of an output filtering operation."""

    original: str
    filtered: str
    original_tokens: int = 0
    filtered_tokens: int = 0
    savings_pct: float = 0.0
    strategy: str = ""

    @property
    def tokens_saved(self) -> int:
        return self.original_tokens - self.filtered_tokens


@dataclass
class SavingsTracker:
    """Track cumulative token savings across filtering operations."""

    total_original_tokens: int = 0
    total_filtered_tokens: int = 0
    operations: int = 0
    by_strategy: dict[str, int] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total_saved(self) -> int:
        return self.total_original_tokens - self.total_filtered_tokens

    @property
    def overall_savings_pct(self) -> float:
        if self.total_original_tokens == 0:
            return 0.0
        return round(self.total_saved / self.total_original_tokens * 100, 1)

    def record(self, result: FilterResult) -> None:
        self.total_original_tokens += result.original_tokens
        self.total_filtered_tokens += result.filtered_tokens
        self.operations += 1
        self.by_strategy[result.strategy] = (
            self.by_strategy.get(result.strategy, 0) + result.tokens_saved
        )
        if len(self.history) >= 100:
            self.history.pop(0)
        self.history.append({
            "original_tokens": result.original_tokens,
            "filtered_tokens": result.filtered_tokens,
            "savings_pct": result.savings_pct,
            "strategy": result.strategy,
        })

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_original_tokens": self.total_original_tokens,
            "total_filtered_tokens": self.total_filtered_tokens,
            "total_saved": self.total_saved,
            "overall_savings_pct": self.overall_savings_pct,
            "operations": self.operations,
            "by_strategy": self.by_strategy,
        }

    def gain_summary(self) -> str:
        """One-line summary of savings (rtk gain style)."""
        if self.operations == 0:
            return "No filtering operations yet."
        return (
            f"Token savings: {self.total_saved:,} tokens saved "
            f"({self.overall_savings_pct}%) across {self.operations} ops. "
            f"Top strategy: {max(self.by_strategy, key=self.by_strategy.get, default='none')}"
        )


class OutputFilter:
    """Filter and compress command outputs to reduce LLM token consumption.

    Provides category-specific filters for common command types:
    git, tests, logs, file listings, docker, and generic output.
    """

    def __init__(self) -> None:
        self.tracker = SavingsTracker()

    # ── Public API ──────────────────────────────────────────────────────────

    def filter_git_status(self, raw: str) -> FilterResult:
        """Compact git status output — keep only changed file paths."""
        lines = raw.strip().split("\n")
        compact_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Keep changed file indicators, skip informational lines
            if stripped.startswith(("modified:", "deleted:", "new file:", "renamed:")):
                compact_lines.append(stripped)
                continue
            if any(skip in stripped for skip in (
                "On branch", "Your branch is", "nothing to commit",
                "Changes not staged", "Changes to be committed",
                "Untracked files", "no changes added",
                'use "git', "  (",
            )):
                continue
            compact_lines.append(stripped)

        return self._build_result(raw, "\n".join(compact_lines), "git_status")

    def filter_git_log(self, raw: str, max_lines: int = 10) -> FilterResult:
        """Compact git log — one line per commit."""
        lines = [l.strip() for l in raw.strip().split("\n") if l.strip()]
        compact = lines[:max_lines]
        return self._build_result(raw, "\n".join(compact), "git_log")

    def filter_git_diff(self, raw: str) -> FilterResult:
        """Compact git diff — keep file headers, collapse hunks."""
        lines = raw.strip().split("\n")
        compact_lines: list[str] = []
        hunk_count = 0
        for line in lines:
            if line.startswith("diff --git") or line.startswith("---") or line.startswith("+++"):
                compact_lines.append(line)
                hunk_count = 0
            elif line.startswith("@@"):
                hunk_count += 1
                if hunk_count <= 2:
                    compact_lines.append(line)
            elif hunk_count <= 2 and (line.startswith("+") or line.startswith("-")):
                compact_lines.append(line)
            elif hunk_count > 2:
                pass  # collapse remaining hunk lines
        return self._build_result(raw, "\n".join(compact_lines), "git_diff")

    def filter_test_output(self, raw: str) -> FilterResult:
        """Compact test output — keep only failures and summary."""
        lines = raw.strip().split("\n")
        failures: list[str] = []
        summary: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(("FAILED ", "FAIL: ", "ERROR ", "ERRORS:")):
                failures.append(stripped)
            elif any(kw in stripped.lower() for kw in ("passed", "failed", "error", "warning", "===")):
                summary.append(stripped)

        compact = []
        if failures:
            compact.append(f"FAILURES ({len(failures)}):")
            compact.extend(failures[:20])  # cap at 20
        if summary:
            compact.append("\nSUMMARY:")
            compact.extend(summary[-5:])  # last 5 summary lines
        return self._build_result(raw, "\n".join(compact), "test_output")

    def filter_log_output(self, raw: str) -> FilterResult:
        """Deduplicate log lines and keep only unique patterns."""
        lines = [l.strip() for l in raw.strip().split("\n") if l.strip()]
        # Count and deduplicate
        counter = Counter(lines)
        compact = []
        for line, count in counter.most_common(30):
            if count > 1:
                compact.append(f"[x{count}] {line}")
            else:
                compact.append(line)
        return self._build_result(raw, "\n".join(compact), "log_dedup")

    def filter_file_listing(self, raw: str) -> FilterResult:
        """Group files by directory for compact listing."""
        lines = [l.strip() for l in raw.strip().split("\n") if l.strip()]
        by_dir: dict[str, list[str]] = {}
        for line in lines:
            if "/" in line:
                directory = line.rsplit("/", 1)[0]
            else:
                directory = "."
            by_dir.setdefault(directory, []).append(line.rsplit("/", 1)[-1] if "/" in line else line)

        compact = []
        for directory, files in sorted(by_dir.items()):
            if len(files) <= 3:
                for f in files:
                    compact.append(f"{directory}/{f}" if directory != "." else f)
            else:
                compact.append(f"{directory}/ ({len(files)} files)")
        return self._build_result(raw, "\n".join(compact), "file_listing")

    def filter_generic(self, raw: str) -> FilterResult:
        """Generic smart filtering — remove empty lines, truncate long output."""
        lines = [l.strip() for l in raw.strip().split("\n") if l.strip()]
        if len(lines) > 100:
            lines = lines[:50] + [f"... ({len(lines) - 100} more lines) ..."] + lines[-50:]
        # Remove pure whitespace/separator lines
        lines = [l for l in lines if not re.match(r'^[\s\-=_#*~]+$', l)]
        return self._build_result(raw, "\n".join(lines), "generic")

    def filter_command(self, command: str, output: str) -> FilterResult:
        """Auto-detect command type and apply the best filter."""
        cmd_lower = command.lower().split()[0] if command else ""

        # Route to specialized filters
        if cmd_lower == "git":
            subcmd = command.lower().split()[1] if len(command.split()) > 1 else ""
            if subcmd == "status":
                return self.filter_git_status(output)
            elif subcmd == "log":
                return self.filter_git_log(output)
            elif subcmd == "diff":
                return self.filter_git_diff(output)
            else:
                return self.filter_generic(output)

        if any(tool in cmd_lower for tool in ("pytest", "jest", "vitest", "cargo test", "go test", "npm test")):
            return self.filter_test_output(output)

        if cmd_lower in ("docker", "kubectl"):
            return self.filter_generic(output)

        if cmd_lower in ("ls", "dir", "tree", "find"):
            return self.filter_file_listing(output)

        if "log" in cmd_lower or cmd_lower in ("journalctl", "tail"):
            return self.filter_log_output(output)

        return self.filter_generic(output)

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation based on character count."""
        return max(1, int(len(text) * _TOKENS_PER_CHAR))

    def _build_result(self, original: str, filtered: str, strategy: str) -> FilterResult:
        orig_tokens = self._estimate_tokens(original)
        filt_tokens = self._estimate_tokens(filtered)
        savings = round((1 - filt_tokens / max(1, orig_tokens)) * 100, 1)

        result = FilterResult(
            original=original,
            filtered=filtered,
            original_tokens=orig_tokens,
            filtered_tokens=filt_tokens,
            savings_pct=savings,
            strategy=strategy,
        )
        self.tracker.record(result)
        log.debug(
            "OutputFilter: %s saved %d tokens (%.1f%%)",
            strategy, result.tokens_saved, savings,
        )
        return result


# ── Singleton ─────────────────────────────────────────────────────────────────

_filter_instance: OutputFilter | None = None


def get_output_filter() -> OutputFilter:
    """Get or create the singleton OutputFilter instance."""
    global _filter_instance
    if _filter_instance is None:
        _filter_instance = OutputFilter()
    return _filter_instance


def filter_output(command: str, output: str) -> FilterResult:
    """Convenience function: filter command output."""
    return get_output_filter().filter_command(command, output)


def get_savings_summary() -> str:
    """Get token savings summary."""
    return get_output_filter().tracker.gain_summary()

#!/usr/bin/env python3
"""scripts/parse_pytest_failures.py

Extract failing test node IDs from a pytest run's captured output.

Why this exists
---------------
``agency-cycle.yml`` and ``continuous-improvement.yml`` feed the IDs they find
into the self-healing agent, which then runs ``pytest <id>`` on each one. A
grep over the raw log cannot do that safely, and both workflows got it wrong in
opposite directions:

- ``grep -E '^(FAILED|ERROR) '`` (agency-cycle) also matched pytest's captured
  **log records**, which render as ``LEVEL    logger:file.py:lineno message``.
  ``ERROR    qwen-proxy:app_settings.py:70 ...`` starts with ``ERROR`` followed
  by a space, so ``awk '{print $2}'`` yielded ``qwen-proxy:app_settings.py:70``
  — not a node ID. Every follow-up ``pytest`` on it died with "file or
  directory not found", the agent could never converge, and it escalated to a
  human every run (issue #1354).
- ``grep '^FAILED '`` (continuous-improvement) missed ``ERROR`` summary lines
  entirely, so a run whose only failure was a collection/fixture error reported
  an empty list (issue #1352).

Only pytest's ``short test summary info`` block lists real outcomes, so that is
the region parsed, and every candidate is shape-checked before being emitted.

Exit codes
----------
``0`` always — a run with no failures is not an error here. Callers key off the
pytest exit code, not this script's.

Usage
-----
::

    python scripts/parse_pytest_failures.py /tmp/test_output.txt
    python scripts/parse_pytest_failures.py /tmp/out.txt --format csv --max 5
    python -m pytest ... | python scripts/parse_pytest_failures.py -
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

__all__ = ["extract_failures", "is_node_id"]

# The banner pytest prints above the outcome list, e.g.
# "=========================== short test summary info ============================"
_SUMMARY_HEADER = re.compile(r"^=+\s*short test summary info\s*=+$")

# A summary outcome line: "FAILED tests/test_x.py::test_y - AssertionError: ..."
# Exactly one space, then a non-whitespace candidate node ID.
_OUTCOME = re.compile(r"^(?:FAILED|ERROR) (\S+)")

DEFAULT_MAX = 10


def is_node_id(candidate: str) -> bool:
    """Return True if *candidate* has the shape of a pytest node ID.

    A node ID is ``path/to/test_file.py`` optionally followed by
    ``::Class::test_name``. The file part must therefore end in ``.py`` and
    must not itself contain a colon — which is what rejects a captured log
    record's ``logger:file.py:lineno`` locator such as
    ``qwen-proxy:app_settings.py:70``.
    """
    file_part = candidate.split("::", 1)[0]
    return file_part.endswith(".py") and ":" not in file_part


def _summary_region(lines: list[str]) -> list[str]:
    """Return the lines at or after pytest's first summary banner.

    Falls back to the whole output when no banner is present (for example a
    run cut short before pytest printed one). That fallback is safe because
    every candidate still has to pass :func:`is_node_id`.
    """
    for index, line in enumerate(lines):
        if _SUMMARY_HEADER.match(line.strip()):
            return lines[index + 1:]
    return lines


def extract_failures(output: str, max_results: int = DEFAULT_MAX) -> list[str]:
    """Return up to *max_results* unique failing node IDs from pytest *output*.

    Order is preserved as pytest reported it. Both ``FAILED`` (assertion
    failures) and ``ERROR`` (collection/fixture errors) count as failures —
    the self-healing agent needs to see both.
    """
    found: list[str] = []
    for line in _summary_region(output.splitlines()):
        match = _OUTCOME.match(line)
        if match is None:
            continue
        node_id = match.group(1)
        if not is_node_id(node_id) or node_id in found:
            continue
        found.append(node_id)
        if len(found) >= max_results:
            break
    return found


def _read(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    return Path(source).read_text(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("source", help="pytest output file, or '-' for stdin")
    parser.add_argument(
        "--format",
        choices=("lines", "csv"),
        default="lines",
        help="newline-delimited (default) or comma-separated on one line",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=DEFAULT_MAX,
        dest="max_results",
        help=f"maximum node IDs to emit (default {DEFAULT_MAX})",
    )
    args = parser.parse_args(argv)

    failures = extract_failures(_read(args.source), max_results=args.max_results)
    if args.format == "csv":
        print(",".join(failures))
    else:
        for node_id in failures:
            print(node_id)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

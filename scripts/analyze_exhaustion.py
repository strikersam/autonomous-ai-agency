#!/usr/bin/env python3
"""scripts/analyze_exhaustion.py

Decide whether a run that ran out of retries has actually *earned* the
``quick-note:exhausted`` label, and write the analysis that justifies it.

Why this exists
---------------
``process-quick-note.yml`` used to treat exhaustion as a bare counter: three
failed attempts, add the label, paste the last 40 lines of log, walk away. No
step ever asked *why* it failed, so two very different situations were treated
identically — the agent being genuinely unable to write the fix, and the agent
being handed a task that was never fixable in the first place.

The second case is what actually happened, every day for weeks. A parser bug
fed the loop ``qwen-proxy:app_settings.py:70`` — a captured log record, not a
test — so every ``pytest`` on it died with "file or directory not found". Three
attempts, exhausted, issue abandoned. 238 closed issues carry that shape. The
information needed to catch it was right there in the log and nothing read it.

Worse, the repo already *had* the diagnosis. ``SelfHealingAgent._classify_failure``
correctly reported ``infrastructure_error — "no code change can fix it"`` for the
MongoDB failure in issue #1360, and the workflow marked the issue exhausted
anyway. This module puts that verdict in the decision path.

Verdicts
--------
``needs-triage``
    No real pytest node ID could be recovered from the output. The loop was
    chasing something that is not a test; retrying cannot help and neither can
    a human reading a "tests failed" report. The input itself is the bug.
``blocked-infrastructure``
    Every recovered failure is an unavailable external service. Not the agent's
    fault and not fixable by any diff, so spending the retry budget on it — and
    then blaming the agent by marking it exhausted — is simply wrong.
``exhausted``
    Real tests, real code-level failures, genuinely attempted and not fixed.
    This is the only case the label was ever meant for.

Only ``exhausted`` should apply the label. The other two keep the issue
retryable, because the thing standing in the way is not the agent.

Usage
-----
::

    python scripts/analyze_exhaustion.py /tmp/impl_output.txt \\
        --attempts 3 --verdict-file /tmp/verdict.txt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.parse_pytest_failures import extract_failures  # noqa: E402

__all__ = ["Analysis", "analyze"]

VERDICT_EXHAUSTED = "exhausted"
VERDICT_INFRA = "blocked-infrastructure"
VERDICT_TRIAGE = "needs-triage"

# Signature of the parser bug this module exists to catch: pytest was handed
# something that is not a node ID and refused to collect it.
_NOT_A_TEST_MARKERS = ("file or directory not found", "no tests ran")


class Analysis:
    """The verdict plus the human-readable justification behind it."""

    def __init__(self, verdict: str, failures: list[str], categories: dict[str, str],
                 report: str) -> None:
        self.verdict = verdict
        self.failures = failures
        self.categories = categories
        self.report = report


def _classify(text: str) -> str:
    """Classify *text* with the repo's own classifier.

    Imported lazily: ``agent.self_healing`` pulls in the agent stack, which is
    available in the workflow (deps are installed) but needlessly heavy for a
    caller that only wants the parse. Falls back to ``unknown`` rather than
    crashing the exhaustion path — a missing classification must never be the
    reason an issue gets stranded.
    """
    try:
        from agent.self_healing import SelfHealingAgent

        return SelfHealingAgent._classify_failure(text).value
    except Exception:  # pragma: no cover - defensive, import-environment dependent
        return "unknown"


def analyze(output: str, attempts: int = 3) -> Analysis:
    """Return the exhaustion :class:`Analysis` for a run's captured *output*."""
    failures = extract_failures(output, max_results=25)
    lowered = output.lower()

    if not failures:
        looks_uncollectable = any(m in lowered for m in _NOT_A_TEST_MARKERS)
        reason = (
            "pytest was asked to run something that is not a test node ID and "
            "refused to collect it"
            if looks_uncollectable
            else "no failing test could be recovered from the run output"
        )
        report = (
            "### Exhaustion analysis — `needs-triage`\n\n"
            f"After {attempts} attempts, **{reason}**.\n\n"
            "Retrying cannot help: there is no test here to fix. The failing "
            "input is the defect, not the code under test. Leaving this issue "
            "retryable rather than marking it `quick-note:exhausted`, because "
            "the agent was never given a fixable task.\n"
        )
        return Analysis(VERDICT_TRIAGE, [], {}, report)

    categories = {node_id: _classify(output) for node_id in failures}
    distinct = set(categories.values())

    if distinct == {"infrastructure_error"}:
        report = (
            "### Exhaustion analysis — `blocked-infrastructure`\n\n"
            f"All {len(failures)} recovered failure(s) classify as "
            "`infrastructure_error`: an external service the run depends on was "
            "unavailable. No code change can make an unreachable service "
            "answer, so the retry budget was spent on something no diff could "
            "have fixed.\n\n"
            "Not marking this `quick-note:exhausted` — that label means *the "
            "agent tried and could not write the fix*, which is not what "
            "happened here.\n\n"
            + _failure_table(categories)
        )
        return Analysis(VERDICT_INFRA, failures, categories, report)

    report = (
        "### Exhaustion analysis — `exhausted`\n\n"
        f"{len(failures)} real failing test(s) survived {attempts} attempts. "
        "These are code-level failures against collectable tests, so the label "
        "is warranted and this needs a human.\n\n"
        + _failure_table(categories)
    )
    return Analysis(VERDICT_EXHAUSTED, failures, categories, report)


def _failure_table(categories: dict[str, str]) -> str:
    rows = "\n".join(f"| `{nid}` | `{cat}` |" for nid, cat in categories.items())
    return f"| Failing test | Category |\n|---|---|\n{rows}\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("source", help="run output file, or '-' for stdin")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument(
        "--verdict-file",
        help="write the bare verdict here for the workflow to branch on",
    )
    args = parser.parse_args(argv)

    text = (
        sys.stdin.read()
        if args.source == "-"
        else Path(args.source).read_text(encoding="utf-8", errors="replace")
    )
    result = analyze(text, attempts=args.attempts)

    if args.verdict_file:
        Path(args.verdict_file).write_text(result.verdict + "\n", encoding="utf-8")
    print(result.report)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

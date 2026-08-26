#!/usr/bin/env python3
"""scripts/triage_orphaned_context_prs.py

Decide what to do about a draft context PR whose planning doc never became an
implementation.

The failure mode
----------------
``issue-context-generator.yml`` opens a **draft** PR carrying a plan, and
``process-quick-note.yml`` is supposed to come back and implement it. The
implementer only ever looks at *open* issues that are not
``quick-note:exhausted`` / ``quick-note:rejected``. So the moment an issue is
closed or exhausted, its draft PR becomes unreachable: no workflow will ever
look at it again, and nothing says so out loud. Nine such PRs accumulated
(#1318, #1323, #1327, #1332, #1348, #1351, #1353, #1357, #1359), every one of
their issues closed and exhausted.

The judgement this encodes
--------------------------
Recovery must not simply strip ``quick-note:exhausted`` wherever it finds it —
that would undo the analysis gate in ``analyze_exhaustion.py`` and put the loop
straight back to grinding on genuinely unfixable work. The distinction is
whether the exhaustion was ever *justified*:

- An issue exhausted **with** a recorded analysis was judged on its merits.
  Leave it alone; a human asked for it to stop.
- An issue exhausted **without** one predates the gate. It was labelled by a
  bare counter that never asked why, which is exactly the bug — those deserve
  one fair re-run.
- A **closed** issue with an open draft PR is stranded regardless: the plan
  exists, the implementation does not, and nothing can reach it.

``rejected`` is always left alone. It is a deliberate decision not to build,
not a failure to.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

__all__ = ["Decision", "decide", "issue_number_from_branch"]

# Marker written by analyze_exhaustion.py when it upholds the label. Its
# presence is the evidence that a human-grade judgement was actually made.
ANALYSIS_MARKER = "### Exhaustion analysis"

_BRANCH_RE = re.compile(r"^claude/context-issue-(\d+)$")

ACTION_REOPEN = "reopen"
ACTION_CLEAR_EXHAUSTED = "clear-exhausted"
ACTION_SKIP = "skip"


class Decision:
    def __init__(self, action: str, reason: str) -> None:
        self.action = action
        self.reason = reason

    def as_dict(self) -> dict[str, str]:
        return {"action": self.action, "reason": self.reason}


def issue_number_from_branch(branch: str) -> int | None:
    """Return the issue number a context branch was generated for, if any."""
    match = _BRANCH_RE.match(branch.strip())
    return int(match.group(1)) if match else None


def decide(issue: dict) -> Decision:
    """Decide how to recover the *issue* behind an orphaned draft PR.

    *issue* is the ``gh issue view --json state,labels,comments`` shape.
    """
    labels = {lbl.get("name", "") for lbl in issue.get("labels") or []}
    state = (issue.get("state") or "").upper()
    comments = issue.get("comments") or []

    if "quick-note:rejected" in labels:
        return Decision(
            ACTION_SKIP,
            "labelled quick-note:rejected — a deliberate decision not to build, "
            "not a failure to build",
        )

    has_analysis = any(
        ANALYSIS_MARKER in (c.get("body") or "") for c in comments
    )

    if state == "CLOSED":
        return Decision(
            ACTION_REOPEN,
            "issue is closed but its draft plan PR is still open — the "
            "implementer only looks at open issues, so this work is "
            "unreachable by every workflow",
        )

    if "quick-note:exhausted" in labels:
        if has_analysis:
            return Decision(
                ACTION_SKIP,
                "exhausted with a recorded analysis — that verdict was reached "
                "on the merits and should stand",
            )
        return Decision(
            ACTION_CLEAR_EXHAUSTED,
            "exhausted with no analysis on record — labelled by the bare "
            "retry counter that never asked why it failed, so it has never "
            "actually been judged",
        )

    return Decision(ACTION_SKIP, "already open and retryable — the loop can reach it")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("issue_json", help="`gh issue view --json ...` output, or '-'")
    args = parser.parse_args(argv)

    raw = sys.stdin.read() if args.issue_json == "-" else Path(args.issue_json).read_text(
        encoding="utf-8"
    )
    print(json.dumps(decide(json.loads(raw)).as_dict()))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

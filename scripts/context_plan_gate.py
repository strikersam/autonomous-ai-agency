#!/usr/bin/env python3
"""scripts/context_plan_gate.py

Decide whether a generated context plan may be implemented.

Why this exists
---------------
On 2026-08-28 the autonomous implementer merged 1,199 lines to ``master`` under
a pull request (#1357) whose own title read *"docs: reject: SEO
backlog-to-roadmap is out of scope for autonomous-ai-agency"* and whose body
read **"🛑 REJECT — nothing here belongs in this repository."** The planning
pass wrote that verdict; the implement pass ran on the same branch and built the
thing anyway.

The plan also recorded that it had never read its own source — *"Fetch status:
⚠️ NOT FETCHED — the plan below is unverified against the source"* — and a
Quality Gate listing one unmet rule whose text is literally *"treat the items
below as unresolved before implementing"*. All three signals were sitting in a
file committed to the repository, and nothing read them.

A ``quick-note:rejected`` label does exist, applied by
``issue-context-generator.yml``. It is not sufficient on its own: it is written
by a *different* workflow, best-effort (``|| echo "::warning::"``), only when a
PR was created, and it can be removed by hand or never applied if that workflow
fails. Enforcement that lives only in another job's side effect is enforcement
that goes missing without a sound.

This module reads the plan document itself, at the point of use, and answers one
question: may this be implemented? It fails **closed** — an unreadable or
unrecognised plan blocks, because "I could not tell" and "yes" must not look the
same. That confusion is the defect this repository keeps paying for.

Markers
-------
Every string matched here is produced by a renderer in this repo:
``generate_context.VERDICT_BADGES``, ``generate_context._build_grounding_block``
and ``context_rules.format_violations``. ``tests/test_context_plan_gate.py``
imports those producers and asserts the parser still recognises what they emit,
so the two cannot drift apart silently.

Exit codes
----------
``0`` when the plan permits implementation, ``1`` when it does not, ``2`` when
the plan could not be read at all. Callers that want the reason rather than the
status read the ``key=value`` lines on stdout.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Verdicts that describe work worth doing. Anything else — including a verdict
# this parser does not recognise — blocks.
IMPLEMENTABLE_VERDICTS = frozenset({"adopt", "adapt"})

# Substrings unique to each rendered verdict badge. Matched on the bolded token
# rather than the whole sentence so a reworded explanation does not silently
# stop matching; the test suite pins these against the real badge strings.
_VERDICT_MARKERS: tuple[tuple[str, str], ...] = (
    ("reject", "**REJECT**"),
    ("adapt", "**ADAPT**"),
    ("adopt", "**ADOPT**"),
)

_NOT_FETCHED = "**NOT FETCHED**"
_UNMET_RULES = re.compile(r"\*\*(\d+) unmet rule\(s\)\*\*")
_GATE_PASSED = "Passed every machine-checked rule"


@dataclass(frozen=True)
class PlanDecision:
    """What a context plan says about its own fitness to be built."""

    verdict: str
    source_fetched: bool
    unmet_rules: int
    may_implement: bool
    reason: str

    def as_output_lines(self) -> str:
        """``key=value`` lines a workflow can append to ``$GITHUB_OUTPUT``."""
        return "\n".join(
            (
                f"may_implement={'true' if self.may_implement else 'false'}",
                f"verdict={self.verdict}",
                f"source_fetched={'true' if self.source_fetched else 'false'}",
                f"unmet_rules={self.unmet_rules}",
                # Single-line: a newline here would corrupt $GITHUB_OUTPUT.
                f"reason={self.reason}",
            )
        )


def read_verdict(document: str) -> str:
    """The plan's own verdict, or ``unknown`` when no badge is present.

    Checked reject-first so a document that somehow carries two badges is
    treated as the more restrictive of them.
    """
    for verdict, marker in _VERDICT_MARKERS:
        if marker in document:
            return verdict
    return "unknown"


def read_source_fetched(document: str) -> bool:
    """Did the planner actually retrieve the source it reasoned about?"""
    return _NOT_FETCHED not in document


def read_unmet_rules(document: str) -> int:
    """Count of rulebook violations the generator shipped the plan with."""
    match = _UNMET_RULES.search(document)
    return int(match.group(1)) if match else 0


def evaluate(document: str) -> PlanDecision:
    """Decide, and say why in words a human can act on."""
    verdict = read_verdict(document)
    fetched = read_source_fetched(document)
    unmet = read_unmet_rules(document)

    if verdict == "unknown":
        reason = (
            "the plan records no verdict this gate recognises, so it cannot be "
            "confirmed as approved work"
        )
    elif verdict not in IMPLEMENTABLE_VERDICTS:
        reason = (
            f"the plan's own verdict is {verdict.upper()} — the analysis pass "
            f"concluded there is nothing here to build"
        )
    elif not fetched:
        reason = (
            "the plan was written without retrieving its source, so every claim "
            "in it is unverified"
        )
    elif unmet:
        reason = (
            f"the plan ships with {unmet} unmet rulebook rule(s); its own Quality "
            f"Gate says to treat them as unresolved before implementing"
        )
    else:
        return PlanDecision(verdict, fetched, unmet, True, "plan is grounded and approved")

    return PlanDecision(verdict, fetched, unmet, False, reason)


def evaluate_path(path: Path) -> PlanDecision | None:
    """``None`` when the document does not exist — the caller decides."""
    if not path.is_file():
        return None
    return evaluate(path.read_text(encoding="utf-8"))


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("plan", help="path to the context plan markdown document")
    parser.add_argument(
        "--missing-ok",
        action="store_true",
        help=(
            "treat an absent plan as 'nothing to enforce' rather than a block. "
            "Correct only when no planning pass ran for this issue at all; "
            "never when a context branch exists, because then the plan is "
            "missing rather than absent."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    decision = evaluate_path(Path(args.plan))

    if decision is None:
        if args.missing_ok:
            print("may_implement=true")
            print("verdict=none")
            print("source_fetched=false")
            print("unmet_rules=0")
            print("reason=no context plan was generated for this issue")
            return 0
        print("may_implement=false")
        print("verdict=missing")
        print("source_fetched=false")
        print("unmet_rules=0")
        print(f"reason=expected a context plan at {args.plan} and found none")
        return 2

    print(decision.as_output_lines())
    return 0 if decision.may_implement else 1


if __name__ == "__main__":
    raise SystemExit(main())

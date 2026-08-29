"""A plan that says "do not build this" must stop the thing that builds.

On 2026-08-28 the implementer merged 1,199 lines under PR #1357, whose title
read *"docs: reject: SEO backlog-to-roadmap is out of scope"* and whose body
read **"🛑 REJECT — nothing here belongs in this repository."** The same
document recorded that the planner had never fetched its source, and a Quality
Gate whose text is *"treat the items below as unresolved before implementing"*.

Three refusals, all committed to the repository, none of them read.

The existing defence was a ``quick-note:rejected`` label written by a different
workflow, best-effort, only on the PR-creation path. That is a side effect, not
a gate: when it does not happen, nothing says so and the build proceeds. These
tests cover a gate that reads the plan itself at the point of use and fails
closed, because "I could not tell" must never resolve the same way as "yes".
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / ".github/scripts"))

import context_plan_gate as gate  # noqa: E402


def _plan(
    *,
    verdict_badge: str = "✅ **ADOPT** — build largely as described in the source.",
    fetch_cell: str = "✅ fetched — 41,238 chars of content",
    gate_block: str = "## Quality Gate\n\n✅ Passed every machine-checked rule in `x`.\n",
) -> str:
    """A plan document shaped like the real renderer's output."""
    return (
        "# Issue #1: something\n\n## Source Grounding\n\n"
        "| | |\n|---|---|\n"
        f"| Fetch status | {fetch_cell} |\n\n"
        f"## Decision\n\n{verdict_badge}\n\n---\n\n{gate_block}"
    )


class TestTheProducersAndTheParserCannotDrift:
    """The markers are matched against strings this repo generates elsewhere.

    A hand-copied list here would rot the first time a badge is reworded, and
    the gate would quietly stop recognising a REJECT — which is exactly the
    failure it exists to prevent. So the real renderers are imported and their
    output is fed through the parser.
    """

    def test_every_real_verdict_badge_is_recognised(self) -> None:
        from generate_context import VERDICT_BADGES

        assert VERDICT_BADGES, "no badges to check against; this would pass vacuously"
        for verdict, badge in VERDICT_BADGES.items():
            assert gate.read_verdict(_plan(verdict_badge=badge)) == verdict

    def test_the_real_not_fetched_cell_is_recognised(self) -> None:
        from generate_context import _build_grounding_block

        ungrounded = _build_grounding_block({"url": "https://e.test", "source_fetched": False})
        assert gate.read_source_fetched(ungrounded) is False

    def test_the_real_fetched_cell_reads_as_grounded(self) -> None:
        from generate_context import _build_grounding_block

        grounded = _build_grounding_block(
            {"url": "https://e.test", "source_fetched": True, "source_chars": 41238}
        )
        assert gate.read_source_fetched(grounded) is True

    def test_the_real_violation_block_is_counted(self) -> None:
        import context_rules

        violations = [
            context_rules.Violation(rule="R1", detail="the source was not retrieved"),
            context_rules.Violation(rule="R3", detail="no verdict reason given"),
        ]
        assert gate.read_unmet_rules(context_rules.format_violations(violations)) == 2

    def test_the_real_passing_gate_counts_zero(self) -> None:
        import context_rules

        assert gate.read_unmet_rules(context_rules.format_violations([])) == 0


class TestTheRejectIsHonoured:
    def test_a_reject_plan_may_not_be_implemented(self) -> None:
        decision = gate.evaluate(
            _plan(verdict_badge="🛑 **REJECT** — nothing here belongs in this repository.")
        )
        assert decision.may_implement is False
        assert decision.verdict == "reject"
        assert "REJECT" in decision.reason

    @pytest.mark.parametrize("verdict", ["adopt", "adapt"])
    def test_an_approved_grounded_plan_may_be_implemented(self, verdict: str) -> None:
        from generate_context import VERDICT_BADGES

        decision = gate.evaluate(_plan(verdict_badge=VERDICT_BADGES[verdict]))
        assert decision.may_implement is True
        assert decision.verdict == verdict

    def test_the_pr_1357_document_would_have_been_blocked(self) -> None:
        """The real thing, reconstructed from the merged plan.

        `docs/context/issue-1356.md` is committed on master; if it is present,
        assert against the actual bytes rather than a reconstruction.
        """
        real = REPO_ROOT / "docs/context/issue-1356.md"
        document = (
            real.read_text(encoding="utf-8")
            if real.is_file()
            else _plan(
                verdict_badge="🛑 **REJECT** — nothing here belongs in this repository.",
                fetch_cell="⚠️ **NOT FETCHED** — the plan below is unverified against the source",
                gate_block="## Quality Gate\n\n⚠️ **1 unmet rule(s)** from `x`.\n\n- **R1** — not retrieved\n",
            )
        )
        decision = gate.evaluate(document)
        assert decision.may_implement is False, (
            "the plan that produced b368f9e7 must not pass this gate"
        )


class TestItFailsClosed:
    """An unreadable plan is not an approved plan."""

    def test_a_plan_with_no_verdict_blocks(self) -> None:
        decision = gate.evaluate("# Issue #1\n\nSome prose with no badge at all.\n")
        assert decision.may_implement is False
        assert decision.verdict == "unknown"

    def test_an_unfetched_source_blocks_even_when_approved(self) -> None:
        decision = gate.evaluate(
            _plan(
                fetch_cell="⚠️ **NOT FETCHED** — the plan below is unverified against the source"
            )
        )
        assert decision.may_implement is False
        assert "unverified" in decision.reason

    def test_unmet_rules_block_even_when_approved_and_grounded(self) -> None:
        decision = gate.evaluate(
            _plan(gate_block="## Quality Gate\n\n⚠️ **2 unmet rule(s)** from `x`.\n")
        )
        assert decision.may_implement is False
        assert decision.unmet_rules == 2

    def test_reject_wins_over_a_second_badge(self) -> None:
        both = _plan(
            verdict_badge=(
                "✅ **ADOPT** — build largely as described.\n\n"
                "🛑 **REJECT** — nothing here belongs in this repository."
            )
        )
        assert gate.read_verdict(both) == "reject"


class TestTheCli:
    def test_an_approved_plan_exits_zero(self, tmp_path: Path, capsys) -> None:
        plan = tmp_path / "issue-1.md"
        plan.write_text(_plan(), encoding="utf-8")
        assert gate.main([str(plan)]) == 0
        assert "may_implement=true" in capsys.readouterr().out

    def test_a_rejected_plan_exits_one(self, tmp_path: Path, capsys) -> None:
        plan = tmp_path / "issue-1.md"
        plan.write_text(
            _plan(verdict_badge="🛑 **REJECT** — nothing here belongs in this repository."),
            encoding="utf-8",
        )
        assert gate.main([str(plan)]) == 1
        assert "may_implement=false" in capsys.readouterr().out

    def test_a_missing_plan_exits_two_by_default(self, tmp_path: Path, capsys) -> None:
        assert gate.main([str(tmp_path / "nope.md")]) == 2
        assert "may_implement=false" in capsys.readouterr().out

    def test_missing_ok_permits_an_unplanned_issue(self, tmp_path: Path, capsys) -> None:
        """No planning pass ran at all — there is no decision to honour."""
        assert gate.main([str(tmp_path / "nope.md"), "--missing-ok"]) == 0
        out = capsys.readouterr().out
        assert "may_implement=true" in out
        assert "verdict=none" in out

    def test_the_reason_never_contains_a_newline(self, tmp_path: Path, capsys) -> None:
        """A multi-line value corrupts every later key in $GITHUB_OUTPUT."""
        plan = tmp_path / "issue-1.md"
        plan.write_text(
            _plan(verdict_badge="🛑 **REJECT** — nothing here belongs in this repository."),
            encoding="utf-8",
        )
        gate.main([str(plan)])
        for line in capsys.readouterr().out.splitlines():
            if line.startswith("reason="):
                assert "\n" not in line

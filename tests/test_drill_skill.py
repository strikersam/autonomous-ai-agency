"""The /drill skill and its read-only inventory script.

The skill's phase 2 table and the script's categories must agree: an item the
script files under a category the skill never mentions would get no handling
rule. The rest pins the classification and CI-summary logic the skill relies on,
and the do/don't rules learned from real drills.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / ".claude" / "skills" / "drill" / "SKILL.md"
sys.path.insert(0, str(REPO / "scripts"))

import drill_inventory as inv  # noqa: E402

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


def _frontmatter() -> dict:
    text = SKILL.read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---", 2)[1])


def _pr(ref: str, author: str = "strikersam", updated: datetime = NOW - timedelta(days=1)) -> dict:
    return {"head": {"ref": ref, "sha": "abc"}, "user": {"login": author},
            "updated_at": updated.isoformat().replace("+00:00", "Z")}


def _issue(title: str, *labels: str) -> dict:
    return {"title": title, "labels": [{"name": n} for n in labels]}


# ── the skill file ──────────────────────────────────────────────────────────

def test_skill_frontmatter_names_the_slash_command():
    meta = _frontmatter()
    assert meta["name"] == "drill"
    assert "/drill" in meta["triggers"]
    assert len(meta["description"]) > 50


def test_every_reference_in_the_skill_exists():
    for ref in _frontmatter()["references"]:
        assert (REPO / ref).exists(), ref


def test_every_category_the_script_emits_has_a_handling_rule():
    body = SKILL.read_text(encoding="utf-8")
    table = body[body.index("| Category |"): body.index("**Implementing a fix:**")]
    emitted = {
        inv.classify_pr(_pr("claude/mine"), own_branch="claude/mine"),
        inv.classify_pr(_pr("dependabot/pip/x", "dependabot[bot]")),
        inv.classify_pr(_pr("agent/task-1")),
        inv.classify_pr(_pr("claude/daily-automation-2026-10-19")),
        inv.classify_pr(_pr("claude/some-session")),
        inv.classify_pr(_pr("feature/x")),
        inv.classify_issue(_issue("quick-note:https://x", "quick-note:rejected")),
        inv.classify_issue(_issue("quick-note:https://x")),
        inv.classify_issue(_issue("Routine backlog", "routine-backlog")),
        inv.classify_issue(_issue("Agency: Cannot Fix Tests", "agency-escalation")),
        inv.classify_issue(_issue("crash", "bug")),
    }
    missing = [c for c in emitted if f"`{c}`" not in table]
    assert not missing, f"categories with no rule in the phase 2 table: {missing}"


@pytest.mark.parametrize("rule", [
    "force-push master", "--no-verify", "skip, disable", "IN FLIGHT",
    "regression test that fails before the fix", "both `CHANGELOG.md` and `docs/changelog.md`",
    "rule 40", "update-branch", "Re-run `python scripts/drill_inventory.py`",
    "Render connector", "Cancel every check-in", "dead branch", "--target",
])
def test_skill_keeps_the_rules_learned_from_real_drills(rule):
    assert rule in SKILL.read_text(encoding="utf-8")


# ── classification ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("ref,author,expected", [
    ("dependabot/pip/zipp-gte-4.1.1", "dependabot[bot]", "dependabot"),
    ("dependabot/npm_and_yarn/frontend/all-patches", "dependabot[bot]", "dependabot"),
    ("agent/task-c42d4658", "strikersam", "agent"),
    ("claude/daily-automation-2026-10-19", "strikersam", "automation"),
    ("claude/harness-scan-2026-10-19", "strikersam", "automation"),
    ("claude/context-issue-1758", "strikersam", "automation"),
    ("claude/evidence-driven-verification", "strikersam", "session"),
    ("fix/self-improvement-throughput", "strikersam", "human"),
])
def test_classify_pr(ref, author, expected):
    assert inv.classify_pr(_pr(ref, author)) == expected


@pytest.mark.parametrize("issue,expected", [
    (_issue("quick-note:https://x.com/a", "quick-note:rejected"), "quick-note-rejected"),
    (_issue("quick-note:https://x.com/a"), "quick-note"),
    (_issue("Routine backlog — 2026-W43", "routine-backlog"), "routine"),
    (_issue("fix: nightly regression failures — Server errors", "bug", "needs-triage"), "automation-bug"),
    (_issue("Agency: Cannot Fix Tests", "bug", "agency-escalation"), "automation-bug"),
    (_issue("Login button does nothing", "bug"), "bug"),
    (_issue("Idea: dark mode"), "other"),
])
def test_classify_issue(issue, expected):
    assert inv.classify_issue(issue) == expected


def test_the_drills_own_pr_is_never_someone_elses_in_flight_work():
    """Live drill 2026-10-19: the drill's own just-opened PR was flagged IN FLIGHT
    ("don't touch") because every recent claude/* PR looked like another session's."""
    pr = _pr("claude/cleanup-open-prs-issues-kdzv7g", updated=NOW - timedelta(minutes=5))
    category = inv.classify_pr(pr, own_branch="claude/cleanup-open-prs-issues-kdzv7g")
    assert category == "own"
    assert inv.is_in_flight(pr, category, NOW) is False
    assert inv.classify_pr(pr) == "session", "without own_branch it stays a session PR"


def test_a_recent_session_pr_is_in_flight_and_an_old_one_is_not():
    recent = _pr("claude/x", updated=NOW - timedelta(minutes=30))
    stale = _pr("claude/x", updated=NOW - timedelta(hours=5))
    assert inv.is_in_flight(recent, "session", NOW) is True
    assert inv.is_in_flight(stale, "session", NOW) is False
    # Only session PRs can be another session's live work.
    assert inv.is_in_flight(recent, "dependabot", NOW) is False


# ── CI summaries ────────────────────────────────────────────────────────────

def test_a_rerun_that_passed_overrides_the_earlier_failure():
    runs = [
        # Newest first, as the API may return them: list order must not decide.
        {"name": "Test", "conclusion": "success", "status": "completed", "started_at": "2026-10-19T09:00:00Z"},
        {"name": "Test", "conclusion": "failure", "status": "completed", "started_at": "2026-10-19T08:00:00Z"},
        {"name": "Lint", "conclusion": "success", "status": "completed", "started_at": "2026-10-19T08:00:00Z"},
    ]
    assert inv.summarize_checks(runs) == {"state": "green", "failing": [], "pending": []}


def test_failing_beats_pending_and_pending_beats_green():
    failing = [{"name": "A", "conclusion": "failure", "status": "completed"},
               {"name": "B", "conclusion": None, "status": "in_progress"}]
    pending = [{"name": "B", "conclusion": None, "status": "queued"}]
    assert inv.summarize_checks(failing)["state"] == "red"
    assert inv.summarize_checks(pending) == {"state": "pending", "failing": [], "pending": ["B"]}
    assert inv.summarize_checks([])["state"] == "green"


def test_only_a_workflow_whose_newest_run_failed_is_still_red():
    runs = [
        {"name": "Nightly", "status": "completed", "conclusion": "success", "created_at": "2026-10-15T02:00:00Z"},
        {"name": "Nightly", "status": "completed", "conclusion": "failure", "created_at": "2026-10-14T02:00:00Z"},
        {"name": "Agency", "status": "completed", "conclusion": "failure", "created_at": "2026-10-15T03:00:00Z"},
        {"name": "Agency", "status": "in_progress", "conclusion": None, "created_at": "2026-10-15T04:00:00Z"},
    ]
    assert inv.still_red_workflows(runs) == ["Agency"]


# ── end to end, offline ─────────────────────────────────────────────────────

def test_collect_and_render_without_network(monkeypatch):
    responses = {
        "pulls?state=open": [{"number": 7, "title": "bump x", "draft": False,
                              **_pr("dependabot/pip/x", "dependabot[bot]")}],
        "pulls/7": {"mergeable_state": "behind"},
        "commits/abc/check-runs": {"check_runs": [{"name": "Test", "conclusion": "failure", "status": "completed"}]},
        "issues?state=open": [{"number": 8, "title": "Routine backlog", "labels": [{"name": "routine-backlog"}]},
                              {"number": 7, "title": "bump x", "labels": [], "pull_request": {}}],
        "commits/master/check-runs": {"check_runs": [{"name": "Test", "conclusion": "success", "status": "completed"}]},
        "actions/runs": {"workflow_runs": []},
    }

    def fake_gh_json(path):
        return next(v for k, v in responses.items() if k in path)

    monkeypatch.setattr(inv, "gh_json", fake_gh_json)
    data = inv.collect("o/r", NOW)
    assert [p["number"] for p in data["prs"]] == [7]
    assert [i["number"] for i in data["issues"]] == [8], "PRs listed by the issues endpoint must be dropped"
    assert data["prs"][0]["ci"]["failing"] == ["Test"]
    text = inv.render(data)
    assert re.search(r"\| #7 \| PR \| dependabot \| red \| behind \|", text)
    assert "Open items: 2 (1 PRs, 1 issues)." in text
    assert "Master CI: **green**" in text


def test_a_superseded_cancelled_run_does_not_make_master_red():
    """Live drill 2026-10-19: CI and Codespaces runs cancelled by a newer push to
    master were reported as red workflows. Cancelled runs are skipped; the newest
    run that finished decides."""
    runs = [
        {"name": "CI", "status": "completed", "conclusion": "cancelled", "created_at": "2026-10-19T10:07:00Z"},
        {"name": "CI", "status": "completed", "conclusion": "success", "created_at": "2026-10-19T09:50:00Z"},
        {"name": "CI", "status": "in_progress", "conclusion": None, "created_at": "2026-10-19T10:13:00Z"},
        {"name": "Codespaces", "status": "completed", "conclusion": "cancelled", "created_at": "2026-10-19T10:07:00Z"},
        {"name": "Nightly", "status": "completed", "conclusion": "cancelled", "created_at": "2026-10-19T03:00:00Z"},
        {"name": "Nightly", "status": "completed", "conclusion": "failure", "created_at": "2026-10-18T03:00:00Z"},
    ]
    assert inv.still_red_workflows(runs) == ["Nightly"]

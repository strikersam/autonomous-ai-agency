"""Unit tests for the bounty hunter's pure logic (packages/bounty)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from packages.bounty import tracker
from packages.bounty.discovery import candidate_from_item, extract_amount
from packages.bounty.ledger import ROSTER, allocate, compute_pnl, fitness
from packages.bounty.models import Bounty, BountyState, HuntRecord
from packages.bounty.platforms import PLATFORMS, enabled_platforms
from packages.bounty.triage import TriageInput, already_paid, bans_ai, count_competitors, triage
from packages.config.bounty_settings import load_bounty_settings

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def _settings(monkeypatch, **env):
    base = {"BOUNTY_GITHUB_LOGIN": "me", "GH_TOKEN": "t", "GITHUB_REPOSITORY": "me/agency"}
    for key, value in {**base, **env}.items():
        monkeypatch.setenv(key, str(value))
    return load_bounty_settings()


def _bounty(**kw) -> Bounty:
    data = dict(repo="acme/lib", issue_number=7, title="Fix parser", url="https://github.com/acme/lib/issues/7",
                amount_usd=150, created_at=NOW - timedelta(days=3))
    data.update(kw)
    return Bounty(**data)


def _repo_info(**kw):
    info = {"archived": False, "language": "Python", "pushed_at": (NOW - timedelta(days=2)).isoformat()}
    info.update(kw)
    return info


def _comment(login: str, body: str, bot: bool = False):
    return {"user": {"login": login, "type": "Bot" if bot else "User"}, "body": body}


# ── discovery ─────────────────────────────────────────────────────────────────

def test_amount_prefers_label_then_bot_comment_then_title():
    assert extract_amount(["$250"], "[$50] x", ["💎 $100 bounty"], "$10") == 250
    assert extract_amount(["💎 Bounty"], "[$50] x", ["## 💎 $1,200 bounty • acme"], "") == 1200
    assert extract_amount([], "Fix it [$75]", [], "$10") == 75
    assert extract_amount([], "x", [], "pays $2k") == 2000
    assert extract_amount([], "x", [], "no money here") == 0


def test_candidate_skips_pull_requests_and_bad_slugs():
    item = {"repository_url": "https://api.github.com/repos/acme/lib", "number": 3, "title": "t",
            "html_url": "u", "labels": [{"name": "$100"}]}
    assert candidate_from_item(item, [], "algora").amount_usd == 100
    assert candidate_from_item({**item, "pull_request": {}}, []) is None
    bad = {**item, "repository_url": "https://api.github.com/repos/../../etc"}
    assert candidate_from_item(bad, []) is None


def test_platform_registry_and_claim_text():
    assert [p.platform_id for p in enabled_platforms("opire, algora,nope")] == ["opire", "algora"]
    assert "/claim #9" in PLATFORMS["algora"].claim_text(9)
    assert "Fixes #9" in PLATFORMS["generic"].claim_text(9)
    assert "/claim" not in PLATFORMS["generic"].claim_text(9)


# ── triage ────────────────────────────────────────────────────────────────────

def test_triage_accepts_a_fresh_uncontested_bounty(monkeypatch):
    verdict = triage(TriageInput(_bounty(), _repo_info()), _settings(monkeypatch), ROSTER, now=NOW)
    assert verdict.accept and verdict.agent_id == "hunter-python" and verdict.score > 0


@pytest.mark.parametrize("change, reason", [
    ({"repo_info": _repo_info(archived=True)}, "archived"),
    ({"bounty": _bounty(amount_usd=10)}, "below minimum"),
    ({"repo_info": _repo_info(language="COBOL")}, "no agent covers"),
    ({"bounty": _bounty(created_at=NOW - timedelta(days=400))}, "older than"),
    ({"repo_info": _repo_info(pushed_at=(NOW - timedelta(days=300)).isoformat())}, "unmaintained"),
    ({"comments": [_comment("algora-pbc[bot]", "🎉 The bounty has been rewarded to @x", bot=True)]}, "awarded"),
    ({"policy_text": "We do not accept AI-generated pull requests."}, "refuses AI"),
])
def test_triage_rejections(monkeypatch, change, reason):
    item = TriageInput(_bounty(), _repo_info())
    for key, value in change.items():
        setattr(item, key, value)
    verdict = triage(item, _settings(monkeypatch), ROSTER, now=NOW)
    assert not verdict.accept
    assert any(reason in r for r in verdict.reasons), verdict.reasons


def test_competitors_counted_per_user_excluding_self():
    comments = [_comment("a", "/attempt #7"), _comment("a", "/attempt #7 again"),
                _comment("b", "working on it\n/claim #7"), _comment("me", "/attempt #7"),
                _comment("c", "nice issue")]
    assert count_competitors(comments, "me") == 2


def test_too_many_competitors_rejects(monkeypatch):
    comments = [_comment(u, "/attempt") for u in "abc"]
    verdict = triage(TriageInput(_bounty(), _repo_info(), comments), _settings(monkeypatch), ROSTER, now=NOW)
    assert not verdict.accept and "3 competing attempts" in verdict.reasons


def test_paid_detection_ignores_humans():
    assert not already_paid([_comment("someone", "I was rewarded once")])
    assert already_paid([_comment("opire-bot[bot]", "Bounty claimed by @x")])


def test_ai_policy_detection_has_no_false_positive_on_neutral_text():
    assert bans_ai("PRs that are AI-generated will not be accepted.")
    assert not bans_ai("We use AI for triage. Please write tests for every PR.")


# ── ledger ────────────────────────────────────────────────────────────────────

def _record(agent: str, state: BountyState, revenue: float = 0.0) -> HuntRecord:
    return HuntRecord(bounty=_bounty(), agent_id=agent, state=state, revenue_usd=revenue)


def test_pnl_charges_review_time_and_counts_revenue():
    records = [_record("hunter-python", BountyState.FAILED),
               _record("hunter-python", BountyState.DECLINED),
               _record("hunter-python", BountyState.PAID, 150.0)]
    row = compute_pnl(records, ROSTER, review_cost_usd=5)["hunter-python"]
    assert (row.attempts, row.reviews, row.paid) == (3, 2, 1)
    assert row.cost_usd == 10 and row.net_usd == 140


def test_agents_that_never_earn_are_retired():
    records = [_record("hunter-web", BountyState.DECLINED) for _ in range(10)]
    pnl = compute_pnl(records, ROSTER, review_cost_usd=5)
    assert fitness(pnl["hunter-web"], retire_after=10) == 0
    share = allocate(pnl, slots=4, retire_after=10)
    assert share["hunter-web"] == 0 and sum(share.values()) == 4


def test_earners_get_more_slots_and_all_retired_means_no_work():
    records = [_record("hunter-python", BountyState.PAID, 500.0)]
    share = allocate(compute_pnl(records, ROSTER, 5), slots=6, retire_after=10)
    assert share["hunter-python"] > share["hunter-web"]
    dead = [_record(a.agent_id, BountyState.DECLINED) for a in ROSTER for _ in range(3)]
    assert sum(allocate(compute_pnl(dead, ROSTER, 5), 5, retire_after=3).values()) == 0


# ── tracker ───────────────────────────────────────────────────────────────────

def test_tracking_issue_round_trip_and_state_change_keeps_diff():
    record = HuntRecord(bounty=_bounty(title="@maintainer please"), agent_id="hunter-python",
                        state=BountyState.AWAITING_REVIEW, fork_repo="me/lib", branch="b", base_branch="main")
    body = tracker.render_body(record, "me", diff="+fixed\n```\n", test_log="1 passed")
    assert tracker.parse_record(body) == record
    assert "bounty:approved" in body and "```\n```" not in body
    assert "@maintainer" not in tracker.issue_title(record)
    moved = record.model_copy(update={"state": BountyState.SUBMITTED, "upstream_pr": 4})
    new_body = tracker.rerender(body, moved, "me")
    assert tracker.parse_record(new_body).state is BountyState.SUBMITTED
    assert "+fixed" in new_body and "Your decision" not in new_body
    assert tracker.labels_for(moved) == ["bounty-hunt", "bounty:submitted"]


def test_parse_record_tolerates_garbage():
    assert tracker.parse_record("no record") is None
    assert tracker.parse_record("<!-- bounty-record:v1\n{not json}\n-->") is None


def test_settings_defaults(monkeypatch):
    for key in ("BOUNTY_MIN_USD", "BOUNTY_PLATFORMS", "BOUNTY_HUNTER_ENABLED"):
        monkeypatch.delenv(key, raising=False)
    settings = _settings(monkeypatch, BOUNTY_MAX_COMPETITORS="oops")
    assert settings.min_usd == 50 and settings.platforms == "algora,opire"
    assert settings.max_competitors == 2 and settings.enabled is False

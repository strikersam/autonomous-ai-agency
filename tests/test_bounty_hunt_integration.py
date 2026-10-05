"""Integration tests: solver loop, patch guards on a real git repo, and the
approve → submit → merged → paid flow against a fake GitHub."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from packages.bounty import hunt, tracker
from packages.bounty.models import Bounty, BountyState, HuntRecord
from packages.bounty.solver import solve
from packages.bounty.workspace import git, inspect_patch
from packages.config.bounty_settings import load_bounty_settings


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "lib.py").write_text("def add(a, b):\n    return a - b\n")
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"]):
        assert asyncio.run(git(repo, *args)).code == 0
    return repo


def _call(name: str, **args: Any) -> dict[str, Any]:
    return {"id": name, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def _scripted_chat(turns: list[list[dict[str, Any]]]):
    queue = list(turns)

    async def chat(messages, tools):
        calls = queue.pop(0) if queue else []
        return {"choices": [{"message": {"content": "", "tool_calls": calls}}],
                "usage": {"total_tokens": 100}}

    return chat


BOUNTY = Bounty(repo="acme/lib", issue_number=7, title="add() subtracts", url="u", amount_usd=100)


def test_solver_writes_fix_and_finishes(tmp_path):
    repo = _git_repo(tmp_path)
    chat = _scripted_chat([
        [_call("read_file", path="lib.py")],
        [_call("write_file", path="lib.py", content="def add(a, b):\n    return a + b\n")],
        [_call("finish", summary="add() now adds")],
    ])
    result = asyncio.run(solve(BOUNTY, "body", [], repo, chat, max_steps=10, plan=None))
    assert result.finished and result.summary == "add() now adds"
    assert result.tokens == 300 and result.tests == "unverified"
    assert "a + b" in (repo / "lib.py").read_text()


def test_solver_refuses_protected_paths_and_enforces_max_steps(tmp_path):
    repo = _git_repo(tmp_path)
    chat = _scripted_chat([[_call("write_file", path=".github/workflows/x.yml", content="evil")]] * 5)
    result = asyncio.run(solve(BOUNTY, "", [], repo, chat, max_steps=3, plan=None))
    assert not result.finished and result.steps == 3
    assert not (repo / ".github").exists()


def test_solver_cannot_escape_the_workspace(tmp_path):
    repo = _git_repo(tmp_path)
    chat = _scripted_chat([[_call("read_file", path="../../etc/passwd")], [_call("finish", summary="x")]])
    asyncio.run(solve(BOUNTY, "", [], repo, chat, max_steps=3, plan=None))
    outside = tmp_path.parent / "escaped.txt"
    chat = _scripted_chat([[_call("write_file", path="../escaped.txt", content="x")], [_call("finish")]])
    asyncio.run(solve(BOUNTY, "", [], repo, chat, max_steps=3, plan=None))
    assert not (tmp_path / "escaped.txt").exists() and not outside.exists()


def test_patch_guards(tmp_path):
    repo = _git_repo(tmp_path)
    (repo / "lib.py").write_text("def add(a, b):\n    return a + b\n")
    assert asyncio.run(inspect_patch(repo, max_lines=50)).ok

    (repo / "key.txt").write_text("token = ghp_" + "a" * 30 + "\n")
    report = asyncio.run(inspect_patch(repo, max_lines=50))
    assert "patch contains a credential-shaped string" in report.problems

    (repo / "key.txt").unlink()
    (repo / "lib.py").unlink()
    report = asyncio.run(inspect_patch(repo, max_lines=50))
    assert any(p.startswith("deletes") for p in report.problems)


def test_empty_and_oversized_patches_rejected(tmp_path):
    repo = _git_repo(tmp_path)
    assert "empty patch" in asyncio.run(inspect_patch(repo, max_lines=50)).problems
    (repo / "big.py").write_text("x = 1\n" * 100)
    assert any("limit" in p for p in asyncio.run(inspect_patch(repo, max_lines=50)).problems)


class FakeGitHub:
    """Records writes; answers reads from canned data."""

    def __init__(self) -> None:
        self.issue_state = "open"
        self.comments: dict[int, list[dict[str, Any]]] = {}
        self.pull: dict[str, Any] = {"state": "open", "merged": False}
        self.created_pulls: list[dict[str, Any]] = []
        self.updates: list[dict[str, Any]] = []

    async def get_issue(self, repo, number):
        return {"state": self.issue_state, "body": ""}

    async def issue_comments(self, repo, number):
        return self.comments.get(number, [])

    async def create_pull(self, repo, **kw):
        self.created_pulls.append({"repo": repo, **kw})
        return {"number": 42}

    async def get_pull(self, repo, number):
        return self.pull

    async def update_issue(self, repo, number, **fields):
        self.updates.append(fields)
        return {}


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("BOUNTY_GITHUB_LOGIN", "me")
    monkeypatch.setenv("GH_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "me/agency")
    return load_bounty_settings()


def _awaiting() -> tuple[HuntRecord, str]:
    record = HuntRecord(bounty=BOUNTY, agent_id="hunter-python", state=BountyState.AWAITING_REVIEW,
                        fork_repo="me/lib", branch="bounty/7-fix", base_branch="main",
                        summary="add() now adds", tests="passed")
    return record, tracker.render_body(record, "me", diff="+a + b")


def test_approve_opens_claiming_pr_and_records_it(settings):
    gh = FakeGitHub()
    record, body = _awaiting()
    out = asyncio.run(hunt.submit(gh, settings, 5, body, record))
    assert out.state is BountyState.SUBMITTED and out.upstream_pr == 42
    pull = gh.created_pulls[0]
    assert pull["head"] == "me:bounty/7-fix" and pull["base"] == "main"
    assert "/claim #7" in pull["body"] and "Fixes #7" in pull["body"]
    assert "AI assistance" in pull["body"]
    assert gh.updates[-1]["labels"] == ["bounty-hunt", "bounty:submitted"]


def test_approve_does_nothing_when_bounty_already_gone(settings):
    gh = FakeGitHub()
    gh.issue_state = "closed"
    record, body = _awaiting()
    out = asyncio.run(hunt.submit(gh, settings, 5, body, record))
    assert out.state is BountyState.LOST and gh.created_pulls == []
    assert gh.updates[-1]["state"] == "closed"


def test_approve_is_idempotent_for_non_waiting_records(settings):
    gh = FakeGitHub()
    record, body = _awaiting()
    done = record.model_copy(update={"state": BountyState.SUBMITTED})
    assert asyncio.run(hunt.submit(gh, settings, 5, body, done)) is done
    assert gh.created_pulls == []


def test_decline_closes_the_record(settings):
    gh = FakeGitHub()
    record, body = _awaiting()
    out = asyncio.run(hunt.decline(gh, settings, 5, body, record))
    assert out.state is BountyState.DECLINED and gh.updates[-1]["state"] == "closed"


def test_merged_then_paid_books_revenue(settings):
    gh = FakeGitHub()
    record, body = _awaiting()
    submitted = record.model_copy(update={"state": BountyState.SUBMITTED, "upstream_pr": 42})
    gh.pull = {"state": "closed", "merged": True}
    merged = asyncio.run(hunt.advance(gh, settings, (5, submitted, body)))
    assert merged.state is BountyState.MERGED and merged.revenue_usd == 0
    gh.comments[42] = [{"user": {"login": "algora-pbc[bot]", "type": "Bot"},
                        "body": "🎉 @me has been rewarded $100"}]
    paid = asyncio.run(hunt.advance(gh, settings, (5, merged, body)))
    assert paid.state is BountyState.PAID and paid.revenue_usd == 100.0


def test_payout_to_someone_else_is_not_revenue(settings):
    gh = FakeGitHub()
    record, body = _awaiting()
    merged = record.model_copy(update={"state": BountyState.MERGED, "upstream_pr": 42})
    gh.comments[7] = [{"user": {"login": "algora-pbc[bot]", "type": "Bot"},
                       "body": "🎉 @rival has been rewarded $100"}]
    assert asyncio.run(hunt.advance(gh, settings, (5, merged, body))).state is BountyState.MERGED


def test_closed_unmerged_pr_is_lost(settings):
    gh = FakeGitHub()
    record, body = _awaiting()
    submitted = record.model_copy(update={"state": BountyState.SUBMITTED, "upstream_pr": 42})
    gh.pull = {"state": "closed", "merged": False}
    assert asyncio.run(hunt.advance(gh, settings, (5, submitted, body))).state is BountyState.LOST


@pytest.mark.parametrize("path", ["./.github/x.yml", ".git/config", "a/../.github/y", "/.github/z"])
def test_protected_path_variants_are_refused(tmp_path, path):
    repo = _git_repo(tmp_path)
    chat = _scripted_chat([[_call("write_file", path=path, content="evil")], [_call("finish", summary="")]])
    asyncio.run(solve(BOUNTY, "", [], repo, chat, max_steps=3, plan=None))
    assert asyncio.run(git(repo, "status", "--porcelain")).out.strip() == ""


class FullQueueGitHub(FakeGitHub):
    """Tracking repo already holds the maximum number of open reviews."""

    def __init__(self, open_reviews: int) -> None:
        super().__init__()
        record, body = _awaiting()
        self.issues = [{"number": n, "body": body} for n in range(1, open_reviews + 1)]
        self.searched = False
        self.created: list[str] = []

    async def list_tracking_issues(self, repo, label, state="all"):
        return self.issues if label == tracker.TRACK_LABEL else []

    async def search_issues(self, query, per_page=50, page=1):
        self.searched = True
        return []

    async def create_issue(self, repo, title, body, labels):
        self.created.append(title)
        return {"number": 99}


def test_full_review_queue_stops_new_work(settings):
    gh = FullQueueGitHub(open_reviews=settings.max_open_reviews)
    summary = asyncio.run(hunt.run_hunt(gh, settings, chat=_scripted_chat([])))
    assert "Slots this run: 0" in summary and not gh.searched


def test_ledger_goes_to_the_run_summary_never_a_public_issue(settings):
    # A public "Bounty hunter ledger" issue drew a stranger's bounty bot, which
    # opened a PR against it asking to be paid (PR #1668).
    gh = FullQueueGitHub(open_reviews=0)
    summary = asyncio.run(hunt.run_hunt(gh, settings, chat=None))
    assert "hunter-python" in summary and "Agency total" in summary
    assert gh.created == []


def test_waiting_review_expires_when_bounty_closes(settings):
    gh = FakeGitHub()
    record, body = _awaiting()
    assert asyncio.run(hunt.advance(gh, settings, (5, record, body))).state is BountyState.AWAITING_REVIEW
    gh.issue_state = "closed"
    assert asyncio.run(hunt.advance(gh, settings, (5, record, body))).state is BountyState.LOST


class SearchGitHub(FakeGitHub):
    """Search answers per query; one platform's search fails outright."""

    async def search_issues(self, query, per_page=50, page=1):
        if page > 1:
            return []
        if "opire" in query:
            raise hunt.GitHubError("HTTP 403")
        return [
            {"repository_url": "https://api.github.com/repos/acme/lib", "number": 7, "title": "x [$100]",
             "html_url": "u", "labels": [{"name": "💎 Bounty"}]},
            {"repository_url": "https://api.github.com/repos/../../etc", "number": 1, "title": "$500"},
            {"repository_url": "https://api.github.com/repos/acme/lib", "number": 8, "title": "seen"},
        ]

    async def get_repo(self, repo):
        return {"archived": False, "language": "Python"}

    async def policy_text(self, repo):
        return ""


def test_discovery_survives_failures_and_skips_known_and_invalid(settings):
    found = asyncio.run(hunt.discover(SearchGitHub(), settings, {"acme/lib#8"}))
    assert [(c.bounty.key, c.bounty.amount_usd) for c in found] == [("acme/lib#7", 100)]


class SpamGitHub(SearchGitHub):
    """One repository labels dozens of issues; one real bounty sits behind them."""

    async def search_issues(self, query, per_page=50, page=1):
        if "opire" in query or page > 1:
            return []
        spam = [{"repository_url": "https://api.github.com/repos/spam/farm", "number": n, "title": "$100"}
                for n in range(1, 40)]
        real = {"repository_url": "https://api.github.com/repos/acme/lib", "number": 7, "title": "x [$100]"}
        return [*spam, real]


def test_one_repo_cannot_crowd_out_the_rest(settings):
    found = asyncio.run(hunt.discover(SpamGitHub(), settings, set()))
    repos = [c.bounty.repo for c in found]
    assert repos.count("spam/farm") == hunt.MAX_PER_REPO and "acme/lib" in repos


def test_rejection_summary_groups_reasons():
    from packages.bounty.models import Verdict
    scored = [(None, Verdict(accept=False, reasons=["amount $10 below minimum $50"])),
              (None, Verdict(accept=False, reasons=["amount $20 below minimum $50"])),
              (None, Verdict(accept=True))]
    assert hunt.rejection_summary(scored) == ["- rejected (2×): amount N below minimum N"]

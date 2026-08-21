"""tests/test_pr_approval_gate.py — the green-PR Telegram approval sweep.

Covers the pure decision logic (`pr_is_green`, `select_notifiable`) and the
`run_sweep` orchestrator over injected fake adapters, plus the Telegram
callback_data contract the card relies on.
"""
from __future__ import annotations

import asyncio

import pytest

from services import pr_approval_gate as gate


# ── pr_is_green ──────────────────────────────────────────────────────────────


class TestPrIsGreen:
    def test_all_success_is_green(self):
        runs = [
            {"status": "completed", "conclusion": "success"},
            {"status": "completed", "conclusion": "skipped"},
            {"status": "completed", "conclusion": "neutral"},
        ]
        assert gate.pr_is_green(runs) is True

    def test_empty_is_not_green(self):
        assert gate.pr_is_green([]) is False

    def test_incomplete_is_not_green(self):
        assert gate.pr_is_green([{"status": "in_progress", "conclusion": None}]) is False

    def test_a_failure_is_not_green(self):
        runs = [
            {"status": "completed", "conclusion": "success"},
            {"status": "completed", "conclusion": "failure"},
        ]
        assert gate.pr_is_green(runs) is False


# ── select_notifiable ────────────────────────────────────────────────────────


def _pr(number: int, sha: str, *, draft: bool = False, state: str = "open") -> dict:
    return {"number": number, "draft": draft, "state": state, "head": {"sha": sha}}


class TestSelectNotifiable:
    def test_green_unnotified_open_pr_is_selected(self):
        prs = [_pr(1, "aaa")]
        checks = {1: [{"status": "completed", "conclusion": "success"}]}
        out = gate.select_notifiable(prs, checks, set())
        assert [p["number"] for p in out] == [1]

    def test_draft_is_skipped(self):
        prs = [_pr(1, "aaa", draft=True)]
        checks = {1: [{"status": "completed", "conclusion": "success"}]}
        assert gate.select_notifiable(prs, checks, set()) == []

    def test_already_notified_same_sha_is_skipped(self):
        prs = [_pr(1, "aaa")]
        checks = {1: [{"status": "completed", "conclusion": "success"}]}
        assert gate.select_notifiable(prs, checks, {"1:aaa"}) == []

    def test_new_sha_re_notifies(self):
        prs = [_pr(1, "bbb")]
        checks = {1: [{"status": "completed", "conclusion": "success"}]}
        out = gate.select_notifiable(prs, checks, {"1:aaa"})  # old sha notified
        assert [p["number"] for p in out] == [1]

    def test_red_pr_is_skipped(self):
        prs = [_pr(1, "aaa")]
        checks = {1: [{"status": "completed", "conclusion": "failure"}]}
        assert gate.select_notifiable(prs, checks, set()) == []


# ── run_sweep (injected fakes) ───────────────────────────────────────────────


class TestRunSweep:
    def _run(self, **kw):
        return asyncio.run(gate.run_sweep(persist=False, **kw))

    def test_cards_green_prs_and_records_them(self):
        prs = [_pr(1, "aaa"), _pr(2, "bbb", draft=True), _pr(3, "ccc")]
        green = {"aaa": True, "ccc": False}
        sent: list[int] = []

        async def list_open_prs():
            return prs

        async def get_check_runs(sha):
            return [{"status": "completed", "conclusion": "success" if green.get(sha) else "failure"}]

        async def send_card(pr):
            sent.append(pr["number"])
            return True

        notified: set[str] = set()
        carded = self._run(
            list_open_prs=list_open_prs, get_check_runs=get_check_runs,
            send_card=send_card, notified=notified,
        )
        assert carded == [1]          # only the green, non-draft PR
        assert sent == [1]
        assert "1:aaa" in notified    # recorded so it won't re-card next sweep

    def test_failed_send_is_not_recorded(self):
        async def list_open_prs():
            return [_pr(1, "aaa")]

        async def get_check_runs(sha):
            return [{"status": "completed", "conclusion": "success"}]

        async def send_card(pr):
            return False  # Telegram send failed

        notified: set[str] = set()
        carded = self._run(
            list_open_prs=list_open_prs, get_check_runs=get_check_runs,
            send_card=send_card, notified=notified,
        )
        assert carded == []
        assert notified == set()  # not recorded → will retry next sweep

    def test_list_failure_is_fail_soft(self):
        async def list_open_prs():
            raise RuntimeError("GitHub down")

        async def get_check_runs(sha):
            return []

        async def send_card(pr):
            return True

        assert self._run(
            list_open_prs=list_open_prs, get_check_runs=get_check_runs,
            send_card=send_card, notified=set(),
        ) == []


# ── Telegram callback_data contract ──────────────────────────────────────────


def test_card_keyboard_callback_data_parses_to_pr_actions():
    """The card's buttons must parse to pr_merge / pr_reject with the PR number."""
    import telegram_bot as tb
    kb = gate._card_keyboard(1278)
    datas = [btn["callback_data"] for row in kb["inline_keyboard"] for btn in row]
    assert datas == ["fb:pr_merge:1278", "fb:pr_reject:1278"]
    for data in datas:
        action, arg = tb._parse_callback(data)
        assert action.startswith("pr_")
        assert arg == "1278"

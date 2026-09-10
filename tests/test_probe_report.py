"""tests/test_probe_report.py — the catalogue-probe drift-report step.

`probe_report.py` turns a probe `--json` summary into exactly one tracking
issue — but only for a **retired** model id (HTTP 404/410), the one failure a
repo config change fixes. Account/transient failures (402 billing, 400
out-of-credit, 429, 5xx, timeouts, unreachable providers) are logged, never
ticketed — that noise is what made issue #1434 churn. The GitHub operations are
injected so the branching is verified without a network.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GITHUB_SCRIPTS = REPO_ROOT / ".github/scripts"


@pytest.fixture
def report():
    sys.path.insert(0, str(GITHUB_SCRIPTS))
    import probe_report as mod

    return mod


class _Recorder:
    """Injectable stand-ins for the three GitHub operations."""

    def __init__(self, existing: list[dict] | None = None):
        self._existing = existing or []
        self.created: list[tuple] = []
        self.updated: list[tuple] = []

    def list_issues(self) -> list[dict]:
        return self._existing

    def create_issue(self, title, body, label) -> dict:
        self.created.append((title, body, label))
        return {"number": 4242}

    def update_issue(self, number, title, body) -> dict:
        self.updated.append((number, title, body))
        return {"number": number}

    def run(self, report_mod, summary):
        return report_mod.run(
            summary,
            list_issues=self.list_issues,
            create_issue=self.create_issue,
            update_issue=self.update_issue,
        )


# A retired id (404/410) — the only repo-actionable drift.
_RETIRED = {
    "ok": False,
    "reachable": 2,
    "unreachable": [],
    "unlistable": [],
    "unservable": ["nvidia:old/retired-model"],
    "unservable_detail": [{"id": "nvidia:old/retired-model", "detail": "HTTP 410"}],
}

# The real issue-#1434 shape: billing / out-of-credit / outage / unreachable —
# all account or transient, none repo-actionable.
_TRANSIENT = {
    "ok": False,
    "reachable": 1,
    "unreachable": ["groq"],
    "unlistable": [],
    "unservable": [
        "cerebras:gpt-oss-120b",
        "nvidia:nvidia/nemotron-3-super-120b-a12b",
        "anthropic:claude-sonnet-5",
    ],
    "unservable_detail": [
        {"id": "cerebras:gpt-oss-120b", "detail": "HTTP 402"},
        {"id": "nvidia:nvidia/nemotron-3-super-120b-a12b", "detail": "HTTP 503"},
        {"id": "anthropic:claude-sonnet-5", "detail": "HTTP 400"},
    ],
}

_GREEN = {
    "ok": True,
    "reachable": 4,
    "unreachable": [],
    "unlistable": [],
    "unservable": [],
    "unservable_detail": [],
}


class TestReconciliation:
    def test_green_run_touches_no_issue(self, report):
        rec = _Recorder()
        assert rec.run(report, _GREEN) == "noop"
        assert rec.created == [] and rec.updated == []

    def test_transient_and_account_failures_are_not_filed(self, report):
        # 402/503/400 + an unreachable provider: real failures, but nothing a
        # config edit fixes — must never open a ticket (the #1434 churn).
        rec = _Recorder(existing=[])
        assert rec.run(report, _TRANSIENT) == "noop"
        assert rec.created == [] and rec.updated == []

    def test_a_reachable_but_unlistable_provider_is_not_drift(self, report):
        summary = {
            "ok": True, "reachable": 1, "unreachable": [], "unlistable": ["nvidia"],
            "unservable": [], "unservable_detail": [],
        }
        rec = _Recorder()
        assert rec.run(report, summary) == "noop"
        assert rec.created == [] and rec.updated == []

    def test_a_retired_id_creates_one_issue(self, report):
        rec = _Recorder(existing=[])
        result = rec.run(report, _RETIRED)
        assert result == "created:#4242"
        assert len(rec.created) == 1 and rec.updated == []
        title, body, label = rec.created[0]
        assert label == report.DEFAULT_LABEL
        assert report.MARKER in body
        assert "nvidia:old/retired-model" in body
        assert "HTTP 410" in body

    def test_repeat_retired_updates_the_existing_issue(self, report):
        existing = [{"number": 77, "body": f"old text\n{report.MARKER}\n"}]
        rec = _Recorder(existing=existing)
        result = rec.run(report, _RETIRED)
        assert result == "updated:#77"
        assert rec.created == [] and len(rec.updated) == 1
        number, _title, body = rec.updated[0]
        assert number == 77 and "HTTP 410" in body

    def test_retired_among_transient_still_files_only_the_retired(self, report):
        mixed = dict(_TRANSIENT)
        mixed["unservable"] = _TRANSIENT["unservable"] + ["nvidia:old/retired-model"]
        mixed["unservable_detail"] = _TRANSIENT["unservable_detail"] + [
            {"id": "nvidia:old/retired-model", "detail": "HTTP 404"}
        ]
        rec = _Recorder(existing=[])
        assert rec.run(report, mixed) == "created:#4242"
        _title, body, _label = rec.created[0]
        assert "nvidia:old/retired-model" in body
        # The transient/account ids are not promoted into the ticket body.
        assert "cerebras:gpt-oss-120b" not in body
        assert "HTTP 402" not in body

    def test_a_pull_request_with_the_marker_is_ignored(self, report):
        existing = [{"number": 9, "pull_request": {}, "body": report.MARKER}]
        rec = _Recorder(existing=existing)
        assert rec.run(report, _RETIRED) == "created:#4242"
        assert len(rec.created) == 1


class TestBuildBody:
    def test_body_carries_marker_and_only_retired_ids(self, report):
        mixed = dict(_TRANSIENT)
        mixed["unservable_detail"] = _TRANSIENT["unservable_detail"] + [
            {"id": "nvidia:old/retired-model", "detail": "HTTP 410"}
        ]
        body = report.build_body(mixed, now="2026-09-10 06:00 UTC")
        assert report.MARKER in body
        assert "nvidia:old/retired-model" in body
        assert "HTTP 410" in body
        assert "2026-09-10 06:00 UTC" in body
        # Account/transient ids stay out of the ticket.
        assert "cerebras:gpt-oss-120b" not in body


class TestIsRetired:
    def test_404_and_410_are_retired(self, report):
        assert report._is_retired("HTTP 404")
        assert report._is_retired("HTTP 410")

    def test_account_and_transient_codes_are_not_retired(self, report):
        for detail in ("HTTP 402", "HTTP 400", "HTTP 429", "HTTP 503", "TimeoutError", ""):
            assert not report._is_retired(detail)


class TestFindTrackingIssue:
    def test_matches_on_the_marker(self, report):
        issues = [
            {"number": 1, "body": "unrelated"},
            {"number": 2, "body": f"drift here {report.MARKER}"},
        ]
        found = report.find_tracking_issue(issues)
        assert found is not None and found["number"] == 2

    def test_returns_none_when_absent(self, report):
        assert report.find_tracking_issue([{"number": 1, "body": "none here"}]) is None

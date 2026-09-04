"""tests/test_probe_report.py — the catalogue-probe drift-report step.

`probe_report.py` turns a probe `--json` summary into exactly one tracking
issue: created when drift first appears, updated (never duplicated) on repeat
failures, and left entirely untouched on a clean run. The GitHub operations are
injected so this branching is verified without a network — the acceptance-test
requirement for issue #1422 item 1.
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


_DRIFT = {
    "ok": False,
    "reachable": 2,
    "unreachable": ["groq"],
    "unlistable": [],
    "unservable": ["cerebras:gpt-oss-120b"],
    "unservable_detail": [{"id": "cerebras:gpt-oss-120b", "detail": "HTTP 402"}],
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
        assert rec.created == []
        assert rec.updated == []

    def test_a_reachable_but_unlistable_provider_is_not_drift(self, report):
        # unlistable means the provider *answered* but would not list — reachable,
        # not drifted. It must not, on its own, open an issue.
        summary = {
            "ok": True,
            "reachable": 1,
            "unreachable": [],
            "unlistable": ["nvidia"],
            "unservable": [],
            "unservable_detail": [],
        }
        rec = _Recorder()
        assert rec.run(report, summary) == "noop"
        assert rec.created == [] and rec.updated == []

    def test_first_drift_creates_one_issue(self, report):
        rec = _Recorder(existing=[])
        result = rec.run(report, _DRIFT)
        assert result == "created:#4242"
        assert len(rec.created) == 1
        assert rec.updated == []
        title, body, label = rec.created[0]
        assert label == report.DEFAULT_LABEL
        assert report.MARKER in body
        # Provider, model id, and status code are all named.
        assert "cerebras:gpt-oss-120b" in body
        assert "HTTP 402" in body
        assert "groq" in body

    def test_repeat_drift_updates_the_existing_issue(self, report):
        existing = [{"number": 77, "body": f"old text\n{report.MARKER}\n"}]
        rec = _Recorder(existing=existing)
        result = rec.run(report, _DRIFT)
        assert result == "updated:#77"
        assert rec.created == []
        assert len(rec.updated) == 1
        number, _title, body = rec.updated[0]
        assert number == 77
        assert "HTTP 402" in body

    def test_a_pull_request_with_the_marker_is_ignored(self, report):
        # The issues endpoint returns PRs too; a PR must never be mistaken for
        # the tracker (that would suppress a real issue).
        existing = [{"number": 9, "pull_request": {}, "body": report.MARKER}]
        rec = _Recorder(existing=existing)
        assert rec.run(report, _DRIFT) == "created:#4242"
        assert len(rec.created) == 1


class TestBuildBody:
    def test_body_carries_marker_and_every_failure(self, report):
        body = report.build_body(_DRIFT, now="2026-09-04 06:00 UTC")
        assert report.MARKER in body
        assert "cerebras:gpt-oss-120b" in body
        assert "HTTP 402" in body
        assert "groq" in body
        assert "2026-09-04 06:00 UTC" in body


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

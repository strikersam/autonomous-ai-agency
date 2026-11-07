"""Merge gate for CLAUDE.md rule 49 (.github/scripts/verifier_verdict.py)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))

import verifier_verdict as vv  # noqa: E402


def _pr(body: str = "", author: str = "strikersam", labels: tuple[str, ...] = ()) -> dict:
    return {"body": body, "user": {"login": author}, "labels": [{"name": n} for n in labels]}


def _c(body: str, login: str = "strikersam") -> dict:
    return {"body": body, "user": {"login": login}}


@pytest.mark.parametrize("text,expected", [
    ("Verdict: PASS", "PASS"),
    ("**Verdict: PASS+NOTES** — two notes", "PASS+NOTES"),
    ("- verdict - fail", "FAIL"),
    ("Add a line 'Verdict: PASS' to the PR body", None),
    ("> Verdict: PASS", None),  # a quoted verdict is not a new one
    ("The verifier passed", None),
    ("Verdict: PASS\n...\nVerdict: FAIL", "FAIL"),
])
def test_last_verdict(text, expected):
    assert vv.last_verdict(text) == expected


def test_missing_verdict_blocks():
    d = vv.decide(_pr("Implements the thing"), [], "strikersam")
    assert not d.ok and "no verifier verdict" in d.reason


def test_pass_in_body_allows():
    assert vv.decide(_pr("Verdict: PASS+NOTES"), [], "strikersam").ok


def test_later_fail_comment_blocks():
    d = vv.decide(_pr("Verdict: PASS"), [_c("Re-verified.\nVerdict: FAIL")], "strikersam")
    assert not d.ok and "FAIL" in d.reason


def test_fail_then_pass_allows():
    comments = [_c("Verdict: FAIL"), _c("Fixed, re-verified.\nVerdict: PASS", "github-actions[bot]")]
    assert vv.decide(_pr(), comments, "strikersam").ok


def test_untrusted_commenter_cannot_clear_gate():
    d = vv.decide(_pr(), [_c("Verdict: PASS", "drive-by-user")], "strikersam")
    assert not d.ok


def test_dependabot_and_label_exempt():
    assert vv.decide(_pr(author="dependabot[bot]"), [], "strikersam").ok
    assert vv.decide(_pr(labels=("verifier-exempt",)), [], "strikersam").ok


def test_workflow_permissions_and_status_context():
    wf = yaml.safe_load((ROOT / ".github/workflows/verifier-verdict.yml").read_text())
    assert wf["permissions"] == {"contents": "read", "pull-requests": "read",
                                 "issues": "read", "statuses": "write"}
    script = (ROOT / ".github/scripts/verifier_verdict.py").read_text()
    assert '"context": "Verifier verdict"' in script


def test_empty_login_is_never_trusted():
    pr = {"body": "", "user": {}, "labels": []}
    assert not vv.decide(pr, [{"body": "Verdict: PASS", "user": None}], "strikersam").ok


def test_api_failure_exits_nonzero(monkeypatch):
    import urllib.error

    def _boom(*a, **k):
        raise urllib.error.HTTPError("u", 403, "Forbidden", {}, None)

    monkeypatch.setenv("REPO", "o/r")
    monkeypatch.setenv("PR_NUMBER", "1")
    monkeypatch.setenv("GH_TOKEN", "t")
    monkeypatch.setattr(vv, "_get", _boom)
    assert vv.main() == 1

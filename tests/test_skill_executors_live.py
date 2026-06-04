"""tests/test_skill_executors_live.py — live graphify + council-review executors.

These two skills were previously descriptor-only (returned a "skill_registered"
stub).  They now run real logic: graphify queries the committed knowledge-graph
artifacts, and council-review performs deterministic rules-based static analysis
over a diff.  No mocks, no canned verdicts.
"""
from __future__ import annotations

from services.skill_bindings import _run_graphify, _run_council_review, get_skill_bindings


# ── graphify ──────────────────────────────────────────────────────────────────


def test_graphify_report_reads_real_artifact():
    out = _run_graphify({"action": "report"})
    # The repo ships graphify-out/GRAPH_REPORT.md, so this must be a real read.
    assert out["available"] is True
    assert out["source"] in ("graph-report", "graphify-cli")
    assert out.get("total_lines", 0) > 0


def test_graphify_search_returns_real_matches():
    out = _run_graphify({"action": "query", "query": "WorkflowOrchestrator"})
    assert out["available"] is True
    # Either CLI answered or we searched the report — both are real sources.
    assert out["source"] in ("graphify-cli", "graph-report-search")


def test_graphify_is_enabled_in_registry():
    skill = get_skill_bindings().get("graphify")
    assert skill is not None and skill.is_enabled is True


# ── council-review ──────────────────────────────────────────────────────────────


def test_council_flags_hardcoded_secret_and_rejects():
    diff = '+++ b/app.py\n+api_key = "sk-live-abcdef123456"\n+print("debug")\n'
    out = _run_council_review({"diff": diff, "changed_files": ["app.py"]})
    assert out["verdict"] == "REJECTED"  # high-severity secret finding
    assert out["perspectives"]["security"] == "FAIL"
    messages = " ".join(f["message"] for f in out["findings"])
    assert "credential" in messages.lower() or "secret" in messages.lower()


def test_council_clean_diff_is_approved():
    diff = (
        "+++ b/util.py\n"
        "+def add(a: int, b: int) -> int:\n"
        "+    return a + b\n"
    )
    out = _run_council_review({"diff": diff, "changed_files": ["util.py"]})
    assert out["verdict"] == "APPROVED"
    assert all(v == "PASS" for v in out["perspectives"].values())


def test_council_empty_diff_is_blocked():
    out = _run_council_review({"diff": "   "})
    assert out["verdict"] == "BLOCKED"


def test_council_print_is_maintainability_warning_not_rejection():
    diff = "+++ b/x.py\n+print('hello')\n"
    out = _run_council_review({"diff": diff})
    # print() is low severity → WARN, not a hard fail.
    assert out["verdict"] in ("APPROVED_WITH_CONDITIONS", "APPROVED")
    assert out["perspectives"]["maintainability"] in ("WARN", "FAIL")


def test_council_review_is_enabled_in_registry():
    skill = get_skill_bindings().get("council-review")
    assert skill is not None and skill.is_enabled is True

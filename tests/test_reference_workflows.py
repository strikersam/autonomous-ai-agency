"""Phase 7: the three reference workflows on deterministic fixtures (no network, no LLM)."""
from __future__ import annotations

import asyncio
import json

import pytest

from packages.runs.approvals import RunApprovals
from packages.runs.artifacts import ArtifactStore
from packages.runs.composer import Composer
from packages.runs.models import RunState
from packages.runs.reference_workflows import (BugFixture, BugToPrWorkflow, CiFailure,
                                               FailureClass, QaFanoutWorkflow, QaFixture,
                                               QaInvestigationWorkflow, QualityReport)
from packages.runs.reference_workflows.qa_fanout import AgentFixture
from packages.runs.reference_workflows.qa_investigation import CiPipeline
from packages.runs.side_effects import ReleaseNotApproved, require_release_approval
from packages.runs.store import RunStore


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for key in ("AGENCY_KILL_SWITCH", "RUNS_MAX_CHILDREN", "RUNS_MAX_DEPTH", "RUNS_MAX_PARALLEL"):
        monkeypatch.delenv(key, raising=False)


async def drive(wf, spec):
    store = wf.executor.runs
    composer = Composer(store, wf.executor, cancel_poll_s=0.01)
    root = await composer.start(spec)
    return composer, root, await composer.run(root.run_id, spec)


async def artifact_json(store: RunStore, run_id: str, name: str) -> dict:
    arts = ArtifactStore(store)
    ref = next(r for r in await arts.list(run_id) if r.name == name)
    return json.loads((await arts.get(run_id, ref.artifact_id)).content)


# ── workflow A ────────────────────────────────────────────────────────────────

async def test_a_bug_to_pr_stops_at_human_approval_with_a_complete_draft_pr():
    wf = BugToPrWorkflow(RunStore())
    composer, root, res = await drive(wf, wf.spec())
    assert res.state == "waiting_for_approval" and res.waiting_on == "human_approval"
    assert wf.executor.calls == ["triage", "coding", "tests", "verify", "draft_pr"]
    pr = await artifact_json(wf.executor.runs, root.run_id, "draft-pull-request.json")
    assert pr["acceptance_criteria"] and pr["implementation_summary"] and pr["tests"]
    assert pr["evidence_links"][0].startswith(f"/api/runs/{root.run_id}/artifacts/art_")
    assert pr["draft"] is True and pr["merge"].startswith("blocked")
    verdict = res.results["verify"].output
    assert verdict["verdict"] == "PASS" and verdict["verifier"].startswith("verifier:")
    # a person approves and the run resumes to success without redoing a step
    await composer.approve(root.run_id, "human_approval", actor="priya")
    done = await composer.run(root.run_id, wf.spec())
    assert done.state == "succeeded" and wf.executor.calls.count("coding") == 1


@pytest.mark.parametrize("fixture", [
    BugFixture(tests_ran=False, tests_passed=None, tests_failed=None),
    BugFixture(tests_passed=3, tests_failed=2),
    BugFixture(tests_passed=None, tests_failed=0)], ids=["missing", "failing", "incomplete"])
async def test_a_verifier_fails_on_a_missing_or_failing_test_result(fixture):
    wf = BugToPrWorkflow(RunStore(), fixture)
    _, root, res = await drive(wf, wf.spec())
    assert res.state == "failed" and res.results["verify"].state == "failed"
    assert res.results["draft_pr"].state == "skipped"
    assert "draft_pr" not in wf.executor.calls
    arts = [a.name for a in await ArtifactStore(wf.executor.runs).list(root.run_id)]
    assert "draft-pull-request.json" not in arts


async def test_a_never_merges_or_deploys_without_approval():
    from agent.autonomy_gate import AutonomyViolation, assert_agent_can_merge

    wf = BugToPrWorkflow(RunStore())
    _, root, res = await drive(wf, wf.spec())
    assert res.results["draft_pr"].output["guards"] == {"merge": "blocked", "deploy": "blocked"}
    with pytest.raises(AutonomyViolation):
        assert_agent_can_merge(agent_initiated=True)
    with pytest.raises(ReleaseNotApproved):
        await require_release_approval(root.run_id, "deploy", {"issue": "BUG-101"},
                                       {"env": "production"}, store=wf.executor.runs)


async def test_a_draft_step_fails_when_a_release_guard_is_open(monkeypatch):
    import packages.runs.reference_workflows.bug_to_pr as mod

    monkeypatch.setattr(mod, "assert_agent_can_merge", lambda **_: None)  # a broken merge gate
    wf = BugToPrWorkflow(RunStore())
    _, _, res = await drive(wf, wf.spec())
    assert res.results["draft_pr"].state == "failed" and "guard open" in res.results["draft_pr"].error


# ── workflow B ────────────────────────────────────────────────────────────────

async def test_b_investigation_classifies_every_failure_class():
    wf = QaInvestigationWorkflow(RunStore())
    _, root, res = await drive(wf, wf.spec())
    assert res.state == "succeeded" and res.results["verify"].output["verdict"] == "PASS"
    report = QualityReport.model_validate(
        await artifact_json(wf.executor.runs, root.run_id, "quality-report.json"))
    by_test = {f.test: f for f in report.findings}
    assert by_test["test_checkout_total"].classification is FailureClass.APPLICATION_DEFECT
    assert by_test["test_search_debounce"].classification is FailureClass.FLAKY_TEST
    assert by_test["test_upload"].classification is FailureClass.INFRASTRUCTURE_FAILURE
    assert by_test["test_pdf_export"].classification is FailureClass.ENVIRONMENT_ISSUE
    assert by_test["test_mystery"].classification is FailureClass.INCONCLUSIVE
    assert report.total_failures == 5 and sum(report.counts.values()) == 5
    assert all(f.evidence for f in report.findings if f.classification is not FailureClass.INCONCLUSIVE)


async def test_b_verifier_fails_a_failed_pipeline_with_no_failure_record():
    wf = QaInvestigationWorkflow(RunStore(), CiPipeline(status="failed", failures=[]))
    _, _, res = await drive(wf, wf.spec())
    assert res.state == "failed" and res.results["verify"].state == "failed"
    assert "no failure record" in res.results["verify"].error


def test_b_verifier_rejects_an_unevidenced_or_miscounted_report():
    from packages.runs.reference_workflows import FailureFinding
    from packages.runs.reference_workflows.qa_investigation import report_defects

    bare = FailureFinding(test="t1", classification=FailureClass.APPLICATION_DEFECT, reason="x")
    report = QualityReport(pipeline="p", total_failures=2, findings=[bare], counts={"application_defect": 1})
    defects = report_defects(report, ["t1", "t2"], "failed")
    assert any("t2 is not classified" in d for d in defects)
    assert any("no log evidence" in d for d in defects)
    assert any("counts do not match" in d for d in defects)


async def test_b_a_secret_in_a_ci_log_is_redacted_in_the_report_artifact():
    secret = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
    pipe = CiPipeline(failures=[CiFailure(test="t", log=[f"AssertionError: token={secret}"])])
    wf = QaInvestigationWorkflow(RunStore(), pipe)
    _, root, _ = await drive(wf, wf.spec())
    arts = ArtifactStore(wf.executor.runs)
    for ref in await arts.list(root.run_id):
        assert secret not in (await arts.get(root.run_id, ref.artifact_id)).content


# ── workflow C ────────────────────────────────────────────────────────────────

async def test_c_fanout_runs_agents_in_parallel_within_the_cap(monkeypatch):
    monkeypatch.setenv("RUNS_MAX_PARALLEL", "2")
    wf = QaFanoutWorkflow(RunStore())
    running = peak = 0
    inner = wf.executor._steps.copy()

    def slow(fn):
        async def run(job):
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.05)
            running -= 1
            return await fn(job)
        return run

    for name in ("regression", "accessibility", "api_smoke"):
        wf.executor._steps[name] = slow(inner[name])
    _, root, res = await drive(wf, wf.spec())
    assert res.state == "succeeded" and peak == 2
    got = await artifact_json(wf.executor.runs, root.run_id, "consolidated-assessment.json")
    assert got["overall"] == "pass" and got["failed_agents"] == []


async def test_c_one_agent_failing_still_yields_an_assessment_that_marks_it():
    fx = QaFixture(agents={"regression": AgentFixture(), "accessibility": AgentFixture(fails=True),
                           "api_smoke": AgentFixture()})
    wf = QaFanoutWorkflow(RunStore(), fx)
    _, root, res = await drive(wf, wf.spec())
    assert res.state == "succeeded" and res.partial is True
    assert res.results["accessibility"].state == "failed"
    got = await artifact_json(wf.executor.runs, root.run_id, "consolidated-assessment.json")
    assert got["overall"] == "partial" and got["failed_agents"] == ["accessibility"]
    assert res.results["verify"].output["verdict"] == "PASS"


async def test_c_verifier_fails_on_a_missing_test_result():
    fx = QaFixture(agents={"regression": AgentFixture(passed=None, failed=None),
                           "accessibility": AgentFixture(), "api_smoke": AgentFixture()})
    wf = QaFanoutWorkflow(RunStore(), fx)
    _, _, res = await drive(wf, wf.spec())
    assert res.state == "failed" and "no test result" in res.results["verify"].error


def test_c_verifier_rejects_a_pass_claim_over_failing_tests():
    from packages.runs.reference_workflows import AgentAssessment, ConsolidatedAssessment
    from packages.runs.reference_workflows.qa_fanout import assessment_defects

    rows = [AgentAssessment(agent=a, status="completed", tests_passed=5, tests_failed=1 if a == "regression" else 0)
            for a in ("regression", "accessibility", "api_smoke")]
    claim = ConsolidatedAssessment(overall="pass", agents=rows)
    assert any("not supported" in d for d in assessment_defects(claim))
    assert not assessment_defects(claim.model_copy(update={"overall": "fail"}))


async def test_reference_composition_rows_are_tenant_stamped():
    wf = QaFanoutWorkflow(RunStore())
    spec = wf.spec(company_id="acme", owner_id="u1")
    _, root, _ = await drive(wf, spec)
    assert (await wf.executor.runs.get(root.run_id)).company_id == "acme"

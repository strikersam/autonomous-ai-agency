"""Why the agency's self-improvement shipped nothing on 2026-10-15, and the fixes.

Production logs for 24 hours showed no task passing verification:
1. research tasks were judged as code reviews and rejected for having no diff;
2. changed files were clipped for the judge without a marker, so the judge
   rejected them as "ends abruptly";
3. the improvement loop re-filed the same fixes after every deploy, on top of
   the earlier failed copies;
4. an agency task's own failure was filed as an incident, whose fix task failed
   in turn.
"""
from __future__ import annotations

import time

import pytest

from agent import judge_brief
from agent import log_monitor as log_monitor_module
from agent.models import AgentPlan, AgentStep
from tasks import improvement_throttle
from tasks.automation import TaskAutomationService
from tasks.models import Task, TaskStatus
from tasks.store import TaskStore

# ── 1 and 2: the judge ─────────────────────────────────────────────────────────

_RESEARCH = [{
    "step_id": 1, "status": "applied", "description": "Research the Ollama release",
    "changed_files": [],
    "observations": [{"tool": "fetch_url", "result": "Ollama 0.40.5 adds KV cache quantisation"},
                     {"tool": "finish", "result": "Recommend upgrading: halves memory on long prompts"}],
}]


def test_a_run_that_changed_no_files_is_judged_on_its_findings():
    assert judge_brief.changed_nothing(_RESEARCH)
    system = judge_brief.judge_system(_RESEARCH)
    assert system == judge_brief.NO_CHANGE_JUDGE_SYSTEM
    assert "code-review judge" in system  # callers that route on it still match
    assert "REJECT when the goal required changing files" in system


def test_a_run_that_changed_files_keeps_the_code_review_judge():
    steps = [{"step_id": 1, "status": "applied", "changed_files": ["a.py"]}]
    assert not judge_brief.changed_nothing(steps)
    assert judge_brief.judge_system(steps) == judge_brief.CODE_JUDGE_SYSTEM
    assert not judge_brief.changed_nothing([])  # no step ran: not a research run


def test_findings_are_bounded_and_clipping_is_marked():
    big = [{"step_id": 1, "status": "applied", "changed_files": [],
            "observations": [{"tool": "read_file", "result": "x" * 5000}] * 20}]
    text = judge_brief.findings(big)
    assert len(text) < 10_000
    assert "[clipped, 5000 chars in total]" in text
    assert text.startswith("[earlier findings clipped")
    assert judge_brief.findings([]) == "(no findings recorded)"


def test_clipped_file_content_says_the_file_continues():
    shown = judge_brief.clip_content("agent/tools.py", "def f():\n    return 1\n" * 500, 3000)
    assert "first 3000 of" in shown and "the file continues past this point" in shown
    whole = judge_brief.clip_content("a.py", "x = 1\n", 3000)
    assert "continues" not in whole and whole.endswith("x = 1\n")


async def test_runner_shows_findings_not_a_missing_diff_for_a_research_run(tmp_path):
    from agent.loop import AgentRunner

    runner = AgentRunner(ollama_base="http://localhost:1", workspace_root=str(tmp_path))
    plan = AgentPlan(goal="Research Ollama 0.40.5 and recommend", steps=[
        AgentStep(id=1, description="Research the Ollama release", files=[], type="analyze")])

    brief = await runner._judge_brief(plan, _RESEARCH, [])

    assert "Diff: (unavailable)" not in brief
    assert "Findings (no files were changed)" in brief
    assert "Recommend upgrading" in brief


async def test_runner_marks_clipped_changed_file_content(tmp_path):
    from agent.loop import AgentRunner

    (tmp_path / "big.py").write_text("x = 1\n" * 2000)
    runner = AgentRunner(ollama_base="http://localhost:1", workspace_root=str(tmp_path))

    text, shown = await runner._changed_content(["big.py"])

    assert shown == 1 and "the file continues past this point" in text


# ── 3: the improvement loop flood ─────────────────────────────────────────────

class _Job:
    def __init__(self, name: str, tags: list[str]) -> None:
        self.job_id, self.name, self.tags = f"job_{abs(hash(name)) % 10**8}", name, tags
        self.cron, self.instruction = "0 9 * * *", "fix it"


def _fix(name: str) -> _Job:
    return _Job(name, ["auto-improvement", "todo_fixme"])


async def _add(store: TaskStore, title: str, status: TaskStatus, **extra) -> Task:
    return await store.create(Task(owner_id="system", title=title, status=status,
                                   tags=["auto-improvement", "todo_fixme"], **extra))


@pytest.fixture
def store():
    return TaskStore()


async def test_same_fix_is_not_filed_again_while_its_task_is_open(store):
    await _add(store, "fix: TODO in a.py [todo_fixme]", TaskStatus.TODO)
    automation = TaskAutomationService(store=store)

    assert await automation.handle_scheduled_job(_fix("fix: TODO in a.py [todo_fixme]")) is None
    assert len(await store.list_all()) == 1


async def test_a_fix_that_failed_today_is_not_repeated_but_one_from_yesterday_is(store):
    failed = await _add(store, "fix: TODO in a.py [todo_fixme]", TaskStatus.FAILED)
    automation = TaskAutomationService(store=store)
    assert await automation.handle_scheduled_job(_fix("fix: TODO in a.py [todo_fixme]")) is None

    failed.updated_at = time.time() - 2 * 24 * 3600
    store._mem[failed.task_id] = failed.model_dump(mode="json")  # bypass update()'s touch()
    assert await automation.handle_scheduled_job(_fix("fix: TODO in a.py [todo_fixme]")) is not None


async def test_open_self_improvement_tasks_are_capped(store):
    cap = improvement_throttle.MAX_OPEN_IMPROVEMENT_TASKS
    for i in range(cap):
        await _add(store, f"fix: issue {i} [todo_fixme]", TaskStatus.TODO)
    automation = TaskAutomationService(store=store)

    assert await automation.handle_scheduled_job(_fix("fix: a new issue [todo_fixme]")) is None
    done = await store.list_all(status=TaskStatus.TODO)
    done[0].status = TaskStatus.DONE
    await store.update(done[0])
    assert await automation.handle_scheduled_job(_fix("fix: a new issue [todo_fixme]")) is not None


async def test_other_scheduled_jobs_are_never_throttled(store):
    for i in range(improvement_throttle.MAX_OPEN_IMPROVEMENT_TASKS + 2):
        await _add(store, f"fix: issue {i} [todo_fixme]", TaskStatus.TODO)
    job = _Job("company:acme:health-scan", ["company-agency"])

    task = await TaskAutomationService(store=store).handle_scheduled_job(job)

    assert task is not None and task.title == "company:acme:health-scan"


# ── 4: a task failing is not an incident ──────────────────────────────────────

def test_an_agency_task_failure_files_no_incident_and_no_fix_task(monkeypatch):
    recorded: list[str] = []
    dispatched: list[str] = []
    monkeypatch.setattr(log_monitor_module, "_record_operational", lambda n, m: recorded.append(m))
    monkeypatch.setattr(log_monitor_module, "_dispatch_async", lambda t, d, s=None: dispatched.append(t))
    monkeypatch.setattr(log_monitor_module, "_note_recurrence", lambda sig: None)
    monitor = log_monitor_module.LogMonitor()

    monitor._on_log_error("hermes-server", "ERROR", "hermes_server: task task_f799f62442838873 failed\n"
                          "Traceback ...\nruntimes.base.RuntimeExecutionError: Runtime 'internal_agent'")
    assert recorded == [] and dispatched == []

    monitor._on_log_error("hermes-server", "ERROR", "request to provider timed out")  # still counted
    monitor._on_log_error("services.foo", "ERROR", "KeyError: 'name' in services/foo.py")  # still a fix task
    assert recorded == ["request to provider timed out"] and len(dispatched) == 1


async def test_a_recent_failure_is_found_behind_many_newer_unrelated_failures(store):
    """Verifier finding: only the 200 newest failures were read, of every kind."""
    await _add(store, "fix: TODO in a.py [todo_fixme]", TaskStatus.FAILED)
    for i in range(250):
        await store.create(Task(owner_id="u", title=f"other {i}", status=TaskStatus.FAILED))

    assert await improvement_throttle.skip_reason(
        store, "fix: TODO in a.py [todo_fixme]", ["auto-improvement"]) is not None


def test_a_code_plan_whose_edits_changed_nothing_stays_with_the_code_judge():
    """Verifier note: a code goal must not be judged as research because its edits did nothing."""
    plan = AgentPlan(goal="Fix the TODO in foo.py", steps=[
        AgentStep(id=1, description="Edit foo.py", files=["foo.py"], type="edit")])
    skipped = [{"step_id": 1, "status": "skipped", "changed_files": []}]
    assert judge_brief.judge_system(skipped, plan) == judge_brief.CODE_JUDGE_SYSTEM
    research = AgentPlan(goal="Research X", steps=[
        AgentStep(id=1, description="Look into X", files=["README.md"], type="analyze")])
    assert judge_brief.judge_system(_RESEARCH, research) == judge_brief.NO_CHANGE_JUDGE_SYSTEM


def test_a_real_bug_wrapped_by_the_runtime_still_files_a_fix_task(monkeypatch):
    """Verifier finding: only the first line marks a task outcome; a traceback is not filtered."""
    dispatched: list[str] = []
    monkeypatch.setattr(log_monitor_module, "_record_operational", lambda n, m: None)
    monkeypatch.setattr(log_monitor_module, "_dispatch_async", lambda t, d, s=None: dispatched.append(t))
    monkeypatch.setattr(log_monitor_module, "_note_recurrence", lambda sig: None)

    log_monitor_module.LogMonitor()._on_log_error(
        "agent.job_manager", "ERROR",
        "Agent job j1 failed\nTraceback ...\nTypeError: bad\n"
        "runtimes.base.RuntimeExecutionError: Runtime 'internal_agent' execution error")

    assert len(dispatched) == 1


def test_an_analyze_step_that_called_a_writing_tool_keeps_the_code_judge():
    """CodeRabbit on #1772: an analyze step can call write_file yet report no changed files."""
    wrote = [{**_RESEARCH[0], "observations": _RESEARCH[0]["observations"] + [
        {"tool": "write_file", "args": {"path": "notes.md"}, "result": "ok"}]}]
    assert not judge_brief.changed_nothing(wrote)
    ran = [{**_RESEARCH[0], "observations": [{"tool": "run_command", "result": "ok"}]}]
    unknown = [{**_RESEARCH[0], "observations": [{"tool": "some_new_registry_tool", "result": "ok"}]}]
    assert not judge_brief.changed_nothing(ran) and not judge_brief.changed_nothing(unknown)
    assert judge_brief.changed_nothing(_RESEARCH)  # read-only research still qualifies
    # The tool prompt tells the model to call get_current_time first; that is a read.
    timed = [{**_RESEARCH[0], "observations": [{"tool": "get_current_time", "result": "now"}]
              + _RESEARCH[0]["observations"]}]
    assert judge_brief.changed_nothing(timed)

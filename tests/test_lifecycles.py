"""The lifecycle catalogue must stay valid, current and behaviour-compatible.

These tests are the guardrail for ``packages/lifecycle``: the declaration is
well formed, the generated map is not stale, lookup errors are actionable, and
adopting the declaration at the task lifecycle did not change a single legal or
illegal move (including the user-visible error text).
"""
from __future__ import annotations
import importlib

import json
import subprocess
import sys
from pathlib import Path

import pytest

from packages.lifecycle.catalogue import CATALOGUE_FINDINGS, TASK_LIFECYCLE
from packages.lifecycle.machine import IllegalTransition, StateMachine
from packages.lifecycle.registry import all_machines, get_machine, machine_names
from packages.lifecycle.render import render_markdown
from packages.lifecycle.status_types import inspect as inspect_status_type
from packages.lifecycle.status_types import reports as status_type_reports
from packages.lifecycle.status_types import values_of
from tasks.models import Task, TaskStatus
from tasks.service import ALLOWED_TRANSITIONS, TaskRuleError, TaskWorkflowService
from tasks.store import TaskStore

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "lifecycles.md"


def _workflow() -> TaskWorkflowService:
    return TaskWorkflowService(store=TaskStore())


def test_every_declared_lifecycle_is_well_formed() -> None:
    machines = all_machines()
    assert len(machines) >= 20
    for machine in machines:
        machine.validate()  # raises with a specific reason when inconsistent
        assert set(machine.transitions) == set(machine.states)
        assert all(set(targets) <= set(machine.states) for targets in machine.transitions.values())
        assert machine.owner and machine.description


def test_names_are_unique_and_an_unknown_lookup_suggests_the_right_one() -> None:
    names = machine_names()
    assert len(names) == len(set(names))
    with pytest.raises(KeyError) as excinfo:
        get_machine("tsak")
    message = str(excinfo.value)
    assert "task" in message and "Known lifecycles" in message


def test_a_bad_declaration_fails_at_construction_with_a_specific_reason() -> None:
    with pytest.raises(ValueError, match="undeclared transition targets"):
        StateMachine(
            name="broken",
            states=frozenset({"a", "b"}),
            initial="a",
            transitions={"a": frozenset({"b"}), "b": frozenset({"nowhere"})},
            owner="test",
            description="broken on purpose",
        )


def test_every_finding_points_at_a_registered_lifecycle() -> None:
    known = set(machine_names())
    assert CATALOGUE_FINDINGS
    for finding in CATALOGUE_FINDINGS:
        assert finding.title and finding.detail
        assert finding.machines
        assert set(finding.machines) <= known


def test_task_machine_reproduces_the_previous_transition_table_exactly() -> None:
    expected = {
        "todo": ["blocked", "failed", "in_progress", "wont_do"],
        "in_progress": ["blocked", "done", "failed", "in_review", "wont_do"],
        "in_review": ["blocked", "done", "failed", "in_progress", "wont_do"],
        "blocked": ["failed", "in_progress", "wont_do"],
        "needs_clarification": ["blocked", "done", "failed", "in_progress", "todo", "wont_do"],
        "done": ["in_progress"],
        "failed": ["blocked", "in_progress", "todo", "wont_do"],
        "wont_do": ["in_progress", "todo"],
    }
    assert TASK_LIFECYCLE.name == "task"
    assert set(TASK_LIFECYCLE.states) == {status.value for status in TaskStatus}
    assert {
        source.value: sorted(target.value for target in targets)
        for source, targets in ALLOWED_TRANSITIONS.items()
    } == expected
    assert {
        source: sorted(TASK_LIFECYCLE.allowed(source)) for source in TASK_LIFECYCLE.states
    } == expected


def test_illegal_task_move_keeps_its_message_and_reports_the_alternatives() -> None:
    task = Task(owner_id="qa@example.com", title="probe")
    with pytest.raises(TaskRuleError) as excinfo:
        _workflow().transition(task, TaskStatus.DONE, actor="user:qa@example.com")
    assert str(excinfo.value) == "Cannot transition task from todo to done"
    assert "in_progress" in excinfo.value.allowed
    assert task.status is TaskStatus.TODO


def test_legal_task_moves_are_still_accepted() -> None:
    for source, target in (
        (TaskStatus.TODO, TaskStatus.IN_PROGRESS),
        (TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW),
        (TaskStatus.IN_REVIEW, TaskStatus.IN_PROGRESS),
        (TaskStatus.FAILED, TaskStatus.TODO),
        (TaskStatus.WONT_DO, TaskStatus.IN_PROGRESS),
    ):
        task = Task(owner_id="qa@example.com", title="probe")
        task.status = source
        _workflow().transition(
            task, target, actor="user:qa@example.com", review_reason="Ready for review"
        )
        assert task.status is target


def test_each_illegal_task_move_names_a_state_in_the_error() -> None:
    for source in TASK_LIFECYCLE.states:
        for target in TASK_LIFECYCLE.states:
            if source == target or TASK_LIFECYCLE.can(source, target):
                continue
            task = Task(owner_id="qa@example.com", title="probe")
            task.status = TaskStatus(source)
            with pytest.raises(TaskRuleError) as excinfo:
                _workflow().transition(task, TaskStatus(target), actor="user:qa@example.com")
            assert str(excinfo.value) == f"Cannot transition task from {source} to {target}"


def test_require_raises_an_actionable_illegal_transition() -> None:
    with pytest.raises(IllegalTransition) as excinfo:
        TASK_LIFECYCLE.require("todo", "done")
    error = excinfo.value
    assert error.machine == "task"
    assert error.allowed == ("blocked", "failed", "in_progress", "wont_do")
    assert "allowed from 'todo'" in str(error)


def test_generated_document_is_current() -> None:
    assert DOC_PATH.exists(), "python scripts/lifecycles.py docs --write"
    assert DOC_PATH.read_text(encoding="utf-8") == render_markdown(all_machines(), CATALOGUE_FINDINGS)


def test_cli_serves_an_agent_with_json() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/lifecycles.py", "show", "task", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["name"] == "task"
    assert "wont_do" in payload["terminal"]
    assert "done" in payload["transitions"]["in_progress"]

    before_subcommand = subprocess.run(
        [sys.executable, "scripts/lifecycles.py", "--json", "list"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert before_subcommand.returncode == 0, before_subcommand.stderr
    assert len(json.loads(before_subcommand.stdout)) >= 20


def test_task_status_enums_are_distinct():
    """Four lifecycles, four names — importing the wrong one must fail at import.

    `tasks/models.py` keeps `TaskStatus`; the other three say which machine they
    drive so a reader cannot type-check against the wrong state vocabulary.
    """
    from agent.coordinator import CoordinatorTaskStatus
    from agents.research_coordinator import ResearchTaskStatus
    from agents.workflow_engine import WorkflowTaskStatus
    from tasks.models import TaskStatus

    enums = {
        "TaskStatus": TaskStatus,
        "CoordinatorTaskStatus": CoordinatorTaskStatus,
        "WorkflowTaskStatus": WorkflowTaskStatus,
        "ResearchTaskStatus": ResearchTaskStatus,
    }
    assert {cls.__name__ for cls in enums.values()} == set(enums)
    assert len({id(cls) for cls in enums.values()}) == 4

    for module in ("agent.coordinator", "agents.workflow_engine", "agents.research_coordinator"):
        imported = importlib.import_module(module)
        assert not hasattr(imported, "TaskStatus"), f"{module} still exposes TaskStatus"


STATUS_TYPES = {
    "bounty": "packages.bounty.models:BountyState",
    "direct_chat": "agent.schemas:DirectChatState",
    "governance_approval": "packages.governance.approvals:ApprovalStatus",
    "heal": "agent.self_healing:HealState",
    "task": "tasks.models:TaskStatus",
    "task_workflow_phase": "agent.workflow:WorkflowPhase",
    "workflow_phase": "workflow.models:PhaseStatus",
    "workflow_run": "workflow.models:WorkflowStatus",
    "workflow_slice": "workflow.models:SliceStatus",
    "workspace": "agent.workspace:WorkspaceStatus",
}


def _probe_machine(name: str, states: set[str], status_type: str) -> StateMachine:
    return StateMachine(
        name=name,
        states=frozenset(states),
        initial=sorted(states)[0],
        transitions={state: frozenset() for state in states},
        owner="test",
        description="binding probe",
        status_type=status_type,
    )


def test_every_status_type_matches_its_declared_lifecycle() -> None:
    """An enum member and a declared state must not be able to drift apart."""
    reports = {report.lifecycle: report for report in status_type_reports(all_machines())}
    assert set(STATUS_TYPES) <= set(reports)
    for lifecycle, spec in STATUS_TYPES.items():
        assert reports[lifecycle].status_type == spec
    for report in reports.values():
        assert report.ok, report.describe()


def test_status_type_drift_names_both_sides() -> None:
    drifted = _probe_machine("drifted", {"todo"}, "tasks.models:TaskStatus")
    report = inspect_status_type(drifted)
    assert report is not None and not report.ok
    assert "in_progress" in report.undeclared
    assert report.missing == ()
    assert "drifted" in report.describe() and "in_progress" in report.describe()


def test_a_state_without_a_member_is_reported_too() -> None:
    extra = _probe_machine("extra", {"todo", "teleported"}, "tasks.models:TaskStatus")
    report = inspect_status_type(extra)
    assert report is not None
    assert report.missing == ("teleported",)
    assert not report.ok


def test_a_broken_status_type_reference_reads_as_a_problem() -> None:
    broken = _probe_machine("broken", {"todo"}, "tasks.models:NoSuchStatus")
    report = inspect_status_type(broken)
    assert report is not None and not report.ok
    assert "NoSuchStatus" in (report.error or "")


def test_literal_status_aliases_are_supported() -> None:
    assert values_of("workflow.models:SliceStatus") == (
        "pending",
        "running",
        "applied",
        "failed",
        "skipped",
    )


def test_cli_check_validates_status_types() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/lifecycles.py", "check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "status types match" in result.stdout

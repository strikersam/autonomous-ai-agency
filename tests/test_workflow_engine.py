"""Tests for agents/workflow_engine.py — SuperClaude Workflow Engine.

Uses importlib to load the module directly, bypassing agents/__init__.py deps.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    path = Path(__file__).parent.parent / "agents" / "workflow_engine.py"
    spec = importlib.util.spec_from_file_location("workflow_engine", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["workflow_engine"] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load_module()
Task = mod.Task
TaskStatus = mod.TaskStatus
Workflow = mod.Workflow
WorkflowEngine = mod.WorkflowEngine


class TestTask:
    """Tests for Task dataclass."""

    def test_create(self):
        t = Task(task_id="t1", name="Task 1")
        assert t.task_id == "t1"
        assert t.status == TaskStatus.PENDING

    def test_execute_no_action(self):
        t = Task(task_id="t1", name="Task 1")
        result = t.execute()
        assert "no action" in result.lower()

    def test_execute_with_action(self):
        t = Task(task_id="t1", name="Task 1",
                 action=lambda: "done")
        assert t.execute() == "done"

    def test_reset(self):
        t = Task(task_id="t1", name="Task 1",
                 action=lambda: "done")
        t.execute()
        t.status = TaskStatus.COMPLETED
        t.reset()
        assert t.status == TaskStatus.PENDING
        assert t.result is None

    def test_default_depends_on(self):
        t = Task(task_id="t1", name="Task 1")
        assert t.depends_on == []


class TestWorkflow:
    """Tests for Workflow."""

    def test_add_task(self):
        wf = Workflow(workflow_id="w1", name="Test")
        wf.add_task(Task(task_id="t1", name="Task 1"))
        assert wf.task_count == 1

    def test_add_duplicate_raises(self):
        wf = Workflow(workflow_id="w1", name="Test")
        wf.add_task(Task(task_id="t1", name="Task 1"))
        try:
            wf.add_task(Task(task_id="t1", name="Dup"))
            assert False, "Expected ValueError"
        except ValueError:
            pass

    def test_remove_task(self):
        wf = Workflow(workflow_id="w1", name="Test")
        wf.add_task(Task(task_id="t1", name="Task 1"))
        wf.remove_task("t1")
        assert wf.task_count == 0

    def test_remove_cleans_dependencies(self):
        wf = Workflow(workflow_id="w1", name="Test")
        wf.add_task(Task(task_id="t1", name="T1"))
        wf.add_task(Task(task_id="t2", name="T2", depends_on=["t1"]))
        wf.remove_task("t1")
        t2 = wf.get_task("t2")
        assert t2.depends_on == []

    def test_validate_dag_clean(self):
        wf = Workflow(workflow_id="w1", name="Test")
        wf.add_task(Task(task_id="a", name="A"))
        wf.add_task(Task(task_id="b", name="B", depends_on=["a"]))
        wf.add_task(Task(task_id="c", name="C", depends_on=["b"]))
        assert wf.validate_dag() is True

    def test_validate_dag_cycle(self):
        wf = Workflow(workflow_id="w1", name="Test")
        wf.add_task(Task(task_id="a", name="A", depends_on=["b"]))
        wf.add_task(Task(task_id="b", name="B", depends_on=["a"]))
        assert wf.validate_dag() is False

    def test_ready_tasks(self):
        wf = Workflow(workflow_id="w1", name="Test")
        t1 = Task(task_id="t1", name="T1", action=lambda: "ok")
        wf.add_task(t1)
        wf.add_task(Task(task_id="t2", name="T2", depends_on=["t1"]))
        t1.status = TaskStatus.COMPLETED
        ready = wf.ready_tasks()
        assert len(ready) == 1
        assert ready[0].task_id == "t2"

    def test_completed_count(self):
        wf = Workflow(workflow_id="w1", name="Test")
        t1 = Task(task_id="t1", name="T1")
        t1.status = TaskStatus.COMPLETED
        wf.add_task(t1)
        wf.add_task(Task(task_id="t2", name="T2"))
        assert wf.completed_count == 1


class TestWorkflowEngine:
    """Tests for WorkflowEngine."""

    def test_register_workflow(self):
        engine = WorkflowEngine()
        wf = Workflow(workflow_id="w1", name="Test")
        engine.register(wf)
        assert engine.workflow_count == 1

    def test_unregister(self):
        engine = WorkflowEngine()
        engine.register(Workflow(workflow_id="w1", name="Test"))
        engine.unregister("w1")
        assert engine.workflow_count == 0

    def test_execute_linear_dag(self):
        engine = WorkflowEngine()
        wf = Workflow(workflow_id="w1", name="Linear")
        results = []
        wf.add_task(Task(task_id="a", name="A", action=lambda: results.append("a") or "a"))
        wf.add_task(Task(task_id="b", name="B", action=lambda: results.append("b") or "b", depends_on=["a"]))
        wf.add_task(Task(task_id="c", name="C", action=lambda: results.append("c") or "c", depends_on=["b"]))
        engine.register(wf)
        executed = engine.execute("w1")
        assert len(executed) == 3
        assert results == ["a", "b", "c"]

    def test_execute_parallel_ready(self):
        engine = WorkflowEngine()
        wf = Workflow(workflow_id="w1", name="Parallel")
        wf.add_task(Task(task_id="a", name="A", action=lambda: "a"))
        wf.add_task(Task(task_id="b", name="B", action=lambda: "b"))
        engine.register(wf)
        executed = engine.execute("w1")
        assert len(executed) == 2

    def test_execute_cycle_raises(self):
        engine = WorkflowEngine()
        wf = Workflow(workflow_id="w1", name="Cycle")
        wf.add_task(Task(task_id="a", name="A", depends_on=["b"]))
        wf.add_task(Task(task_id="b", name="B", depends_on=["a"]))
        engine.register(wf)
        try:
            engine.execute("w1")
            assert False, "Expected ValueError"
        except ValueError:
            pass

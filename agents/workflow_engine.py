"""SuperClaude Workflow Engine — Workflow, Task, and topological DAG execution.

Issue: #235
Branch: fix/quick-note-235-workflow
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Set


class TaskStatus(Enum):
    """Execution status of a task within a workflow."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Task:
    """A single task within a workflow DAG."""

    task_id: str
    name: str
    action: Optional[Callable[[], str]] = None
    depends_on: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    retries: int = 0
    max_retries: int = 0

    def execute(self) -> str:
        """Execute the task's action."""
        if self.action is None:
            return f"Task '{self.name}' has no action."
        return self.action()

    def reset(self) -> None:
        """Reset the task to pending state."""
        self.status = TaskStatus.PENDING
        self.result = None


@dataclass
class Workflow:
    """A named collection of tasks forming a DAG."""

    workflow_id: str
    name: str
    _tasks: Dict[str, Task] = field(default_factory=dict)

    def add_task(self, task: Task) -> None:
        """Add a task to the workflow."""
        if task.task_id in self._tasks:
            raise ValueError(f"Task '{task.task_id}' already exists in workflow.")
        self._tasks[task.task_id] = task

    def remove_task(self, task_id: str) -> None:
        """Remove a task from the workflow."""
        if task_id not in self._tasks:
            raise KeyError(f"Task '{task_id}' not found.")
        self._tasks.pop(task_id)
        for t in self._tasks.values():
            t.depends_on = [d for d in t.depends_on if d != task_id]

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def validate_dag(self) -> bool:
        """Check that the task graph is a valid DAG (no cycles)."""
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            task = self._tasks.get(node)
            if task is not None:
                for dep in task.depends_on:
                    if dep not in visited:
                        if dfs(dep):
                            return True
                    elif dep in rec_stack:
                        return True
            rec_stack.discard(node)
            return False

        for task_id in self._tasks:
            if task_id not in visited:
                if dfs(task_id):
                    return False
        return True

    def ready_tasks(self) -> List[Task]:
        """Return tasks whose dependencies are all satisfied."""
        completed_ids = {
            tid for tid, t in self._tasks.items()
            if t.status == TaskStatus.COMPLETED
        }
        return [
            t for t in self._tasks.values()
            if t.status == TaskStatus.PENDING
            and all(d in completed_ids for d in t.depends_on)
        ]

    @property
    def task_count(self) -> int:
        """Number of tasks in the workflow."""
        return len(self._tasks)

    @property
    def completed_count(self) -> int:
        """Number of completed tasks."""
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED)

    @property
    def failed_count(self) -> int:
        """Number of failed tasks."""
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED)


@dataclass
class WorkflowEngine:
    """Executes workflows using topological ordering."""

    _workflows: Dict[str, Workflow] = field(default_factory=dict)

    def register(self, workflow: Workflow) -> None:
        """Register a workflow with the engine."""
        if workflow.workflow_id in self._workflows:
            raise ValueError(f"Workflow '{workflow.workflow_id}' already registered.")
        self._workflows[workflow.workflow_id] = workflow

    def unregister(self, workflow_id: str) -> None:
        """Remove a workflow."""
        if workflow_id not in self._workflows:
            raise KeyError(f"Workflow '{workflow_id}' not found.")
        self._workflows.pop(workflow_id)

    def execute(self, workflow_id: str) -> List[Task]:
        """Execute a workflow topologically, returning the task results.

        Tasks are executed in waves: any task whose dependencies are all
        satisfied is eligible to run. Execution continues until no ready
        tasks remain.
        """
        if workflow_id not in self._workflows:
            raise KeyError(f"Workflow '{workflow_id}' not found.")

        workflow = self._workflows[workflow_id]
        if not workflow.validate_dag():
            raise ValueError(f"Workflow '{workflow.name}' contains a cycle.")

        completed: List[Task] = []

        while True:
            ready = workflow.ready_tasks()
            if not ready:
                break
            for task in ready:
                task.status = TaskStatus.RUNNING
                try:
                    task.result = task.execute()
                    task.status = TaskStatus.COMPLETED
                except Exception:
                    task.status = TaskStatus.FAILED
                    task.result = "Execution failed"
                completed.append(task)

        return completed

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get a workflow by ID."""
        return self._workflows.get(workflow_id)

    @property
    def workflow_count(self) -> int:
        """Number of registered workflows."""
        return len(self._workflows)

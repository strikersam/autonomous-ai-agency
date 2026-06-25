"""
Multi-Agent Research Coordinator — orchestrate a team of specialized research agents.

Inspired by:
https://machinelearningmastery.com/build-multi-agent-research-assistant/

Pattern: a coordinator decomposes a research question into sub-tasks, dispatches
them to specialized agents (web search, code search, doc reader, summarizer),
collects partial findings, and synthesizes a final answer.

Quick-Note Issue: #238
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

log = logging.getLogger("research_coordinator")


class TaskStatus(str, Enum):
    """Lifecycle states for a research task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"  # waiting on dependency


class AgentRole(str, Enum):
    """Specialized agent roles in the research team."""

    WEB_SEARCHER = "web_searcher"
    CODE_SEARCHER = "code_searcher"
    DOC_READER = "doc_reader"
    SUMMARIZER = "summarizer"
    CRITIC = "critic"
    SYNTHESIZER = "synthesizer"


@dataclass
class ResearchTask:
    """A single decomposed sub-task in the research plan."""

    task_id: str
    question: str
    role: AgentRole
    status: TaskStatus = TaskStatus.PENDING
    depends_on: list[str] = field(default_factory=list)
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

    def is_ready(self, completed_ids: set[str]) -> bool:
        """Returns True when every dependency has completed."""
        if self.status != TaskStatus.PENDING:
            return False
        return all(dep in completed_ids for dep in self.depends_on)

    def mark_running(self) -> None:
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()

    def mark_completed(self, result: str) -> None:
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now()

    def mark_failed(self, error: str) -> None:
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()

    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


# Handler signature: receives the task and the bag of completed-task results,
# returns the result string (or raises to fail).
TaskHandler = Callable[["ResearchTask", dict[str, str]], str]


@dataclass
class ResearchAgent:
    """A specialized agent that executes tasks of a specific role."""

    name: str
    role: AgentRole
    handler: TaskHandler
    tasks_completed: int = 0
    tasks_failed: int = 0

    def can_handle(self, task: ResearchTask) -> bool:
        return task.role == self.role

    def execute(self, task: ResearchTask, context: dict[str, str]) -> ResearchTask:
        """Run the task and return it (mutated) with status set."""
        if not self.can_handle(task):
            task.mark_failed(f"agent {self.name} cannot handle role {task.role}")
            self.tasks_failed += 1
            return task

        task.mark_running()
        try:
            result = self.handler(task, context)
            task.mark_completed(result)
            self.tasks_completed += 1
        except Exception as exc:
            task.mark_failed(str(exc))
            self.tasks_failed += 1
            log.exception("Task %s failed in agent %s", task.task_id, self.name)
        return task


class ResearchOrchestrator:
    """
    Coordinates a multi-agent research workflow.

    Workflow:
        1. plan(question) → list of ResearchTasks (dependency DAG)
        2. register_agent(...) per role
        3. run() executes ready tasks until all complete or blocked
        4. synthesize() combines completed results into a final answer
    """

    def __init__(self) -> None:
        self.tasks: dict[str, ResearchTask] = {}
        self.agents: dict[AgentRole, list[ResearchAgent]] = {}
        self.history: list[str] = []  # task IDs in completion order

    # ── Planning ──────────────────────────────────────────────────────────

    def add_task(self, task: ResearchTask) -> None:
        if task.task_id in self.tasks:
            raise ValueError(f"task {task.task_id} already exists")
        self.tasks[task.task_id] = task

    def plan(self, question: str) -> list[ResearchTask]:
        """
        Decompose a research question into a default DAG.

        Default plan:
          web → docs (parallel)
          ↓     ↓
          summarize
          ↓
          critic
          ↓
          synthesize
        """
        web = ResearchTask(
            task_id="web_search",
            question=f"Search the web for: {question}",
            role=AgentRole.WEB_SEARCHER,
        )
        docs = ResearchTask(
            task_id="doc_read",
            question=f"Read relevant documentation for: {question}",
            role=AgentRole.DOC_READER,
        )
        summary = ResearchTask(
            task_id="summarize",
            question=f"Summarize findings about: {question}",
            role=AgentRole.SUMMARIZER,
            depends_on=["web_search", "doc_read"],
        )
        critic = ResearchTask(
            task_id="critique",
            question="Critique the summary for accuracy and gaps",
            role=AgentRole.CRITIC,
            depends_on=["summarize"],
        )
        synth = ResearchTask(
            task_id="synthesize",
            question=f"Final answer to: {question}",
            role=AgentRole.SYNTHESIZER,
            depends_on=["summarize", "critique"],
        )

        for t in (web, docs, summary, critic, synth):
            self.add_task(t)
        return [web, docs, summary, critic, synth]

    # ── Agents ────────────────────────────────────────────────────────────

    def register_agent(self, agent: ResearchAgent) -> None:
        self.agents.setdefault(agent.role, []).append(agent)

    def _pick_agent(self, role: AgentRole) -> Optional[ResearchAgent]:
        """Round-robin pick within a role (least-loaded first)."""
        candidates = self.agents.get(role, [])
        if not candidates:
            return None
        return min(candidates, key=lambda a: a.tasks_completed + a.tasks_failed)

    # ── Execution ─────────────────────────────────────────────────────────

    def _ready_tasks(self) -> list[ResearchTask]:
        completed = {tid for tid, t in self.tasks.items()
                     if t.status == TaskStatus.COMPLETED}
        return [t for t in self.tasks.values() if t.is_ready(completed)]

    def _context(self) -> dict[str, str]:
        return {tid: t.result or ""
                for tid, t in self.tasks.items()
                if t.status == TaskStatus.COMPLETED}

    def run(self, max_iterations: int = 100) -> dict[str, ResearchTask]:
        """Execute the DAG until all tasks resolve or no progress is possible."""
        for _ in range(max_iterations):
            ready = self._ready_tasks()
            if not ready:
                break
            for task in ready:
                agent = self._pick_agent(task.role)
                if agent is None:
                    task.status = TaskStatus.BLOCKED
                    task.error = f"no agent for role {task.role.value}"
                    continue
                agent.execute(task, self._context())
                if task.status == TaskStatus.COMPLETED:
                    self.history.append(task.task_id)
        return self.tasks

    # ── Output ────────────────────────────────────────────────────────────

    def synthesize(self) -> str:
        """Return the final synthesized answer, or a status report if blocked."""
        synth = self.tasks.get("synthesize")
        if synth and synth.status == TaskStatus.COMPLETED:
            return synth.result or ""
        # fallback: stitch whatever completed
        parts = [
            f"[{tid}] {t.result}" for tid, t in self.tasks.items()
            if t.status == TaskStatus.COMPLETED and t.result
        ]
        if parts:
            return "\n\n".join(parts)
        return "Research incomplete: no tasks completed."

    def status(self) -> dict[str, int]:
        """Status counts across all tasks."""
        counts: dict[str, int] = {s.value: 0 for s in TaskStatus}
        for t in self.tasks.values():
            counts[t.status.value] += 1
        return counts

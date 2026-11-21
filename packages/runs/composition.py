"""packages/runs/composition.py — the typed spec and result of a composition.

A ``CompositionSpec`` is a tree of ``Step``s run by ``packages/runs/composer.py``:
task steps (one child run each), groups (sequence or parallel, with a failure
policy), and approval steps. Specs are plain Pydantic data so they can be stored,
validated and, later, accepted from an API; a callable ``predicate`` is the one
code only escape hatch and is never serialised.
"""
from __future__ import annotations

import hashlib
from enum import Enum
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

StepOutcome = Literal["succeeded", "failed", "skipped", "cancelled", "waiting"]


class FailurePolicy(str, Enum):
    """What a group does when a child fails."""

    FAIL_FAST = "fail_fast"      # stop launching, cancel running siblings, group fails
    CONTINUE = "continue"        # run everything; the group succeeds if any child did
    REQUIRE_ALL = "require_all"  # run everything; the group fails if any child failed
    QUORUM = "quorum"            # run everything; the group succeeds with >= quorum successes


class StepCondition(BaseModel):
    """Run the step only when step ``step`` ended in ``outcome``."""

    step: str
    outcome: Literal["succeeded", "failed"] = "succeeded"


class StepResult(BaseModel):
    """The recorded outcome of one step (``output`` must be JSON)."""

    key: str
    state: StepOutcome
    output: Any = None
    error: str | None = None
    run_id: str | None = None


Predicate = Callable[[dict[str, StepResult]], bool]


class Step(BaseModel):
    """One node of a composition: a task, a group of steps, or an approval pause."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    key: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,64}$")
    kind: Literal["task", "group", "approval"] = "task"
    title: str = Field(default="", max_length=512)
    prompt: str = Field(default="", max_length=32_000)
    agent_id: str | None = None
    # Expected cost (USD) of this step, used to reserve root budget before it starts.
    estimated_cost: float | None = Field(default=None, ge=0)
    mode: Literal["sequence", "parallel"] = "sequence"
    policy: FailurePolicy = FailurePolicy.FAIL_FAST
    quorum: int | None = Field(default=None, ge=1)
    steps: list["Step"] = Field(default_factory=list)
    when: StepCondition | None = None
    predicate: Predicate | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def _shape(self) -> "Step":
        if self.kind == "group" and not self.steps:
            raise ValueError(f"group step {self.key!r} needs steps")
        if self.kind != "group" and self.steps:
            raise ValueError(f"only a group step may hold steps ({self.key!r})")
        if self.policy is FailurePolicy.QUORUM and self.quorum is None:
            raise ValueError(f"step {self.key!r}: policy quorum needs quorum")
        return self


class CompositionSpec(BaseModel):
    """A whole composition: the top level is itself a group of ``steps``."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(default="composition", max_length=128)
    steps: list[Step] = Field(min_length=1)
    mode: Literal["sequence", "parallel"] = "sequence"
    policy: FailurePolicy = FailurePolicy.FAIL_FAST
    quorum: int | None = Field(default=None, ge=1)
    deadline_s: float | None = Field(default=None, gt=0)
    budget: dict[str, float] = Field(default_factory=dict)
    company_id: str | None = None
    owner_id: str | None = None

    @model_validator(mode="after")
    def _unique_keys(self) -> "CompositionSpec":
        seen: set[str] = set()
        stack = list(self.steps)
        while stack:
            step = stack.pop()
            if step.key in seen:
                raise ValueError(f"duplicate step key {step.key!r}")
            seen.add(step.key)
            stack.extend(step.steps)
        if self.policy is FailurePolicy.QUORUM and self.quorum is None:
            raise ValueError("policy quorum needs quorum")
        return self


class CompositionResult(BaseModel):
    """What ``Composer.run`` returns: the parent's state, every step result and the join."""

    run_id: str
    state: str
    results: dict[str, StepResult] = Field(default_factory=dict)
    aggregate: list[Any] = Field(default_factory=list)  # outputs of succeeded steps, in order
    failed: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    waiting_on: str | None = None
    partial: bool = False  # succeeded although some step failed (continue or quorum)
    error: str | None = None


class ChildJob(BaseModel):
    """What an executor receives for one child run."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str
    task_id: str
    parent_run_id: str
    depth: int
    step: Step
    prior: dict[str, Any] = Field(default_factory=dict)  # outputs of earlier steps by key
    company_id: str | None = None
    owner_id: str | None = None


class ChildOutcome(BaseModel):
    """What an executor returns; cost and tokens are charged to the root run's budget."""

    success: bool
    output: Any = None
    error: str | None = None
    cost_usd: float = 0.0
    tokens: int = 0
    steps: int = 1


ChildExecutor = Callable[[ChildJob], Awaitable[ChildOutcome]]


def child_run_id(parent_run_id: str, step_key: str) -> str:
    """The child run id of a step: stable, so spawning it twice finds the same run."""
    return "run_" + hashlib.sha256(f"{parent_run_id}:{step_key}".encode()).hexdigest()[:32]


def child_task_id(parent_run_id: str, step_key: str) -> str:
    """The child task id of a step, stable for the same reason."""
    return "task_" + hashlib.sha256(f"{parent_run_id}:{step_key}".encode()).hexdigest()[:16]

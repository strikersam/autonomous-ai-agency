"""packages/runs/models.py — the durable run record, its events and its side effect ledger.

A run is one attempt series at a unit of work (a task run or an orchestrator
run). The record survives the process that started it, so a worker that takes
over an expired lease can see what happened and resume or park it.

Timestamps are epoch seconds. The SQLite backend's own helpers may write an
ISO string into ``updated_at``; the validators below coerce either form back to
a float so a record always reads the same on every backend.
"""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from packages.storage.state_persistence import parse_expiry

SCHEMA_VERSION = 1


class RunState(str, Enum):
    """Every state a run can be in. The legal moves live in the ``run`` lifecycle."""

    CREATED = "created"
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    WAITING_FOR_AGENT = "waiting_for_agent"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    RETRYING = "retrying"
    RECOVERING = "recovering"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    DEAD_LETTER = "dead_letter"


TERMINAL_STATES: frozenset[RunState] = frozenset(
    {RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED, RunState.TIMED_OUT,
     RunState.DEAD_LETTER}
)


def _epoch(value: Any) -> float | None:
    if value is None:
        return None
    return parse_expiry(value)


def new_run_id() -> str:
    """A fresh, unguessable run id."""
    return f"run_{uuid.uuid4().hex}"


class RunRecord(BaseModel):
    """One durable run. Additive fields only; old documents keep validating."""

    model_config = ConfigDict(use_enum_values=False, extra="ignore")

    run_id: str = Field(default_factory=new_run_id)
    parent_run_id: str | None = None
    root_run_id: str | None = None
    retry_of: str | None = None
    task_id: str | None = None
    company_id: str | None = None
    agent_id: str | None = None
    agent_version: str | None = None
    runtime_id: str | None = None
    runtime_version: str | None = None
    requested_model: str | None = None
    resolved_model: str | None = None
    workflow_id: str | None = None
    workflow_version: str | None = None
    owner_id: str | None = None
    initiated_by: str | None = None
    state: RunState = RunState.CREATED
    phase: str | None = None
    created_at: float = Field(default_factory=time.time)
    started_at: float | None = None
    updated_at: float = Field(default_factory=time.time)
    completed_at: float | None = None
    attempt: int = 1
    retry_history: list[dict[str, Any]] = Field(default_factory=list)
    budget: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)
    checkpoint_ref: str | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    trace_id: str | None = None
    span_id: str | None = None
    failure_reason: str | None = None
    recovery_history: list[dict[str, Any]] = Field(default_factory=list)
    lease_token: int | None = None
    op_seq: int = 0
    event_seq: int = 0
    idempotency_key: str | None = None
    depth: int = 0
    waiting_reason: str | None = None
    deadline_at: float | None = None
    cancel_requested: bool = False
    schema_version: int = SCHEMA_VERSION

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _required_ts(cls, v: Any) -> float:
        ts = _epoch(v)
        return ts if ts is not None else time.time()

    @field_validator("started_at", "completed_at", "deadline_at", mode="before")
    @classmethod
    def _optional_ts(cls, v: Any) -> float | None:
        return _epoch(v)

    @property
    def is_terminal(self) -> bool:
        """True when the run reached a resting state."""
        return self.state in TERMINAL_STATES

    def to_doc(self) -> dict[str, Any]:
        """The stored form: plain JSON types, ``_id`` equal to ``run_id``."""
        doc = self.model_dump(mode="json")
        doc["_id"] = self.run_id
        return doc


class RunEvent(BaseModel):
    """One append only entry in a run's timeline; ``seq`` is monotonic per run."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    run_id: str
    seq: int
    ts: float = Field(default_factory=time.time)
    kind: str
    actor: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("ts", mode="before")
    @classmethod
    def _ts(cls, v: Any) -> float:
        ts = _epoch(v)
        return ts if ts is not None else time.time()


class OperationState(str, Enum):
    """Where one side effecting call is: never started, in flight, or settled."""

    PENDING = "pending"
    EXECUTING = "executing"
    COMMITTED = "committed"
    FAILED = "failed"


class OperationRecord(BaseModel):
    """One side effecting call of a run, keyed by ``(run_id, seq)``."""

    model_config = ConfigDict(extra="ignore")

    op_id: str
    run_id: str
    seq: int
    tool: str
    action_hash: str
    target: dict[str, Any] = Field(default_factory=dict)
    state: OperationState = OperationState.PENDING
    token: int | None = None
    op_deadline: float | None = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    result_ref: str | None = None
    error: str | None = None

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _required_ts(cls, v: Any) -> float:
        ts = _epoch(v)
        return ts if ts is not None else time.time()

    @field_validator("op_deadline", mode="before")
    @classmethod
    def _optional_ts(cls, v: Any) -> float | None:
        return _epoch(v)

    @staticmethod
    def make_id(run_id: str, seq: int) -> str:
        """The composite key ``"<run_id>:<seq>"`` (unique on every backend)."""
        return f"{run_id}:{seq}"

    def to_doc(self) -> dict[str, Any]:
        """The stored form, ``_id`` equal to ``op_id``."""
        doc = self.model_dump(mode="json")
        doc["_id"] = self.op_id
        return doc

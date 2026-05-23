"""agent/contract.py — Typed public contract for the agent job lifecycle.

Phase 1 of the agency-core migration: replace raw dicts in AgentJob with
validated Pydantic models so callers get compile-time checks, automatic docs,
and a stable serialisation surface.

Usage
-----
The contract lives *outside* the AgentJobManager so it can be imported from
any layer (API handlers, tests, CLI tools) without creating circular imports::

    from agent.contract import AgentJobRequest, AgentJobResult, AgentJobError

Design principles
-----------------
* All public fields are explicit — no ``**kwargs`` bags.
* Secrets (tokens, API keys) are never stored in these models.
* Models are immutable after construction (``model_config = frozen``).
* ``AgentJobResult`` carries a canonical ``response`` plus an opaque ``raw``
  blob so callers can consume the normalised message without knowing which
  runtime produced it.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ─── request ──────────────────────────────────────────────────────────────────

class AgentJobRequest(BaseModel):
    """Validated input for creating a new agent job.

    Passed from the API handler into ``AgentJobManager.create_job()`` so that
    all inputs are type-checked and documented before they touch the job queue.
    """

    model_config = {"frozen": True}

    # Caller context
    session_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Chat session the job belongs to.",
    )
    owner_id: str | None = Field(
        default=None,
        max_length=256,
        description="User ID of the requesting user. None only in test contexts.",
    )

    # Task payload
    instruction: str = Field(
        ...,
        min_length=1,
        max_length=32_768,
        description="Natural-language instruction for the agent.",
    )

    # Model / provider routing
    requested_model: str | None = Field(
        default=None,
        max_length=256,
        description="Specific model to use (e.g. 'qwen3-coder-480b'). "
        "None means use the provider default.",
    )
    provider_id: str | None = Field(
        default=None,
        max_length=256,
        description="Provider to route the job to. None means use the active default.",
    )
    runtime_id: str = Field(
        default="internal_agent",
        max_length=128,
        description="Runtime identifier: 'internal_agent' | 'claude_code' | …",
    )

    # Feature flags
    allow_commercial_fallback: bool = Field(
        default=True,
        description="Whether the router may fall back to a commercial provider if "
        "the primary provider is unavailable.",
    )

    @field_validator("session_id", "owner_id", "requested_model", "provider_id", "runtime_id", mode="before")
    @classmethod
    def _strip_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("instruction", mode="before")
    @classmethod
    def _strip_instruction(cls, v: Any) -> Any:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("instruction must not be blank")
            return stripped
        return v


# ─── result / error ───────────────────────────────────────────────────────────

AgentJobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]

_KNOWN_ERROR_CODES = frozenset(
    {"runtime_preflight", "runtime_unavailable", "runtime_execution_error", "unknown"}
)


class AgentJobError(BaseModel):
    """Structured error payload attached to a failed job."""

    model_config = {"frozen": True}

    code: str = Field(
        default="unknown",
        description="Machine-readable error category (runtime_preflight | "
        "runtime_unavailable | runtime_execution_error | unknown).",
    )
    type: str = Field(
        default="Exception",
        description="Python exception class name.",
    )
    message: str = Field(
        default="",
        description="Human-readable error description.",
    )
    report: dict[str, Any] | None = Field(
        default=None,
        description="Optional structured report from the runtime (preflight checks, etc.).",
    )

    @field_validator("code", mode="before")
    @classmethod
    def _normalise_code(cls, v: Any) -> str:
        s = str(v).strip() if v is not None else "unknown"
        return s if s in _KNOWN_ERROR_CODES else "unknown"


class AgentJobResult(BaseModel):
    """Typed result returned by a completed agent job.

    The ``response`` field is the canonical assistant-facing message — callers
    should use this rather than parsing ``raw``.  ``raw`` is preserved for
    debugging and for runtimes that need to pass structured data back to
    advanced callers.
    """

    model_config = {"frozen": True}

    response: str = Field(
        default="",
        description="Canonical assistant-facing response text.",
    )
    raw: dict[str, Any] | str | None = Field(
        default=None,
        description="Opaque runtime payload. Not for display; for diagnostics only.",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: Any) -> Any:
        """Accept a bare string (legacy runner output) or a full dict."""
        if isinstance(data, str):
            return {"response": data, "raw": data}
        if isinstance(data, dict) and "response" not in data:
            # Try to pull a canonical message from common runner keys
            response = (
                data.get("response")
                or data.get("summary")
                or data.get("output")
                or (data.get("report") if isinstance(data.get("report"), str) else None)
                or ""
            )
            return {"response": response, "raw": data}
        return data


# ─── job status snapshot (returned by GET /api/chat/agent-jobs/{id}) ──────────

class AgentJobSnapshot(BaseModel):
    """Complete point-in-time view of a job, safe to serialise as API response."""

    job_id: str
    session_id: str
    instruction: str
    owner_id: str | None = None
    status: AgentJobStatus = "queued"
    phase: str = "queued"
    runtime_id: str = "internal_agent"
    workspace_path: str | None = None
    requested_model: str | None = None
    provider_id: str | None = None
    created_at: str = ""
    updated_at: str = ""
    heartbeat_at: str = ""
    progress_events: list[dict[str, Any]] = Field(default_factory=list)
    result: AgentJobResult | None = None
    error: AgentJobError | None = None

    @property
    def final_message(self) -> str | None:
        """Convenience: the canonical text response, whether success or failure."""
        if self.result is not None:
            return self.result.response or None
        if self.error is not None:
            return self.error.message or None
        return None

    @classmethod
    def from_agent_job(cls, job: Any) -> "AgentJobSnapshot":
        """Build a snapshot from an ``AgentJob`` dataclass instance."""
        result = None
        if job.result is not None:
            result = AgentJobResult.model_validate(job.result)

        error = None
        if job.error is not None:
            error = AgentJobError.model_validate(job.error)

        return cls(
            job_id=job.job_id,
            session_id=job.session_id,
            instruction=job.instruction,
            owner_id=job.owner_id,
            status=job.status,  # type: ignore[arg-type]
            phase=job.phase,
            runtime_id=job.runtime_id,
            workspace_path=job.workspace_path,
            requested_model=job.requested_model,
            provider_id=job.provider_id,
            created_at=job.created_at,
            updated_at=job.updated_at,
            heartbeat_at=job.heartbeat_at,
            progress_events=list(job.progress_events),
            result=result,
            error=error,
        )

# Pydantic v2 with `from __future__ import annotations` requires model_rebuild()
# for models that reference forward-declared types or `Any`.
AgentJobError.model_rebuild()
AgentJobResult.model_rebuild()
AgentJobSnapshot.model_rebuild()

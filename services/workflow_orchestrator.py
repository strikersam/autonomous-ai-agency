"""
services/workflow_orchestrator.py — Canonical Execution Backbone

THE single entry point for ALL agent-driven work in Agency Core.

Golden path (enforced; no bypass):
  CLASSIFY → PLAN → SELECT_SPECIALIST → PREFLIGHT → BIND_CONTEXT →
  EXECUTE → VERIFY → JUDGE → SUMMARIZE → PERSIST → MONITOR

Key design rules:
  - Every transition carries typed Pydantic payloads (extra="forbid").
  - ApprovalGate is mandatory between PLAN and EXECUTE — no code path
    can skip it without explicit approval.
  - SkillBindings are resolved at BIND_CONTEXT and injected into the
    execution context.
  - All other execution paths (AgentRunner.loop, Agency.run_cycle,
    MultiAgentSwarm.run, AgentSwarm.run_phase) are soft-deprecated
    and emit warnings when used outside this orchestrator.
  - #522: Per-phase timeouts (120s default), exponential backoff retries,
    provider failover with llm_provenance tracking.
  - #522: Heartbeat updated after each phase; stall watchdog recovers.
  - #522: Step-level checkpointing persists run state to durable store.
  - #522: Async approve enqueues via FIFO concurrency-limited queue.

Feature flag:
  AGENCY_WORKFLOW_MODE=orchestrator   → enforce golden path (default)
  AGENCY_WORKFLOW_MODE=legacy         → allow old parallel paths (warn)

Usage:
    orchestrator = get_workflow_orchestrator()
    result = await orchestrator.execute(
        request="Fix the failing auth tests",
        user_id="user@example.com",
        company_id="comp_abc",
    )
    # Blocks at ApprovalGate unless auto_approve=True
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger("agency.orchestrator")

# ── Timeouts & Retries (#522) ─────────────────────────────────────────────────
_PHASE_TIMEOUT_SEC = float(os.environ.get("ORCHESTRATOR_PHASE_TIMEOUT_SEC", "120"))
_MAX_PHASE_RETRIES = int(os.environ.get("ORCHESTRATOR_MAX_PHASE_RETRIES", "2"))
_BACKOFF_BASE_SEC = float(os.environ.get("ORCHESTRATOR_BACKOFF_BASE_SEC", "1.0"))


def _resolve_push_token(github_token: str | None, user_id: str | None) -> str | None:
    """GitHub token used to push branches / open PRs during EXECUTION (#506).

    Precedence:
      1. The per-request / per-user token (Settings > GitHub) always wins.
      2. The operator/server token (GH_TOKEN/GH_PAT/GITHUB_TOKEN) is the fallback
         for internal system runs (no user_id) — and for user-initiated runs only
         when explicitly opted in via ``ORCHESTRATOR_ALLOW_SERVER_TOKEN_FOR_USER_RUNS``.

    Defaulting the opt-in OFF preserves the multi-tenant guard (a user run must not
    silently borrow the service account's repo access); the operator of a
    single-tenant agency sets the flag (or connects a per-user token) so that
    runs can actually open PRs instead of executing and then failing to push.
    """
    if github_token:
        return github_token
    allow_user_runs = os.environ.get(
        "ORCHESTRATOR_ALLOW_SERVER_TOKEN_FOR_USER_RUNS", ""
    ).strip().lower() in ("1", "true", "yes", "on")
    if user_id is None or allow_user_runs:
        return (
            os.environ.get("GH_TOKEN")
            or os.environ.get("GH_PAT")
            or os.environ.get("GITHUB_TOKEN")
        )
    return None


# ── Feature flag ──────────────────────────────────────────────────────────────

WORKFLOW_MODE = os.environ.get("AGENCY_WORKFLOW_MODE", "orchestrator")

if WORKFLOW_MODE not in ("orchestrator", "legacy"):
    log.warning(
        "AGENCY_WORKFLOW_MODE=%r unrecognised; falling back to 'orchestrator'",
        WORKFLOW_MODE,
    )
    WORKFLOW_MODE = "orchestrator"


# Narrow exception list for the CEO → AgentRunner fallback path. The CEO
# may legitimately fail when a runtime is missing, an LLM endpoint is
# unreachable, or the swarm cannot start; in those cases we want to fall
# through to the single-runner path so the run can still succeed. Program
# errors (KeyError, AttributeError, etc.) must NOT be swallowed.
_CEO_FALLBACK_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)
try:
    import httpx as _httpx  # type: ignore
    _CEO_FALLBACK_EXCEPTIONS = _CEO_FALLBACK_EXCEPTIONS + (
        _httpx.ConnectError,
        _httpx.ReadTimeout,
        _httpx.ConnectTimeout,
    )
except ImportError:
    pass


# ── CEO fallback observability (#P1) ───────────────────────────────────────────
# Module-level counters so the operator can SEE when the CEO delegation layer
# silently falls back to single AgentRunner. Without this, every CEO outage
# looks like a successful run — the request still completes via the fallback,
# but the operator has no signal that the multi-agent layer is broken.
# Exposed via get_ceo_fallback_stats() for admin / health endpoints.
import threading as _threading
_ceo_fallback_lock = _threading.Lock()
_ceo_fallback_stats: dict[str, int] = {
    "verdict_non_ok": 0,        # CEO returned PARTIAL / FAILED verdict
    "transport_error": 0,       # CEO raised one of _CEO_FALLBACK_EXCEPTIONS
    "ceo_ok": 0,                # CEO returned OK verdict
    "ceo_low_complexity_bypass": 0,  # low-complexity: skipped CEO entirely
}


def get_ceo_fallback_stats() -> dict[str, int]:
    """Return a snapshot of CEO delegation outcomes for observability.

    The four counters let the operator answer, at a glance:
      - Is the CEO layer actually working? (ceo_ok should dominate)
      - How often is the fallback path firing? (verdict_non_ok + transport_error)
      - Is the low-complexity bypass being hit too aggressively?
        (ceo_low_complexity_bypass should be a minority)
    """
    with _ceo_fallback_lock:
        return dict(_ceo_fallback_stats)


def reset_ceo_fallback_stats() -> None:
    """Reset the counters (test helper)."""
    with _ceo_fallback_lock:
        for k in _ceo_fallback_stats:
            _ceo_fallback_stats[k] = 0


def _record_ceo_fallback(reason: str) -> None:
    """Bump the named counter under the lock (best-effort, never raises)."""
    try:
        with _ceo_fallback_lock:
            if reason in _ceo_fallback_stats:
                _ceo_fallback_stats[reason] += 1
    except Exception:  # pragma: no cover
        pass


# ── Orchestrator bypass flag (prevents circular deprecation block) ──────────
# Uses contextvars.ContextVar for async/coroutine safety — each async task
# gets its own isolated bypass flag. When the WorkflowOrchestrator itself
# calls AgentRunner (in _handle_execute), it sets this True to bypass the
# deprecation check. All other callers are blocked.
_BYPASS: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_orchestrator_bypass", default=False
)


def _allow_paid_brain() -> bool:
    """True when the operator explicitly opted into a paid (Anthropic) brain.

    Thin wrapper over the shared :func:`brain_policy.allow_paid_brain` so the
    orchestrator and the ``agent/loop.py`` runtime share one source of truth
    (issue #656). Default ``False`` — the brain never silently calls a paid API;
    when no free provider is configured it falls through to local Ollama.
    """
    try:
        from brain_policy import allow_paid_brain
        return allow_paid_brain()
    except Exception as exc:  # noqa: BLE001 - defensive fallback, must stay free-only
        # Surface the failure (operators must know the policy loader degraded),
        # but still fall back to the raw env so we never accidentally enable paid.
        log.warning(
            "brain_policy.allow_paid_brain unavailable; falling back to ALLOW_PAID_BRAIN env: %s",
            exc,
        )
        return os.environ.get("ALLOW_PAID_BRAIN", "").strip().lower() in {
            "1", "true", "yes", "on",
        }


async def _resolve_brain_provider(
    exclude_base_urls: set[str] | None = None,
) -> tuple[str, dict | None, str | None]:
    """Resolve the LLM endpoint for agent execution.

    Thin wrapper around the single source of truth in ``brain_policy.
    resolve_active_brain``.Kept as a module-level alias so existing callers
    (tests/orchestrator/caller modules) keep working unchanged. The actual
    selection logic — env override, fee-first skip-paid, exclusion list,
    Ollama fallback — lives in :func:`brain_policy.resolve_active_brain` so
    every selector (CEO dispatcher, harness adapter, model router, scripts)
    defers to one implementation.
    """
    from brain_policy import resolve_active_brain
    brain = await resolve_active_brain(exclude_base_urls=exclude_base_urls)
    return brain.base_url, brain.auth_headers, brain.model



def _orchestrator_bypass() -> bool:
    """True when the WorkflowOrchestrator is the caller (bypass deprecation)."""
    return _BYPASS.get()


async def get_provider_role_tags() -> dict[str, dict[str, Any]]:
    """Classify every configured provider as brain / sub-agent / fallback.

    Returns a dict keyed by ``provider_id`` with::

        {
          "<provider_id>": {
            "is_brain": bool,            # currently selected as the brain
            "role": "brain" | "sub-agent" | "fallback" | "available" | "unconfigured",
            "reason": str,               # short human-readable explanation
          },
          ...
        }

    Roles map to what the operator sees in the Providers screen::

        brain       — _resolve_brain_provider() picks this one right now.
        sub-agent   — reachable, configured, but NOT the brain. Will be tried
                      by provider-router failover when the brain is excluded
                      by a transient failure (e.g. cooldown / 5xx).
        fallback    — paid commercial provider (Anthropic) that the brain
                      resolver only selects when no free provider is configured.
                      Operators see a clear tag so they understand they will
                      be billed if the brain resolver ever falls through to it.
        available   — configured, reachable, but role unknown (e.g. env-override
                      AGENT_LLM_BASE_URL is masking the resolution).
        unconfigured — record exists but api_key / base_url is missing.

    Never raises — a malformed provider record degrades to ``role="available"``
    with ``reason`` explaining the issue, so the UI always renders something
    useful.
    """
    out: dict[str, dict[str, Any]] = {}
    brain_record: dict | None = None
    brain_base_norm: str | None = None
    try:
        brain_base, _hdrs, _model = await _resolve_brain_provider()
        brain_base_norm = brain_base.rstrip("/")
    except Exception as exc:
        log.debug("get_provider_role_tags: brain resolution failed: %s", exc)

    try:
        from backend.server import _list_configured_provider_records
        records = list(await _list_configured_provider_records())
    except Exception as exc:
        log.debug("get_provider_role_tags: provider list fetch failed: %s", exc)
        records = []

    def _norm(base: str) -> str:
        return (base or "").rstrip("/")

    for rec in records:
        pid = str(rec.get("provider_id") or "").strip()
        if not pid:
            continue
        rtype = str(rec.get("type") or "").lower()
        base = _norm(str(rec.get("base_url") or ""))
        key = str(rec.get("api_key") or "").strip()
        is_paid = rtype in ("anthropic", "emergent-anthropic")

        # Brain match: same normalised base URL, accounting for the /v1 suffix
        # that _resolve_brain_provider appends for openai-compatible providers.
        is_brain = False
        if brain_base_norm and base:
            for candidate in (base, f"{base}/v1"):
                if candidate == brain_base_norm:
                    is_brain = True
                    break

        if not base or (rtype != "ollama" and not key):
            role = "unconfigured"
            reason = "Missing base_url or API key"
        elif is_brain:
            role = "brain"
            reason = "Used as the brain for agent execution"
            brain_record = rec
        elif is_paid:
            role = "fallback"
            reason = (
                "Paid commercial fallback — only selected when no free provider "
                "is configured. Will incur costs."
            )
        else:
            role = "sub-agent"
            reason = (
                "Reachable backup — used by provider-router failover when the "
                "brain is excluded (cooldown / 5xx)."
            )
        out[pid] = {"is_brain": is_brain, "role": role, "reason": reason}

    # If the brain resolved to an env-override URL that doesn't match any
    # configured record, surface that fact so the UI can label whichever
    # provider is closest (e.g. the env override wins over all of them).
    if brain_base_norm and brain_record is None:
        log.info(
            "get_provider_role_tags: brain resolved to %s which is not in the "
            "configured provider records (likely AGENT_LLM_BASE_URL env override)",
            brain_base_norm,
        )

    return out


def is_legacy_mode() -> bool:
    """True when parallel execution paths are allowed (with warnings)."""
    return WORKFLOW_MODE == "legacy" or _BYPASS.get()


def _get_ceo_dispatcher():
    """Lazy import + singleton for the CEO delegation layer.

    Kept in workflow_orchestrator.py to avoid an import cycle: ceo_dispatcher
    imports _BYPASS from this module, so importing ceo_dispatcher at top of
    this file would create a cycle on first import.
    """
    from services.ceo_dispatcher import get_ceo_dispatcher as _g
    return _g()


def _merge_changed_files(specialists: list[dict]) -> list[str]:
    """Re-export the canonical helper from ceo_dispatcher for backward compat."""
    from services.ceo_dispatcher import _merge_changed_files as _impl
    return _impl(specialists)


def emit_deprecation(caller: str) -> None:
    """Log a deprecation warning when a parallel path is used."""
    log.warning(
        "DEPRECATED EXECUTION PATH: %s bypasses WorkflowOrchestrator. "
        "Set AGENCY_WORKFLOW_MODE=orchestrator to enforce the golden path. "
        "This path will be removed in a future release.",
        caller,
    )


# ── Golden Path Phases ────────────────────────────────────────────────────────


class Phase(Enum):
    """The 11 canonical phases of the Agency Core golden path."""

    CLASSIFY = "classify"
    PLAN = "plan"
    SELECT_SPECIALIST = "select_specialist"
    PREFLIGHT = "preflight"
    BIND_CONTEXT = "bind_context"
    EXECUTE = "execute"
    VERIFY = "verify"
    JUDGE = "judge"
    SUMMARIZE = "summarize"
    PERSIST = "persist"
    MONITOR = "monitor"


GOLDEN_PATH: list[Phase] = [
    Phase.CLASSIFY,
    Phase.PLAN,
    Phase.SELECT_SPECIALIST,
    Phase.PREFLIGHT,
    Phase.BIND_CONTEXT,
    Phase.EXECUTE,
    Phase.VERIFY,
    Phase.JUDGE,
    Phase.SUMMARIZE,
    Phase.PERSIST,
    Phase.MONITOR,
]

TERMINAL_PHASES: frozenset[Phase] = frozenset({
    Phase.SUMMARIZE,  # after summarize, persist+monitor are fire-and-forget
})


# ── Typed Contracts ────────────────────────────────────────────────────────────


class ExecutionRequest(BaseModel):
    """Canonical request to execute work through the golden path.

    This is the ONLY entry point for agent-driven work.  All other paths
    (AgentRunner.run, Agency.run_cycle, etc.) are soft-deprecated.
    """

    model_config = ConfigDict(extra="forbid")

    request: str = Field(..., min_length=1, max_length=16000)
    user_id: str | None = None
    company_id: str | None = None
    session_id: str | None = None
    auto_approve: bool = Field(
        default=False,
        description="Skip ApprovalGate for trusted/internal callers",
    )
    max_steps: int = Field(default=30, ge=1, le=100)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # The CALLER's GitHub token, so workflow execution acts with the user's own
    # repo permissions — not the server-wide service account. exclude=True keeps
    # it out of every model_dump()/as_dict() so it never leaks in API output.
    github_token: str | None = Field(default=None, exclude=True, repr=False)
    # Optional isolated workspace for this run (e.g. a git worktree path).
    # When set, the orchestrator and AgentRunner use it as the workspace_root
    # instead of os.getcwd() — addressing #504 worktree-isolation for
    # concurrent runs. The caller is responsible for creating and cleaning
    # up the worktree; the orchestrator just respects the path.
    worktree_path: str | None = None


class ClassifyOutput(BaseModel):
    """CLASSIFY phase: domain and task type determination."""

    model_config = ConfigDict(extra="forbid")

    domain: str = Field(default="general")
    task_type: str = Field(default="general")
    complexity: str = Field(default="medium")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class PlanOutput(BaseModel):
    """PLAN phase: structured execution plan."""

    model_config = ConfigDict(extra="forbid")

    goal: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    estimated_files: list[str] = Field(default_factory=list)
    requires_risky_review: bool = False
    requires_approval: bool = True


class SpecialistSelection(BaseModel):
    """SELECT_SPECIALIST phase: which specialist(s) handle this work."""

    model_config = ConfigDict(extra="forbid")

    specialist_ids: list[str] = Field(default_factory=list)
    specialist_names: list[str] = Field(default_factory=list)
    families: list[str] = Field(default_factory=list)
    routing_reason: str = ""


class PreflightReport(BaseModel):
    """PREFLIGHT phase: readiness check before execution."""

    model_config = ConfigDict(extra="forbid")

    ready: bool = False
    issues: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[dict[str, str]] = Field(default_factory=list)
    provider_health: dict[str, bool] = Field(default_factory=dict)
    git_ready: bool = False
    workspace_ok: bool = False


class BoundContext(BaseModel):
    """BIND_CONTEXT phase: resolved skills, memory, and company graph."""

    model_config = ConfigDict(extra="forbid")

    skill_ids: list[str] = Field(default_factory=list)
    memory_keys: list[str] = Field(default_factory=list)
    company_graph_snapshot: dict[str, Any] = Field(default_factory=dict)
    workspace_path: str | None = None


class ExecutionResult(BaseModel):
    """EXECUTE phase: raw result from specialist agent(s)."""

    model_config = ConfigDict(extra="forbid")

    output: str = ""
    changed_files: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    duration_ms: int = 0


class VerificationResult(BaseModel):
    """VERIFY phase: post-execution verification."""

    model_config = ConfigDict(extra="forbid")

    passed: bool = False
    checks: list[dict[str, Any]] = Field(default_factory=list)
    test_results: dict[str, Any] = Field(default_factory=dict)
    pr_verified: bool = False
    issues: list[str] = Field(default_factory=list)


class JudgeVerdict(BaseModel):
    """JUDGE phase: final pass/fail verdict."""

    model_config = ConfigDict(extra="forbid")

    verdict: str = Field(default="BLOCKED")  # APPROVED | APPROVED_WITH_CONDITIONS | REJECTED | BLOCKED
    security: str = Field(default="PASS")    # PASS | WARN | FAIL
    correctness: str = Field(default="PASS")  # PASS | WARN | FAIL
    notes: str = ""


class SummaryOutput(BaseModel):
    """SUMMARIZE phase: human-readable summary."""

    model_config = ConfigDict(extra="forbid")

    summary: str = ""
    next_steps: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class PersistOutput(BaseModel):
    """PERSIST phase: what was written to Company Graph and durable storage."""

    model_config = ConfigDict(extra="forbid")

    company_graph_updated: bool = False
    session_events_written: int = 0
    artifact_paths: list[str] = Field(default_factory=list)


class MonitorOutput(BaseModel):
    """MONITOR phase: KPIs logged for autonomous operation tracking."""

    model_config = ConfigDict(extra="forbid")

    time_to_pickup_ms: int = 0
    time_to_first_heartbeat_ms: int = 0
    time_to_resolution_ms: int = 0
    specialist_utilization: dict[str, int] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


# Maps WorkflowRun phase-output attribute names to their Pydantic model class.
# Used by restore_in_flight() to rehydrate typed models from checkpoint
# snapshots (which store plain dicts via as_dict()) — without this, restored
# phase outputs stay as raw dicts and `run.verification.passed` etc. raise
# AttributeError once the golden path is resumed.
_PHASE_OUTPUT_MODELS: dict[str, type[BaseModel]] = {
    "classify": ClassifyOutput,
    "plan": PlanOutput,
    "specialist": SpecialistSelection,
    "preflight": PreflightReport,
    "bound_context": BoundContext,
    "execution": ExecutionResult,
    "verification": VerificationResult,
    "judge": JudgeVerdict,
    "summary": SummaryOutput,
    "persist": PersistOutput,
    "monitor": MonitorOutput,
}


# ── Orchestrator ──────────────────────────────────────────────────────────────


@dataclass
class WorkflowRun:
    """In-flight state for a single golden-path execution."""

    run_id: str = field(default_factory=lambda: "wfo_" + secrets.token_hex(6))
    started_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    status: str = "pending"  # pending → running → awaiting_approval → executing → queued → done | failed

    # Multi-tenant ownership — set from the originating ExecutionRequest so
    # list_runs/get_run/approve can be scoped per user (admin sees all).
    user_id: str | None = None
    company_id: str | None = None

    # ── #522: Reliability fields ─────────────────────────────────────────
    # Heartbeat updated after every phase; watchdog detects stalls.
    last_heartbeat: float = field(default_factory=time.time)
    # Retry counter for auto-requeue on stall.
    retry_count: int = 0
    # LLM provenance per phase: {"classify": "nvidia-nim/nemotron-super", ...}
    llm_provenance: dict[str, str] = field(default_factory=dict)
    # Phase attempt counters for retry tracking.
    phase_attempts: dict[str, int] = field(default_factory=dict)

    # Phase outputs (None until the phase completes)
    classify: ClassifyOutput | None = None
    plan: PlanOutput | None = None
    specialist: SpecialistSelection | None = None
    preflight: PreflightReport | None = None
    bound_context: BoundContext | None = None
    execution: ExecutionResult | None = None
    verification: VerificationResult | None = None
    judge: JudgeVerdict | None = None
    summary: SummaryOutput | None = None
    persist: PersistOutput | None = None
    monitor: MonitorOutput | None = None

    approved: bool = False
    approved_by: str | None = None
    approved_at: str | None = None
    current_phase: str | None = None
    error: str | None = None
    # G5: how this run's code change should land per the company's RepoConnection
    # DeliveryPolicy — {"action": open_pr|direct_push|telegram_gate|
    # awaiting_repo_connection, "requires_approval": bool, "reason": str}.
    merge_decision: dict[str, Any] | None = None
    # Store the original request for resume-after-approval
    _request: Any = None

    def as_dict(self) -> dict[str, Any]:
        def _dump(val):
            """Safely serialize phase output — handles both Pydantic models and raw dicts."""
            if val is None:
                return None
            if hasattr(val, 'model_dump'):
                return val.model_dump()
            if isinstance(val, dict):
                return val
            return str(val)

        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "status": self.status,
            "current_phase": self.current_phase,
            "user_id": self.user_id,
            "company_id": self.company_id,
            "approved": self.approved,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "merge_decision": self.merge_decision,
            "last_heartbeat": self.last_heartbeat,
            "retry_count": self.retry_count,
            "llm_provenance": self.llm_provenance,
            "classify": _dump(self.classify),
            "plan": _dump(self.plan),
            "specialist": _dump(self.specialist),
            "preflight": _dump(self.preflight),
            "bound_context": _dump(self.bound_context),
            "execution": _dump(self.execution),
            "verification": _dump(self.verification),
            "judge": _dump(self.judge),
            "summary": _dump(self.summary),
            "persist": _dump(self.persist),
            "monitor": _dump(self.monitor),
            "error": self.error,
            "_request": self._request.model_dump() if self._request and hasattr(self._request, 'model_dump') else None,
        }


class WorkflowOrchestrator:
    """Canonical execution backbone for Agency Core.

    All agent-driven work MUST flow through ``execute()``.  Parallel paths
    (AgentRunner.run, Agency.run_cycle, etc.) are soft-deprecated.

    The orchestrator enforces the golden path:
      CLASSIFY → PLAN → SELECT_SPECIALIST → PREFLIGHT → BIND_CONTEXT →
      EXECUTE → VERIFY → JUDGE → SUMMARIZE → PERSIST → MONITOR

    ApprovalGate: after PLAN, execution blocks until ``approve()`` is called
    (unless ``auto_approve=True`` in the ExecutionRequest).
    """

    def __init__(self) -> None:
        self._runs: dict[str, WorkflowRun] = {}
        self._phase_handlers: dict[Phase, Callable] = {}
        self._register_default_handlers()
        # #522: Checkpoint store for crash recovery (lazy init)
        self._checkpoint_store = None

    def _get_checkpoint_store(self):
        if self._checkpoint_store is None:
            try:
                from services.orchestrator_checkpoint import get_orchestrator_checkpoint_store
                self._checkpoint_store = get_orchestrator_checkpoint_store()
            except Exception:
                self._checkpoint_store = _NoopStore()
        return self._checkpoint_store

    async def _checkpoint(self, run: WorkflowRun) -> None:
        """Persist run state for crash recovery."""
        try:
            await self._get_checkpoint_store().save(run)
        except Exception as exc:
            log.debug("Checkpoint save failed for run %s (non-fatal): %s", run.run_id, exc)

    async def _notify_approval_gate(self, run: WorkflowRun, req: ExecutionRequest) -> None:
        """Proactively push a Telegram approval-gate message (Autonomy Charter G1).

        Best-effort and non-fatal: a notification failure must not block the
        golden path — the run still sits in ``awaiting_approval`` and remains
        visible via the API/board regardless.
        """
        try:
            from telegram_service import NotificationDispatcher

            plan = run.plan
            goal = plan.goal if plan is not None else req.request
            steps = [str(s.get("description", s)) for s in (plan.steps if plan is not None else [])]
            risk_reason = ""
            if plan is not None and plan.requires_risky_review:
                risk_reason = "Plan touches a sensitive/risky path (requires_risky_review=true)."
            # G5: surface how the change will land (and why we're gating it).
            md = run.merge_decision
            if md:
                landing = f"Landing: {md.get('action')} — {md.get('reason') or ''}".strip()
                risk_reason = f"{risk_reason} {landing}".strip() if risk_reason else landing

            NotificationDispatcher().send_approval_gate(
                run_id=run.run_id,
                company_id=run.company_id,
                goal=goal,
                plan_steps=steps,
                risk_reason=risk_reason,
            )
        except Exception as exc:  # noqa: BLE001 - best-effort cross-cutting notify
            # WARNING (not DEBUG): a failed approval-gate push means the operator
            # silently loses the alert channel while the run still pauses.
            log.warning("Approval-gate notify failed for run %s (non-fatal): %s", run.run_id, exc)

    async def _resolve_merge_decision(self, run: WorkflowRun):
        """Consult the company's RepoConnection DeliveryPolicy (G5) to decide how
        this run's code change should land.

        Returns a ``services.repo_connection.MergeDecision`` (``open_pr`` /
        ``direct_push`` / ``telegram_gate`` / ``awaiting_repo_connection``) or
        ``None`` when there is no company or the lookup fails — in which case the
        normal gate logic applies unchanged. Best-effort: never blocks the gate.
        """
        if not run.company_id:
            return None
        try:
            from services.company_graph_store import get_company_graph_store
            from services.repo_connection import decide_merge

            store = get_company_graph_store()
            company = await asyncio.wait_for(store.get_company(run.company_id), timeout=8.0)
            conn = getattr(company, "repo_connection", None) if company is not None else None
            return decide_merge(conn)
        except Exception as exc:  # noqa: BLE001 — never block the gate on this
            log.warning("Merge-decision resolve failed for run %s: %s", run.run_id, exc)
            return None

    async def _record_first_merge_consent(self, run: WorkflowRun) -> None:
        """G5: once the operator approves a run that was gated specifically for the
        first unattended merge on a newly connected repo, record consent on the
        Company's RepoConnection so later merges follow the detected policy
        instead of re-gating. Best-effort; never raises into the approve path.
        """
        md = run.merge_decision
        if not md or md.get("action") != "telegram_gate" or not run.company_id:
            return
        try:
            from services.company_graph_store import get_company_graph_store
            from services.repo_connection import record_first_merge_consent

            store = get_company_graph_store()
            company = await asyncio.wait_for(store.get_company(run.company_id), timeout=8.0)
            conn = getattr(company, "repo_connection", None) if company is not None else None
            if conn is None:
                return
            updated = company.model_copy(
                update={"repo_connection": record_first_merge_consent(conn)}
            )
            await asyncio.wait_for(store.update_company(updated), timeout=8.0)
            log.info(
                "G5: recorded first-merge consent for company %s (repo %s)",
                run.company_id, conn.full_name,
            )
        except Exception as exc:  # noqa: BLE001 — best-effort
            log.warning("Could not record first-merge consent for run %s: %s", run.run_id, exc)

    # ── Public API ────────────────────────────────────────────────────────────

    async def _run_phase_with_timeout(
        self, run: WorkflowRun, req: ExecutionRequest, phase: Phase, handler: Callable
    ) -> None:
        """Run a phase with timeout, retries, and provider provenance tracking (#522).

        Each LLM-bearing phase is wrapped in asyncio.wait_for() with
        _PHASE_TIMEOUT_SEC (default 120s).  On timeout, the phase is retried
        up to _MAX_PHASE_RETRIES times with exponential backoff.  Provider
        provenance is recorded in run.llm_provenance[phase.value].
        """
        attempt = 0
        last_exc: Exception | None = None

        while attempt <= _MAX_PHASE_RETRIES:
            run.phase_attempts[phase.value] = attempt + 1
            try:
                started = time.time()
                # Periodic heartbeat — update last_heartbeat every 30s while the
                # phase runs so the supervisor knows it is not stalled (#522).
                async def _heartbeat():
                    while True:
                        await asyncio.sleep(30)
                        run.last_heartbeat = time.time()
                heartbeat_task = asyncio.create_task(_heartbeat())
                try:
                    await asyncio.wait_for(
                        handler(run, req),
                        timeout=_PHASE_TIMEOUT_SEC,
                    )
                finally:
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass
                elapsed = time.time() - started
                run.last_heartbeat = time.time()
                log.debug(
                    "Phase %s completed in %.1fs (attempt %d)",
                    phase.value, elapsed, attempt + 1,
                )
                return
            except asyncio.TimeoutError:
                attempt += 1
                last_exc = TimeoutError(f"Phase {phase.value} timed out after {_PHASE_TIMEOUT_SEC}s")
                log.warning(
                    "Phase %s timed out (attempt %d/%d)",
                    phase.value, attempt, _MAX_PHASE_RETRIES + 1,
                )
                if attempt <= _MAX_PHASE_RETRIES:
                    backoff = _BACKOFF_BASE_SEC * (2 ** (attempt - 1))
                    await asyncio.sleep(backoff)
            except Exception as exc:
                attempt += 1
                last_exc = exc
                log.warning(
                    "Phase %s failed (attempt %d/%d): %s",
                    phase.value, attempt, _MAX_PHASE_RETRIES + 1, exc,
                )
                if attempt <= _MAX_PHASE_RETRIES and self._is_retryable(exc):
                    backoff = _BACKOFF_BASE_SEC * (2 ** (attempt - 1))
                    await asyncio.sleep(backoff)
                elif not self._is_retryable(exc):
                    break

        raise last_exc or RuntimeError(f"Phase {phase.value} failed after {attempt} attempts")

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """True when this error class is worth retrying (transient)."""
        name = type(exc).__name__
        msg = str(exc).lower()
        retryable = {
            "TimeoutError", "ConnectionError", "ConnectionRefusedError",
            "ConnectionResetError", "RemoteDisconnected", "ReadTimeout",
            "ConnectTimeout", "HTTPError",  # some httpx errors
        }
        if name in retryable:
            return True
        for signal in ("429", "503", "502", "timeout", "connection", "throttl", "rate limit"):
            if signal in msg:
                return True
        return False

    async def execute(
        self, req: ExecutionRequest, *, resume_run_id: str | None = None
    ) -> WorkflowRun:
        """Execute a request through the full golden path.

        Blocks at ApprovalGate unless ``req.auto_approve`` is True.
        If ``resume_run_id`` is provided, resumes from that run and skips
        phases that already have output.
        Returns the completed WorkflowRun.
        """
        if resume_run_id and resume_run_id in self._runs:
            run = self._runs[resume_run_id]
        else:
            run = WorkflowRun()
        run._request = req
        # Stamp ownership from the originating request (new runs only; resumed
        # runs keep their original owner so approval can't re-attribute them).
        if run.user_id is None:
            run.user_id = req.user_id
        if run.company_id is None:
            run.company_id = req.company_id
        run.status = "running"
        self._runs[run.run_id] = run

        log.info("WorkflowOrchestrator: run=%s request=%.100s", run.run_id, req.request)

        # Phase → output mapping for skip detection when resuming
        _PHASE_OUTPUT = {
            Phase.CLASSIFY: "classify",
            Phase.PLAN: "plan",
            Phase.SELECT_SPECIALIST: "specialist",
            Phase.PREFLIGHT: "preflight",
            Phase.BIND_CONTEXT: "bound_context",
            Phase.EXECUTE: "execution",
            Phase.VERIFY: "verification",
            Phase.JUDGE: "judge",
            Phase.SUMMARIZE: "summary",
            Phase.PERSIST: "persist",
            Phase.MONITOR: "monitor",
        }

        for phase in GOLDEN_PATH:
            run.current_phase = phase.value

            # Skip already-completed phases when resuming
            attr_name = _PHASE_OUTPUT.get(phase)
            if attr_name and resume_run_id:
                existing = getattr(run, attr_name, None)
                if existing is not None:
                    log.debug(
                        "WorkflowOrchestrator: run=%s skipping completed phase %s",
                        run.run_id, phase.value,
                    )
                    continue

            log.debug("WorkflowOrchestrator: run=%s phase=%s", run.run_id, phase.value)

            try:
                handler = self._phase_handlers.get(phase)
                if handler is None:
                    log.warning("No handler registered for phase %s — skipping", phase)
                    continue

                # #522: Run phase with timeout, retries, and heartbeat tracking.
                # LLM-bearing phases (PLAN, EXECUTE, VERIFY, JUDGE) get the full
                # timeout/retry treatment; lightweight phases (CLASSIFY, PERSIST)
                # run directly.
                _LLM_PHASES = {Phase.PLAN, Phase.BIND_CONTEXT, Phase.EXECUTE, Phase.VERIFY, Phase.JUDGE}
                if phase in _LLM_PHASES:
                    await self._run_phase_with_timeout(run, req, phase, handler)
                else:
                    await handler(run, req)
                    run.last_heartbeat = time.time()

                # #522: Checkpoint after each successful phase.
                await self._checkpoint(run)

                # ApprovalGate after PLAN. The gate fires when the request is not
                # auto-approved, OR when the target repo's delivery policy forces
                # it (G5): the **first unattended merge on a newly connected repo**
                # always pauses for Telegram approval, even under auto_approve,
                # until the operator confirms its detected DeliveryPolicy.
                if phase == Phase.PLAN and not run.approved:
                    decision = await self._resolve_merge_decision(run)
                    if decision is not None:
                        run.merge_decision = {
                            "action": decision.action,
                            "requires_approval": decision.requires_approval,
                            "reason": decision.reason,
                        }
                    gate_forced = decision is not None and decision.requires_approval
                    if (not req.auto_approve) or gate_forced:
                        run.status = "awaiting_approval"
                        await self._checkpoint(run)
                        await self._notify_approval_gate(run, req)
                        log.info(
                            "WorkflowOrchestrator: run=%s PAUSED at ApprovalGate%s — "
                            "call approve() to continue",
                            run.run_id,
                            " (forced by repo first-merge policy)" if gate_forced else "",
                        )
                        return run

            except Exception as exc:
                log.exception("WorkflowOrchestrator: run=%s phase=%s FAILED", run.run_id, phase)
                run.status = "failed"
                run.error = f"{type(exc).__name__}: {exc}"
                await self._checkpoint(run)
                return run

        if run.verification is not None and not run.verification.passed:
            run.status = "failed"
            run.error = run.error or "; ".join(
                run.verification.issues or ["Verification failed"]
            )
            log.info(
                "WorkflowOrchestrator: run=%s FAILED — verification did not pass", run.run_id
            )
            return run

        run.status = "done"
        log.info("WorkflowOrchestrator: run=%s DONE", run.run_id)
        return run

    async def approve_and_resume(
        self, run_id: str, approved_by: str = "human"
    ) -> WorkflowRun:
        """Approve a run paused at the ApprovalGate and resume execution.

        Returns the completed run after all phases finish.
        """
        run = self.approve(run_id, approved_by=approved_by)
        # G5: record first-merge consent on the synchronous resume path too, so
        # it is covered regardless of which approve API the caller used.
        await self._record_first_merge_consent(run)
        if run._request is not None:
            return await self.execute(run._request, resume_run_id=run_id)
        return run

    async def approve_async(self, run_id: str, approved_by: str = "human") -> WorkflowRun:
        """#522: Approve a run and enqueue it for async execution via the FIFO queue.

        Returns IMMEDIATELY (the caller gets 202) — the run executes asynchronously
        when a concurrency slot opens.  This prevents the approve endpoint from
        blocking (and timing out) on long-running executions.

        Idempotent on the approval transition (#652 review): the Telegram gate
        calls ``approve()`` synchronously first (fast validation + correct inline
        feedback) and *then* fires ``approve_async()`` to resume. If the run is
        already approved we skip the redundant second transition/log and just
        enqueue it — avoiding a double-approve race.
        """
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(f"WorkflowRun {run_id!r} not found")
        # Reject repeat approvals before enqueueing (Codex P2): the API approve
        # route calls approve_async() directly, so a retry/double-click on an
        # already-approved run (now queued/running/done) must NOT be enqueued
        # again — OrchestratorQueue has no dedup and runs 2 concurrently, which
        # would duplicate side effects (commits/PRs). We keep the same
        # status==awaiting_approval guard approve() enforces, then only skip the
        # redundant approval *transition* when the Telegram gate already ran the
        # synchronous approve() (approved=True, status still awaiting_approval).
        if run.status != "awaiting_approval":
            raise ValueError(f"Run {run_id} is {run.status!r}, not awaiting_approval")
        if not run.approved:
            run = self.approve(run_id, approved_by=approved_by)
        # G5: persist first-merge consent so subsequent merges on this repo follow
        # the detected DeliveryPolicy instead of re-gating (best-effort).
        await self._record_first_merge_consent(run)
        try:
            from services.orchestrator_queue import get_orchestrator_queue
            queue = get_orchestrator_queue()
            await queue.enqueue(
                run_id,
                self.execute,
                run._request,
                resume_run_id=run_id,
            )
            run.status = "queued"
        except Exception:
            # Fall back to inline execution if queue is unavailable
            log.warning("Orchestrator queue unavailable — falling back to inline execution")
            return await self.execute(run._request, resume_run_id=run_id)
        return run

    async def restore_in_flight(self) -> int:
        """#522: Restore in-flight runs from checkpoint store after a restart.

        Returns the number of runs restored.
        """
        try:
            docs = await self._get_checkpoint_store().restore_in_flight_runs()
            count = 0
            for doc in docs:
                run_id = doc.get("run_id")
                snapshot = doc.get("snapshot", {})
                if not run_id or not snapshot:
                    continue
                # Reconstruct a minimal run from the snapshot
                run = WorkflowRun(run_id=run_id)
                run.status = snapshot.get("status", "queued")
                run.current_phase = snapshot.get("current_phase")
                run.user_id = snapshot.get("user_id")
                run.company_id = snapshot.get("company_id")
                run.last_heartbeat = snapshot.get("last_heartbeat", time.time())
                run.retry_count = snapshot.get("retry_count", 0)
                run.llm_provenance = snapshot.get("llm_provenance", {})
                run.phase_attempts = snapshot.get("phase_attempts", {})
                run.approved = snapshot.get("approved", False)
                run.merge_decision = snapshot.get("merge_decision")
                run.error = snapshot.get("error")
                # Restore phase outputs so skip detection works on retry.
                # Without this every resume re-runs all phases from scratch.
                # Reconstruct typed Pydantic models (not raw dicts) — downstream
                # code accesses attributes like `run.verification.passed`, which
                # raises AttributeError on a plain dict.
                for _attr, _model_cls in _PHASE_OUTPUT_MODELS.items():
                    _val = snapshot.get(_attr)
                    if _val is None:
                        continue
                    if isinstance(_val, dict):
                        try:
                            _val = _model_cls(**_val)
                        except Exception:
                            log.warning(
                                "restore_in_flight: run=%s could not reconstruct "
                                "%s from snapshot — phase will be re-run", run_id, _attr,
                            )
                            continue
                    setattr(run, _attr, _val)
                # Restore _request so supervisor can requeue without losing the original task.
                _req_dict = snapshot.get("_request")
                if _req_dict and isinstance(_req_dict, dict):
                    try:
                        run._request = ExecutionRequest(**_req_dict)
                    except Exception:
                        pass
                self._runs[run_id] = run
                # A run without its original request can never be resumed —
                # execute() needs req.user_id/req.company_id/etc. Fail it now
                # instead of leaving it queued/running for the supervisor to
                # endlessly retry-and-crash on execute(None, ...).
                if run.status in ("queued", "running", "pending") and run._request is None:
                    run.status = "failed"
                    run.error = (run.error or "") + " | Cannot resume: request not persisted in checkpoint"
                    count += 1
                    continue
                # Re-enqueue queued/pending runs so they resume execution.
                if run.status in ("queued", "running", "pending") and run._request is not None:
                    try:
                        from services.orchestrator_queue import get_orchestrator_queue
                        queue = get_orchestrator_queue()
                        await queue.enqueue(
                            run_id,
                            self.execute,
                            run._request,
                            resume_run_id=run_id,
                        )
                    except Exception:
                        pass
                count += 1
            log.info("Restored %d in-flight run(s) from checkpoint store", count)
            return count
        except Exception as exc:
            log.warning("Failed to restore in-flight runs: %s", exc)
            return 0

    def approve(self, run_id: str, approved_by: str = "human") -> WorkflowRun:
        """Approve a run paused at the ApprovalGate.

        The caller must re-invoke ``execute()`` with the same ExecutionRequest
        to resume from the phase after PLAN.
        """
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(f"WorkflowRun {run_id!r} not found")
        if run.status != "awaiting_approval":
            raise ValueError(
                f"Run {run_id} is {run.status!r}, not awaiting_approval"
            )
        run.approved = True
        run.approved_by = approved_by
        run.approved_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        log.info("WorkflowOrchestrator: run=%s APPROVED by %s", run_id, approved_by)
        return run

    def get_run(self, run_id: str) -> WorkflowRun | None:
        return self._runs.get(run_id)

    def cancel_run(self, run_id: str) -> bool:
        """Cancel a run by removing it from memory entirely.

        Marks the run as cancelled and clears _request BEFORE deleting from the
        dict so the supervisor (which snapshots runs) cannot re-queue a stale
        reference even if it processes the run concurrently.

        Returns True if the run existed, False otherwise.
        """
        run = self._runs.get(run_id)
        if run is None:
            return False
        run.status = "cancelled"
        run._request = None
        del self._runs[run_id]
        log.info("WorkflowOrchestrator: run=%s CANCELLED (removed)", run_id)
        return True

    def cancel_runs_bulk(self, run_ids: list[str] | None = None, *, status: str | None = None) -> int:
        """Cancel multiple runs at once.

        If ``run_ids`` is provided, cancels those specific runs.
        If ``status`` is provided, cancels all runs matching that status.
        Returns the number of runs cancelled.

        Each run is marked cancelled + _request cleared BEFORE dict deletion
        so concurrent supervisor ticks cannot re-queue stale snapshots.
        """
        if run_ids:
            to_cancel = [rid for rid in run_ids if rid in self._runs]
            for rid in to_cancel:
                r = self._runs[rid]
                r.status = "cancelled"
                r._request = None
                del self._runs[rid]
                log.info("WorkflowOrchestrator: run=%s CANCELLED (bulk)", rid)
            return len(to_cancel)
        if status:
            to_cancel = [
                rid for rid, r in self._runs.items()
                if r.status == status
            ]
            for rid in to_cancel:
                r = self._runs[rid]
                r.status = "cancelled"
                r._request = None
                del self._runs[rid]
                log.info(
                    "WorkflowOrchestrator: run=%s CANCELLED (bulk, status=%s)",
                    rid, status,
                )
            return len(to_cancel)
        return 0

    def list_runs(
        self, limit: int = 50, *, owner_id: str | None = None
    ) -> list[dict[str, Any]]:
        """List recent runs.

        When ``owner_id`` is provided, only runs stamped with that ``user_id``
        are returned — the per-user scoping used by non-admin callers.  Pass
        ``owner_id=None`` (the default) for the admin/unscoped view.
        """
        runs = list(self._runs.values())
        if owner_id is not None:
            runs = [r for r in runs if r.user_id == owner_id]
        return [r.as_dict() for r in runs[-limit:]]

    # ── Default Phase Handlers ────────────────────────────────────────────────

    async def update_task(
        self,
        run_id: str,
        *,
        additional_instructions: str | None = None,
        operator: str = "admin",
    ) -> WorkflowRun:
        """Inject additional instructions into a paused or running WorkflowRun.

        Used by the Telegram ``/redirect <run_id> <instruction>`` command and
        the ``POST /api/workflow/orchestrator/update-task/{run_id}`` endpoint
        so an operator can redirect the agent mid-flight (e.g. "actually,
        only fix tests X and Y \u2014 leave the others alone") without replanning
        from scratch. Always checkpoints so a bot\u2192orchestrator connection
        drop cannot lose the redirect.
        """
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(f"WorkflowRun {run_id!r} not found")
        if run.status in ("done", "failed", "cancelled"):
            raise ValueError(
                f"Run {run_id} is {run.status!r} and cannot accept new instructions"
            )
        req = run._request
        if req is None:
            raise ValueError(
                f"Run {run_id} has no ExecutionRequest \u2014 cannot inject instructions"
            )
        meta = dict(req.metadata or {})
        if additional_instructions is not None:
            meta["additional_instructions"] = additional_instructions
            meta["updated_by"] = operator
            meta["updated_at_utc"] = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            )
        run._request = req.model_copy(update={"metadata": meta})
        await self._checkpoint(run)
        log.info(
            "WorkflowOrchestrator: run=%s update_task by=%s instructions=%s",
            run_id, operator, bool(additional_instructions),
        )
        return run

    def _register_default_handlers(self) -> None:
        self._phase_handlers[Phase.CLASSIFY] = self._handle_classify
        self._phase_handlers[Phase.PLAN] = self._handle_plan
        self._phase_handlers[Phase.SELECT_SPECIALIST] = self._handle_select_specialist
        self._phase_handlers[Phase.PREFLIGHT] = self._handle_preflight
        self._phase_handlers[Phase.BIND_CONTEXT] = self._handle_bind_context
        self._phase_handlers[Phase.EXECUTE] = self._handle_execute
        self._phase_handlers[Phase.VERIFY] = self._handle_verify
        self._phase_handlers[Phase.JUDGE] = self._handle_judge
        self._phase_handlers[Phase.SUMMARIZE] = self._handle_summarize
        self._phase_handlers[Phase.PERSIST] = self._handle_persist
        self._phase_handlers[Phase.MONITOR] = self._handle_monitor

    async def _handle_classify(self, run: WorkflowRun, req: ExecutionRequest) -> None:
        """Determine domain and task type from the request text."""
        from agent.workflow import classify_domain

        domain = classify_domain(req.request)
        task_type = domain

        # Refine task type from keywords
        request_lower = req.request.lower()
        if any(kw in request_lower for kw in ("fix", "bug", "repair", "broken")):
            task_type = "bug_fix"
        elif any(kw in request_lower for kw in ("add", "implement", "feature", "new")):
            task_type = "feature"
        elif any(kw in request_lower for kw in ("refactor", "clean", "restructure")):
            task_type = "refactor"
        elif any(kw in request_lower for kw in ("review", "audit", "assess")):
            task_type = "review"
        elif any(kw in request_lower for kw in ("deploy", "release", "ship")):
            task_type = "release"

        complexity = "medium"
        if len(req.request) > 2000:
            complexity = "high"
        elif len(req.request) < 200:
            complexity = "low"

        run.classify = ClassifyOutput(
            domain=domain,
            task_type=task_type,
            complexity=complexity,
            confidence=0.85,
        )
        log.info("Classify: domain=%s type=%s complexity=%s", domain, task_type, complexity)

    async def _handle_plan(self, run: WorkflowRun, req: ExecutionRequest) -> None:
        """Generate a structured execution plan.

        Uses the LLM if available; falls back to a rule-based plan.
        """
        classify = run.classify
        domain = classify.domain if classify else "general"

        # Try LLM-based planning via the CRISPY engine
        try:
            from workflow.engine import get_engine
            from workflow.models import WorkflowBuildRequest as WfBuildReq

            engine = get_engine()
            wf_run = await engine.create_run(
                WfBuildReq(
                    request=req.request,
                    title=req.request[:80],
                )
            )
            # Extract plan from the CRISPY workflow run
            plan_artifact = engine._artifact_store.content_by_name(
                wf_run.run_id, "plan.md"
            )
            if plan_artifact:
                run.plan = PlanOutput(
                    goal=req.request[:200],
                    steps=[{"description": s} for s in plan_artifact.split("\n") if s.strip()][:20],
                    estimated_files=[],
                    requires_risky_review="risky" in req.request.lower(),
                    requires_approval=True,
                )
                return
        except Exception as exc:
            log.debug("LLM planning unavailable, using rule-based: %s", exc)

        # Rule-based fallback
        steps = []
        if domain == "security":
            steps = [
                {"description": "Identify the security vulnerability or pattern"},
                {"description": "Implement the fix with minimal changes"},
                {"description": "Add or update security tests"},
                {"description": "Verify no regressions with pytest -x"},
            ]
        elif domain == "testing":
            steps = [
                {"description": "Analyze test failures and identify root cause"},
                {"description": "Fix tests — never mock to hide real failures"},
                {"description": "Run pytest -x to confirm all pass"},
            ]
        elif domain == "docs":
            steps = [
                {"description": "Identify docs that need updating"},
                {"description": "Update docs with accurate, current information"},
                {"description": "Verify no dead links or placeholder content"},
            ]
        else:
            steps = [
                {"description": "Analyze the codebase to understand the current state"},
                {"description": "Implement the requested change with minimal, correct code"},
                {"description": "Add or update tests"},
                {"description": "Run pytest -x and confirm all pass"},
                {"description": "Update docs/changelog.md"},
            ]

        run.plan = PlanOutput(
            goal=req.request[:200],
            steps=steps,
            estimated_files=[],
            requires_risky_review="risky" in req.request.lower(),
            requires_approval=True,
        )

    async def _handle_select_specialist(self, run: WorkflowRun, req: ExecutionRequest) -> None:
        """Select the best specialist(s) for the classified domain."""
        classify = run.classify
        domain = classify.domain if classify else "general"
        specialist_ids: list[str] = []
        specialist_names: list[str] = []
        families: list[str] = []

        # Try to find specialists via Company Graph
        if req.company_id:
            try:
                from services.specialist import get_specialist_service
                svc = get_specialist_service()
                specialists = await svc.list_specialists(req.company_id)
                if specialists:
                    # Match by domain/system type
                    for s in specialists:
                        if domain in (s.system_types or []):
                            specialist_ids.append(s.id)
                            specialist_names.append(s.name)
                            families.append(s.family.value if hasattr(s.family, 'value') else str(s.family))
                    if specialist_ids:
                        run.specialist = SpecialistSelection(
                            specialist_ids=specialist_ids[:3],
                            specialist_names=specialist_names[:3],
                            families=families[:3],
                            routing_reason=f"Matched {len(specialist_ids)} specialist(s) for domain={domain}",
                        )
                        return
            except Exception as exc:
                log.debug("Specialist lookup via Company Graph failed: %s", exc)

        # Fallback: agent store lookup
        try:
            from agents.store import get_agent_store
            agent_store = get_agent_store()
            all_agents = await agent_store.list_all(limit=50)
            candidates = [
                a for a in all_agents
                if domain in (a.tags or []) or getattr(a, 'domain', None) == domain
            ]
            if candidates:
                best = max(candidates, key=lambda a: getattr(a, 'last_used_at', 0) or 0)
                run.specialist = SpecialistSelection(
                    specialist_ids=[best.agent_id],
                    specialist_names=[best.name],
                    families=[getattr(best, 'domain', 'general')],
                    routing_reason=f"Agent store match: {best.name}",
                )
                return
        except Exception as exc:
            log.debug("Agent store lookup failed: %s", exc)

        # Default: no specialist found
        run.specialist = SpecialistSelection(
            specialist_ids=[],
            specialist_names=["default-agent"],
            families=["general"],
            routing_reason=f"No domain specialist for '{domain}'; using default runtime",
        )

    async def _handle_preflight(self, run: WorkflowRun, req: ExecutionRequest) -> None:
        """Run doctor checks before execution."""
        issues: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        provider_health: dict[str, bool] = {}
        git_ready = False
        workspace_ok = False

        try:
            from agent.doctor import DirectChatDoctor
            # Preflight must validate the SAME credentials execution will use —
            # the caller's token — so a green preflight reflects the caller's
            # real GitHub access. Fall back to the env token only for internal
            # system runs (no user_id), matching _handle_execute.
            github_token = req.github_token
            if github_token is None and req.user_id is None:
                github_token = os.environ.get("GH_TOKEN") or os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN")
            doctor = DirectChatDoctor(github_token=github_token)
            report = await doctor.check_all()

            ready = report.ready
            for issue in report.issues:
                entry = {"code": issue.code, "message": issue.message, "hint": issue.fix_hint or ""}
                if issue.code in {"missing_git_binary", "invalid_github_token", "git_repo_access"}:
                    issues.append(entry)
                else:
                    warnings.append(entry)

            git_ready = not any(
                i["code"] in {"missing_git_binary", "invalid_github_token", "git_repo_access"}
                for i in issues
            )
            workspace_ok = True
        except Exception as exc:
            log.warning("Preflight via doctor failed: %s", exc)
            ready = True  # Proceed if doctor is unavailable
            warnings.append({"code": "doctor_unavailable", "message": str(exc), "hint": ""})

        # Check provider health
        try:
            from router.health import check_all_providers
            provider_health = await check_all_providers()
        except Exception:
            provider_health = {"default": True}

        run.preflight = PreflightReport(
            ready=ready,
            issues=issues,
            warnings=warnings,
            provider_health=provider_health,
            git_ready=git_ready,
            workspace_ok=workspace_ok,
        )

        if issues:
            log.warning("Preflight: %d blocking issue(s) found", len(issues))
            for issue in issues:
                log.warning("  - %s: %s", issue["code"], issue["message"])

    async def _handle_bind_context(self, run: WorkflowRun, req: ExecutionRequest) -> None:
        """Resolve and bind skills, memory, and Company Graph context."""
        skill_ids: list[str] = []
        memory_keys: list[str] = []
        company_graph: dict[str, Any] = {}
        loop = asyncio.get_event_loop()

        # Skill bindings — recommend_for_company is synchronous; run in executor
        # so it cannot block the event loop and prevent asyncio.wait_for cancellation.
        try:
            from services.skill_bindings import get_skill_bindings
            sb = get_skill_bindings()
            classify = run.classify
            domain = classify.domain if classify else "general"
            families = list(run.specialist.families) if run.specialist else []
            recommended = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: sb.recommend_for_company(
                        system_types=[domain], specialist_families=families
                    ),
                ),
                timeout=10.0,
            )
            skill_ids = [
                r["skill_id"] for r in recommended
                if r.get("is_enabled", True) and r.get("skill_id")
            ]
            log.info(
                "BindContext: resolved %d skill(s) for domain=%s families=%s",
                len(skill_ids), domain, families,
            )
        except Exception as exc:
            log.debug("Skill binding failed (non-fatal): %s", exc)

        # Load Company Graph if company_id provided
        if req.company_id:
            try:
                from services.company_graph_store import CompanyGraphStore
                store = CompanyGraphStore()
                company = await asyncio.wait_for(
                    store.get_company(req.company_id), timeout=8.0
                )
                if company:
                    company_graph = company.model_dump() if hasattr(company, 'model_dump') else {}
            except Exception as exc:
                log.debug("Company Graph load failed (non-fatal): %s", exc)

        # Load user memory — synchronous; run in executor
        if req.user_id:
            try:
                from agent.user_memory import UserMemoryStore
                mem_store = UserMemoryStore()
                memories = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: mem_store.recall_all(req.user_id)),
                    timeout=8.0,
                )
                memory_keys = list(memories.keys()) if memories else []
            except Exception:
                pass

        run.bound_context = BoundContext(
            skill_ids=skill_ids,
            memory_keys=memory_keys,
            company_graph_snapshot=company_graph,
            workspace_path=os.getcwd(),
        )

    async def _handle_execute(self, run: WorkflowRun, req: ExecutionRequest) -> None:
        """Execute the plan via the selected specialist(s).

        For medium/high-complexity tasks, the CEO delegation layer fans the
        request out across multiple specialists (scout + dev + reviewer)
        running concurrently on the best-fit runtimes. For low-complexity
        tasks, a single AgentRunner call avoids the fan-out overhead.
        """
        plan = run.plan
        specialist = run.specialist

        if plan is None:
            run.execution = ExecutionResult(output="No plan to execute")
            return

        # Execute the FULL user request, not the truncated plan.goal (which is
        # only a 200-char summary).  Dropping the tail would lose file names,
        # constraints, and acceptance criteria for long requests.  The plan goal
        # is included as a header for context.
        instruction = req.request
        if plan.goal and plan.goal.strip() and plan.goal[:200] != req.request[:200]:
            instruction = f"Goal: {plan.goal}\n\nFull request:\n{req.request}"

        # CEO delegation for medium/high complexity: fan out to multiple
        # specialists. For low complexity, fall through to the single-runner
        # path (cheaper, avoids concurrency overhead).
        classify = run.classify
        complexity = classify.complexity if classify else "medium"
        domain = classify.domain if classify else "general"

        if complexity in ("medium", "high"):
            try:
                ceo = _get_ceo_dispatcher()
                gh_token = _resolve_push_token(req.github_token, req.user_id)
                workspace_root = req.worktree_path or os.getcwd()
                ceo_result = await ceo.delegate(
                    instruction,
                    complexity=complexity,
                    domain=domain,
                    specialists=list(specialist.specialist_names) if specialist and specialist.specialist_names else None,
                    runtimes=None,
                    user_id=req.user_id,
                    github_token=gh_token,
                    workspace_root=workspace_root,
                )
                # The swarm's internal try/except swallows per-task errors as
                # status="error" payloads (it never re-raises), so an exception
                # never escapes the CEO. We instead inspect CEOResult.verdict
                # to decide whether to use the CEO's output or fall through
                # to the single AgentRunner path.
                if ceo_result.verdict == "OK":
                    _record_ceo_fallback("ceo_ok")
                    run.llm_provenance["ceo_verdict"] = ceo_result.verdict
                    run.llm_provenance["ceo_fanout"] = "true" if ceo_result.fanout_used else "false"
                    run.llm_provenance["ceo_runtimes_woken"] = ",".join(ceo_result.runtimes_woken)
                    run.execution = ExecutionResult(
                        output=ceo_result.summary,
                        changed_files=_merge_changed_files(ceo_result.specialists),
                        tool_calls=[],
                        artifacts=[{"ceo": ceo_result.as_dict()}],
                        duration_ms=int(ceo_result.total_duration_s * 1000),
                    )
                    return
                # Verdict != OK — the CEO returned, but at least one specialist
                # failed. Bump the counter and surface a loud warning so the
                # operator can see the multi-agent layer is degraded, not just
                # silently falling through.
                _record_ceo_fallback("verdict_non_ok")
                log.warning(
                    "CEO delegation verdict=%s (%d/%d specialists ok); falling back to single AgentRunner",
                    ceo_result.verdict,
                    sum(1 for s in ceo_result.specialists if s.get("status") == "ok"),
                    len(ceo_result.specialists),
                )
            except _CEO_FALLBACK_EXCEPTIONS as exc:
                # Availability/transport error — fall through to single-runner
                # path so the run can still succeed via AgentRunner. The counter
                # bump + WARNING-level log (not DEBUG) is the signal: the CEO
                # layer is unreachable, every request is paying the single-runner
                # cost instead of the parallel multi-agent one.
                _record_ceo_fallback("transport_error")
                log.warning(
                    "CEO delegation unavailable (%s: %s); falling back to single AgentRunner",
                    type(exc).__name__, exc,
                )
            except Exception as exc:
                # Logic bug or programming error — log full traceback and
                # surface as a real failure (do NOT silently fall back, which
                # would mask the bug).
                log.exception("CEO delegation failed unexpectedly")
                raise

        # Single-runner path: AgentRunner (bypass deprecation via flag)
        try:
            from agent.loop import AgentRunner
            import os as _os
            import services.workflow_orchestrator as _wo

            # Set the bypass token so AgentRunner.run() doesn't block us.
            # Uses ContextVar for async/coroutine safety.
            _token = _wo._BYPASS.set(True)
            try:
                # Use the caller's GitHub token so the workflow acts with the
                # user's own repo permissions. Only fall back to the server-wide
                # token for internal/system runs (no user_id) — never let a
                # user-initiated run borrow the service account's repo access.
                gh_token = _resolve_push_token(req.github_token, req.user_id)
                # Provider failover (#522): on each retry we exclude the base
                # URLs that already failed so _resolve_brain_provider returns the
                # NEXT provider in priority order. Failed URLs accumulate on the
                # run across phase retries.
                _prev_failed = run.llm_provenance.get("_failed_execute", "")
                failed_urls: set[str] = (
                    set(u for u in _prev_failed.split(",") if u) if _prev_failed else set()
                )
                brain_base, brain_headers, brain_model = await _resolve_brain_provider(
                    exclude_base_urls=failed_urls,
                )
                # Record provider provenance for failover tracking.
                run.llm_provenance["execute"] = (brain_model or brain_base.split("/")[-1] or "unknown")
                runner = AgentRunner(
                    ollama_base=brain_base,
                    provider_headers=brain_headers,
                    workspace_root=_os.getcwd(),
                    github_token=gh_token,
                    email=req.user_id,
                )
                try:
                    result = await runner.run(
                        instruction=instruction,
                        history=[],
                        requested_model=brain_model,
                        auto_commit=False,
                        max_steps=req.max_steps,
                        user_id=req.user_id,
                        session_id=req.session_id,
                    )
                except Exception:
                    # Mark this provider's URL as failed so the retry (driven by
                    # _run_phase_with_timeout) fails over to the next provider,
                    # then re-raise so the retry loop actually fires.
                    failed_urls.add(brain_base.rstrip("/"))
                    run.llm_provenance["_failed_execute"] = ",".join(sorted(failed_urls))
                    raise
                run.execution = ExecutionResult(
                    output=result.get("summary", ""),
                    changed_files=[
                        f for step in result.get("steps", [])
                        for f in step.get("changed_files", [])
                    ],
                    tool_calls=[],
                    artifacts=[result.get("judge", {})],
                    duration_ms=0,
                )
            finally:
                _wo._BYPASS.reset(_token)
        except Exception as exc:
            log.exception("Execution failed (attempt provider=%s): %s",
                          run.llm_provenance.get("execute"), exc)
            # Re-raise so _run_phase_with_timeout's retry/backoff + provider
            # failover loop engages. Only the final exhausted attempt should
            # surface as a failed run (handled by the retry wrapper).
            raise

    async def _handle_verify(self, run: WorkflowRun, req: ExecutionRequest) -> None:
        """Verify execution results."""
        execution = run.execution
        if execution is None:
            run.verification = VerificationResult(passed=False, issues=["No execution result to verify"])
            return

        checks: list[dict[str, Any]] = []
        passed = True
        pr_verified = False

        # Only code-editing task types must change files. Read-only work
        # (review/audit/research/docs queries) legitimately produces useful
        # output with zero changed files — requiring edits would always fail it.
        _EDITING_TASK_TYPES = {"bug_fix", "feature", "refactor", "release"}
        task_type = run.classify.task_type if run.classify else "general"
        edits_expected = task_type in _EDITING_TASK_TYPES

        # Check for changed files
        if execution.changed_files:
            checks.append({"check": "files_changed", "passed": True, "detail": f"{len(execution.changed_files)} file(s)"})
        elif edits_expected:
            checks.append({"check": "files_changed", "passed": False, "detail": "No files changed"})
            passed = False
        else:
            # Read-only task: success requires meaningful output instead.
            has_output = bool((execution.output or "").strip())
            checks.append({
                "check": "read_only_output",
                "passed": has_output,
                "detail": f"{task_type}: produced output" if has_output else f"{task_type}: empty output",
            })
            if not has_output:
                passed = False

        # Check judge verdict from execution
        judge_data = None
        if execution.artifacts:
            for art in execution.artifacts:
                if isinstance(art, dict) and art.get("verdict"):
                    judge_data = art
                    break

        if judge_data:
            verdict = judge_data.get("verdict", "BLOCKED")
            checks.append({"check": "judge_verdict", "passed": verdict in ("APPROVED", "APPROVED_WITH_CONDITIONS"), "detail": verdict})
            if verdict not in ("APPROVED", "APPROVED_WITH_CONDITIONS"):
                passed = False

        # Try to verify PR if GitHub token available. Use the caller's token
        # (same as preflight/execute) so verification reflects the caller's
        # access; env fallback only for internal/system runs (no user_id).
        github_token = _resolve_push_token(req.github_token, req.user_id)
        if github_token and execution.output:
            import re
            pr_matches = re.findall(r'github\.com/([^/]+/[^/]+)/pull/(\d+)', execution.output)
            if pr_matches:
                try:
                    from agent.safe_agency import verify_pr_exists
                    owner_repo, pr_number = pr_matches[0]
                    owner, repo = owner_repo.split("/", 1)
                    pr_verified = await verify_pr_exists(github_token, owner, repo, int(pr_number))
                    checks.append({"check": "pr_exists", "passed": pr_verified, "detail": f"PR #{pr_number}"})
                except Exception:
                    checks.append({"check": "pr_exists", "passed": False, "detail": "Verification error"})

        run.verification = VerificationResult(
            passed=passed,
            checks=checks,
            test_results={},
            pr_verified=pr_verified,
            issues=[] if passed else ["Verification failed"],
        )

    async def _handle_judge(self, run: WorkflowRun, req: ExecutionRequest) -> None:
        """Issue final pass/fail verdict."""
        verification = run.verification
        execution = run.execution

        if verification is None or execution is None:
            run.judge = JudgeVerdict(verdict="BLOCKED", notes="Missing verification or execution data")
            return

        if verification.passed and execution.output and len(execution.output) > 10:
            run.judge = JudgeVerdict(
                verdict="APPROVED",
                security="PASS",
                correctness="PASS",
                notes="All checks passed. Output produced.",
            )
        elif verification.passed:
            run.judge = JudgeVerdict(
                verdict="APPROVED_WITH_CONDITIONS",
                security="PASS",
                correctness="WARN",
                notes="Verification passed but output is minimal.",
            )
        else:
            run.judge = JudgeVerdict(
                verdict="REJECTED",
                security="WARN",
                correctness="FAIL",
                notes=f"Verification failed: {', '.join(verification.issues)}",
            )

    async def _handle_summarize(self, run: WorkflowRun, req: ExecutionRequest) -> None:
        """Produce a human-readable summary with evidence."""
        judge = run.judge
        execution = run.execution
        classify = run.classify

        verdict_text = judge.verdict if judge else "UNKNOWN"
        output_text = execution.output if execution else ""
        domain = classify.domain if classify else "general"

        summary = (
            f"[{verdict_text}] {domain}: {req.request[:100]}"
        )
        if execution and execution.changed_files:
            summary += f" — {len(execution.changed_files)} file(s) changed"

        next_steps: list[str] = []
        if judge and judge.verdict in ("APPROVED", "APPROVED_WITH_CONDITIONS"):
            next_steps.append("Merge changes and deploy")
        elif judge and judge.verdict == "REJECTED":
            next_steps.append("Review failures and retry with corrections")
            if judge.notes:
                next_steps.append(f"Issue: {judge.notes}")
        else:
            next_steps.append("Manual review required")

        evidence: list[dict[str, Any]] = []
        if execution:
            evidence.append({
                "type": "execution_output",
                "summary": output_text[:500] if output_text else "(no output)",
                "files": execution.changed_files,
            })

        run.summary = SummaryOutput(
            summary=summary,
            next_steps=next_steps,
            evidence=evidence,
        )

    async def _handle_persist(self, run: WorkflowRun, req: ExecutionRequest) -> None:
        """Persist results to Company Graph and durable storage."""
        company_updated = False
        events_written = 0
        artifact_paths: list[str] = []

        # Update Company Graph if company_id provided
        if req.company_id and run.summary:
            try:
                from datetime import datetime, timezone
                from services.company_graph_store import CompanyGraphStore
                store = CompanyGraphStore()
                company = await store.get_company(req.company_id)
                if company:
                    # `Company` is a frozen, extra="forbid" model with no
                    # `activity_log` field, so we cannot mutate it in place.
                    # Record workflow activity in the existing mutable
                    # `integration_config` dict and bump `last_activity`, then
                    # persist a copy via model_copy (respects the contract).
                    cfg = dict(company.integration_config or {})
                    activity = list(cfg.get("workflow_activity", []))
                    activity.append({
                        "run_id": run.run_id,
                        "timestamp": run.started_at,
                        "verdict": run.judge.verdict if run.judge else "UNKNOWN",
                        "summary": run.summary.summary,
                    })
                    # Cap the log so it can't grow unbounded.
                    cfg["workflow_activity"] = activity[-50:]
                    updated = company.model_copy(update={
                        "integration_config": cfg,
                        "last_activity": datetime.now(timezone.utc),
                    })
                    await store.update_company(updated)
                    # Verify the round-trip: some backends (e.g. the SQLite
                    # fallback) don't persist integration_config/last_activity,
                    # so only report success if the activity actually survived.
                    # (It is always durably recorded in the session event log
                    # below regardless of backend.)
                    verify = await store.get_company(req.company_id)
                    company_updated = bool(
                        verify and (verify.integration_config or {}).get("workflow_activity")
                    )
                    if not company_updated:
                        log.info(
                            "Company Graph activity not persisted by backend "
                            "(recorded in session event log instead)."
                        )
            except Exception as exc:
                log.warning("Company Graph persist failed (non-fatal): %s", exc)

        # Write session events
        if req.session_id:
            try:
                from agent.state import AgentSessionStore
                store = AgentSessionStore()
                store.append_event(req.session_id, "workflow_complete", run.as_dict())
                events_written = 1
            except Exception as exc:
                log.debug("Session event write failed (non-fatal): %s", exc)

        run.persist = PersistOutput(
            company_graph_updated=company_updated,
            session_events_written=events_written,
            artifact_paths=artifact_paths,
        )

    async def _handle_monitor(self, run: WorkflowRun, req: ExecutionRequest) -> None:
        """Log KPIs for autonomous operation tracking."""
        run.monitor = MonitorOutput(
            time_to_pickup_ms=0,
            time_to_first_heartbeat_ms=0,
            time_to_resolution_ms=0,
            specialist_utilization={},
            errors=[run.error] if run.error else [],
        )
        log.info(
            "WorkflowOrchestrator KPI: run=%s verdict=%s",
            run.run_id,
            run.judge.verdict if run.judge else "UNKNOWN",
        )


class _NoopStore:
    """No-op checkpoint store when the real one is unavailable."""
    async def save(self, run: Any) -> None:
        pass
    async def restore_in_flight_runs(self) -> list[dict[str, Any]]:
        return []


# ── Singleton ─────────────────────────────────────────────────────────────────

_orchestrator: WorkflowOrchestrator | None = None


def get_workflow_orchestrator() -> WorkflowOrchestrator:
    """Return the shared WorkflowOrchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WorkflowOrchestrator()
    return _orchestrator


def reset_orchestrator() -> None:
    """Reset the singleton (test helper)."""
    global _orchestrator
    _orchestrator = None

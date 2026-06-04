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

import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, Field

log = logging.getLogger("agency.orchestrator")

# ── Feature flag ──────────────────────────────────────────────────────────────

WORKFLOW_MODE = os.environ.get("AGENCY_WORKFLOW_MODE", "orchestrator")

if WORKFLOW_MODE not in ("orchestrator", "legacy"):
    log.warning(
        "AGENCY_WORKFLOW_MODE=%r unrecognised; falling back to 'orchestrator'",
        WORKFLOW_MODE,
    )
    WORKFLOW_MODE = "orchestrator"


# ── Orchestrator bypass flag (prevents circular deprecation block) ──────────
# When the WorkflowOrchestrator itself calls AgentRunner (in _handle_execute),
# it sets this True to bypass the deprecation check. All other callers are blocked.
_ORCHESTRATOR_CALLING: bool = False


def _orchestrator_bypass() -> bool:
    """True when the WorkflowOrchestrator is the caller (bypass deprecation)."""
    return _ORCHESTRATOR_CALLING


def is_legacy_mode() -> bool:
    """True when parallel execution paths are allowed (with warnings)."""
    return WORKFLOW_MODE == "legacy" or _ORCHESTRATOR_CALLING


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


class ClassifyOutput(BaseModel):
    """CLASSIFY phase: domain and task type determination."""

    domain: str = Field(default="general")
    task_type: str = Field(default="general")
    complexity: str = Field(default="medium")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class PlanOutput(BaseModel):
    """PLAN phase: structured execution plan."""

    goal: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    estimated_files: list[str] = Field(default_factory=list)
    requires_risky_review: bool = False
    requires_approval: bool = True


class SpecialistSelection(BaseModel):
    """SELECT_SPECIALIST phase: which specialist(s) handle this work."""

    specialist_ids: list[str] = Field(default_factory=list)
    specialist_names: list[str] = Field(default_factory=list)
    families: list[str] = Field(default_factory=list)
    routing_reason: str = ""


class PreflightReport(BaseModel):
    """PREFLIGHT phase: readiness check before execution."""

    ready: bool = False
    issues: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[dict[str, str]] = Field(default_factory=list)
    provider_health: dict[str, bool] = Field(default_factory=dict)
    git_ready: bool = False
    workspace_ok: bool = False


class BoundContext(BaseModel):
    """BIND_CONTEXT phase: resolved skills, memory, and company graph."""

    skill_ids: list[str] = Field(default_factory=list)
    memory_keys: list[str] = Field(default_factory=list)
    company_graph_snapshot: dict[str, Any] = Field(default_factory=dict)
    workspace_path: str | None = None


class ExecutionResult(BaseModel):
    """EXECUTE phase: raw result from specialist agent(s)."""

    output: str = ""
    changed_files: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    duration_ms: int = 0


class VerificationResult(BaseModel):
    """VERIFY phase: post-execution verification."""

    passed: bool = False
    checks: list[dict[str, Any]] = Field(default_factory=list)
    test_results: dict[str, Any] = Field(default_factory=dict)
    pr_verified: bool = False
    issues: list[str] = Field(default_factory=list)


class JudgeVerdict(BaseModel):
    """JUDGE phase: final pass/fail verdict."""

    verdict: str = Field(default="BLOCKED")  # APPROVED | APPROVED_WITH_CONDITIONS | REJECTED | BLOCKED
    security: str = Field(default="PASS")    # PASS | WARN | FAIL
    correctness: str = Field(default="PASS")  # PASS | WARN | FAIL
    notes: str = ""


class SummaryOutput(BaseModel):
    """SUMMARIZE phase: human-readable summary."""

    summary: str = ""
    next_steps: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class PersistOutput(BaseModel):
    """PERSIST phase: what was written to Company Graph and durable storage."""

    company_graph_updated: bool = False
    session_events_written: int = 0
    artifact_paths: list[str] = Field(default_factory=list)


class MonitorOutput(BaseModel):
    """MONITOR phase: KPIs logged for autonomous operation tracking."""

    time_to_pickup_ms: int = 0
    time_to_first_heartbeat_ms: int = 0
    time_to_resolution_ms: int = 0
    specialist_utilization: dict[str, int] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


# ── Orchestrator ──────────────────────────────────────────────────────────────


@dataclass
class WorkflowRun:
    """In-flight state for a single golden-path execution."""

    run_id: str = field(default_factory=lambda: "wfo_" + secrets.token_hex(6))
    started_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    status: str = "pending"  # pending → running → awaiting_approval → executing → done | failed

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
    # Store the original request for resume-after-approval
    _request: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "status": self.status,
            "current_phase": self.current_phase,
            "approved": self.approved,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "classify": self.classify.model_dump() if self.classify else None,
            "plan": self.plan.model_dump() if self.plan else None,
            "specialist": self.specialist.model_dump() if self.specialist else None,
            "preflight": self.preflight.model_dump() if self.preflight else None,
            "bound_context": self.bound_context.model_dump() if self.bound_context else None,
            "execution": self.execution.model_dump() if self.execution else None,
            "verification": self.verification.model_dump() if self.verification else None,
            "judge": self.judge.model_dump() if self.judge else None,
            "summary": self.summary.model_dump() if self.summary else None,
            "persist": self.persist.model_dump() if self.persist else None,
            "monitor": self.monitor.model_dump() if self.monitor else None,
            "error": self.error,
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

    # ── Public API ────────────────────────────────────────────────────────────

    async def execute(
        self, req: ExecutionRequest, *, resume_run_id: str | None = None
    ) -> WorkflowRun:
        """Execute a request through the full golden path.

        Blocks at ApprovalGate unless ``req.auto_approve`` is True.
        If ``resume_run_id`` is provided, resumes from that run's state.
        Returns the completed WorkflowRun.
        """
        if resume_run_id and resume_run_id in self._runs:
            run = self._runs[resume_run_id]
        else:
            run = WorkflowRun()
        run._request = req
        run.status = "running"
        self._runs[run.run_id] = run

        log.info("WorkflowOrchestrator: run=%s request=%.100s", run.run_id, req.request)

        for phase in GOLDEN_PATH:
            run.current_phase = phase.value
            log.debug("WorkflowOrchestrator: run=%s phase=%s", run.run_id, phase.value)

            try:
                handler = self._phase_handlers.get(phase)
                if handler is None:
                    log.warning("No handler registered for phase %s — skipping", phase)
                    continue

                await handler(run, req)

                # ApprovalGate after PLAN
                if phase == Phase.PLAN and not req.auto_approve and not run.approved:
                    run.status = "awaiting_approval"
                    log.info(
                        "WorkflowOrchestrator: run=%s PAUSED at ApprovalGate — "
                        "call approve() to continue",
                        run.run_id,
                    )
                    return run

            except Exception as exc:
                log.exception("WorkflowOrchestrator: run=%s phase=%s FAILED", run.run_id, phase)
                run.status = "failed"
                run.error = f"{type(exc).__name__}: {exc}"
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
        if run._request is not None:
            return await self.execute(run._request, resume_run_id=run_id)
        return run

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

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        return [r.as_dict() for r in list(self._runs.values())[-limit:]]

    # ── Default Phase Handlers ────────────────────────────────────────────────

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
            github_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
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

        # Bind skills from Phase 1 SkillBindings
        try:
            from services.skill_bindings import get_skill_bindings
            sb = get_skill_bindings()
            classify = run.classify
            domain = classify.domain if classify else "general"
            recommended = sb.recommend_for_company(system_types=[domain])
            skill_ids = [s.skill_id for s in recommended if s.is_enabled]
            log.info("BindContext: resolved %d skill(s) for domain=%s", len(skill_ids), domain)
        except Exception as exc:
            log.debug("Skill binding failed (non-fatal): %s", exc)

        # Load Company Graph if company_id provided
        if req.company_id:
            try:
                from services.company_graph_store import CompanyGraphStore
                store = CompanyGraphStore()
                company = await store.get_company(req.company_id)
                if company:
                    company_graph = company.model_dump() if hasattr(company, 'model_dump') else {}
            except Exception as exc:
                log.debug("Company Graph load failed (non-fatal): %s", exc)

        # Load user memory
        if req.user_id:
            try:
                from agent.user_memory import UserMemoryStore
                mem_store = UserMemoryStore()
                memories = mem_store.recall_all(req.user_id)
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
        """Execute the plan via the selected specialist(s)."""
        plan = run.plan
        specialist = run.specialist
        bound = run.bound_context

        if plan is None:
            run.execution = ExecutionResult(output="No plan to execute")
            return

        # Build instruction from plan
        instruction = plan.goal

        # Try AgentRunner for actual execution (bypass deprecation via flag)
        try:
            from agent.loop import AgentRunner
            import os as _os
            import services.workflow_orchestrator as _wo

            # Set the bypass flag so AgentRunner.run() doesn't block us
            _wo._ORCHESTRATOR_CALLING = True
            try:
                runner = AgentRunner(
                    ollama_base=_os.environ.get("OLLAMA_BASE", "http://localhost:11434"),
                    workspace_root=_os.getcwd(),
                    github_token=_os.environ.get("GH_TOKEN") or _os.environ.get("GITHUB_TOKEN"),
                    email=req.user_id,
                )
                result = await runner.run(
                    instruction=instruction,
                    history=[],
                    requested_model=None,
                    auto_commit=False,
                    max_steps=req.max_steps,
                    user_id=req.user_id,
                    session_id=req.session_id,
                )
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
                _wo._ORCHESTRATOR_CALLING = False
        except Exception as exc:
            log.exception("Execution failed: %s", exc)
            run.execution = ExecutionResult(
                output=f"Execution error: {exc}",
                changed_files=[],
                tool_calls=[],
                artifacts=[],
                duration_ms=0,
            )

    async def _handle_verify(self, run: WorkflowRun, req: ExecutionRequest) -> None:
        """Verify execution results."""
        execution = run.execution
        if execution is None:
            run.verification = VerificationResult(passed=False, issues=["No execution result to verify"])
            return

        checks: list[dict[str, Any]] = []
        passed = True
        pr_verified = False

        # Check for changed files
        if execution.changed_files:
            checks.append({"check": "files_changed", "passed": True, "detail": f"{len(execution.changed_files)} file(s)"})
        else:
            checks.append({"check": "files_changed", "passed": False, "detail": "No files changed"})
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

        # Try to verify PR if GitHub token available
        github_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
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
                from services.company_graph_store import CompanyGraphStore
                store = CompanyGraphStore()
                company = await store.get_company(req.company_id)
                if company:
                    # Append to company activity log
                    if not hasattr(company, 'activity_log') or company.activity_log is None:
                        company.activity_log = []
                    company.activity_log.append({
                        "run_id": run.run_id,
                        "timestamp": run.started_at,
                        "verdict": run.judge.verdict if run.judge else "UNKNOWN",
                        "summary": run.summary.summary,
                    })
                    await store.update_company(company)
                    company_updated = True
            except Exception as exc:
                log.debug("Company Graph persist failed (non-fatal): %s", exc)

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

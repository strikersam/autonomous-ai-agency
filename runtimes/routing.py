"""runtimes/routing.py — RuntimeRoutingPolicyEngine.

Implements the 8-step routing decision flow:
  1. Classify task type and complexity
  2. Choose best-fit runtime
  3. Choose best-fit model/provider inside that runtime (local first)
  4. Validate result (schema, tool success, quality heuristics)
  5. Retry locally once with stronger model if configured
  6. Switch runtime on runtime-level failure
  7. Escalate to paid provider only if policy allows
  8. Log every routing/escalation decision with full reason

Admin-configurable controls:
  - max_paid_escalations_per_day
  - never_use_paid_providers
  - require_approval_before_paid_escalation
  - per_agent fallback thresholds
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from runtimes.base import (
    RuntimeAdapter,
    RuntimeCapability,
    RuntimePreflightError,
    RuntimeUnavailableError,
    RuntimeExecutionError,
    TaskResult,
    TaskSpec,
)

if TYPE_CHECKING:
    from runtimes.registry import RuntimeCapabilityRegistry
    from runtimes.health import RuntimeHealthService

log = logging.getLogger("qwen-proxy")


def _governance_identity(spec: "TaskSpec", runtime: "RuntimeAdapter") -> Any:
    """Resolve the acting identity for a runtime dispatch.

    Identity comes from ``spec.context``, which the agency already threads
    through for other purposes. A task with no agent attached resolves to
    ``agent:unknown`` and therefore to the least-privileged default group,
    never an unrestricted one.
    """
    from packages.governance.identity import resolve_identity

    context = spec.context or {}
    # session_id must be STABLE across a task's dispatch attempts (primary and
    # every fallback), or the per-session budget never accumulates and the
    # ceilings can never bite on the runtime path. Prefer a session threaded
    # through the task context; otherwise anchor deterministically on the task
    # id so one task's dispatches share one budget. resolve_identity would
    # otherwise mint a fresh random session per call.
    session_id = context.get("session_id") or context.get("session")
    if not session_id and spec.task_id:
        session_id = "sess_task_" + hashlib.sha256(
            str(spec.task_id).encode("utf-8")
        ).hexdigest()[:16]
    return resolve_identity(
        agent_name=context.get("agent_name") or context.get("agent"),
        owner=context.get("agent_owner") or context.get("user_email"),
        session_id=session_id or None,
        task_id=spec.task_id,
        repo=spec.repo_url,
        runtime=runtime.RUNTIME_ID,
    )


def _audit_dispatch(
    identity: Any, spec: "TaskSpec", runtime: "RuntimeAdapter", verdict: Any, blocked: bool
) -> None:
    """Record one runtime-dispatch decision in the audit trail.

    The instruction body is deliberately **not** stored. It is free text
    authored by an agent or a user and can contain anything — truncating it
    would not protect a secret sitting in the first 200 characters, and the
    audit does not need it: ``task_id`` is the join key to the full task
    record, so shape metadata (type and length) is all this row has to carry.
    """
    from packages.governance.audit import events_from_identity, record_event

    fields = events_from_identity(identity)
    fields["policy_group"] = verdict.group
    fields.update({
        "surface": verdict.surface.value,
        "action": runtime.RUNTIME_ID,
        "tool": "runtime.dispatch",
        "arguments": {
            "task_type": spec.task_type,
            "instruction_chars": len(spec.instruction or ""),
        },
        "decision": verdict.decision.value,
        "effective": verdict.effective.value,
        "reason": verdict.reason,
        "rule_id": verdict.rule_id,
        "mode": verdict.mode.value,
        "result_status": "blocked" if blocked else "ok",
    })
    record_event(**fields)


def _blocked_result(spec: "TaskSpec", runtime: "RuntimeAdapter", verdict: Any) -> "TaskResult":
    """Build the failed TaskResult returned when policy denies a dispatch.

    A result rather than an exception: callers of ``route_and_execute``
    already handle an unsuccessful result, whereas a new exception type would
    propagate somewhere none of them expect. The reason travels in ``output``
    (which callers surface) and structurally in ``metadata`` (which callers
    can branch on without string-matching prose).
    """
    return TaskResult(
        runtime_id=runtime.RUNTIME_ID,
        task_id=spec.task_id,
        success=False,
        output=f"[governance] denied: {verdict.reason} (rule {verdict.rule_id})",
        metadata={
            "governance_blocked": True,
            "governance_rule_id": verdict.rule_id,
        },
    )


def _governance_check(
    spec: "TaskSpec", runtime: "RuntimeAdapter", decision: "RoutingDecision"
) -> "TaskResult | None":
    """Evaluate a runtime dispatch against policy; audit it either way.

    Returns ``None`` when the dispatch may proceed, or a failed
    :class:`TaskResult` when policy blocks it.

    Called for the primary runtime **and for every fallback runtime** — a
    fallback executes a different adapter than the one that was checked, so
    checking only the primary would let a restricted agent reach a denied
    runtime simply by having its permitted one fail.

    Never raises. Like every other governance seam in this repo, a failure in
    the layer itself allows the dispatch and logs — a control that can take
    out task execution would be a worse liability than the risk it mitigates.
    """
    try:
        from packages.governance.enforcement import governance_enabled

        if not governance_enabled():
            return None

        from packages.governance.enforcement import get_gate
        from packages.governance.policy import (
            Decision,
            Mode,
            PolicyDecision,
            Surface,
            get_policy_engine,
        )

        engine = get_policy_engine()
        identity = _governance_identity(spec, runtime)
        verdict = engine.evaluate(Surface.RUNTIME, runtime.RUNTIME_ID, identity)

        # Budget: a runtime dispatch consumes session budget like any guarded
        # tool call, so the six ceilings apply to work handed to a runtime too —
        # otherwise an agent could evade an exhausted in-process budget just by
        # dispatching the same work to an adapter. Count the dispatch, then
        # check; both count and check share the one budget the AgentRunner path
        # reads, keyed by the same session.
        gate = get_gate()
        session_id = str(getattr(identity, "session_id", "") or "anonymous")
        budget = gate.budgets.get(session_id, engine.limits_for(identity))
        budget.tool_calls += 1
        budget.per_tool_calls[runtime.RUNTIME_ID] = (
            budget.per_tool_calls.get(runtime.RUNTIME_ID, 0) + 1
        )
        exhausted = budget.check()

        policy_deny = verdict.effective is Decision.DENY
        # Budget denial respects the mode exactly as policy does: observe records
        # a would-block without stopping the dispatch, enforce stops it.
        budget_deny = bool(exhausted) and engine.mode is Mode.ENFORCE

        if budget_deny and not policy_deny:
            # Record the budget verdict (not the policy ALLOW) so the audit row
            # and the returned reason name what actually blocked.
            verdict = PolicyDecision(
                decision=Decision.DENY, surface=Surface.RUNTIME,
                action=runtime.RUNTIME_ID,
                reason=f"session budget exhausted: {exhausted}",
                rule_id="budget.session.exhausted",
                mode=engine.mode, group=verdict.group,
            )

        blocked = policy_deny or budget_deny
        _audit_dispatch(identity, spec, runtime, verdict, blocked)

        if not blocked:
            return None

        log.warning(
            "Runtime dispatch blocked by %s: %s -> %s (%s)",
            "budget" if (budget_deny and not policy_deny) else "policy",
            identity.agent_id, runtime.RUNTIME_ID, verdict.rule_id,
        )
        decision.reason += f"; blocked by governance ({verdict.rule_id})"
        return _blocked_result(spec, runtime, verdict)
    except Exception as exc:  # noqa: BLE001 - fail open, consistent with the other seams
        log.warning("Runtime governance check failed (%s); allowing dispatch", exc)
        return None


# ── Policy model ──────────────────────────────────────────────────────────────

@dataclass
class RoutingPolicy:
    """Admin-configurable routing policy.

    Defaults are conservative (local-first, no paid escalation).
    """
    never_use_paid_providers: bool = True
    require_approval_before_paid_escalation: bool = True
    max_paid_escalations_per_day: int = 0
    local_retry_with_stronger_model: bool = True
    preferred_runtime_id: str | None = None        # global default
    fallback_runtime_ids: list[str] = field(default_factory=list)
    # Per-task-type runtime overrides: {"code_generation": "opencode", ...}
    task_type_runtime_overrides: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "never_use_paid_providers": self.never_use_paid_providers,
            "require_approval_before_paid_escalation": self.require_approval_before_paid_escalation,
            "max_paid_escalations_per_day": self.max_paid_escalations_per_day,
            "local_retry_with_stronger_model": self.local_retry_with_stronger_model,
            "preferred_runtime_id": self.preferred_runtime_id,
            "fallback_runtime_ids": self.fallback_runtime_ids,
            "task_type_runtime_overrides": self.task_type_runtime_overrides,
        }


# ── Routing decision log ──────────────────────────────────────────────────────

@dataclass
class RoutingDecision:
    """Full record of a routing decision — audit-trail entry."""
    task_id: str
    task_type: str
    selected_runtime_id: str
    model_used: str | None
    provider_used: str | None
    reason: str
    escalated: bool = False
    escalation_reason: str | None = None
    fallback_attempted: bool = False
    fallback_runtime_id: str | None = None
    timestamp: float = field(default_factory=time.time)

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "selected_runtime_id": self.selected_runtime_id,
            "model_used": self.model_used,
            "provider_used": self.provider_used,
            "reason": self.reason,
            "escalated": self.escalated,
            "escalation_reason": self.escalation_reason,
            "fallback_attempted": self.fallback_attempted,
            "fallback_runtime_id": self.fallback_runtime_id,
            "timestamp": self.timestamp,
        }


# ── Engine ────────────────────────────────────────────────────────────────────

class RuntimeRoutingPolicyEngine:
    """Routes a TaskSpec to the best available runtime following the
    configured policy.  All routing decisions are logged for audit."""

    def __init__(
        self,
        registry: "RuntimeCapabilityRegistry",
        health_service: "RuntimeHealthService",
        policy: RoutingPolicy | None = None,
    ) -> None:
        self._registry = registry
        self._health = health_service
        self._policy = policy or RoutingPolicy()
        self._decision_log: list[RoutingDecision] = []

    # ── Policy management ─────────────────────────────────────────────────────

    @property
    def policy(self) -> RoutingPolicy:
        return self._policy

    def update_policy(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            if hasattr(self._policy, k):
                setattr(self._policy, k, v)
            else:
                log.warning("Unknown policy field: %s", k)

    # ── Main routing entry point ──────────────────────────────────────────────

    async def route_and_execute(self, spec: TaskSpec) -> tuple[TaskResult, RoutingDecision]:
        """
        Selects a runtime for the given task, executes the task (including readiness checks, configured fallbacks, and optional paid escalation), and records the routing decision.
        
        Parameters:
            spec (TaskSpec): Task specification including task_id, task_type, model/provider preferences, and escalation flags.
        
        Returns:
            tuple[TaskResult, RoutingDecision]: The execution result and a RoutingDecision containing the selected runtime, model/provider used, reasons, and any fallback or escalation details.
        
        Raises:
            RuntimeUnavailableError: If no healthy runtime is available for the task type.
            
        Side effects:
            Appends the produced RoutingDecision to the engine's internal decision log.
        """
        task_type = spec.task_type or "general"

        # Step 2: Choose runtime
        preferred_id = (
            self._policy.task_type_runtime_overrides.get(task_type)
            or spec.provider_preference
            or self._policy.preferred_runtime_id
        )
        runtime, candidates_info = self._pick_runtime(task_type, preferred_id)

        if runtime is None:
            log.warning("No healthy runtime candidates for task_type=%s; candidates: %s", task_type, candidates_info)
            raise RuntimeUnavailableError("*", f"No healthy runtime found for task type '{task_type}'")

        decision = RoutingDecision(
            task_id=spec.task_id,
            task_type=task_type,
            selected_runtime_id=runtime.RUNTIME_ID,
            model_used=spec.model_preference,
            provider_used=spec.provider_preference,
            reason=f"Best-fit runtime for task_type='{task_type}' (tier={runtime.TIER.value})",
        )
        # Append audit detail to decision.reason for observability
        try:
            decision.reason += f"; candidates={candidates_info}"
        except Exception:
            pass

        # ── Governance ────────────────────────────────────────────────────
        # The last coverage gap in docs/governance/README.md: `_dispatch_tool`
        # and the MCP surface were governed, but runtime *dispatch* was not —
        # so an agent restricted from writing files in-process could still hand
        # the same work to a runtime adapter that writes files in its own
        # container. This closes that: the choice of executor is now a governed
        # decision, and every dispatch is attributed and audited.
        #
        # Guarded after selection rather than before, so the audit row records
        # which runtime was actually chosen (and therefore which one a policy
        # would need to name) instead of only the requested preference.
        blocked = _governance_check(spec, runtime, decision)
        if blocked is not None:
            self._decision_log.append(decision)
            return blocked, decision

        # Step 4–6: Execute with retry/fallback
        result = await self._execute_with_fallback(spec, runtime, decision)
        self._decision_log.append(decision)
        return result, decision

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _pick_runtime(
        self,
        task_type: str,
        preferred_id: str | None,
    ) -> tuple[RuntimeAdapter | None, list[dict[str, object]]]:
        """
        Selects an available runtime for the given task type, preferring a specified runtime when available.
        
        Parameters:
            task_type (str): The task type to match against runtime capabilities.
            preferred_id (str | None): Optional runtime ID to prefer if that runtime is available.
        
        Returns:
            tuple[selected_runtime, candidates_info]:
                selected_runtime (RuntimeAdapter | None): The chosen runtime adapter, or `None` if no capable runtime is currently available.
                candidates_info (list[dict[str, object]]): An ordered list of candidate metadata dictionaries containing:
                    - "runtime_id": runtime identifier (str)
                    - "tier": runtime tier value (str)
                    - "available": availability boolean
                    - "health": health snapshot as a dict or `None`
        """
        candidates = self._registry.capable_of(task_type)
        candidates_info: list[dict[str, object]] = []
        available = []
        for a in candidates:
            health = self._health.get_health(a.RUNTIME_ID)
            is_avail = self._health.is_available(a.RUNTIME_ID)
            candidates_info.append({
                "runtime_id": a.RUNTIME_ID,
                "tier": a.TIER.value,
                "available": is_avail,
                "health": health.as_dict() if health else None,
            })
            if is_avail:
                available.append(a)
        log.info("Runtime candidate scan for task_type=%s: %s", task_type, candidates_info)
        if not available:
            return None, candidates_info
        if preferred_id:
            for a in available:
                if a.RUNTIME_ID == preferred_id:
                    log.info("Preferred runtime %s selected for task_type=%s", preferred_id, task_type)
                    return a, candidates_info
            log.info("Preferred runtime %s not available; falling back", preferred_id)
        selected = available[0]
        log.info("Selected runtime %s for task_type=%s (tier=%s)", selected.RUNTIME_ID, task_type, selected.TIER.value)
        return selected, candidates_info

    async def _execute_with_fallback(
        self,
        spec: TaskSpec,
        primary_runtime: RuntimeAdapter,
        decision: RoutingDecision,
    ) -> TaskResult:
        """
        Execute the given task spec on the primary runtime, attempt configured fallback runtimes on failures, and optionally perform paid escalation.
        
        Mutates `decision` with execution metadata (e.g., `model_used`, `provider_used`, `fallback_attempted`, `fallback_runtime_id`, `reason`, and escalation fields) when a runtime succeeds or an escalation occurs.
        
        Parameters:
            decision (RoutingDecision): Routing decision record that will be updated with outcome details.
        
        Returns:
            TaskResult: The successful execution result from the primary runtime, a fallback runtime, or a paid escalation.
        
        Raises:
            RuntimeUnavailableError: If all runtime attempts fail, if paid escalation requires approval, or if paid escalation is blocked by daily budget limits.
        """
        last_exec_error: str = ""
        try:
            report = await primary_runtime.readiness_check(spec)
            if not report.ready:
                raise RuntimePreflightError(primary_runtime.RUNTIME_ID, report)
            result = await primary_runtime.execute(spec)
            decision.model_used = result.model_used
            decision.provider_used = result.provider_used
            return result
        except (RuntimeUnavailableError, RuntimeExecutionError, RuntimePreflightError) as exc:
            last_exec_error = str(exc)
            log.warning("Primary runtime %s failed: %s — attempting fallback",
                        primary_runtime.RUNTIME_ID, exc)

        # Step 6: Try fallback runtimes
        # Note: allow fallback to the same runtime when the failure was a transient
        # execution error (e.g. LLM validation), not a health/availability failure.
        fallback_ids = self._policy.fallback_runtime_ids or []
        for fid in fallback_ids:
            fb_runtime = self._registry.get(fid)
            if fb_runtime and self._health.is_available(fid):
                # Govern every fallback, not just the primary. A fallback runs a
                # *different* adapter than the one checked in route_and_execute,
                # so checking only the primary would let a restricted agent
                # reach a denied runtime simply by having its permitted one
                # fail — the policy would hold on the happy path and evaporate
                # on the error path.
                #
                # A denied fallback is skipped rather than aborting the chain:
                # the agent may not use *this* runtime, which says nothing
                # about the next one. If every fallback is denied the loop ends
                # at the existing "no fallback succeeded" path unchanged.
                if _governance_check(spec, fb_runtime, decision) is not None:
                    continue
                try:
                    report = await fb_runtime.readiness_check(spec)
                    if not report.ready:
                        raise RuntimePreflightError(fid, report)
                    result = await fb_runtime.execute(spec)
                    decision.fallback_attempted = True
                    decision.fallback_runtime_id = fid
                    decision.reason += f"; fell back to {fid}"
                    decision.model_used = result.model_used
                    decision.provider_used = result.provider_used
                    return result
                except (RuntimeUnavailableError, RuntimeExecutionError, RuntimePreflightError) as fb_exc:
                    last_exec_error = str(fb_exc)
                    log.warning("Fallback runtime %s also failed: %s", fid, fb_exc)

        # Step 7: Paid escalation — routed through ProviderManager
        if spec.allow_paid_escalation and not self._policy.never_use_paid_providers:
            if self._policy.require_approval_before_paid_escalation:
                raise RuntimeUnavailableError(
                    "*",
                    "All local runtimes failed; paid escalation requires human approval "
                    "(require_approval_before_paid_escalation=True).",
                )
            # Check daily escalation budget
            today_escalations = sum(
                1 for d in self._decision_log
                if d.escalated and (time.time() - d.timestamp) < 86400
            )
            if (
                self._policy.max_paid_escalations_per_day > 0
                and today_escalations >= self._policy.max_paid_escalations_per_day
            ):
                raise RuntimeUnavailableError(
                    "*",
                    f"Paid escalation budget exhausted "
                    f"({today_escalations}/{self._policy.max_paid_escalations_per_day} today).",
                )
            # Attempt escalation via ProviderManager
            escalation_result = await self._escalate_via_provider_manager(spec, decision)
            if escalation_result is not None:
                return escalation_result

        raise RuntimeUnavailableError(
            "*",
            f"All runtimes failed and policy prevents paid escalation."
            + (f" Last error: {last_exec_error}" if last_exec_error else ""),
        )

    async def _escalate_via_provider_manager(
        self,
        spec: TaskSpec,
        decision: RoutingDecision,
    ) -> TaskResult | None:
        """Attempt paid escalation through ProviderManager.

        Routes the task to the first available cloud provider.  Returns a
        TaskResult on success, or None if no cloud provider is configured.
        """
        try:
            from webui.providers import ProviderManager
            import httpx as _httpx

            pm = ProviderManager()
            providers = await pm.list_providers() if hasattr(pm, "list_providers") else []

            for provider_rec in providers:
                pname = getattr(provider_rec, "name", "") or ""
                if pname.lower() in ("ollama", "local"):
                    continue   # skip local providers

                base_url = getattr(provider_rec, "base_url", "") or ""
                api_key  = getattr(provider_rec, "api_key", "") or ""

                if not base_url or not api_key:
                    continue

                # Build an OpenAI-compatible chat completion request
                model = spec.model_preference or "gpt-4o-mini"
                try:
                    async with _httpx.AsyncClient(timeout=60) as client:
                        resp = await client.post(
                            f"{base_url.rstrip('/')}/chat/completions",
                            headers={
                                "Authorization": f"Bearer {api_key}",
                                "Content-Type": "application/json",
                            },
                            json={
                                "model":    model,
                                "messages": [{"role": "user", "content": spec.instruction}],
                            },
                        )
                        if resp.status_code == 200:
                            data    = resp.json()
                            output  = data["choices"][0]["message"]["content"]
                            decision.escalated           = True
                            decision.escalation_reason   = f"Local runtimes unavailable; escalated to {pname}"
                            decision.selected_runtime_id = f"paid:{pname}"
                            decision.model_used          = model
                            decision.provider_used       = pname
                            log.warning(
                                "PAID ESCALATION: task %s escalated to %s model %s",
                                spec.task_id, pname, model,
                            )
                            return TaskResult(
                                runtime_id=f"paid:{pname}",
                                task_id=spec.task_id,
                                success=True,
                                output=output,
                                model_used=model,
                                provider_used=pname,
                            )
                except Exception as provider_exc:
                    log.warning("Paid escalation to %s failed: %s", pname, provider_exc)
                    continue

        except ImportError:
            log.debug("ProviderManager not available for paid escalation.")
        except Exception as e:
            log.error("Paid escalation error: %s", e)

        return None

    # ── Audit log ─────────────────────────────────────────────────────────────

    def get_decision_log(self, limit: int = 100) -> list[dict]:
        """Return the last *limit* routing decisions (newest first)."""
        return [d.as_dict() for d in reversed(self._decision_log[-limit:])]

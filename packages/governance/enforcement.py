"""packages/governance/enforcement.py — where a verdict becomes an outcome.

The policy engine judges; this module is the only thing allowed to *act* on a
judgement. Keeping the two apart is what makes the engine testable in
isolation and makes "who blocked this?" answerable with one grep.

This is the highest-risk file in the governance package, because it sits in
the path of every agent tool call in a platform running 34 autonomous loops.
Three rules follow from that, and each is enforced structurally rather than by
convention:

**It cannot change behaviour while in observe mode.** :meth:`GovernanceGate.guard`
returns ``allowed=True`` unless ``decision.effective`` is a block, and
``effective`` is hard-wired to ALLOW in observe mode by
:class:`~packages.governance.policy.PolicyDecision`. Enforcement never reads
``decision.decision`` to decide whether to proceed.

**It cannot fail the caller.** Every path is wrapped: a bug in the policy
engine, the audit log, or the approval store produces a logged warning and an
allow, never an exception into ``_dispatch_tool``. A governance layer that can
break tool dispatch is a governance layer that gets reverted.

**It classifies before it judges.** A tool name alone is not the governed
action — ``read_file`` on ``README.md`` and ``read_file`` on ``.env`` are
different actions on the filesystem surface. :func:`classify` extracts the
real subject (path, host, repo, command) so filesystem and network rules
apply to what the agent is actually touching, not to the name of the function
it called.

Cost governance lives here too, because runaway loops are enforced the same
way policy is: :class:`SessionBudget` caps tool calls, spend, tokens, wall
time, recursion depth, and retries per session. These are the concrete
defences against the "runaway loops / token explosions / recursive agents /
infinite retries" failure modes — a policy file cannot stop a loop, a counter
can.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urlparse

from packages.governance.policy import Decision, PolicyDecision, Surface, get_policy_engine

log = logging.getLogger("governance.enforcement")


# ── Tool → surface classification ────────────────────────────────────────────
# Maps a tool name pattern to the surface it acts on and the argument key that
# carries the real subject. Ordered most-specific-first; the first match wins.
_TOOL_SURFACE_RULES: tuple[tuple[tuple[str, ...], Surface, tuple[str, ...]], ...] = (
    (("run_command", "execute_command", "shell", "bash", "sandbox.exec"),
     Surface.SHELL, ("cmd", "command")),
    (("fetch_url", "web_search", "fetch_rss", "youtube_transcript", "http_get", "browse"),
     Surface.NETWORK, ("url", "query")),
    (("read_file", "write_file", "head_file", "apply_diff", "list_files", "file_index",
      "delete_file", "search_code"),
     Surface.FILESYSTEM, ("path", "query")),
    (("github_*", "clone_repo", "git_push", "git_commit", "git_diff"),
     Surface.GITHUB, ("repo_name", "repo_url", "branch")),
    (("docker_*", "sandbox.create", "sandbox.destroy", "build_image", "compose_*"),
     Surface.DOCKER, ("profile", "image")),
    (("db_*", "mongo_*", "sql_*", "query_db"), Surface.DATABASE, ("collection", "query")),
    (("recall_memory", "save_memory", "vector_*", "embed_*"), Surface.MEMORY, ("key",)),
    (("mcp_*", "call_tool"), Surface.MCP, ("name", "server")),
    (("playwright_*", "browser_*", "screenshot"), Surface.BROWSER, ("url",)),
)


def classify(tool: str, args: dict[str, Any] | None = None) -> tuple[Surface, str]:
    """Return the ``(surface, action)`` a tool call really represents.

    The *action* is the thing policy rules are written against: a path for
    filesystem calls, a hostname for network calls, the command line for shell
    calls. Falling back to the tool name keeps the function total — an
    unrecognised tool is still governed on the TOOL surface rather than
    escaping evaluation.
    """
    import fnmatch

    args = args or {}
    name = (tool or "").strip()
    lowered = name.lower()

    for patterns, surface, arg_keys in _TOOL_SURFACE_RULES:
        if not any(fnmatch.fnmatch(lowered, p) for p in patterns):
            continue
        for key in arg_keys:
            value = args.get(key)
            if value in (None, ""):
                continue
            text = str(value)
            if surface is Surface.NETWORK:
                # Rules are written against hosts; a full URL would only ever
                # match a wildcard, silently making domain rules inert.
                host = _host_of(text)
                if host:
                    return surface, host
                continue
            return surface, text
        # A tool on this surface with no usable subject argument still belongs
        # to the surface — e.g. `git_push` with an implicit branch.
        return surface, name
    return Surface.TOOL, name


def _host_of(value: str) -> str:
    """Extract a hostname from a URL, or return a bare host unchanged."""
    text = value.strip()
    if "://" in text:
        try:
            return (urlparse(text).hostname or "").lower()
        except ValueError:
            return ""
    # `web_search` passes a query, not a host — a query with spaces is not one.
    return text.lower() if text and " " not in text and "." in text else ""


# ── Cost / runaway governance ────────────────────────────────────────────────


class BudgetExceeded(Exception):
    """Raised internally when a session exhausts a limit. Never escapes guard()."""


@dataclass
class SessionBudget:
    """Per-session consumption counters and their ceilings.

    Ceilings come from the identity's policy group, so a research agent and a
    coding agent can have different allowances without any code change. A
    ceiling of ``0`` or a missing key means unlimited for that dimension —
    absence must not silently mean "zero allowed", which would block
    everything the moment a limit key is omitted.
    """

    session_id: str
    limits: dict[str, float] = field(default_factory=dict)
    tool_calls: int = 0
    cost_usd: float = 0.0
    tokens: int = 0
    retries: int = 0
    depth: int = 0
    started_at: float = field(default_factory=time.monotonic)

    @property
    def elapsed_s(self) -> float:
        return time.monotonic() - self.started_at

    def check(self) -> str | None:
        """Return the name of the first exhausted limit, or None."""
        checks = (
            ("max_tool_calls", self.tool_calls),
            ("max_cost_usd", self.cost_usd),
            ("max_tokens", self.tokens),
            ("max_retries", self.retries),
            ("max_depth", self.depth),
            ("max_duration_s", self.elapsed_s),
        )
        for key, used in checks:
            ceiling = self.limits.get(key, 0)
            if ceiling and used >= ceiling:
                return f"{key}={used:.4g} reached ceiling {ceiling:.4g}"
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "tool_calls": self.tool_calls,
            "cost_usd": round(self.cost_usd, 6),
            "tokens": self.tokens,
            "retries": self.retries,
            "depth": self.depth,
            "elapsed_s": round(self.elapsed_s, 1),
            "limits": dict(self.limits),
        }


class BudgetTracker:
    """Holds live session budgets, bounded so it cannot leak.

    Sessions end without notice — an agent crashes, a task times out — so
    entries are evicted oldest-first past a cap rather than waiting for a
    close that may never come.
    """

    def __init__(self, capacity: int = 500) -> None:
        self._budgets: dict[str, SessionBudget] = {}
        self._lock = threading.Lock()
        self._capacity = max(1, capacity)

    def get(self, session_id: str, limits: dict[str, float] | None = None) -> SessionBudget:
        with self._lock:
            budget = self._budgets.get(session_id)
            if budget is None:
                budget = SessionBudget(session_id=session_id, limits=dict(limits or {}))
                self._budgets[session_id] = budget
                if len(self._budgets) > self._capacity:
                    oldest = sorted(self._budgets.items(), key=lambda kv: kv[1].started_at)
                    for key, _ in oldest[: len(self._budgets) - self._capacity]:
                        self._budgets.pop(key, None)
            elif limits and not budget.limits:
                budget.limits = dict(limits)
            return budget

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            return [b.to_dict() for b in self._budgets.values()]

    def clear(self) -> None:
        with self._lock:
            self._budgets.clear()


@dataclass
class GuardResult:
    """The outcome of guarding one action."""

    allowed: bool
    decision: PolicyDecision
    approval_id: str | None = None
    budget: SessionBudget | None = None

    @property
    def denial_message(self) -> str:
        """A message safe to hand back to the model as a tool result.

        Names the rule so the agent can adapt (pick a different tool, a
        different path) instead of retrying the same blocked call — the
        difference between a control that shapes behaviour and one that just
        produces an error loop.
        """
        return (
            f"[governance] {self.decision.decision.value}: {self.decision.reason} "
            f"(rule {self.decision.rule_id})"
        )


class GovernanceGate:
    """The one seam through which governed actions pass."""

    def __init__(self, budgets: BudgetTracker | None = None) -> None:
        self._budgets = budgets or BudgetTracker()

    @property
    def budgets(self) -> BudgetTracker:
        return self._budgets

    async def guard(
        self,
        identity: Any,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        surface: Surface | None = None,
        action: str | None = None,
        wait_for_approval: bool = True,
    ) -> GuardResult:
        """Evaluate, gate, and (if required) hold for approval.

        Returns a :class:`GuardResult`; never raises. The caller proceeds when
        ``allowed`` is True and returns :attr:`GuardResult.denial_message` as
        the tool result otherwise.
        """
        try:
            return await self._guard_inner(
                identity, tool, args, surface, action, wait_for_approval
            )
        except Exception as exc:  # noqa: BLE001 - governance must not break dispatch
            log.warning(
                "Governance guard failed for tool %r (%s); allowing and auditing "
                "the failure", tool, exc,
            )
            fallback = PolicyDecision(
                decision=Decision.ALLOW, surface=surface or Surface.TOOL,
                action=action or tool, reason=f"guard error: {exc}",
                rule_id="enforcement.error.fail-open",
            )
            self._audit(identity, tool, args, fallback, status="guard-error", error=str(exc))
            return GuardResult(allowed=True, decision=fallback)

    async def _guard_inner(
        self,
        identity: Any,
        tool: str,
        args: dict[str, Any] | None,
        surface: Surface | None,
        action: str | None,
        wait_for_approval: bool,
    ) -> GuardResult:
        from packages.config import settings

        engine = get_policy_engine()
        resolved_surface, resolved_action = classify(tool, args)
        if surface is not None:
            resolved_surface = surface
        if action is not None:
            resolved_action = action

        decision, resolved_surface, resolved_action = evaluate_call(
            engine, identity, tool, args, surface=resolved_surface, action=resolved_action
        )

        # Budget is checked after policy so an audit row shows the policy
        # verdict too, and enforced before the action so an exhausted session
        # cannot spend more while an approval is pending.
        session_id = str(getattr(identity, "session_id", "") or "anonymous")
        budget = self._budgets.get(session_id, engine.limits_for(identity))
        exhausted = budget.check()
        if exhausted:
            budget_decision = PolicyDecision(
                decision=Decision.DENY, surface=resolved_surface, action=resolved_action,
                reason=f"session budget exhausted: {exhausted}",
                rule_id="budget.session.exhausted", mode=decision.mode, group=decision.group,
            )
            self._audit(identity, tool, args, budget_decision, status="blocked")
            return GuardResult(
                allowed=budget_decision.effective is not Decision.DENY,
                decision=budget_decision, budget=budget,
            )

        budget.tool_calls += 1

        effective = decision.effective
        if effective is Decision.DENY:
            self._audit(identity, tool, args, decision, status="blocked")
            return GuardResult(allowed=False, decision=decision, budget=budget)

        if effective is Decision.REQUIRE_APPROVAL:
            approval_id, approved = await self._await_approval(
                identity, tool, args, decision, wait_for_approval, settings
            )
            self._audit(
                identity, tool, args, decision,
                status="approved" if approved else "blocked", approval_id=approval_id,
            )
            return GuardResult(
                allowed=approved, decision=decision, approval_id=approval_id, budget=budget
            )

        # Observe mode records what *would* have been blocked. This is the
        # signal an operator uses to decide when enforce is safe; without it,
        # turning enforcement on is a guess.
        if decision.would_block:
            self._audit(identity, tool, args, decision, status="observed-would-block")
        return GuardResult(allowed=True, decision=decision, budget=budget)

    async def _await_approval(
        self,
        identity: Any,
        tool: str,
        args: dict[str, Any] | None,
        decision: PolicyDecision,
        wait_for_approval: bool,
        settings: Any,
    ) -> tuple[str | None, bool]:
        """Create an approval request and wait for its verdict."""
        from packages.governance.approvals import ApprovalStatus, get_approval_store

        if settings.governance_auto_approve:
            # Configured, audited, off-by-default. Exists so local development
            # is not blocked on a dashboard that is not running.
            log.info("Auto-approving %s (GOVERNANCE_AUTO_APPROVE=true)", decision.action)
            return "auto-approve", True

        store = get_approval_store()
        request = store.create(
            agent_id=str(getattr(identity, "agent_id", "agent:unknown")),
            owner=str(getattr(identity, "owner", "system")),
            session_id=str(getattr(identity, "session_id", "")),
            surface=decision.surface.value,
            action=decision.action,
            reason=decision.reason,
            rule_id=decision.rule_id,
            arguments=args or {},
            task_id=getattr(identity, "task_id", None),
            repo=getattr(identity, "repo", None),
            branch=getattr(identity, "branch", None),
            ttl_s=settings.governance_approval_ttl_s,
        )
        if not wait_for_approval:
            return request.approval_id, False
        status = await store.wait(request.approval_id)
        return request.approval_id, status is ApprovalStatus.APPROVED

    def record_result(
        self,
        identity: Any,
        tool: str,
        args: dict[str, Any] | None,
        decision: PolicyDecision,
        *,
        result: Any = "",
        error: str | None = None,
        duration_ms: float = 0.0,
        cost_usd: float = 0.0,
        tokens: int = 0,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ) -> None:
        """Audit the *outcome* of an allowed action and charge its cost.

        Split from :meth:`guard` because the decision and the outcome happen
        at different times: guarding is before the call, cost and duration are
        only known after. Charging here (rather than at guard time) is what
        makes ``max_cost_usd`` reflect real spend instead of an estimate.
        """
        try:
            session_id = str(getattr(identity, "session_id", "") or "anonymous")
            budget = self._budgets.get(session_id)
            budget.cost_usd += max(0.0, float(cost_usd or 0.0))
            budget.tokens += max(0, int(tokens or 0))
            if error:
                budget.retries += 1
            self._audit(
                identity, tool, args, decision,
                status="error" if error else "ok",
                result=str(result) if result is not None else "",
                error=error, duration_ms=duration_ms, cost_usd=cost_usd,
                tokens=tokens, llm_provider=llm_provider, llm_model=llm_model,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Governance result recording failed for %r: %s", tool, exc)

    @staticmethod
    def _audit(
        identity: Any,
        tool: str,
        args: dict[str, Any] | None,
        decision: PolicyDecision,
        *,
        status: str,
        result: str = "",
        error: str | None = None,
        approval_id: str | None = None,
        duration_ms: float = 0.0,
        cost_usd: float = 0.0,
        tokens: int = 0,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ) -> None:
        from packages.governance.audit import events_from_identity, record_event

        fields = events_from_identity(identity)
        # The identity carries the group the caller *requested*; the decision
        # carries the one that actually governed. They differ whenever the
        # requested group does not exist (an identity defaults its group to its
        # own agent id, which usually has no group of that name and resolves to
        # `default`). Recording the requested one would make an audit row
        # disagree with its own rule_id — so the effective group wins.
        fields["policy_group"] = decision.group
        record_event(
            **fields,
            surface=decision.surface.value,
            action=decision.action,
            tool=tool,
            arguments=args or {},
            decision=decision.decision.value,
            effective=decision.effective.value,
            reason=decision.reason,
            rule_id=decision.rule_id,
            mode=decision.mode.value,
            result_status=status,
            result=result,
            error=error,
            approval_id=approval_id,
            duration_ms=duration_ms,
            cost_usd=cost_usd,
            total_tokens=tokens,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )


# Restrictiveness ordering. Used to combine the verdicts from the two
# surfaces a single tool call belongs to; the stricter one always wins, so
# adding a second evaluation can only ever tighten a decision, never loosen
# one. That property is what makes the dual evaluation safe to add.
_RESTRICTIVENESS: dict[Decision, int] = {
    Decision.ALLOW: 0,
    Decision.REQUIRE_APPROVAL: 1,
    Decision.DENY: 2,
}


def evaluate_call(
    engine: Any,
    identity: Any,
    tool: str,
    args: dict[str, Any] | None = None,
    *,
    surface: Surface | None = None,
    action: str | None = None,
) -> tuple[PolicyDecision, Surface, str]:
    """Judge one tool call, exactly as :meth:`GovernanceGate.guard` would.

    Extracted so the ``/api/governance/policy/simulate`` endpoint and the live
    enforcement path share one implementation. That is not tidiness — a
    simulator that evaluates differently from the enforcer actively misleads
    the operator using it to decide whether ``mode: enforce`` is safe, which
    is the one job simulation has.

    Pure: evaluates and returns, charging no budget and taking no action.

    A tool call is two facts, not one: *which tool* was invoked and *what it
    touches*. ``write_file`` on ``src/app.py`` is a TOOL fact (``write_file``)
    and a FILESYSTEM fact (``src/app.py``), and a policy author writing
    ``tool.allow: [read_file, ...]`` reasonably expects ``write_file`` to be
    refused by that list. Judging only the subject-bearing surface would
    silently ignore the tool allow-list for every tool that carries a path or
    a URL — i.e. for nearly all of them. Both are evaluated and the stricter
    verdict wins, so the second evaluation can only ever tighten.
    """
    classified_surface, classified_action = classify(tool, args)
    resolved_surface = surface or classified_surface
    resolved_action = action if action is not None else classified_action

    context: dict[str, Any] = {}
    if resolved_surface is Surface.FILESYSTEM:
        context["mode"] = "write" if _is_write_tool(tool) else "read"

    decision = engine.evaluate(resolved_surface, resolved_action, identity, context)
    if resolved_surface is not Surface.TOOL and tool:
        decision = _more_restrictive(decision, engine.evaluate(Surface.TOOL, tool, identity))
    return decision, resolved_surface, resolved_action


def _more_restrictive(first: PolicyDecision, second: PolicyDecision) -> PolicyDecision:
    """Return whichever decision blocks harder, preferring *first* on a tie.

    Ties keep the subject-surface decision because its ``reason`` names the
    concrete thing that was touched (the path, the host), which is more
    useful in an audit row than the tool name the caller already knows.
    """
    return second if _RESTRICTIVENESS[second.decision] > _RESTRICTIVENESS[first.decision] else first


def _is_write_tool(tool: str) -> bool:
    """True when *tool* mutates the filesystem.

    Drives which filesystem allow-list applies (``read`` vs ``write``), so a
    group can grant broad read and narrow write — the read-only/read-write
    mount distinction, expressed in policy.
    """
    lowered = (tool or "").lower()
    return any(
        marker in lowered
        for marker in ("write", "apply_diff", "delete", "remove", "mkdir", "move", "rename")
    )


_GATE: GovernanceGate | None = None
_GATE_LOCK = threading.Lock()


def get_gate() -> GovernanceGate:
    global _GATE
    with _GATE_LOCK:
        if _GATE is None:
            _GATE = GovernanceGate()
        return _GATE


def reset_gate(gate: GovernanceGate | None = None) -> None:
    """Replace the process-wide gate. Tests only."""
    global _GATE
    with _GATE_LOCK:
        _GATE = gate


async def guard_tool_call(
    identity: Any,
    tool: str,
    args: dict[str, Any] | None = None,
    **kwargs: Any,
) -> GuardResult:
    """Module-level convenience used by call sites that hold no gate."""
    return await get_gate().guard(identity, tool, args, **kwargs)


def governance_enabled() -> bool:
    """True when the governance layer should run at all.

    A single global off switch matters more than it looks: it is what lets an
    operator disable a misbehaving control instantly without a deploy, which
    is the difference between a security layer that survives an incident and
    one that gets ripped out during it.
    """
    try:
        from packages.config import settings

        return settings.governance_enabled
    except Exception:  # noqa: BLE001
        return False


def resolve_identity_for_runner(runner: Any, **context: Any) -> Any:
    """Best-effort identity for an ``AgentRunner``-like object.

    Wiring governance into existing call sites must not require threading an
    identity through every layer first, so this derives one from whatever the
    runner already exposes and caches it on the runner for the rest of the
    run — keeping ``session_id`` stable, which is what makes per-session
    budgets and audit correlation work.
    """
    from packages.governance.identity import resolve_identity

    cached = getattr(runner, "_governance_identity", None)
    if cached is not None:
        return cached.with_context(**context) if context else cached

    identity = resolve_identity(
        agent_name=getattr(runner, "agent_name", None) or getattr(runner, "name", None),
        owner=getattr(runner, "user_email", None) or getattr(runner, "owner", None),
        runtime=getattr(runner, "runtime_id", None),
        task_id=getattr(runner, "task_id", None),
        repo=getattr(runner, "repo", None),
        branch=getattr(runner, "branch", None),
        **context,
    )
    try:
        runner._governance_identity = identity  # noqa: SLF001 - cache on the runner
    except Exception as exc:  # noqa: BLE001 - a slotted/frozen runner is fine
        # Not fatal, but not silent either: without the cache every call gets a
        # fresh session_id, which splits one run's budget and audit rows across
        # many sessions. Worth a line in the log when it happens.
        log.debug(
            "Could not cache identity on %s (%s); per-session budget and audit "
            "correlation will be per-call for this runner",
            type(runner).__name__, type(exc).__name__,
        )
    return identity

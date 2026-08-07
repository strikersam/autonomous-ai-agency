"""Governance on runtime dispatch — the last coverage gap.

`AgentRunner._dispatch_tool` and the MCP HTTP surface were governed, but the
choice of *executor* was not. An agent restricted from writing files in-process
could hand the same work to a runtime adapter that writes files in its own
container — the restriction was real but routable around.

Pinned here:
  * a dispatch is evaluated and audited on the `runtime` surface,
  * `enforce` mode blocks and the adapter never executes,
  * `observe` mode changes nothing,
  * a blocked dispatch returns a failed TaskResult rather than raising, and
    carries a structured reason callers can branch on,
  * the governance layer failing cannot take out task execution.
"""
from __future__ import annotations

from typing import Any, Iterator

import pytest

from packages.governance.audit import AuditLog, reset_audit_log
from packages.governance.policy import PolicyEngine, Surface, reset_policy_engine
from runtimes.base import (
    IntegrationMode,
    RuntimeAdapter,
    RuntimeCapability,
    RuntimeHealth,
    RuntimeExecutionError,
    RuntimeTier,
    RuntimeUnavailableError,
    TaskResult,
    TaskSpec,
)
from runtimes.routing import (
    RoutingDecision,
    RuntimeRoutingPolicyEngine,
    _governance_check,
)


class StubAdapter(RuntimeAdapter):
    RUNTIME_ID = "stub_runtime"
    DISPLAY_NAME = "Stub"
    DESCRIPTION = "test double"
    TIER = RuntimeTier.FIRST_CLASS
    INTEGRATION_MODE = IntegrationMode.NATIVE
    DOCS_URL = ""
    # `code_generation` requires BOTH of these in TASK_CAPABILITY_MAP, which is
    # also the realistic shape for a runtime that writes code.
    CAPABILITIES = frozenset({
        RuntimeCapability.CODE_GENERATION,
        RuntimeCapability.FILE_READ_WRITE,
    })

    def __init__(self) -> None:
        super().__init__({})
        self.executed: list[str] = []

    async def health_check(self) -> RuntimeHealth:
        return RuntimeHealth(runtime_id=self.RUNTIME_ID, available=True)

    async def execute(self, spec: TaskSpec) -> TaskResult:
        self.executed.append(spec.task_id)
        return TaskResult(
            runtime_id=self.RUNTIME_ID, task_id=spec.task_id,
            success=True, output="done",
        )


@pytest.fixture(autouse=True)
def isolated_governance() -> Iterator[None]:
    reset_audit_log(AuditLog(capacity=100))
    yield
    reset_audit_log(None)
    reset_policy_engine(None)


def _engine(mode: str, **document: Any) -> PolicyEngine:
    engine = PolicyEngine({"mode": mode, **document})
    reset_policy_engine(engine)
    return engine


def _decision(adapter: RuntimeAdapter) -> RoutingDecision:
    """A RoutingDecision matching what route_and_execute would have built."""
    return RoutingDecision(
        task_id="t1", task_type="general", selected_runtime_id=adapter.RUNTIME_ID,
        model_used=None, provider_used=None, reason="test",
    )


def _spec(**kwargs: Any) -> TaskSpec:
    return TaskSpec(
        task_id=kwargs.pop("task_id", "task_1"),
        instruction=kwargs.pop("instruction", "do the thing"),
        **kwargs,
    )


# ── The seam itself ──────────────────────────────────────────────────────────


def test_blocked_dispatch_returns_a_failed_result_not_an_exception():
    """`route_and_execute` callers handle failure; they do not expect a new
    exception type, so blocking must not introduce one."""
    _engine("enforce", baseline={"runtime": {"deny": ["stub_runtime"]}})
    adapter = StubAdapter()
    decision = _decision(adapter)
    result = _governance_check(_spec(), adapter, decision)
    assert isinstance(result, TaskResult)
    assert result.success is False
    assert "[governance] denied" in result.output


def test_blocked_dispatch_carries_a_structured_reason():
    """So callers can branch without string-matching the output.

    Regression: an earlier draft passed `error=` to TaskResult, which has no
    such field — a TypeError that `compileall` cannot catch.
    """
    _engine("enforce", baseline={"runtime": {"deny": ["stub_runtime"]}})
    adapter = StubAdapter()
    decision = _decision(adapter)
    result = _governance_check(_spec(), adapter, decision)
    assert result.metadata["governance_blocked"] is True
    assert result.metadata["governance_rule_id"].startswith("baseline.runtime.deny")
    assert "blocked by governance" in decision.reason


def test_allowed_dispatch_returns_none_so_execution_proceeds():
    _engine("enforce")
    adapter = StubAdapter()
    decision = _decision(adapter)
    assert _governance_check(_spec(), adapter, decision) is None


def test_observe_mode_never_blocks_a_dispatch():
    """Same Golden Rule guarantee as every other governance seam."""
    _engine("observe", baseline={"runtime": {"deny": ["*"]}})
    adapter = StubAdapter()
    decision = _decision(adapter)
    assert _governance_check(_spec(), adapter, decision) is None


# ── End-to-end through the routing engine ────────────────────────────────────


def _routing_engine(adapter: RuntimeAdapter) -> RuntimeRoutingPolicyEngine:
    """A routing engine wired to one healthy stub adapter."""
    from runtimes.health import RuntimeHealthService
    from runtimes.registry import RuntimeCapabilityRegistry

    registry = RuntimeCapabilityRegistry()
    registry.register(adapter)
    health = RuntimeHealthService(registry)
    # Mark it healthy directly: _pick_runtime consults cached health, and this
    # test is about the governance gate, not the health poller.
    health._cache[adapter.RUNTIME_ID] = RuntimeHealth(
        runtime_id=adapter.RUNTIME_ID, available=True
    )
    return RuntimeRoutingPolicyEngine(registry=registry, health_service=health)


async def test_enforce_mode_stops_the_adapter_from_executing():
    """The decisive test: a blocked dispatch must never reach the adapter."""
    _engine("enforce", baseline={"runtime": {"deny": ["stub_runtime"]}})
    adapter = StubAdapter()
    engine = _routing_engine(adapter)

    result, decision = await engine.route_and_execute(_spec(task_type="code_generation"))
    assert result.success is False
    assert adapter.executed == [], "the adapter must never have run"
    assert decision.selected_runtime_id == "stub_runtime"


async def test_observe_mode_lets_the_adapter_run():
    _engine("observe", baseline={"runtime": {"deny": ["stub_runtime"]}})
    adapter = StubAdapter()
    engine = _routing_engine(adapter)

    result, _decision = await engine.route_and_execute(_spec(task_type="code_generation"))
    assert result.success is True
    assert adapter.executed == ["task_1"]


# ── Policy expressiveness ────────────────────────────────────────────────────


def test_a_group_allow_list_restricts_which_runtimes_an_agent_may_use():
    """The point of the surface: a research agent should not be able to
    dispatch to a runtime whose job is editing and committing code."""
    engine = _engine(
        "enforce",
        groups={"research": {"runtime": {"allow": ["internal_agent"]}}},
    )
    from packages.governance.identity import resolve_identity

    identity = resolve_identity(agent_name="x", policy_group="research")
    from packages.governance.policy import Decision

    assert engine.evaluate(Surface.RUNTIME, "internal_agent", identity).decision is Decision.ALLOW
    assert engine.evaluate(Surface.RUNTIME, "docker_agent", identity).decision is Decision.DENY


def test_runtime_is_a_distinct_surface_from_docker():
    """Sandbox lifecycle and executor choice are different decisions."""
    assert Surface.RUNTIME.value == "runtime"
    assert Surface.RUNTIME is not Surface.DOCKER


# ── Auditing ─────────────────────────────────────────────────────────────────


def test_dispatch_is_audited_with_identity_from_the_task_context():
    from packages.governance.audit import get_audit_log
    _engine("observe")
    adapter = StubAdapter()
    decision = _decision(adapter)
    _governance_check(
        _spec(context={"agent_name": "Research Bot", "agent_owner": "sam@example.com"}),
        adapter, decision,
    )
    event = get_audit_log().recent(1)[0]
    assert event["agent_id"] == "agent:research-bot"
    assert event["owner"] == "sam@example.com"
    assert event["surface"] == "runtime"
    assert event["action"] == "stub_runtime"
    assert event["tool"] == "runtime.dispatch"


def test_a_task_with_no_agent_lands_on_the_least_privileged_group():
    from packages.governance.audit import get_audit_log
    _engine("observe")
    adapter = StubAdapter()
    decision = _decision(adapter)
    _governance_check(_spec(), adapter, decision)
    event = get_audit_log().recent(1)[0]
    assert event["agent_id"] == "agent:unknown"
    assert event["policy_group"] == "default"


def test_the_instruction_body_is_never_stored_in_the_audit_row():
    """Truncation would not protect a secret in the first 200 characters.

    The instruction is free text authored by an agent or a user. `task_id` is
    the join key to the full task record, so the audit row only needs the
    dispatch's shape — not its content.
    """
    from packages.governance.audit import get_audit_log
    _engine("observe")
    adapter = StubAdapter()
    decision = _decision(adapter)
    secret = "my password is hunter2 " + "x" * 50_000
    _governance_check(_spec(instruction=secret), adapter, decision)
    event = get_audit_log().recent(1)[0]
    assert "instruction" not in event["arguments"], "the body must not be stored"
    assert event["arguments"]["instruction_chars"] == len(secret)
    assert event["arguments"]["task_type"] == "general"
    assert "hunter2" not in str(event)


# ── Degradation ──────────────────────────────────────────────────────────────


def test_a_broken_governance_layer_allows_the_dispatch(monkeypatch):
    """A control that can take out task execution is a worse liability than
    the risk it mitigates."""
    _engine("enforce", baseline={"runtime": {"deny": ["stub_runtime"]}})

    def exploding() -> Any:
        raise RuntimeError("engine exploded")

    monkeypatch.setattr("packages.governance.policy.get_policy_engine", exploding)
    adapter = StubAdapter()
    decision = _decision(adapter)
    assert _governance_check(_spec(), adapter, decision) is None


def test_governance_disabled_skips_the_check_entirely(monkeypatch):
    from packages.config import settings
    monkeypatch.setattr(settings, "governance_enabled_raw", "false", raising=False)
    _engine("enforce", baseline={"runtime": {"deny": ["stub_runtime"]}})
    adapter = StubAdapter()
    decision = _decision(adapter)
    assert _governance_check(_spec(), adapter, decision) is None


# ── Fallback dispatch (regression) ───────────────────────────────────────────


class SecondAdapter(StubAdapter):
    """A second runtime, used as a fallback target."""

    RUNTIME_ID = "fallback_runtime"
    DISPLAY_NAME = "Fallback"


async def test_a_denied_fallback_runtime_is_never_executed():
    """Regression: checking only the primary left the policy evaporating on the
    error path.

    An agent allowed to use the primary runtime could reach a *denied* fallback
    simply by having the permitted one fail — the control held on the happy
    path and vanished on the one that matters.
    """
    from runtimes.health import RuntimeHealthService
    from runtimes.registry import RuntimeCapabilityRegistry

    _engine("enforce", baseline={"runtime": {"deny": ["fallback_runtime"]}})

    primary = StubAdapter()
    fallback = SecondAdapter()

    async def failing_execute(spec: TaskSpec) -> TaskResult:
        # Must be an exception the primary path actually catches, or it
        # escapes and the fallback loop — the path under test — never runs.
        raise RuntimeExecutionError(primary.RUNTIME_ID, "primary blew up", spec.task_id)

    primary.execute = failing_execute  # type: ignore[method-assign]

    registry = RuntimeCapabilityRegistry()
    registry.register(primary)
    registry.register(fallback)
    health = RuntimeHealthService(registry)
    for adapter in (primary, fallback):
        health._cache[adapter.RUNTIME_ID] = RuntimeHealth(
            runtime_id=adapter.RUNTIME_ID, available=True
        )

    engine = RuntimeRoutingPolicyEngine(registry=registry, health_service=health)
    # Pin the primary: adapters sort alphabetically within a tier, so without
    # this `fallback_runtime` is selected as the primary and the fallback path
    # is never exercised.
    engine.update_policy(
        preferred_runtime_id="stub_runtime",
        fallback_runtime_ids=["fallback_runtime"],
    )

    # Primary is permitted and fails; the only fallback is denied and skipped,
    # so the chain is exhausted and the engine raises its normal
    # "all runtimes failed" error — not a governance error.
    with pytest.raises(RuntimeUnavailableError):
        await engine.route_and_execute(_spec(task_type="code_generation"))

    assert fallback.executed == [], "the denied fallback must never have run"


async def test_an_allowed_fallback_still_runs():
    """The fix must not break legitimate fallback."""
    from runtimes.health import RuntimeHealthService
    from runtimes.registry import RuntimeCapabilityRegistry

    _engine("enforce")   # nothing denied

    primary = StubAdapter()
    fallback = SecondAdapter()

    async def failing_execute(spec: TaskSpec) -> TaskResult:
        # Must be an exception the primary path actually catches, or it
        # escapes and the fallback loop — the path under test — never runs.
        raise RuntimeExecutionError(primary.RUNTIME_ID, "primary blew up", spec.task_id)

    primary.execute = failing_execute  # type: ignore[method-assign]

    registry = RuntimeCapabilityRegistry()
    registry.register(primary)
    registry.register(fallback)
    health = RuntimeHealthService(registry)
    for adapter in (primary, fallback):
        health._cache[adapter.RUNTIME_ID] = RuntimeHealth(
            runtime_id=adapter.RUNTIME_ID, available=True
        )

    engine = RuntimeRoutingPolicyEngine(registry=registry, health_service=health)
    engine.update_policy(
        preferred_runtime_id="stub_runtime",
        fallback_runtime_ids=["fallback_runtime"],
    )

    result, decision = await engine.route_and_execute(_spec(task_type="code_generation"))
    assert result.success is True
    assert fallback.executed == ["task_1"]
    assert decision.fallback_runtime_id == "fallback_runtime"

"""The executor loop must not have a side door around the governance gate.

`execute_skill`, `recommend_skills`, and `spawn_subagent` were dispatched by
calling their implementations directly from ``_execute_step``, skipping
``_run_tool`` -> ``_dispatch_tool``. Since ``_dispatch_tool`` is the only place
the policy gate runs, skill execution and sub-agent spawning could be neither
denied nor audited — the two capabilities where that matters most, because one
runs arbitrary registered code and the other creates a whole new agent.

These tests pin the routing behaviourally: a deny rule must actually stop the
call, and (per the Golden Rule, CLAUDE.md §0) the ungoverned path must return
exactly what it returned before.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from agent.loop import AgentRunner
from packages.governance.approvals import ApprovalStore
from packages.governance.audit import AuditLog
from packages.governance.policy import PolicyEngine, reset_policy_engine


@pytest.fixture(autouse=True)
def isolated_governance():
    """Give every test its own engine, audit log, and approval store."""
    from packages.governance import approvals as approvals_module
    from packages.governance import audit as audit_module

    audit_module.reset_audit_log(AuditLog(capacity=100))
    approvals_module.reset_approval_store(ApprovalStore())
    yield
    reset_policy_engine(None)
    audit_module.reset_audit_log(None)
    approvals_module.reset_approval_store(None)


def _enforce(**document: Any) -> None:
    """Install an enforcing policy engine built from *document*."""
    reset_policy_engine(PolicyEngine({"mode": "enforce", **document}))


@pytest.fixture
def governance_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn the global governance switch on for the duration of a test."""
    monkeypatch.setattr(
        "packages.governance.enforcement.governance_enabled", lambda: True
    )


def _runner(tmp_path: Path) -> AgentRunner:
    """An AgentRunner rooted in an empty workspace under *tmp_path*."""
    root = tmp_path / "repo"
    root.mkdir(exist_ok=True)
    return AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)


def _drive(runner: AgentRunner, tool: str, args: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Run one ``_execute_step`` where the executor picks *tool*, then finishes."""
    calls = iter([
        {"tool": tool, "args": args},
        {"tool": "finish", "args": {"reason": "done"}},
    ])

    async def fake_chat_json(self_arg: object, model: str, messages: list) -> dict[str, Any]:
        """Replay the scripted tool selections instead of calling an LLM."""
        return next(calls)

    monkeypatch.setattr(AgentRunner, "_chat_json", fake_chat_json)
    return asyncio.run(
        runner._execute_step(
            goal="do the thing",
            step={"id": 1, "description": "delegate", "files": [], "type": "analyze"},
            requested_model=None,
        )
    )


def _observations(result: dict[str, Any], tool: str) -> list[Any]:
    """Every observation *result* recorded for *tool*, in order."""
    return [o["result"] for o in result["observations"] if o.get("tool") == tool]


# ── execute_skill ────────────────────────────────────────────────────────────


def test_a_denied_skill_never_executes(tmp_path, monkeypatch, governance_on):
    """The regression: the deny rule used to be evaluated on a path never taken."""
    _enforce(baseline={"tool": {"deny": ["execute_skill"]}})
    executed: list[str] = []
    monkeypatch.setattr(
        AgentRunner, "_execute_skill_tool",
        staticmethod(lambda args: executed.append(str(args)) or "ran"),
    )

    result = _drive(_runner(tmp_path), "execute_skill", {"skill_id": "deploy"}, monkeypatch)

    assert executed == [], "a denied skill must not run"
    observed = _observations(result, "execute_skill")
    assert observed and "deny" in str(observed[0])
    assert "baseline.tool.deny" in str(observed[0]), "names the rule that fired"


def test_an_allowed_skill_still_runs_and_is_audited(tmp_path, monkeypatch, governance_on):
    """Governance must not silently swallow the calls it permits."""
    _enforce(baseline={"tool": {"deny": ["some_other_tool"]}})
    monkeypatch.setattr(
        AgentRunner, "_execute_skill_tool", staticmethod(lambda args: "skill output")
    )

    result = _drive(_runner(tmp_path), "execute_skill", {"skill_id": "lint"}, monkeypatch)

    assert _observations(result, "execute_skill") == ["skill output"]
    from packages.governance.audit import get_audit_log
    assert any(
        (e.get("tool") if isinstance(e, dict) else getattr(e, "tool", None)) == "execute_skill"
        for e in get_audit_log().recent(limit=50)
    ), "an allowed call must still leave an audit record"


def test_skill_result_is_unchanged_when_governance_is_off(tmp_path, monkeypatch):
    """Golden Rule: routing through the seam changes nothing with the gate off."""
    monkeypatch.setattr(
        "packages.governance.enforcement.governance_enabled", lambda: False
    )
    monkeypatch.setattr(
        AgentRunner, "_execute_skill_tool", staticmethod(lambda args: "skill output")
    )

    result = _drive(_runner(tmp_path), "execute_skill", {"skill_id": "lint"}, monkeypatch)

    assert _observations(result, "execute_skill") == ["skill output"]


# ── recommend_skills ─────────────────────────────────────────────────────────


def test_recommend_skills_is_governed_too(tmp_path, monkeypatch, governance_on):
    """The sibling of execute_skill had the same bypass."""
    _enforce(baseline={"tool": {"deny": ["recommend_skills"]}})
    called: list[str] = []
    monkeypatch.setattr(
        AgentRunner, "_recommend_skills_tool",
        staticmethod(lambda args: called.append("x") or "listed"),
    )

    result = _drive(_runner(tmp_path), "recommend_skills", {"query": "deploy"}, monkeypatch)

    assert called == []
    assert "deny" in str(_observations(result, "recommend_skills")[0])


# ── spawn_subagent ───────────────────────────────────────────────────────────


def test_a_denied_spawn_never_creates_a_child_runner(tmp_path, monkeypatch, governance_on):
    """Spawning is the highest-privilege tool in the loop; it must be refusable."""
    _enforce(baseline={"tool": {"deny": ["spawn_subagent"]}})
    spawned: list[str] = []

    async def fake_spawn(self_arg: object, **kwargs: Any) -> dict[str, Any]:
        """Stand in for the real child-runner spawn."""
        spawned.append("spawned")
        return {"summary": "child ran"}

    monkeypatch.setattr(AgentRunner, "_spawn_subagent", fake_spawn)

    result = _drive(
        _runner(tmp_path), "spawn_subagent", {"instruction": "do it"}, monkeypatch
    )

    assert spawned == [], "a denied spawn must not create a child agent"
    assert "deny" in str(_observations(result, "spawn_subagent")[0])


def test_a_string_denial_does_not_break_the_dict_shaped_call_site(
    tmp_path, monkeypatch, governance_on
):
    """A denial arrives as a string where a run() dict used to be guaranteed.

    The old call site did ``sub_result.get("summary", ...)`` unconditionally,
    so a denial would have raised AttributeError inside the executor loop.
    """
    _enforce(baseline={"tool": {"deny": ["spawn_subagent"]}})
    monkeypatch.setattr(
        AgentRunner, "_spawn_subagent",
        lambda self_arg, **kw: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    result = _drive(
        _runner(tmp_path), "spawn_subagent", {"instruction": "do it"}, monkeypatch
    )

    observed = _observations(result, "spawn_subagent")[0]
    assert isinstance(observed, str), "a denial must not be a dict"
    assert "deny" in observed and "baseline.tool.deny" in observed
    # _run_tool converts any exception to "[tool error: …]", so without this
    # the test would still pass if the deny rule stopped firing and the
    # patched implementation raised instead.
    assert "AssertionError" not in observed, "the implementation must not have run"


def test_an_allowed_spawn_still_returns_the_child_result(tmp_path, monkeypatch, governance_on):
    """Golden Rule: the dict shape and the summary fallback are preserved."""
    _enforce(baseline={"tool": {"deny": ["some_other_tool"]}})

    async def fake_spawn(self_arg: object, **kwargs: Any) -> dict[str, Any]:
        """Stand in for the real child-runner spawn."""
        return {"summary": "child ran", "steps": []}

    monkeypatch.setattr(AgentRunner, "_spawn_subagent", fake_spawn)

    result = _drive(
        _runner(tmp_path), "spawn_subagent", {"instruction": "do it"}, monkeypatch
    )

    assert _observations(result, "spawn_subagent") == ["child ran"]


# ── Every advertised tool must parse ─────────────────────────────────────────


def test_every_advertised_tool_name_parses_as_a_tool_call():
    """The defect that made the branches above dead code in the first place.

    ``harness_enrichment`` tells the executor these tools exist, but
    ``ToolCall`` rejected six of them, so selecting one raised a validation
    error that the loop counts as a tool-selection failure — four in a row and
    the step fails. Web Reach was unreachable this way despite being the
    documented mechanism for self-healing lookups (CLAUDE.md §6).
    """
    from pydantic import ValidationError

    from agent.harness_enrichment import ALWAYS_TOOLS
    from agent.models import ToolCall

    rejected = []
    for name, _desc in ALWAYS_TOOLS:
        try:
            ToolCall(tool=name, args={})
        except ValidationError:
            rejected.append(name)
    assert rejected == [], f"advertised but unparseable: {rejected}"


def test_registry_tools_parse_without_being_listed_statically(monkeypatch):
    """Registering + advertising a tool must be enough; no third edit here.

    Deliberately exercises the production singleton — that is the registry
    ``ToolCall`` actually consults — but resets it first so the result cannot
    depend on whether an earlier test already initialised it.
    """
    from agent import capability_registry
    from agent.capability_registry import get_tool_registry
    from agent.models import ToolCall

    monkeypatch.setattr(capability_registry, "_tool_registry", None)
    registry = get_tool_registry()
    assert registry is not None
    names = [t.name for t in registry.list_all()]
    assert "web_search" in names, "fixture assumption: Web Reach is registered"
    for name in names:
        assert ToolCall(tool=name, args={}).tool == name


def test_an_unregistered_tool_name_is_still_rejected():
    """Widening validation must not turn it off."""
    from pydantic import ValidationError

    from agent.models import ToolCall

    with pytest.raises(ValidationError):
        ToolCall(tool="rm_rf_everything", args={})


def test_a_subagent_error_is_not_reported_to_the_model_as_success(
    tmp_path, monkeypatch, governance_on
):
    """`_spawn_subagent` returns error dicts with no `summary` key.

    Defaulting the scratchpad note to "subagent completed" told the executor
    the delegation had worked — and that text is injected into the next
    tool-selection prompt, so the model plans its following step on a false
    premise. Both reachable error paths (empty instruction, depth limit) hit it.
    """
    _enforce(baseline={"tool": {"deny": ["some_other_tool"]}})

    async def fake_spawn(self_arg: object, **kwargs: Any) -> dict[str, Any]:
        """Stand in for the real child-runner spawn."""
        return {"error": "spawn_subagent depth limit reached (5)", "depth": 6}

    monkeypatch.setattr(AgentRunner, "_spawn_subagent", fake_spawn)

    result = _drive(
        _runner(tmp_path), "spawn_subagent", {"instruction": "do it"}, monkeypatch
    )

    observed = _observations(result, "spawn_subagent")[0]
    assert "depth limit reached" in observed
    assert "subagent completed" not in observed


def test_model_supplied_keys_are_not_splatted_into_spawn_subagent(tmp_path, monkeypatch):
    """`args` is model-generated JSON; only named parameters may reach the call.

    `_spawn_subagent` absorbs unknown keys through `**kwargs`, so a splat is
    harmless today — but any parameter it gains later would silently become
    model-controllable. This is the highest-privilege tool in the loop.
    """
    runner = _runner(tmp_path)
    seen: list[dict[str, Any]] = []

    async def fake_spawn(self_arg: object, **kwargs: Any) -> dict[str, Any]:
        """Stand in for the real child-runner spawn."""
        seen.append(kwargs)
        return {"summary": "ok"}

    monkeypatch.setattr(AgentRunner, "_spawn_subagent", fake_spawn)

    asyncio.run(
        runner._dispatch_tool_unguarded(
            "spawn_subagent",
            {"instruction": "hi", "max_steps": 2, "workspace_root": "/etc", "token": "x"},
        )
    )

    assert seen == [{"instruction": "hi", "max_steps": 2, "role": ""}]


def test_spawn_subagent_aliases_still_reach_the_implementation(tmp_path, monkeypatch):
    """The executor may emit `command`/`task`/`text` instead of `instruction`."""
    runner = _runner(tmp_path)
    seen: list[dict[str, Any]] = []

    async def fake_spawn(self_arg: object, **kwargs: Any) -> dict[str, Any]:
        """Stand in for the real child-runner spawn."""
        seen.append(kwargs)
        return {"summary": "ok"}

    monkeypatch.setattr(AgentRunner, "_spawn_subagent", fake_spawn)

    asyncio.run(
        runner._dispatch_tool_unguarded("spawn_subagent", {"command": "do the thing"})
    )

    assert seen[0]["command"] == "do the thing"
    assert seen[0]["instruction"] == "", "empty so the alias fallback engages"


def test_spawn_subagent_is_reachable_through_the_dispatch_seam(tmp_path, monkeypatch):
    """Routing is pointless if the seam cannot dispatch the tool.

    Without a ``spawn_subagent`` branch in ``_dispatch_tool_unguarded`` the
    governed call would fall through to the unknown-tool path and silently
    stop spawning anything.
    """
    runner = _runner(tmp_path)
    seen: list[dict[str, Any]] = []

    async def fake_spawn(self_arg: object, **kwargs: Any) -> dict[str, Any]:
        """Stand in for the real child-runner spawn."""
        seen.append(kwargs)
        return {"summary": "ok"}

    monkeypatch.setattr(AgentRunner, "_spawn_subagent", fake_spawn)

    out = asyncio.run(
        runner._dispatch_tool_unguarded("spawn_subagent", {"instruction": "hi", "max_steps": 2})
    )

    assert out == {"summary": "ok"}
    assert seen == [{"instruction": "hi", "max_steps": 2, "role": ""}]

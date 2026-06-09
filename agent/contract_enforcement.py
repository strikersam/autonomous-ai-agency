"""agent/contract_enforcement.py — Runtime signature locking (J)

Provides _check_kwargs() and _LOCKED parameter sets for all 5 core classes
that must enforce contract discipline (matching Pydantic extra="forbid").

Usage per class:
    from agent.contract_enforcement import (
        LOCKED_JOB_MANAGER_CREATE,
        LOCKED_AGENT_RUNNER_RUN,
        LOCKED_MODEL_ROUTER_ROUTE,
        LOCKED_ORCHESTRATOR_EXECUTE,
        LOCKED_SKILL_REGISTRY_RECOMMEND,
        check_kwargs,
    )
    check_kwargs(kwargs, LOCKED_JOB_MANAGER_CREATE, "AgentJobManager.create_job")
"""
# nosec: B603,B607,B413,B301,B104,B608

from __future__ import annotations

from typing import Any

# ── Locked parameter sets ─────────────────────────────────────────────────────


# AgentJobManager.create_job()
LOCKED_JOB_MANAGER_CREATE: frozenset[str] = frozenset({
    "session_id",
    "instruction",
    "owner_id",
    "runtime_id",
    "workspace_path",
    "requested_model",
    "provider_id",
})

# AgentJobManager.start_job()
LOCKED_JOB_MANAGER_START: frozenset[str] = frozenset({
    "job_id",
    "runner",
})

# AgentJobManager.cancel_job()
LOCKED_JOB_MANAGER_CANCEL: frozenset[str] = frozenset({
    "job_id",
})

# AgentJobManager.get_job()
LOCKED_JOB_MANAGER_GET: frozenset[str] = frozenset({
    "job_id",
})

# AgentJobManager.list_jobs()
# NOTE: limit is NOT locked — it is a legitimate optional param that does not
# break the contract. Add it here only if you want to enforce it as well.
LOCKED_JOB_MANAGER_LIST: frozenset[str] = frozenset({
    "session_id",
})


# AgentRunner.run()
LOCKED_AGENT_RUNNER_RUN: frozenset[str] = frozenset({
    "instruction",
    "history",
    "requested_model",
    "auto_commit",
    "max_steps",
    "user_id",
    "department",
    "key_id",
    "memory_store",
    "session_id",
    "metadata",
})

# AgentRunner.plan()
LOCKED_AGENT_RUNNER_PLAN: frozenset[str] = frozenset({
    "instruction",
    "history",
    "requested_model",
    "max_steps",
    "user_id",
    "memory_store",
    "session_id",
    "metadata",
})

# AgentRunner.configure_sub_agents()
LOCKED_AGENT_RUNNER_CONFIGURE: frozenset[str] = frozenset({
    "configs",
})

# AgentRunner._spawn_subagent()
LOCKED_AGENT_RUNNER_SPAWN: frozenset[str] = frozenset({
    "instruction",
    "max_steps",
    "role",
})


# ModelRouter.route()
LOCKED_MODEL_ROUTER_ROUTE: frozenset[str] = frozenset({
    "requested_model",
    "messages",
    "system",
    "has_tools",
    "stream",
    "override_model",
    "endpoint_type",
    "context_tokens",
})


# WorkflowOrchestrator.execute()
LOCKED_ORCHESTRATOR_EXECUTE: frozenset[str] = frozenset({
    "req",
    "resume_run_id",
})

# WorkflowOrchestrator.approve()
LOCKED_ORCHESTRATOR_APPROVE: frozenset[str] = frozenset({
    "run_id",
    "approved_by",
})

# WorkflowOrchestrator.approve_and_resume()
LOCKED_ORCHESTRATOR_APPROVE_AND_RESUME: frozenset[str] = frozenset({
    "run_id",
    "approved_by",
})

# WorkflowOrchestrator.get_run()
LOCKED_ORCHESTRATOR_GET_RUN: frozenset[str] = frozenset({
    "run_id",
})

# WorkflowOrchestrator.list_runs()
# NOTE: limit has a default so it is accepted; owner_id is keyword-only.
# Both are legitimate and intentionally not locked as enforced params.
LOCKED_ORCHESTRATOR_LIST_RUNS: frozenset[str] = frozenset({
    "limit",
    "owner_id",
})


# SkillRegistry.recommend()
LOCKED_SKILL_REGISTRY_RECOMMEND: frozenset[str] = frozenset({
    "tech_stack",
    "workflow_types",
    "query",
    "limit",
})

# SkillRegistry.list()
LOCKED_SKILL_REGISTRY_LIST: frozenset[str] = frozenset({
    "source",
})

# SkillRegistry.search()
LOCKED_SKILL_REGISTRY_SEARCH: frozenset[str] = frozenset({
    "query",
})

# SkillRegistry.get()
LOCKED_SKILL_REGISTRY_GET: frozenset[str] = frozenset({
    "skill_id",
})

# SkillRegistry.update_github_token()
LOCKED_SKILL_REGISTRY_UPDATE_TOKEN: frozenset[str] = frozenset({
    "token",
})


# ── Enforcement helper ────────────────────────────────────────────────────────


def check_kwargs(kwargs: dict[str, Any], locked: frozenset[str], label: str) -> None:
    """Raise TypeError on unknown kwarg (runtime extra='forbid').

    Args:
        kwargs: The kwargs dict received by the function.
        locked:  The frozenset of accepted parameter names.
        label:   Human-readable label for the error message
                 (e.g. "AgentJobManager.create_job").

    Raises:
        TypeError: if any unknown keyword argument is present.
    """
    unknown = [k for k in kwargs if k not in locked]
    if unknown:
        raise TypeError(
            f"{label}() got unexpected keyword argument(s): {unknown}. "
            f"Accepted: {sorted(locked)}"
        )
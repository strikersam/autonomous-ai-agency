"""AgentRunner carries a real governance identity so sticky grants can apply."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from packages.governance import approvals as approvals_module
from packages.governance.approvals import GrantStore
from packages.governance.enforcement import GovernanceGate, resolve_identity_for_runner


@pytest.fixture(autouse=True)
def grants():
    approvals_module.reset_grant_store(GrantStore())
    yield
    approvals_module.reset_grant_store(None)


def _runner(**kw):
    from agent.loop import AgentRunner

    return AgentRunner(ollama_base="http://localhost:11434", **kw)


def _decision():
    return SimpleNamespace(surface=SimpleNamespace(value="tool"), action="deploy_prod")


def test_runner_identity_uses_bound_agent_and_owner():
    identity = resolve_identity_for_runner(_runner(agent_name="coder", owner="sam@example.com"))
    assert identity.agent_id == "agent:coder"
    assert identity.owner == "sam@example.com"


def test_runner_without_identity_is_generic():
    identity = resolve_identity_for_runner(_runner())
    assert (identity.agent_id, identity.owner) == ("agent:unknown", "system")


def test_generic_runner_cannot_be_granted():
    identity = resolve_identity_for_runner(_runner())
    grant = approvals_module.get_grant_store().grant(
        identity.session_id, "session", "tool", "deploy_prod", "admin", 60,
        agent_id=identity.agent_id, owner=identity.owner,
    )
    assert grant is None


def test_owner_only_runner_can_be_granted_and_skips_the_ask():
    from packages.config import settings

    identity = resolve_identity_for_runner(_runner(owner="sam@example.com"))
    grant = approvals_module.get_grant_store().grant(
        identity.session_id, "action", "tool", "deploy_prod", "admin", 60,
        agent_id=identity.agent_id, owner=identity.owner,
    )
    assert grant is not None
    assert GovernanceGate._find_grant(identity, _decision(), settings) == grant.grant_id


def test_grant_for_one_owner_does_not_match_another_owners_runner():
    from packages.config import settings

    first = resolve_identity_for_runner(_runner(agent_name="coder", owner="sam@example.com"))
    approvals_module.get_grant_store().grant(
        first.session_id, "session", "tool", "x", "admin", 60,
        agent_id=first.agent_id, owner=first.owner,
    )
    other = resolve_identity_for_runner(_runner(agent_name="coder", owner="eve@example.com"))
    # Same session id and agent, different owner: must still ask.
    forged = other.with_context(session_id=first.session_id)
    assert GovernanceGate._find_grant(forged, _decision(), settings) is None
    assert GovernanceGate._find_grant(first, _decision(), settings) is not None


def test_shared_proxy_runner_stays_generic():
    pytest.importorskip("proxy")
    import proxy

    identity = resolve_identity_for_runner(proxy.AGENT_RUNNER)
    assert (identity.agent_id, identity.owner) == ("agent:unknown", "system")

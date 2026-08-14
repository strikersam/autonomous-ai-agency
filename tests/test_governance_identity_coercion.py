"""tests/test_governance_identity_coercion.py — identity derivation must be total.

Regression for the production warning that fired on essentially every runtime
dispatch:

    Runtime governance check failed ('dict' object has no attribute 'strip');
    allowing dispatch

``runtimes/routing.py`` builds the acting identity from
``context.get("agent_name") or context.get("agent")``, and ``context["agent"]``
is sometimes a full agent-profile *dict*, not a name string. Every derivation
site in ``packages/governance/identity.py`` then called ``.strip()`` on it,
which raises ``AttributeError`` — caught by the routing seam, which then failed
*open*: policy enforcement was silently skipped for that dispatch. Identity
resolution is documented as total ("resolving one cannot fail"), so a
loosely-typed context value must be coerced, never raise.
"""
from __future__ import annotations

from packages.governance.identity import (
    UNKNOWN_AGENT_ID,
    resolve_identity,
    slugify_agent,
)


def test_slugify_agent_tolerates_dict():
    # A dict with a name field resolves to that name's slug, not an exception.
    assert slugify_agent({"name": "Research Coordinator"}) == "agent:research-coordinator"
    # A dict with no usable name field collapses to the least-privileged unknown.
    assert slugify_agent({"unrelated": 1}) == UNKNOWN_AGENT_ID
    # Non-str, non-dict values coerce rather than raise.
    assert slugify_agent(12345) == "agent:12345"
    assert slugify_agent(None) == UNKNOWN_AGENT_ID


def test_resolve_identity_with_dict_agent_name_does_not_raise():
    # This is exactly the shape routing.py passes when context["agent"] is a
    # profile dict: agent_name is a dict, not a string.
    identity = resolve_identity(
        agent_name={"name": "Quality Agent", "id": "quality"},
        owner={"email": "owner@example.com"},
    )
    assert identity.agent_id == "agent:quality-agent"
    assert identity.display_name == "Quality Agent"
    # A dict owner with no name-like field falls back to the system owner rather
    # than raising or storing the dict.
    assert identity.owner == "system"


def test_resolve_identity_string_path_unchanged():
    # The common string path must be byte-for-byte what it always was.
    identity = resolve_identity(agent_name="Finance Agent", owner="user@example.com")
    assert identity.agent_id == "agent:finance-agent"
    assert identity.display_name == "Finance Agent"
    assert identity.owner == "user@example.com"
    assert identity.policy_group == "agent:finance-agent"

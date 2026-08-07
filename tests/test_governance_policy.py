"""Tests for the governance policy engine.

The properties pinned here are the ones that make the engine a control rather
than a suggestion:

  * observe mode never blocks (the Golden Rule guarantee),
  * a group cannot loosen a baseline rule,
  * a declared-but-empty allow-list denies everything,
  * path traversal cannot walk around a filesystem rule,
  * a malformed policy degrades to the embedded default instead of crashing.

Each of the first four was a real defect at some point during development, so
these are regression tests, not decoration.
"""
from __future__ import annotations

import pytest

from packages.governance.identity import resolve_identity, slugify_agent, UNKNOWN_AGENT_ID
from packages.governance.policy import (
    DEFAULT_POLICY,
    Decision,
    Mode,
    PolicyEngine,
    Surface,
)


@pytest.fixture
def enforcing_engine() -> PolicyEngine:
    """An engine built from the shipped policy, switched to enforce."""
    import yaml

    with open("config/agent_policy.yaml", encoding="utf-8") as fh:
        document = yaml.safe_load(fh)
    document["mode"] = "enforce"
    return PolicyEngine(document)


@pytest.fixture
def shipped_engine() -> PolicyEngine:
    return PolicyEngine.from_file("config/agent_policy.yaml")


# ── Identity ─────────────────────────────────────────────────────────────────


def test_agent_id_is_stable_across_name_spellings():
    assert slugify_agent("Research Coordinator") == slugify_agent("research-coordinator")
    assert slugify_agent("Research  Coordinator!") == "agent:research-coordinator"


def test_unnamed_agent_gets_the_unknown_id_not_a_privileged_one():
    assert slugify_agent("") == UNKNOWN_AGENT_ID
    assert slugify_agent(None) == UNKNOWN_AGENT_ID


def test_session_ids_are_unique_per_run():
    first = resolve_identity(agent_name="coder")
    second = resolve_identity(agent_name="coder")
    assert first.agent_id == second.agent_id, "agent id must be stable"
    assert first.session_id != second.session_id, "session id must be per-run"


def test_with_context_returns_a_copy_and_ignores_unknown_fields():
    identity = resolve_identity(agent_name="coder")
    enriched = identity.with_context(sandbox_id="sbx_1", nonsense="ignored")
    assert enriched.sandbox_id == "sbx_1"
    assert identity.sandbox_id is None, "original must be unchanged (frozen)"
    assert not hasattr(enriched, "nonsense")


def test_identity_dict_carries_no_secret_fields():
    identity = resolve_identity(agent_name="coder", owner="sam@example.com")
    serialised = identity.to_dict()
    assert "sam@example.com" == serialised["owner"]
    assert not any("token" in k or "secret" in k for k in serialised)


# ── Observe mode: the Golden Rule guarantee ──────────────────────────────────


def test_observe_mode_never_blocks_even_on_a_baseline_deny(shipped_engine):
    """The shipped default must be behaviour-neutral.

    A deny is still *recorded* on `.decision` so the audit trail and the
    would-block metric work — but `.effective`, the only thing enforcement
    reads, stays ALLOW.
    """
    assert shipped_engine.mode is Mode.OBSERVE
    decision = shipped_engine.evaluate(Surface.FILESYSTEM, ".env")
    assert decision.decision is Decision.DENY
    assert decision.effective is Decision.ALLOW
    assert decision.would_block is True


def test_enforce_mode_makes_the_decision_effective(enforcing_engine):
    decision = enforcing_engine.evaluate(Surface.FILESYSTEM, ".env")
    assert decision.decision is Decision.DENY
    assert decision.effective is Decision.DENY


# ── Baseline cannot be loosened ──────────────────────────────────────────────


def test_group_cannot_re_allow_a_baseline_denied_action():
    """The structural guarantee behind 'guardrails that can't be overridden'."""
    engine = PolicyEngine({
        "mode": "enforce",
        "baseline": {"filesystem": {"deny": [".env"]}},
        "groups": {
            # A group that tries as hard as it can to permit the denied path.
            "permissive": {"filesystem": {"allow": ["**", ".env"]}},
        },
    })
    identity = resolve_identity(agent_name="x", policy_group="permissive")
    decision = engine.evaluate(Surface.FILESYSTEM, ".env", identity)
    assert decision.decision is Decision.DENY
    assert decision.rule_id.startswith("baseline."), decision.rule_id


def test_baseline_require_approval_beats_a_group_allow():
    engine = PolicyEngine({
        "mode": "enforce",
        "baseline": {"tool": {"require_approval": ["github_merge_pr"]}},
        "groups": {"g": {"tool": {"allow": ["*"]}}},
    })
    identity = resolve_identity(agent_name="x", policy_group="g")
    decision = engine.evaluate(Surface.TOOL, "github_merge_pr", identity)
    assert decision.decision is Decision.REQUIRE_APPROVAL


# ── Allow-list semantics ─────────────────────────────────────────────────────


def test_declared_but_empty_allow_list_denies_everything():
    """`write: []` means no writes — not 'unrestricted'.

    Regression: an earlier build dropped falsy rule lists during compilation,
    so the strictest expressible rule silently became the most permissive one.
    """
    engine = PolicyEngine({
        "mode": "enforce",
        "groups": {"ro": {"filesystem": {"read": ["**"], "write": []}}},
    })
    identity = resolve_identity(agent_name="x", policy_group="ro")
    assert engine.evaluate(
        Surface.FILESYSTEM, "src/app.py", identity, {"mode": "write"}
    ).decision is Decision.DENY
    assert engine.evaluate(
        Surface.FILESYSTEM, "src/app.py", identity, {"mode": "read"}
    ).decision is Decision.ALLOW


def test_absent_allow_list_leaves_the_surface_unrestricted():
    engine = PolicyEngine({"mode": "enforce", "groups": {"g": {}}})
    identity = resolve_identity(agent_name="x", policy_group="g")
    decision = engine.evaluate(Surface.TOOL, "anything_at_all", identity)
    assert decision.decision is Decision.ALLOW
    assert decision.rule_id.endswith("default-allow")


def test_allow_list_is_default_deny_for_unlisted_actions():
    engine = PolicyEngine({
        "mode": "enforce",
        "groups": {"g": {"tool": {"allow": ["read_file", "list_files"]}}},
    })
    identity = resolve_identity(agent_name="x", policy_group="g")
    assert engine.evaluate(Surface.TOOL, "read_file", identity).decision is Decision.ALLOW
    assert engine.evaluate(Surface.TOOL, "write_file", identity).decision is Decision.DENY


# ── Matching ─────────────────────────────────────────────────────────────────


def test_path_traversal_cannot_escape_a_filesystem_rule(enforcing_engine):
    """`a/../.env` must be judged as `.env`, not as an unmatched path."""
    for path in (".env", "a/../.env", "./config/../.env", "x/y/../../.env"):
        decision = enforcing_engine.evaluate(Surface.FILESYSTEM, path)
        assert decision.decision is Decision.DENY, f"{path} slipped past the rule"


def test_nested_secret_paths_are_denied(enforcing_engine):
    for path in ("backend/.env", "deploy/prod/.ssh/id_rsa", "certs/server.pem"):
        assert enforcing_engine.evaluate(Surface.FILESYSTEM, path).decision is Decision.DENY


def test_cidr_rules_match_literal_ips_only(enforcing_engine):
    assert enforcing_engine.evaluate(Surface.NETWORK, "169.254.169.254").decision is Decision.DENY
    assert enforcing_engine.evaluate(Surface.NETWORK, "10.1.2.3").decision is Decision.DENY
    assert enforcing_engine.evaluate(Surface.NETWORK, "8.8.8.8").decision is Decision.ALLOW


def test_domain_rules_cover_subdomains_but_a_wildcard_does_not_cover_the_apex():
    engine = PolicyEngine({"mode": "enforce", "baseline": {"network": {"deny": ["evil.com"]}}})
    assert engine.evaluate(Surface.NETWORK, "evil.com").decision is Decision.DENY
    assert engine.evaluate(Surface.NETWORK, "api.evil.com").decision is Decision.DENY
    assert engine.evaluate(Surface.NETWORK, "notevil.com").decision is Decision.ALLOW


def test_metadata_endpoint_is_denied_by_the_shipped_baseline(enforcing_engine):
    """The SSRF-to-credentials pivot must be closed out of the box."""
    for host in ("169.254.169.254", "metadata.google.internal", "foo.internal"):
        assert enforcing_engine.evaluate(Surface.NETWORK, host).decision is Decision.DENY


# ── Groups ───────────────────────────────────────────────────────────────────


def test_assignment_rules_map_agents_to_groups(shipped_engine):
    research = resolve_identity(agent_name="Deep Research Bot")
    assert shipped_engine.group_for(research).name == "research"
    security = resolve_identity(agent_name="Security Auditor")
    assert shipped_engine.group_for(security).name == "security"


def test_unknown_group_falls_back_to_default_not_to_unrestricted(shipped_engine):
    identity = resolve_identity(agent_name="x", policy_group="does-not-exist")
    assert shipped_engine.group_for(identity).name == "default"


def test_extends_appends_parent_rules_rather_than_replacing_them():
    """A child must not be able to shrink its parent's deny-list."""
    engine = PolicyEngine({
        "mode": "enforce",
        "groups": {
            "parent": {"tool": {"deny": ["dangerous_tool"]}},
            "child": {"extends": "parent", "tool": {"deny": ["another_tool"]}},
        },
    })
    identity = resolve_identity(agent_name="x", policy_group="child")
    assert engine.evaluate(Surface.TOOL, "dangerous_tool", identity).decision is Decision.DENY
    assert engine.evaluate(Surface.TOOL, "another_tool", identity).decision is Decision.DENY


def test_cyclic_extends_does_not_hang():
    engine = PolicyEngine({
        "mode": "enforce",
        "groups": {"a": {"extends": "b"}, "b": {"extends": "a"}},
    })
    assert "a" in engine.group_names()


def test_limits_are_inherited_and_overridable():
    engine = PolicyEngine({
        "groups": {
            "base": {"limits": {"max_tool_calls": 100, "max_cost_usd": 1.0}},
            "big": {"extends": "base", "limits": {"max_cost_usd": 50.0}},
        },
    })
    limits = engine.limits_for(resolve_identity(agent_name="x", policy_group="big"))
    assert limits["max_tool_calls"] == 100, "inherited"
    assert limits["max_cost_usd"] == 50.0, "overridden"


# ── Failure behaviour ────────────────────────────────────────────────────────


def test_missing_policy_file_falls_back_to_the_embedded_default():
    engine = PolicyEngine.from_file("does/not/exist.yaml")
    assert engine.mode is Mode.OBSERVE
    assert "default" in engine.group_names()
    # The fallback is a real policy, not an allow-all.
    assert engine.evaluate(Surface.FILESYSTEM, ".env").would_block


def test_malformed_policy_file_falls_back_instead_of_raising(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("mode: [this is not a mode\n  broken: yaml: everywhere", encoding="utf-8")
    engine = PolicyEngine.from_file(str(bad))
    assert "default" in engine.group_names()
    assert engine.evaluate(Surface.FILESYSTEM, ".env").would_block


def test_non_mapping_policy_root_falls_back(tmp_path):
    bad = tmp_path / "list.yaml"
    bad.write_text("- just\n- a\n- list\n", encoding="utf-8")
    engine = PolicyEngine.from_file(str(bad))
    assert "default" in engine.group_names()


def test_a_broken_pattern_does_not_void_the_remaining_rules():
    engine = PolicyEngine({
        "mode": "enforce",
        "baseline": {"network": {"deny": ["999.999.999.999/99", "evil.com"]}},
    })
    assert engine.evaluate(Surface.NETWORK, "evil.com").decision is Decision.DENY


def test_unknown_mode_defaults_to_observe():
    engine = PolicyEngine({"mode": "yolo", "groups": {}})
    assert engine.mode is Mode.OBSERVE


# ── Introspection ────────────────────────────────────────────────────────────


def test_describe_exposes_rules_without_secret_values(shipped_engine):
    described = shipped_engine.describe()
    assert described["mode"] == "observe"
    assert "baseline" in described and "groups" in described
    blob = repr(described).lower()
    for marker in ("ghp_", "sk-ant-", "nvapi-", "password="):
        assert marker not in blob


def test_embedded_default_policy_is_valid():
    """The fallback must itself compile — it is the last line of defence."""
    engine = PolicyEngine(DEFAULT_POLICY)
    assert "default" in engine.group_names()
    assert engine.limits_for(resolve_identity(agent_name="x"))["max_tool_calls"] > 0

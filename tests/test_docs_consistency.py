"""tests/test_docs_consistency.py — structural defense against narrative drift.

Because `ci.yml` already runs pytest, these assertions ARE the docs-consistency
CI gate required by the truth-reconciliation brief (deliverable #9/#10): they
fail the build when the README, the orchestration doc, the feature matrix, and
the skill registry disagree with each other or with the code.

Scope is deliberately deterministic (no network, no fragile NLP). Each check
guards a specific contradiction that has actually occurred in this repo.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from features.matrix import FeatureMaturity, get_feature_matrix
from services.skill_bindings import get_skill_bindings

_ROOT = Path(__file__).resolve().parent.parent


# ── 1. Orchestration doc must match the worktree code ───────────────────────────


def test_orchestration_doc_does_not_call_worktree_isolation_future() -> None:
    """Per-task worktree isolation is implemented in
    runtimes/adapters/internal_agent.py (`_create_worktree`) and dispatched
    concurrently via asyncio.gather. The architecture doc must not still frame it
    as a future/sequential-only capability (the original brief's contradiction)."""
    doc = (_ROOT / "docs" / "architecture" / "agent-orchestration.md").read_text(encoding="utf-8")
    lowered = doc.lower()
    assert "worktree isolation (future)" not in lowered, (
        "agent-orchestration.md still labels worktree isolation 'Future' — it is "
        "implemented in runtimes/adapters/internal_agent.py._create_worktree."
    )
    assert "the current implementation is sequential" not in lowered, (
        "agent-orchestration.md still claims sequential execution; the dispatcher "
        "runs tasks concurrently via asyncio.gather."
    )
    # And it should actually document the real mechanism.
    assert "_create_worktree" in doc, (
        "agent-orchestration.md should reference the real _create_worktree path."
    )


# ── 2. Feature matrix must be internally consistent and self-documenting ─────────


def test_disabled_features_are_documented_and_not_enabled() -> None:
    """A DISABLED feature must be enabled=False and carry a note explaining why —
    prevents silently demoting load-bearing features without a paper trail."""
    matrix = get_feature_matrix()
    for entry in matrix.list_all():
        if entry.maturity is FeatureMaturity.DISABLED:
            assert entry.enabled is False, (
                f"{entry.feature_id} is DISABLED but enabled=True (contradiction)."
            )
            assert entry.notes.strip(), (
                f"{entry.feature_id} is DISABLED with no note — every demotion must "
                f"be documented in features/matrix.py."
            )


def test_beta_or_experimental_features_carry_a_note() -> None:
    """The brief: no feature may be presented as production-grade while it is still
    beta/experimental without an explicit caveat. The matrix is the source of truth,
    so every non-stable, still-enabled feature must document its caveat."""
    matrix = get_feature_matrix()
    for entry in matrix.list_all():
        if entry.enabled and entry.maturity in (
            FeatureMaturity.BETA,
            FeatureMaturity.EXPERIMENTAL,
        ):
            assert entry.notes.strip(), (
                f"{entry.feature_id} is {entry.maturity.value} and enabled but has no "
                f"note — beta/experimental features must be documented as such."
            )


# ── 3. Skills advertised on the public site / README must be registered ─────────

# These are the skills the README skill table and github-pages-index.html present
# to the public as real, callable capabilities. Each must exist in the runtime
# skill registry (services/skill_bindings.py), or the public site is lying.
_PUBLICLY_ADVERTISED_SKILLS = [
    "ecc-harness-patterns",
    "graphify",
    "council-review",
    "obsidian-knowledge-graph",
]


@pytest.mark.parametrize("skill_id", _PUBLICLY_ADVERTISED_SKILLS)
def test_publicly_advertised_skill_is_registered(skill_id: str) -> None:
    bindings = get_skill_bindings()
    skill = bindings.get(skill_id)
    assert skill is not None, (
        f"Skill '{skill_id}' is advertised on the public site/README but is not in "
        f"the runtime skill registry (services/skill_bindings.py)."
    )


def test_skills_not_in_registry_are_not_claimed_as_registered_skills() -> None:
    """browserbase / agent-browser / perplexity are MCP/CLI tools, NOT runtime
    skills. Guard against someone quietly adding them to the public 'Skill
    Registry' list without registering an executor — they must stay out until
    they are real RuntimeSkills."""
    bindings = get_skill_bindings()
    for skill_id in ("browserbase", "agent-browser", "perplexity"):
        # If one of these ever IS registered, this test should be updated to
        # advertise it publicly — failing loudly is the point.
        assert bindings.get(skill_id) is None, (
            f"'{skill_id}' is now in the registry — either advertise it on the "
            f"public site and add it to _PUBLICLY_ADVERTISED_SKILLS, or remove it."
        )

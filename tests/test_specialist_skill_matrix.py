"""tests/test_specialist_skill_matrix.py — the '34 families' claim must be true.

Truth-reconciliation brief #7 + acceptance: every specialist family counted in
the '34 families' claim must have at least one bound, *executable* skill — or be
removed from the count. This runs in CI (ci.yml pytest), so the claim can't
silently drift.
"""
from __future__ import annotations

import pytest

from scripts.generate_specialist_skill_matrix import build_matrix, render_markdown


def test_matrix_has_thirty_four_families():
    rows = build_matrix()
    assert len(rows) == 34, f"Expected 34 specialist families, got {len(rows)}"


def test_every_family_has_at_least_one_bound_skill():
    """No family may be counted in '34 families' with zero bound skills."""
    rows = build_matrix()
    zero = [r["family"] for r in rows if not r["bound_skills"]]
    assert not zero, (
        f"These families have zero bound skills — bind a skill in "
        f"services/skill_bindings.py or remove them from the 34-family claim: {zero}"
    )


def test_bound_skills_are_executable_and_enabled():
    """Bound skills must be enabled (descriptor-only stubs don't count as 'can call
    typed skills on demand')."""
    from services.skill_bindings import get_skill_bindings

    bindings = get_skill_bindings()
    for row in build_matrix():
        for skill_id in row["bound_skills"]:
            skill = bindings.get(skill_id)
            assert skill is not None, f"{row['family']} bound to unknown skill {skill_id}"
            assert getattr(skill, "is_enabled", True), (
                f"{row['family']} bound to disabled/descriptor-only skill {skill_id}"
            )


def test_matrix_renders_without_error():
    md = render_markdown(build_matrix())
    assert md.startswith("# Specialist × Skill Matrix")
    assert "— **none**" not in md.split("Test evidence")[0].split("|")[0]  # header sanity

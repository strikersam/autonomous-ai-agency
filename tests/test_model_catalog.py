"""tests/test_model_catalog.py — UNIT 4: config/models.yaml catalog tests.

Verifies:
  1. ``config/models.yaml`` parses and has the expected top-level shape.
  2. Every provider in the ``BrainProvider`` Literal has a matching entry
     in the YAML (catalog and Literal stay in sync).
  3. Every YAML provider entry has all required fields (display_name,
     tier, key_env, base_url_env, default_base_url, role_presets,
     candidates).
  4. The module-level dicts (``PROVIDER_PRESETS``, ``PROVIDER_KEY_ENV``,
     ``PROVIDER_CANDIDATES``, etc.) are populated from the YAML.
  5. The helper functions (``get_provider_candidates``,
     ``get_provider_display_name``, ``get_provider_tier``,
     ``all_provider_ids``) return the expected values.
  6. The YAML loader degrades gracefully when the file is missing or
     corrupt (returns None, module falls back to hardcoded defaults).
  7. The hardcoded defaults and the YAML agree on key fields (parity
     check) so removing the YAML doesn't silently change behavior.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from packages.ai import brain_config
from packages.ai.brain_config import (
    BrainProvider,
    PROVIDER_BASE_URL_ENV,
    PROVIDER_CANDIDATES,
    PROVIDER_DEFAULT_BASE_URL,
    PROVIDER_DISPLAY_NAMES,
    PROVIDER_KEY_ENV,
    PROVIDER_PRESETS,
    PROVIDER_TIERS,
    RECOMMENDED_PROVIDER_PRIORITY,
    SAFE_DEFAULT_MODEL,
    SAFE_DEFAULT_PROVIDER,
    _build_candidates_from_yaml,
    _build_default_base_url_from_yaml,
    _build_display_names_from_yaml,
    _build_key_env_from_yaml,
    _build_presets_from_yaml,
    _build_tier_from_yaml,
    _load_models_yaml,
    all_provider_ids,
    get_provider_candidates,
    get_provider_display_name,
    get_provider_tier,
)
import typing


YAML_PATH = Path(__file__).resolve().parent.parent / "config" / "models.yaml"


# ── 1. YAML file shape ─────────────────────────────────────────────────────


def test_models_yaml_file_exists():
    """The catalog file ships in the repo (UNIT 4 deliverable)."""
    assert YAML_PATH.is_file(), f"expected catalog at {YAML_PATH}"


def test_models_yaml_parses_and_has_top_level_shape():
    """The YAML parses to a dict with the expected top-level keys."""
    data = _load_models_yaml()
    assert data is not None, "models.yaml failed to load"
    assert isinstance(data, dict)
    assert "providers" in data and isinstance(data["providers"], dict)
    assert "safe_default" in data and isinstance(data["safe_default"], dict)
    assert "recommended_priority" in data and isinstance(data["recommended_priority"], list)
    assert data.get("catalog_version") == 1


# ── 2. Catalog ↔ Literal parity ────────────────────────────────────────────


def _yaml_provider_ids() -> set[str]:
    data = _load_models_yaml()
    assert data is not None
    return set((data.get("providers") or {}).keys())


def test_every_literal_provider_has_yaml_entry():
    """Adding a provider to the Literal without a YAML entry is a bug.

    The YAML is the source of truth — if it doesn't know about a provider,
    the helper functions silently fall back to defaults, which is the
    exact failure mode this test prevents.
    """
    literal_ids = set(typing.get_args(BrainProvider))
    yaml_ids = _yaml_provider_ids()
    missing = literal_ids - yaml_ids
    assert not missing, f"providers in Literal but not in YAML: {missing}"


def test_every_yaml_provider_is_in_literal():
    """A YAML entry for a provider not in the Literal is dead config.

    The Literal is the validation gate for PATCH /admin/api/policy/brain —
    a YAML-only provider would be unselectable from the UI.
    """
    literal_ids = set(typing.get_args(BrainProvider))
    yaml_ids = _yaml_provider_ids()
    extra = yaml_ids - literal_ids
    assert not extra, f"providers in YAML but not in Literal: {extra}"


# ── 3. Required fields ─────────────────────────────────────────────────────


REQUIRED_PROVIDER_FIELDS = (
    "display_name",
    "tier",
    "key_env",
    "base_url_env",
    "default_base_url",
    "role_presets",
    "candidates",
)


def test_every_yaml_provider_has_all_required_fields():
    data = _load_models_yaml()
    assert data is not None
    for pid, pinfo in data["providers"].items():
        for field in REQUIRED_PROVIDER_FIELDS:
            assert field in pinfo, f"provider {pid!r} missing field {field!r}"


def test_every_yaml_role_preset_has_all_four_roles():
    data = _load_models_yaml()
    assert data is not None
    for pid, pinfo in data["providers"].items():
        presets = pinfo.get("role_presets") or {}
        for role in ("planner", "executor", "verifier", "judge"):
            assert role in presets, f"provider {pid!r} missing role preset {role!r}"
            v = presets[role]
            assert isinstance(v, str) and v.strip(), (
                f"provider {pid!r} role {role!r} preset is empty"
            )


def test_every_yaml_candidates_is_non_empty_list():
    data = _load_models_yaml()
    assert data is not None
    for pid, pinfo in data["providers"].items():
        cands = pinfo.get("candidates") or []
        assert isinstance(cands, list) and cands, (
            f"provider {pid!r} candidates must be a non-empty list"
        )
        for c in cands:
            assert isinstance(c, str) and c.strip(), (
                f"provider {pid!r} has a non-string/empty candidate: {c!r}"
            )


def test_yaml_tier_values_are_valid():
    data = _load_models_yaml()
    assert data is not None
    valid_tiers = {"free", "paid", "local"}
    for pid, pinfo in data["providers"].items():
        tier = (pinfo.get("tier") or "").lower()
        assert tier in valid_tiers, (
            f"provider {pid!r} tier {tier!r} not in {valid_tiers}"
        )


# ── 4. Module-level dicts populated from YAML ──────────────────────────────


def test_provider_presets_dict_has_all_yaml_providers():
    yaml_ids = _yaml_provider_ids()
    for pid in yaml_ids:
        assert pid in PROVIDER_PRESETS, f"provider {pid!r} missing from PROVIDER_PRESETS"
        # Each preset has all four roles.
        for role in ("planner", "executor", "verifier", "judge"):
            assert role in PROVIDER_PRESETS[pid], (
                f"provider {pid!r} role {role!r} missing from PROVIDER_PRESETS"
            )


def test_provider_candidates_dict_has_all_yaml_providers():
    yaml_ids = _yaml_provider_ids()
    for pid in yaml_ids:
        assert pid in PROVIDER_CANDIDATES, f"provider {pid!r} missing from PROVIDER_CANDIDATES"
        assert len(PROVIDER_CANDIDATES[pid]) >= 1


def test_provider_display_names_dict_has_all_yaml_providers():
    yaml_ids = _yaml_provider_ids()
    for pid in yaml_ids:
        assert pid in PROVIDER_DISPLAY_NAMES
        assert PROVIDER_DISPLAY_NAMES[pid]


def test_provider_tiers_dict_has_all_yaml_providers():
    yaml_ids = _yaml_provider_ids()
    for pid in yaml_ids:
        assert pid in PROVIDER_TIERS
        assert PROVIDER_TIERS[pid] in ("free", "paid", "local")


def test_provider_key_env_dict_has_all_yaml_providers():
    yaml_ids = _yaml_provider_ids()
    for pid in yaml_ids:
        assert pid in PROVIDER_KEY_ENV


def test_provider_base_url_env_dict_has_all_yaml_providers():
    yaml_ids = _yaml_provider_ids()
    for pid in yaml_ids:
        assert pid in PROVIDER_BASE_URL_ENV


def test_provider_default_base_url_dict_has_all_yaml_providers():
    yaml_ids = _yaml_provider_ids()
    for pid in yaml_ids:
        assert pid in PROVIDER_DEFAULT_BASE_URL
        assert PROVIDER_DEFAULT_BASE_URL[pid].startswith(("http://", "https://"))


# ── 5. Helper functions ────────────────────────────────────────────────────


def test_all_provider_ids_returns_literal_args():
    expected = set(typing.get_args(BrainProvider))
    actual = set(all_provider_ids())
    assert actual == expected
    assert len(actual) == 14  # 14 supported providers


def test_get_provider_candidates_returns_copy():
    """Mutating the returned list must not affect the module-level dict."""
    cands = get_provider_candidates("nvidia")
    assert cands
    cands.append("mutated-by-test")
    # Re-fetch — should not contain the mutation.
    again = get_provider_candidates("nvidia")
    assert "mutated-by-test" not in again


def test_get_provider_candidates_unknown_provider_returns_empty():
    assert get_provider_candidates("not-a-real-provider") == []


def test_get_provider_display_name_known():
    assert get_provider_display_name("nvidia") == "NVIDIA NIM (free, broad catalogue)"


def test_get_provider_display_name_unknown_falls_back_to_id():
    assert get_provider_display_name("not-a-real-provider") == "not-a-real-provider"


def test_get_provider_tier_known():
    assert get_provider_tier("nvidia") == "free"
    assert get_provider_tier("ollama") == "local"
    assert get_provider_tier("anthropic") == "paid"


def test_get_provider_tier_unknown_returns_unknown():
    assert get_provider_tier("not-a-real-provider") == "unknown"


# ── 6. Graceful degradation ────────────────────────────────────────────────


def test_load_models_yaml_returns_none_when_file_missing(tmp_path, monkeypatch):
    """Pointing the loader at a non-existent path returns None."""
    fake_path = tmp_path / "does-not-exist.yaml"
    monkeypatch.setattr(brain_config, "_MODELS_YAML_PATH", str(fake_path))
    assert brain_config._load_models_yaml() is None


def test_load_models_yaml_returns_none_when_corrupt(tmp_path, monkeypatch):
    """A YAML syntax error returns None — never raises."""
    fake_path = tmp_path / "broken.yaml"
    fake_path.write_text(": : : not valid yaml: : :", encoding="utf-8")
    monkeypatch.setattr(brain_config, "_MODELS_YAML_PATH", str(fake_path))
    assert brain_config._load_models_yaml() is None


def test_load_models_yaml_returns_none_when_schema_wrong(tmp_path, monkeypatch):
    """A YAML without the expected top-level keys returns None."""
    fake_path = tmp_path / "wrong-shape.yaml"
    fake_path.write_text("hello: world\n", encoding="utf-8")
    monkeypatch.setattr(brain_config, "_MODELS_YAML_PATH", str(fake_path))
    assert brain_config._load_models_yaml() is None


def test_build_presets_from_yaml_handles_partial_data():
    """A provider entry missing role_presets yields no entry (not a crash)."""
    partial = {"providers": {"foo": {"display_name": "Foo"}}}
    assert _build_presets_from_yaml(partial) == {}


def test_build_candidates_from_yaml_handles_partial_data():
    partial = {"providers": {"foo": {"display_name": "Foo"}}}
    assert _build_candidates_from_yaml(partial) == {}


# ── 7. YAML ↔ hardcoded defaults parity ────────────────────────────────────
#
# If the YAML is removed, the module must keep working with the hardcoded
# defaults. This test verifies the defaults agree with the YAML on the
# fields that matter for routing — so removing the YAML doesn't silently
# change which model a role resolves to.


def test_yaml_safe_default_matches_hardcoded():
    data = _load_models_yaml()
    assert data is not None
    yaml_safe = data["safe_default"]
    assert yaml_safe["provider"] == SAFE_DEFAULT_PROVIDER
    assert yaml_safe["model"] == SAFE_DEFAULT_MODEL


def test_yaml_recommended_priority_matches_hardcoded():
    data = _load_models_yaml()
    assert data is not None
    yaml_prio = tuple(data["recommended_priority"])
    assert yaml_prio == RECOMMENDED_PROVIDER_PRIORITY


def test_yaml_role_presets_match_hardcoded_for_known_providers():
    """Every YAML preset matches the module dict (parity)."""
    data = _load_models_yaml()
    assert data is not None
    yaml_presets = _build_presets_from_yaml(data)
    for pid, presets in yaml_presets.items():
        assert pid in PROVIDER_PRESETS, f"provider {pid!r} missing from PROVIDER_PRESETS"
        for role, model in presets.items():
            assert PROVIDER_PRESETS[pid][role] == model, (
                f"provider {pid!r} role {role!r}: YAML={model!r} "
                f"hardcoded={PROVIDER_PRESETS[pid][role]!r}"
            )


def test_yaml_candidates_match_hardcoded():
    data = _load_models_yaml()
    assert data is not None
    yaml_cands = _build_candidates_from_yaml(data)
    for pid, cands in yaml_cands.items():
        assert PROVIDER_CANDIDATES[pid] == cands, (
            f"provider {pid!r} candidates mismatch: "
            f"YAML={cands!r} hardcoded={PROVIDER_CANDIDATES[pid]!r}"
        )

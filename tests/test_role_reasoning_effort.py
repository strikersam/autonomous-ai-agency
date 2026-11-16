"""Tests for per-role reasoning-effort tiers (#1892 item 1).

`OLLAMA_REASONING_EFFORT` pins one level for every Ollama call. Planning and judging
benefit from more thinking than a tool-call execution step, so effort is now per role:

    BrainConfig.reasoning_effort_by_role[role]  →  OLLAMA_REASONING_EFFORT  →  built-in map

and a caller that already set `reasoning_effort` still wins over all three.
"""
from __future__ import annotations

import time

import pytest

import packages.ai.brain_config as bc
from packages.ai.brain_config import (
    ROLE_REASONING_EFFORTS,
    BrainConfig,
    resolve_role_reasoning_effort,
)
from packages.ai.router import with_ollama_reasoning_effort
from packages.config import settings


class _StubStore:
    """The subset of BrainConfigStore the sync resolver reads."""

    def __init__(self, config: BrainConfig) -> None:
        self._cache = config
        self._cache_at = time.monotonic()


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    """Every test starts from the shipped configuration: tiers on, no global pin."""
    monkeypatch.setattr(settings, "role_reasoning_effort_enabled_raw", "true")
    monkeypatch.setattr(settings, "ollama_reasoning_effort", "")
    monkeypatch.setattr(bc, "_store", None, raising=False)


def _with_config(monkeypatch, config: BrainConfig) -> None:
    monkeypatch.setattr(bc, "_store", _StubStore(config), raising=False)


def test_built_in_map_is_the_documented_tier_map():
    assert ROLE_REASONING_EFFORTS == {
        "planner": "high",
        "executor": "medium",
        "verifier": "medium",
        "judge": "high",
    }


@pytest.mark.parametrize("role", sorted(ROLE_REASONING_EFFORTS))
def test_each_role_resolves_to_its_tier(role):
    assert resolve_role_reasoning_effort(role) == ROLE_REASONING_EFFORTS[role]


@pytest.mark.parametrize("role", [None, "", "nope"])
def test_unknown_role_resolves_to_nothing(role):
    # `""` is the documented no-op: the field is not sent at all.
    assert resolve_role_reasoning_effort(role) == ""


def test_global_pin_still_beats_the_map(monkeypatch):
    monkeypatch.setattr(settings, "ollama_reasoning_effort", "low")
    assert resolve_role_reasoning_effort("planner") == "low"
    assert resolve_role_reasoning_effort("executor") == "low"


def test_explicit_per_role_override_beats_the_global_pin(monkeypatch):
    monkeypatch.setattr(settings, "ollama_reasoning_effort", "low")
    _with_config(monkeypatch, BrainConfig(reasoning_effort_by_role={"planner": "medium"}))
    assert resolve_role_reasoning_effort("planner") == "medium"  # override wins
    assert resolve_role_reasoning_effort("executor") == "low"  # others keep the pin


def test_switch_off_restores_the_global_only_behaviour(monkeypatch):
    monkeypatch.setattr(settings, "role_reasoning_effort_enabled_raw", "false")
    assert resolve_role_reasoning_effort("planner") == ""
    monkeypatch.setattr(settings, "ollama_reasoning_effort", "low")
    assert resolve_role_reasoning_effort("planner") == "low"


def test_payload_gains_the_role_tier_for_ollama():
    payload = {"model": "north-mini-code-1.0", "messages": []}
    out = with_ollama_reasoning_effort(payload, is_ollama=True, role="planner")
    assert out["reasoning_effort"] == "high"
    assert payload == {"model": "north-mini-code-1.0", "messages": []}  # not mutated


def test_non_ollama_payload_is_the_same_object():
    payload = {"model": "gpt-5.6", "messages": []}
    assert with_ollama_reasoning_effort(payload, is_ollama=False, role="planner") is payload


def test_caller_set_effort_is_never_overwritten():
    payload = {"model": "m", "messages": [], "reasoning_effort": "low"}
    out = with_ollama_reasoning_effort(payload, is_ollama=True, role="judge")
    assert out is payload and out["reasoning_effort"] == "low"


def test_no_role_keeps_the_pre_tier_behaviour(monkeypatch):
    payload = {"model": "m", "messages": []}
    # No role, no global pin: byte-identical payload, the shipped default before tiers.
    assert with_ollama_reasoning_effort(payload, is_ollama=True) is payload
    monkeypatch.setattr(settings, "ollama_reasoning_effort", "low")
    assert with_ollama_reasoning_effort(payload, is_ollama=True)["reasoning_effort"] == "low"


def test_unknown_role_sends_no_field():
    payload = {"model": "m", "messages": []}
    assert with_ollama_reasoning_effort(payload, is_ollama=True, role="planner2") is payload


@pytest.mark.parametrize(
    "overrides",
    [{"plannner": "high"}, {"planner": "max"}, {"executor": ""}],
)
def test_invalid_overrides_are_rejected_at_save_time(overrides):
    # A typo that were silently dropped would look like the tier applied; fail instead.
    with pytest.raises(Exception):
        BrainConfig(reasoning_effort_by_role=overrides)


def test_valid_overrides_round_trip():
    config = BrainConfig(reasoning_effort_by_role={"planner": "low", "judge": "medium"})
    assert config.reasoning_effort_by_role == {"planner": "low", "judge": "medium"}


@pytest.mark.parametrize("overrides", [{"plannner": "high"}, {"planner": "max"}])
def test_patch_model_rejects_invalid_overrides(overrides):
    # The PATCH payload is validated too: set_brain_config merges with
    # model_copy(update=...), which would otherwise persist the bad mapping and
    # make the next read reject the whole brain document.
    with pytest.raises(Exception):
        bc.BrainConfigPatch(reasoning_effort_by_role=overrides)


def test_patch_model_keeps_none_and_valid_values():
    assert bc.BrainConfigPatch().reasoning_effort_by_role is None
    assert bc.BrainConfigPatch(
        reasoning_effort_by_role={"executor": "high"}
    ).reasoning_effort_by_role == {"executor": "high"}


def test_store_refuses_to_persist_an_invalid_merged_document():
    """Backstop for a patch object built without validation."""
    store = bc.BrainConfigStore()
    persisted: list[BrainConfig] = []

    async def _load() -> BrainConfig:
        return BrainConfig()

    async def _persist(config: BrainConfig) -> None:
        persisted.append(config)

    store._load_unlocked = _load  # type: ignore[method-assign]
    store._persist_unlocked = _persist  # type: ignore[method-assign]
    bad = bc.BrainConfigPatch.model_construct(
        reasoning_effort_by_role={"planner": "max"}
    )

    import asyncio

    with pytest.raises(Exception):
        asyncio.run(store.set_brain_config(bad, actor="test"))
    assert persisted == []

"""Retired models are detected from evidence and stored config moves to a live one.

Production (2026-11-12) kept calling ``nvidia/nemotron-3-super-120b-a12b`` two
weeks after NVIDIA retired it: the stored provider record still named it, and
the only thing that could move a stored config off a dead id was a hand-edited
list of dead ids in the startup migration.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from packages.ai import model_retirement as mr

DEAD = "nvidia/nemotron-3-super-120b-a12b"
LIVE = "nvidia/nemotron-3-ultra-550b-a55b"


@pytest.fixture(autouse=True)
def _clean() -> Any:
    mr.reset()
    yield
    mr.reset()


def test_a_model_that_never_failed_a_call_is_never_retired() -> None:
    # Absent from the listing alone proves nothing: ids can be spelled differently.
    assert not mr.is_retired("nvidia", DEAD, served=[LIVE])


def test_failed_calls_plus_absent_from_listing_is_retired() -> None:
    mr.record_strike("nvidia-nim", DEAD)
    assert not mr.is_retired("nvidia", DEAD, served=[LIVE]), "one 404 can be a blip"
    mr.record_strike("nvidia-nim", DEAD)
    assert mr.is_retired("nvidia", DEAD, served=[LIVE])


def test_a_listing_that_omits_the_vendor_prefix_still_counts_as_listed() -> None:
    for _ in range(mr.STRIKES_WHEN_UNLISTED):
        mr.record_strike("nvidia", "openai/gpt-oss-120b")
    assert not mr.is_retired("nvidia", "openai/gpt-oss-120b", served=["gpt-oss-120b"])


def test_replacement_never_picks_a_denied_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from packages.ai import model_policy

    monkeypatch.setattr(mr, "_catalogue", lambda provider: [DEAD, "bad-model", LIVE])
    monkeypatch.setattr(model_policy, "drop_denied", lambda ms: [m for m in ms if m != "bad-model"])
    assert mr.pick_replacement("nvidia", ["bad-model", LIVE], retired={DEAD}) == LIVE
    assert mr.pick_replacement("nvidia", ["bad-model"], retired={DEAD}) is None


def test_one_failed_call_while_still_listed_is_not_retired() -> None:
    mr.record_strike("nvidia", DEAD)
    assert not mr.is_retired("nvidia", DEAD, served=[DEAD, LIVE])


def test_one_failed_call_with_unknown_listing_is_not_retired() -> None:
    mr.record_strike("nvidia", DEAD)
    assert not mr.is_retired("nvidia", DEAD, served=None)


def test_repeated_failures_retire_a_model_the_provider_still_lists() -> None:
    for i in range(mr.STRIKES_TO_RETIRE):
        mr.record_strike("nvidia", DEAD, now=1000.0 + i * 1800)
    assert mr.is_retired("nvidia", DEAD, served=[DEAD, LIVE], now=1000.0 + 3 * 1800)


def test_old_strikes_expire() -> None:
    for i in range(mr.STRIKES_TO_RETIRE):
        mr.record_strike("nvidia", DEAD, now=1000.0 + i)
    later = 1000.0 + mr.STRIKE_WINDOW_SEC + 60
    assert mr.strikes("nvidia", DEAD, now=later) == 0
    assert not mr.is_retired("nvidia", DEAD, served=[DEAD], now=later)


def test_replacement_prefers_the_probed_catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mr, "_catalogue", lambda provider: [DEAD, LIVE, "openai/gpt-oss-20b"])
    served = ["zzz/brand-new-model", "openai/gpt-oss-20b", LIVE]
    assert mr.pick_replacement("nvidia", served, retired={DEAD}) == LIVE


def test_replacement_falls_back_to_a_served_chat_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mr, "_catalogue", lambda provider: [DEAD])
    served = ["nvidia/nv-embed-v2", "nvidia/llama-guard-4", "nvidia/nemotron-3.5-super-vl"]
    assert mr.pick_replacement("nvidia", served, retired={DEAD}) == "nvidia/nemotron-3.5-super-vl"


def test_no_replacement_when_nothing_live_is_known(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mr, "_catalogue", lambda provider: [DEAD])
    assert mr.pick_replacement("nvidia", None, retired={DEAD}) is None
    assert mr.pick_replacement("nvidia", ["nvidia/nv-embed-v2"], retired={DEAD}) is None


async def test_heal_maps_a_retired_model_to_a_live_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mr, "_catalogue", lambda provider: [DEAD, LIVE])

    async def fake_discover(probe: Any) -> list[str]:
        return [LIVE, "openai/gpt-oss-20b"]

    monkeypatch.setattr(mr, "_discover", fake_discover)
    mr.record_strike("nvidia-nim", DEAD)
    mr.record_strike("nvidia-nim", DEAD)
    probe = SimpleNamespace(id="nvidia", base_url="https://x.invalid", api_key="k")
    changed = await mr.heal_providers({"nvidia": probe})
    assert changed == {("nvidia", DEAD): LIVE}
    assert mr.live_model("nvidia-nim", DEAD) == LIVE
    assert mr.live_model("nvidia", LIVE) == LIVE
    assert mr.live_model("groq", DEAD) == DEAD, "a retirement is per provider"


async def test_heal_leaves_config_alone_when_discovery_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_discover(probe: Any) -> None:
        return None

    monkeypatch.setattr(mr, "_discover", fake_discover)
    mr.record_strike("nvidia", DEAD)
    probe = SimpleNamespace(id="nvidia", base_url="https://x.invalid", api_key="k")
    assert await mr.heal_providers({"nvidia": probe}) == {}
    assert mr.live_model("nvidia", DEAD) == DEAD


async def test_heal_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(probe: Any) -> list[str]:
        raise RuntimeError("network down")

    monkeypatch.setattr(mr, "_discover", boom)
    mr.record_strike("nvidia", DEAD)
    probe = SimpleNamespace(id="nvidia", base_url="https://x.invalid", api_key="k")
    assert await mr.heal_providers({"nvidia": probe}) == {}


def test_brain_patch_rewrites_only_retired_roles() -> None:
    mr._REPLACEMENTS[("nvidia", DEAD)] = LIVE
    cfg = SimpleNamespace(
        primary_provider="nvidia", planner_model=DEAD, executor_model="qwen/other",
        verifier_model=DEAD, judge_model=LIVE,
    )
    assert mr.brain_patch_fields(cfg) == {"planner_model": LIVE, "verifier_model": LIVE}


def test_brain_patch_is_empty_when_nothing_is_retired() -> None:
    cfg = SimpleNamespace(
        primary_provider="nvidia", planner_model=LIVE, executor_model=LIVE,
        verifier_model=LIVE, judge_model=LIVE,
    )
    assert mr.brain_patch_fields(cfg) == {}


def test_router_and_discovery_dead_marks_record_strikes() -> None:
    from packages.ai import model_discovery, router

    router._mark_model_dead("nvidia-nim", DEAD, ttl_sec=1, reason="404 Not Found")
    model_discovery.mark_dead("groq", "openai/old-model", ttl_sec=1)
    try:
        assert mr.strikes("nvidia", DEAD) == 1
        assert mr.strikes("groq", "openai/old-model") == 1
    finally:
        router._dead_models.clear()
        model_discovery.reset_cache()


def test_auto_heal_follows_the_platform_control(monkeypatch: pytest.MonkeyPatch) -> None:
    from packages.config import settings

    monkeypatch.setattr(settings, "model_auto_heal_raw", "false", raising=False)
    assert mr.auto_heal_enabled() is False
    monkeypatch.setattr(settings, "model_auto_heal_raw", "true", raising=False)
    assert mr.auto_heal_enabled() is True


def test_control_is_registered_live() -> None:
    from packages.config.control_catalogue import CONTROLS

    spec = next(c for c in CONTROLS if c.key == "MODEL_AUTO_HEAL_ENABLED")
    assert spec.live is True
    assert spec.default == "true"


def test_provider_records_resolve_a_retired_default_model(monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.server as server

    mr._REPLACEMENTS[("nvidia", DEAD)] = LIVE
    records = [
        {"provider_id": "nvidia-nim", "default_model": DEAD},
        {"provider_id": "groq", "default_model": DEAD},
        {"provider_id": "ollama"},
    ]
    healed = server._with_live_default_models(records)
    assert [r.get("default_model") for r in healed] == [LIVE, DEAD, None]
    assert records[0]["default_model"] == DEAD, "the stored record is not mutated"

    monkeypatch.setattr(mr, "auto_heal_enabled", lambda: False)
    assert server._with_live_default_models(records)[0]["default_model"] == DEAD


async def test_heal_once_does_nothing_when_switched_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mr, "auto_heal_enabled", lambda: False)
    mr.record_strike("nvidia", DEAD)
    assert await mr.heal_once({}) == {}

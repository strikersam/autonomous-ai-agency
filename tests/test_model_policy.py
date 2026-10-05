"""Operator model deny-list — DENIED_MODEL_IDS (#1611, item 3).

Every existing guard against a bad model id is reactive: a 410 marks a model
dead after a request failed, and the catalogue probe benches retired models
after the fact. DENIED_MODEL_IDS lets an operator block an id before it is ever
dispatched, from Settings → Platform controls, without a redeploy.
"""
from __future__ import annotations

import asyncio
import os

import pytest

from packages.ai import model_policy
from packages.config import control_overrides
from packages.config.control_registry import coerce, get_control


@pytest.fixture
def denied(monkeypatch):
    """Set DENIED_MODEL_IDS on the settings singleton for one test."""
    from packages.config import settings

    def _set(value: str) -> None:
        monkeypatch.setattr(settings, "denied_model_ids_raw", value)

    return _set


class TestMatching:
    def test_nothing_denied_by_default(self) -> None:
        from packages.config import settings

        assert settings.denied_model_patterns == ()
        assert model_policy.is_model_denied("gpt-6-sol") is False

    def test_exact_case_insensitive_and_glob(self, denied) -> None:
        denied(" GPT-6-Sol , claude-opus-* ")
        assert model_policy.is_model_denied("gpt-6-sol")
        assert model_policy.is_model_denied("Claude-Opus-5-5")
        assert not model_policy.is_model_denied("claude-sonnet-5")
        assert not model_policy.is_model_denied("")

    def test_drop_denied_keeps_order(self, denied) -> None:
        denied("b")
        assert model_policy.drop_denied(["a", "b", "c"]) == ["a", "c"]


def _provider(default_model: str = "m-default"):
    from packages.ai.router import ProviderConfig

    return ProviderConfig(
        provider_id="p1", type="openai-compatible", base_url="https://example.test",
        api_key="k", default_model=default_model,
    )


class TestDispatch:
    def _candidates(self, original, fallbacks, provider=None):
        from packages.ai.router import ProviderRouter

        router = ProviderRouter.__new__(ProviderRouter)
        return router._candidate_models(provider or _provider(), original, fallbacks, True)

    def test_unchanged_when_nothing_is_denied(self) -> None:
        assert self._candidates("m1", ["m2"]) == ["m1", "m2", "m-default"]

    def test_denied_requested_model_is_skipped(self, denied) -> None:
        denied("m1")
        assert self._candidates("m1", ["m2"]) == ["m2", "m-default"]

    def test_all_configured_denied_falls_back_to_allowed_catalogue(self, denied, monkeypatch) -> None:
        from packages.ai import router as ai_router

        denied("m1,m-default")
        monkeypatch.setattr(ai_router, "_catalogue_models", lambda p: ["m-default", "m-cat"])
        assert self._candidates("m1", []) == ["m-cat"]

    def test_everything_denied_skips_the_provider_without_a_cooldown(self, denied, monkeypatch) -> None:
        from packages.ai import router as ai_router
        from packages.ai.router import ProviderRouter

        denied("*")
        failed: list[str] = []

        async def _mark(provider_id, *a, **k):
            failed.append(provider_id)

        monkeypatch.setattr(ai_router, "mark_provider_failed", _mark)
        monkeypatch.setattr(ai_router, "_catalogue_models", lambda p: ["m-cat"])
        router = ProviderRouter.__new__(ProviderRouter)
        attempts: list = []
        result = asyncio.run(router._try_one_provider(
            _provider(), {"messages": []}, "m1", [], True, 0, attempts, 5.0,
        ))
        assert result is None and attempts == [] and failed == []


def _decision(resolved: str, chain: list[str]):
    from router.model_router import RoutingDecision

    return RoutingDecision(
        resolved_model=resolved, requested_model=resolved, mode="auto",
        routing_reason="test", task_category="general", selection_source="heuristic",
        fallback_chain=chain,
    )


class TestModelRouter:
    def test_denied_resolved_model_moves_to_the_next_allowed(self, denied) -> None:
        from router.model_router import _apply_deny_list

        denied("m1")
        out = _apply_deny_list(_decision("m1", ["m2", "m3"]))
        assert out.resolved_model == "m2" and out.fallback_chain == ["m3"]

    def test_all_denied_keeps_a_non_empty_model(self, denied) -> None:
        from router.model_router import _apply_deny_list

        denied("*")
        assert _apply_deny_list(_decision("m1", ["m2"])).resolved_model == "m1"  # rule 21

    def test_route_applies_the_list(self, denied) -> None:
        from router.model_router import get_router

        decision = get_router().route(override_model="m-over")
        denied(decision.resolved_model)
        out = get_router().route(override_model="m-over")
        assert out.resolved_model and out.resolved_model != "m-over"


class TestControl:
    def test_is_a_live_text_control(self) -> None:
        spec = get_control("DENIED_MODEL_IDS")
        assert spec is not None and spec.kind == "text" and spec.live is True

    def test_coerce_normalises_and_dedupes(self) -> None:
        assert coerce("DENIED_MODEL_IDS", " a , b,a,, nvidia/x-1:free ") == "a,b,nvidia/x-1:free"

    @pytest.mark.parametrize("bad", ["a b", "x;rm", "'quoted'"])
    def test_coerce_rejects_junk(self, bad) -> None:
        with pytest.raises(ValueError):
            coerce("DENIED_MODEL_IDS", bad)

    def test_an_override_takes_effect_live(self) -> None:
        before = os.environ.get("DENIED_MODEL_IDS")
        applied = dict(control_overrides._applied)
        try:
            control_overrides.apply_overrides({"DENIED_MODEL_IDS": "gpt-6-sol"})
            assert model_policy.is_model_denied("gpt-6-sol")
            control_overrides.apply_overrides({})  # dropping the override restores env
            assert not model_policy.is_model_denied("gpt-6-sol")
        finally:
            if before is None:
                os.environ.pop("DENIED_MODEL_IDS", None)
            else:
                os.environ["DENIED_MODEL_IDS"] = before
            control_overrides._applied.clear()
            control_overrides._applied.update(applied)

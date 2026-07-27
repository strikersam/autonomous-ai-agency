"""Tests for packages/ai/traffic_director.py — traffic distribution across
providers (LiteLLM-style routing strategies + pre-call budget checks) and its
integration into packages/ai/router.py."""

from __future__ import annotations

import time
from typing import Iterator

import httpx
import pytest

from packages.ai import traffic_director as td
from packages.ai.traffic_director import TrafficDirector, get_director


@pytest.fixture(autouse=True)
def _clean_director() -> Iterator[None]:
    """Reset the process singleton around every test."""
    td.reset()
    yield
    td.reset()


class _P:
    """Minimal provider stand-in — the director only needs ``provider_id``."""

    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"_P({self.provider_id})"


def _ids(providers: list) -> list[str]:
    return [td.provider_id_of(p) for p in providers]


# ---------------------------------------------------------------------------
# active_strategy
# ---------------------------------------------------------------------------

class TestActiveStrategy:
    def test_defaults_to_priority(self, monkeypatch) -> None:
        monkeypatch.delenv("LLM_ROUTING_STRATEGY", raising=False)
        assert td.active_strategy() == td.STRATEGY_PRIORITY

    @pytest.mark.parametrize("name", sorted(td.KNOWN_STRATEGIES))
    def test_known_strategies_pass_through(self, monkeypatch, name: str) -> None:
        monkeypatch.setenv("LLM_ROUTING_STRATEGY", name)
        assert td.active_strategy() == name

    def test_case_and_whitespace_insensitive(self, monkeypatch) -> None:
        monkeypatch.setenv("LLM_ROUTING_STRATEGY", "  LEAST-BUSY  ")
        assert td.active_strategy() == td.STRATEGY_LEAST_BUSY

    def test_unknown_strategy_falls_back_to_priority(self, monkeypatch) -> None:
        """A typo must not silently pick some other distribution."""
        monkeypatch.setenv("LLM_ROUTING_STRATEGY", "round-robin-ish")
        assert td.active_strategy() == td.STRATEGY_PRIORITY


# ---------------------------------------------------------------------------
# ordering
# ---------------------------------------------------------------------------

class TestOrdering:
    def test_priority_strategy_preserves_order_exactly(self, monkeypatch) -> None:
        monkeypatch.setenv("LLM_ROUTING_STRATEGY", "priority")
        d = TrafficDirector()
        providers = [_P("a"), _P("b"), _P("c")]
        # Even with wildly different load, priority order is untouched.
        for _ in range(50):
            d.record_start("a")
        assert _ids(d.order(providers, group_key=lambda p: 0)) == ["a", "b", "c"]

    def test_single_provider_is_never_reordered(self, monkeypatch) -> None:
        monkeypatch.setenv("LLM_ROUTING_STRATEGY", "least-busy")
        d = TrafficDirector()
        assert _ids(d.order([_P("solo")], group_key=lambda p: 0)) == ["solo"]

    def test_least_busy_puts_idle_provider_first(self, monkeypatch) -> None:
        monkeypatch.setenv("LLM_ROUTING_STRATEGY", "least-busy")
        d = TrafficDirector()
        d.record_start("busy")
        d.record_start("busy")
        d.record_start("mid")
        ordered = _ids(d.order([_P("busy"), _P("mid"), _P("idle")], group_key=lambda p: 0))
        assert ordered == ["idle", "mid", "busy"]

    def test_usage_based_prefers_the_provider_with_headroom(self, monkeypatch) -> None:
        monkeypatch.setenv("LLM_ROUTING_STRATEGY", "usage-based")
        monkeypatch.setenv("HOT_MAX_RPM", "10")
        monkeypatch.setenv("COOL_MAX_RPM", "10")
        d = TrafficDirector()
        for _ in range(8):
            d.record_start("hot")
            d.record_end("hot", latency_ms=5)
        d.record_start("cool")
        d.record_end("cool", latency_ms=5)
        ordered = _ids(d.order([_P("hot"), _P("cool")], group_key=lambda p: 0))
        assert ordered == ["cool", "hot"]

    def test_usage_based_demotes_a_recently_rate_limited_provider(
        self, monkeypatch
    ) -> None:
        monkeypatch.setenv("LLM_ROUTING_STRATEGY", "usage-based")
        d = TrafficDirector()
        # "burned" is otherwise the least-used provider, but it just 429'd.
        d.record_start("burned")
        d.record_end("burned", latency_ms=5, status_code=429)
        for _ in range(3):
            d.record_start("fine")
            d.record_end("fine", latency_ms=5)
        ordered = _ids(d.order([_P("burned"), _P("fine")], group_key=lambda p: 0))
        assert ordered == ["fine", "burned"]

    def test_latency_based_prefers_the_fast_provider(self, monkeypatch) -> None:
        monkeypatch.setenv("LLM_ROUTING_STRATEGY", "latency-based")
        d = TrafficDirector()
        for _ in range(5):
            d.record_start("slow")
            d.record_end("slow", latency_ms=4000)
            d.record_start("fast")
            d.record_end("fast", latency_ms=120)
        ordered = _ids(d.order([_P("slow"), _P("fast")], group_key=lambda p: 0))
        assert ordered == ["fast", "slow"]

    def test_latency_based_tries_an_unsampled_provider_first(self, monkeypatch) -> None:
        """A provider with no latency sample must be able to earn one."""
        monkeypatch.setenv("LLM_ROUTING_STRATEGY", "latency-based")
        d = TrafficDirector()
        d.record_start("known")
        d.record_end("known", latency_ms=100)
        ordered = _ids(d.order([_P("known"), _P("unknown")], group_key=lambda p: 0))
        assert ordered[0] == "unknown"

    def test_reordering_never_crosses_a_group_boundary(self, monkeypatch) -> None:
        """The safety invariant: a shuffle may not promote a paid provider
        ahead of the free tier, whatever the load numbers say."""
        monkeypatch.setenv("LLM_ROUTING_STRATEGY", "least-busy")
        d = TrafficDirector()
        for _ in range(20):
            d.record_start("free-a")
            d.record_start("free-b")
        tiers = {"free-a": 0, "free-b": 0, "paid-a": 4, "paid-b": 4}
        providers = [_P("free-a"), _P("free-b"), _P("paid-a"), _P("paid-b")]
        ordered = _ids(
            d.order(providers, group_key=lambda p: tiers[td.provider_id_of(p)])
        )
        assert set(ordered[:2]) == {"free-a", "free-b"}
        assert set(ordered[2:]) == {"paid-a", "paid-b"}

    def test_cold_start_ties_are_broken_randomly(self, monkeypatch) -> None:
        """With every provider idle a stable sort would send the whole burst to
        the first one — the pile-up this module exists to prevent."""
        monkeypatch.setenv("LLM_ROUTING_STRATEGY", "least-busy")
        d = TrafficDirector()
        providers = [_P("a"), _P("b"), _P("c")]
        firsts = {
            _ids(d.order(providers, group_key=lambda p: 0))[0] for _ in range(60)
        }
        assert len(firsts) > 1

    def test_weighted_shuffle_respects_explicit_weights(self, monkeypatch) -> None:
        monkeypatch.setenv("LLM_ROUTING_STRATEGY", "weighted-shuffle")
        monkeypatch.setenv("HEAVY_WEIGHT", "20")
        monkeypatch.setenv("LIGHT_WEIGHT", "1")
        d = TrafficDirector()
        providers = [_P("light"), _P("heavy")]
        heavy_first = sum(
            _ids(d.order(providers, group_key=lambda p: 0))[0] == "heavy"
            for _ in range(300)
        )
        # Expected ~286/300; a very loose bound keeps this from flaking.
        assert heavy_first > 200

    def test_weighted_shuffle_returns_every_provider(self, monkeypatch) -> None:
        monkeypatch.setenv("LLM_ROUTING_STRATEGY", "weighted-shuffle")
        d = TrafficDirector()
        providers = [_P(f"p{i}") for i in range(6)]
        ordered = _ids(d.order(providers, group_key=lambda p: 0))
        assert sorted(ordered) == sorted(_ids(providers))

    def test_weighted_shuffle_falls_back_to_rpm_headroom(self, monkeypatch) -> None:
        """No explicit weights: the provider that has spent less of its minute
        should be picked first more often."""
        monkeypatch.setenv("LLM_ROUTING_STRATEGY", "weighted-shuffle")
        monkeypatch.setenv("SPENT_MAX_RPM", "20")
        monkeypatch.setenv("FRESH_MAX_RPM", "20")
        d = TrafficDirector()
        for _ in range(19):
            d.record_start("spent")
            d.record_end("spent", latency_ms=1)
        providers = [_P("spent"), _P("fresh")]
        fresh_first = sum(
            _ids(d.order(providers, group_key=lambda p: 0))[0] == "fresh"
            for _ in range(300)
        )
        assert fresh_first > 200


# ---------------------------------------------------------------------------
# usage accounting
# ---------------------------------------------------------------------------

class TestAccounting:
    def test_in_flight_tracks_start_and_end(self) -> None:
        d = TrafficDirector()
        d.record_start("p")
        d.record_start("p")
        assert d.snapshot()["providers"]["p"]["in_flight"] == 2
        d.record_end("p", latency_ms=10)
        assert d.snapshot()["providers"]["p"]["in_flight"] == 1

    def test_in_flight_never_goes_negative(self) -> None:
        d = TrafficDirector()
        d.record_end("p", latency_ms=10)
        assert d.snapshot()["providers"]["p"]["in_flight"] == 0

    def test_requests_outside_the_window_are_pruned(self) -> None:
        d = TrafficDirector()
        d.record_start("p")
        d.record_end("p", latency_ms=1, tokens=500)
        usage = d._usage["p"]
        # Backdate the recorded events past the 60s window.
        old = time.monotonic() - (td._WINDOW_SECONDS + 5)
        usage.request_times[0] = old
        usage.token_events[0] = (old, 500)
        snap = d.snapshot()["providers"]["p"]
        assert snap["requests_in_window"] == 0
        assert snap["tokens_in_window"] == 0

    def test_ewma_latency_moves_toward_recent_samples(self) -> None:
        d = TrafficDirector()
        d.record_start("p")
        d.record_end("p", latency_ms=1000)
        assert d._usage["p"].ewma_latency_ms == 1000.0
        d.record_start("p")
        d.record_end("p", latency_ms=0)
        assert 0.0 < d._usage["p"].ewma_latency_ms < 1000.0

    def test_snapshot_reports_the_active_strategy(self, monkeypatch) -> None:
        monkeypatch.setenv("LLM_ROUTING_STRATEGY", "usage-based")
        assert get_director().snapshot()["strategy"] == "usage-based"


# ---------------------------------------------------------------------------
# pre-call budget checks
# ---------------------------------------------------------------------------

class TestOverBudget:
    def test_unconfigured_provider_is_never_over_budget(self) -> None:
        d = TrafficDirector()
        for _ in range(500):
            d.record_start("p")
        assert d.over_budget("p") is None

    def test_unknown_provider_is_never_over_budget(self) -> None:
        assert TrafficDirector().over_budget("never-seen") is None

    def test_rpm_budget_blocks_once_spent(self, monkeypatch) -> None:
        monkeypatch.setenv("P_MAX_RPM", "3")
        d = TrafficDirector()
        for _ in range(2):
            d.record_start("p")
            d.record_end("p", latency_ms=1)
        assert d.over_budget("p") is None
        d.record_start("p")
        d.record_end("p", latency_ms=1)
        assert "rpm" in (d.over_budget("p") or "")

    def test_tpm_budget_blocks_once_spent(self, monkeypatch) -> None:
        monkeypatch.setenv("P_MAX_TPM", "1000")
        d = TrafficDirector()
        d.record_start("p")
        d.record_end("p", latency_ms=1, tokens=600)
        assert d.over_budget("p") is None
        assert "tpm" in (d.over_budget("p", estimated_tokens=500) or "")

    def test_max_parallel_blocks_at_the_concurrency_ceiling(self, monkeypatch) -> None:
        monkeypatch.setenv("P_MAX_PARALLEL", "2")
        d = TrafficDirector()
        d.record_start("p")
        assert d.over_budget("p") is None
        d.record_start("p")
        assert "max-parallel" in (d.over_budget("p") or "")
        d.record_end("p", latency_ms=1)
        assert d.over_budget("p") is None

    def test_budget_frees_up_when_the_window_rolls(self, monkeypatch) -> None:
        monkeypatch.setenv("P_MAX_RPM", "1")
        d = TrafficDirector()
        d.record_start("p")
        d.record_end("p", latency_ms=1)
        assert d.over_budget("p") is not None
        d._usage["p"].request_times[0] = time.monotonic() - (td._WINDOW_SECONDS + 1)
        assert d.over_budget("p") is None

    def test_provider_id_with_dashes_reads_the_underscore_env_var(
        self, monkeypatch
    ) -> None:
        """`NVIDIA-NIM_MAX_RPM` is not settable in most shells; the underscore
        form must work for the router's real, dashed provider ids."""
        monkeypatch.setenv("NVIDIA_NIM_MAX_RPM", "1")
        d = TrafficDirector()
        d.record_start("nvidia-nim")
        d.record_end("nvidia-nim", latency_ms=1)
        assert "rpm" in (d.over_budget("nvidia-nim") or "")


# ---------------------------------------------------------------------------
# router integration
# ---------------------------------------------------------------------------

class TestRouterIntegration:
    @pytest.fixture(autouse=True)
    async def _reset_router_state(self):
        from packages.ai.router import clear_cooldowns

        await clear_cooldowns()
        try:
            from services.shared_state import clear_all_locks

            await clear_all_locks()
        except Exception:
            pass
        yield
        await clear_cooldowns()

    @staticmethod
    def _router(monkeypatch, calls: list[str]):
        from packages.ai.router import ProviderConfig, ProviderRouter

        async def fake_post_chat(self, provider, payload, timeout_sec):
            calls.append(provider.provider_id)
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 10},
                },
                headers={"content-type": "application/json"},
            )

        monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
        return ProviderRouter(
            [
                ProviderConfig(
                    "groq", "openai-compatible", "https://api.groq.com/openai/v1",
                    api_key="k1", default_model="m1", priority=0,
                ),
                ProviderConfig(
                    "cerebras", "openai-compatible", "https://api.cerebras.ai/v1",
                    api_key="k2", default_model="m2", priority=1,
                ),
            ]
        )

    @staticmethod
    def _payload(text: str) -> dict:
        # Distinct content per call so the response cache never short-circuits
        # a request we are asserting about.
        return {"model": "m1", "messages": [{"role": "user", "content": text}]}

    @pytest.mark.anyio
    async def test_over_budget_provider_is_skipped_for_a_sibling(
        self, monkeypatch
    ) -> None:
        """The behaviour this whole change exists for: once the first free
        provider has spent its configured minute, the next request goes to the
        sibling instead of collecting a 429."""
        monkeypatch.delenv("LLM_ROUTING_STRATEGY", raising=False)
        monkeypatch.setenv("GROQ_MAX_RPM", "1")
        calls: list[str] = []
        router = self._router(monkeypatch, calls)

        first = await router.chat_completion(self._payload("one"), max_retries=0)
        second = await router.chat_completion(self._payload("two"), max_retries=0)

        assert first.provider.provider_id == "groq"
        assert second.provider.provider_id == "cerebras"
        assert calls == ["groq", "cerebras"]

    @pytest.mark.anyio
    async def test_default_config_keeps_strict_priority_order(
        self, monkeypatch
    ) -> None:
        """No strategy and no budgets configured — behaviour is unchanged."""
        monkeypatch.delenv("LLM_ROUTING_STRATEGY", raising=False)
        monkeypatch.delenv("GROQ_MAX_RPM", raising=False)
        calls: list[str] = []
        router = self._router(monkeypatch, calls)

        for i in range(4):
            result = await router.chat_completion(
                self._payload(f"msg-{i}"), max_retries=0
            )
            assert result.provider.provider_id == "groq"
        assert calls == ["groq"] * 4

    @pytest.mark.anyio
    async def test_router_records_usage_against_the_director(
        self, monkeypatch
    ) -> None:
        monkeypatch.delenv("LLM_ROUTING_STRATEGY", raising=False)
        calls: list[str] = []
        router = self._router(monkeypatch, calls)

        await router.chat_completion(self._payload("accounted"), max_retries=0)

        stats = get_director().snapshot()["providers"]["groq"]
        assert stats["total_requests"] == 1
        assert stats["in_flight"] == 0  # record_end ran in the finally
        assert stats["tokens_in_window"] == 20

    @pytest.mark.anyio
    async def test_sole_provider_is_never_skipped_for_being_over_budget(
        self, monkeypatch
    ) -> None:
        """With nowhere to route, skipping would turn a slow request into a
        failed one — pacing, not skipping, is the right tool there."""
        from packages.ai.router import ProviderConfig, ProviderRouter

        monkeypatch.setenv("SOLO_MAX_RPM", "1")
        calls: list[str] = []

        async def fake_post_chat(self, provider, payload, timeout_sec):
            calls.append(provider.provider_id)
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "ok"}}]},
                headers={"content-type": "application/json"},
            )

        monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
        router = ProviderRouter(
            [
                ProviderConfig(
                    "solo", "openai-compatible", "https://example.com/v1",
                    api_key="k", default_model="m", priority=0,
                )
            ]
        )

        await router.chat_completion(self._payload("solo-1"), max_retries=0)
        result = await router.chat_completion(self._payload("solo-2"), max_retries=0)

        assert result.provider.provider_id == "solo"
        assert calls == ["solo", "solo"]

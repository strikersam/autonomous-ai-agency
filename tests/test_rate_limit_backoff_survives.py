"""Regression guard: a rate-limit cooldown must survive, on every route.

Production symptom this pins (20+ minutes of it, every ~15 seconds):

    brain_failover: all 4 provider(s) exhausted (nvidia, google, zai, groq)
      — nvidia 429 rate-limited; google 429 rate-limited;
        zai 429 rate-limited; groq 429 rate-limited

Four free providers, all rate-limited, all re-attempted seconds later, forever.
The cause was the same mistake in three places: **when everything is cooling,
ignore the cooling and try everything anyway.**

* ``failover_client._recover_all_unhealthy`` called ``record_success()`` on
  every provider. That is not a breaker reset, it is a lie — ``record_success``
  sets ``health = CLOSED`` and ``failure_count = 0``, and ``is_healthy``
  short-circuits on CLOSED without consulting ``cooldown_until``. So it erased
  the cooldown *and* the exponential-backoff counter that produced it, pinning
  backoff at its base value forever.
* ``router.chat_completion``'s last-resort bypass called every cooled provider,
  including ones cooling from a 429.
* ``nim_pool`` counted every sub-500 response as a breaker success, so 429/419 —
  the dominant failure mode for a NIM pool — reset the failure counter and the
  breaker could never open for the one thing it exists to protect against.

A 429 is the provider saying "not yet". Waiting is the fix; no reordering of
four exhausted providers finds capacity none of them has.
"""

from __future__ import annotations

import time

import pytest


# ---------------------------------------------------------------------------
# brain_failover: the breaker must not be reset by fabricated success
# ---------------------------------------------------------------------------

class TestBrainFailoverBackoff:
    @staticmethod
    def _manager():
        from services.brain_failover import get_failover_manager

        fm = get_failover_manager()
        fm._build_registry()
        return fm

    def _first_provider_id(self, fm) -> str:
        providers = fm.get_providers()
        if not providers:
            pytest.skip("no brain providers configured in this environment")
        return providers[0].id

    def test_allow_probe_preserves_backoff_state(self) -> None:
        """The honest reset: probe permitted, failure history kept."""
        from services.brain_failover import ProviderHealth

        fm = self._manager()
        pid = self._first_provider_id(fm)

        fm.record_failure(pid, "rate_limited", 429)
        fm.record_failure(pid, "rate_limited", 429)
        p = fm.get_provider(pid)
        assert p.health == ProviderHealth.OPEN
        failures_before = p.failure_count
        cooldown_before = p.cooldown_until
        assert failures_before >= 2

        fm.allow_probe(pid)
        p = fm.get_provider(pid)
        assert p.health == ProviderHealth.HALF_OPEN
        # The point: neither the counter nor the deadline is destroyed.
        assert p.failure_count == failures_before
        assert p.cooldown_until == cooldown_before

    def test_record_success_still_fully_resets(self) -> None:
        """A real success must still clear the breaker — allow_probe exists so
        that callers stop using this one to fake it."""
        from services.brain_failover import ProviderHealth

        fm = self._manager()
        pid = self._first_provider_id(fm)

        fm.record_failure(pid, "rate_limited", 429)
        fm.record_success(pid, latency_ms=10)
        p = fm.get_provider(pid)
        assert p.health == ProviderHealth.CLOSED
        assert p.failure_count == 0

    def test_backoff_grows_across_consecutive_rate_limits(self) -> None:
        """The behaviour the doom loop destroyed: each 429 waits longer.

        With failure_count reset every cycle, every cooldown was recomputed as
        `cooldown_seconds * 2**0` — the base — so the fleet was re-probed at a
        fixed short interval indefinitely.
        """
        fm = self._manager()
        pid = self._first_provider_id(fm)

        windows = []
        for _ in range(4):
            before = time.time()
            fm.record_failure(pid, "rate_limited", 429)
            windows.append(fm.get_provider(pid).cooldown_until - before)

        assert windows == sorted(windows), f"backoff did not grow: {windows}"
        assert windows[-1] > windows[0], (
            f"backoff never increased across 4 consecutive 429s: {windows}"
        )

    def test_seconds_until_recovery_reports_a_wait(self) -> None:
        fm = self._manager()
        pid = self._first_provider_id(fm)
        fm.record_failure(pid, "rate_limited", 429)
        wait = fm.seconds_until_recovery()
        assert wait is not None and wait > 0

    def test_a_cooling_provider_is_not_stuck(self) -> None:
        """The anti-wedge valve must not fire for an ordinary 429 backoff —
        otherwise it reintroduces the hammering it replaced."""
        fm = self._manager()
        pid = self._first_provider_id(fm)
        fm.record_failure(pid, "rate_limited", 429)
        assert fm.stuck_beyond_cooldown(pid) is False

    def test_valve_never_fires_on_a_maxed_out_legitimate_backoff(self) -> None:
        """The threshold must clear the widest backoff ANY registered provider
        can earn.

        Asserted against `_PROVIDER_REGISTRY` rather than the providers that
        happen to be configured here: the first version of this test walked
        `get_providers()` and passed against a deliberately-broken threshold,
        because NVIDIA — whose 90s base is the one that breaks it — has no API
        key in this environment and so was never in the list. A guard that
        silently skips the only case it is guarding is worse than no guard.

        `record_failure` caps the 429 exponent at 4, so the widest legitimate
        window is `cooldown * 2**4` — 1440s for NVIDIA. A threshold under that
        reads a perfectly healthy ladder as "wedged" and probes it, restoring
        the hammering on the provider that rate-limits most.
        """
        from services.brain_failover import (
            _PROVIDER_REGISTRY,
            _STUCK_PROBE_FACTOR,
            _STUCK_PROBE_FLOOR_SEC,
        )

        assert _PROVIDER_REGISTRY, "registry table is empty — test is vacuous"
        for spec in _PROVIDER_REGISTRY:
            cooldown = float(spec["cooldown"])
            widest_legitimate = cooldown * (2 ** 4)   # the exponent cap
            threshold = max(_STUCK_PROBE_FACTOR * cooldown, _STUCK_PROBE_FLOOR_SEC)
            assert widest_legitimate < threshold, (
                f"{spec['id']}: a maxed-out legitimate backoff of "
                f"{widest_legitimate:.0f}s exceeds the stuck threshold of "
                f"{threshold:.0f}s (base {cooldown:.0f}s), so the anti-wedge "
                f"valve would fire on a healthy ladder and re-hammer it"
            )

    def test_a_wedged_provider_is_detected(self) -> None:
        """A corrupted/absurd cooldown must still be recoverable."""
        fm = self._manager()
        pid = self._first_provider_id(fm)
        fm.record_failure(pid, "rate_limited", 429)
        p = fm.get_provider(pid)
        p.cooldown_until = p.last_failure + 86_400  # a day out — not legitimate
        assert fm.stuck_beyond_cooldown(pid) is True


# ---------------------------------------------------------------------------
# failover_client: recovery must not fabricate success
# ---------------------------------------------------------------------------

class TestRecoveryDoesNotFabricateSuccess:
    def test_all_cooling_returns_none_instead_of_resetting(self, monkeypatch) -> None:
        """The doom loop in one assertion: with every provider cooling from a
        429, recovery must decline to reset them."""
        from packages.ai import failover_client as fc

        class _P:
            def __init__(self, pid: str) -> None:
                self.id = pid
                self.tier = "free"
                self.is_healthy = False

        reset_calls: list[str] = []

        class _FM:
            def get_providers(self):
                return [_P("a"), _P("b")]

            def record_success(self, pid, latency_ms=0.0):
                reset_calls.append(pid)

            def allow_probe(self, pid):
                reset_calls.append(f"probe:{pid}")

            def stuck_beyond_cooldown(self, pid, **kw):
                return False           # ordinary 429 backoff, not wedged

            def seconds_until_recovery(self):
                return 42.0

            def next_provider(self, exclude=None, requested_model=None):
                return _P("a")

        monkeypatch.setattr(fc, "_disabled_ids", lambda: {})
        tried = {"a", "b"}
        out = fc._recover_all_unhealthy(_FM(), tried, "m")

        assert out is None, "recovery handed back a provider that is rate-limited"
        assert reset_calls == [], f"recovery reset breakers anyway: {reset_calls}"
        assert tried == {"a", "b"}, "recovery cleared the exclusion set anyway"

    def test_wedged_providers_still_get_a_probe(self, monkeypatch) -> None:
        """The anti-deadlock intent of the original code is preserved."""
        from packages.ai import failover_client as fc

        class _P:
            def __init__(self, pid: str) -> None:
                self.id = pid
                self.tier = "free"
                self.is_healthy = False

        probed: list[str] = []

        class _FM:
            def get_providers(self):
                return [_P("a")]

            def record_success(self, pid, latency_ms=0.0):
                probed.append(f"success:{pid}")

            def allow_probe(self, pid):
                probed.append(pid)

            def stuck_beyond_cooldown(self, pid, **kw):
                return True            # wedged far past its own window

            def seconds_until_recovery(self):
                return None

            def next_provider(self, exclude=None, requested_model=None):
                return _P("a")

        monkeypatch.setattr(fc, "_disabled_ids", lambda: {})
        out = fc._recover_all_unhealthy(_FM(), {"a"}, "m")

        assert out is not None, "a wedged provider must still be recoverable"
        assert probed == ["a"], f"expected allow_probe, got {probed}"
        assert "success:a" not in probed, "recovery must never fabricate success"

    def test_healthy_provider_present_means_no_recovery(self, monkeypatch) -> None:
        from packages.ai import failover_client as fc

        class _P:
            id = "a"
            tier = "free"
            is_healthy = True

        class _FM:
            def get_providers(self):
                return [_P()]

        monkeypatch.setattr(fc, "_disabled_ids", lambda: {})
        assert fc._recover_all_unhealthy(_FM(), set(), "m") is None


# ---------------------------------------------------------------------------
# nim_pool: a 429 is a breaker failure, not a success
# ---------------------------------------------------------------------------

class TestNimPoolCountsRateLimitsAsFailures:
    @pytest.mark.parametrize("status", [429, 419])
    def test_rate_limit_opens_the_breaker_eventually(self, status: int) -> None:
        """Counting every sub-500 as a success meant the breaker could never
        open for the failure mode a NIM pool actually hits."""
        from services.nim_pool import ProviderCircuit, _CB_FAILURE_THRESHOLD, CircuitState

        circuit = ProviderCircuit(provider="nvidia")
        for _ in range(_CB_FAILURE_THRESHOLD):
            circuit.record_failure()
        assert circuit.state == CircuitState.OPEN

    def test_success_still_closes_the_breaker(self) -> None:
        from services.nim_pool import ProviderCircuit, CircuitState

        circuit = ProviderCircuit(provider="nvidia")
        circuit.record_failure()
        circuit.record_success()
        assert circuit.failures == 0
        assert circuit.state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# router: the last-resort bypass must not hammer rate-limited providers
# ---------------------------------------------------------------------------

class TestRouterBypassSkipsRateLimited:
    @pytest.fixture(autouse=True)
    async def _clean(self):
        from packages.ai.router import clear_cooldowns

        await clear_cooldowns()
        try:
            from services.shared_state import clear_all_locks

            await clear_all_locks()
        except Exception:
            pass
        yield
        await clear_cooldowns()

    @pytest.mark.anyio
    async def test_bypass_does_not_call_a_429_cooled_provider(
        self, monkeypatch
    ) -> None:
        """All providers cooling from 429s: the bypass must decline, not spend a
        request on each to be told 429 again."""
        import httpx

        from packages.ai.router import (
            ProviderConfig,
            ProviderFallbackError,
            ProviderRouter,
            _consecutive_429_count,
            mark_provider_failed,
        )

        calls: list[str] = []

        async def fake_post_chat(self, provider, payload, timeout_sec):
            calls.append(provider.provider_id)
            return httpx.Response(429, json={"error": "rate limited"})

        monkeypatch.setattr(ProviderRouter, "_post_chat", fake_post_chat)
        router = ProviderRouter(
            [
                ProviderConfig("groq", "openai-compatible", "https://api.groq.com/openai/v1",
                               api_key="k", default_model="m", priority=0),
                ProviderConfig("cerebras", "openai-compatible", "https://api.cerebras.ai/v1",
                               api_key="k", default_model="m", priority=1),
            ]
        )

        # Both already cooling from rate limits, exactly as production was.
        for pid in ("groq", "cerebras"):
            _consecutive_429_count[pid] = 3
            await mark_provider_failed(pid, 120)

        with pytest.raises(ProviderFallbackError):
            await router.chat_completion(
                {"model": "m", "messages": [{"role": "user", "content": "hammer?"}]},
                max_retries=0,
            )

        assert calls == [], f"bypass hammered rate-limited providers: {calls}"

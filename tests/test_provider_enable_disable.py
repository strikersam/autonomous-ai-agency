"""Per-provider on/off switch, with auto-disable for unfixable failures only.

Operator requirement: only healthy providers stay online; a provider that errors
is switched off until a human turns it back on.

The important design constraint is WHICH errors qualify. Auto-disabling on any
error would switch off every free provider the first time a burst tripped a rate
limit — 429 quota refills on its own, so that would be strictly worse than the
problem it solves. Auto-disable therefore fires only for states no retry can fix:
an invalid key (401/403), an empty balance (402 or a billing-shaped 4xx), or an
account with no access to any of the provider's models (404 model_not_found).
"""
from __future__ import annotations

import httpx
import pytest

import services.brain_failover as bf
from packages.ai.failover_client import failover_chat_completion


@pytest.fixture(autouse=True)
def isolated_kv(tmp_path, monkeypatch):
    """Point the kv_store at a temp DB so tests never touch real state."""
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "kv.db"))
    monkeypatch.setattr(bf, "_DISABLED_CACHE", ({}, 0.0))
    yield
    monkeypatch.setattr(bf, "_DISABLED_CACHE", ({}, 0.0))


class TestPersistence:
    def test_disable_then_enable_round_trips(self) -> None:
        bf.set_provider_enabled("groq", False, "manual test")
        assert "groq" in bf.disabled_providers(force=True)
        assert bf.disabled_providers(force=True)["groq"] == "manual test"

        bf.set_provider_enabled("groq", True)
        assert "groq" not in bf.disabled_providers(force=True)

    def test_auto_disable_is_idempotent_and_keeps_first_reason(self) -> None:
        bf.auto_disable_provider("zhipu", "401 invalid or expired API key")
        bf.auto_disable_provider("zhipu", "something else later")

        reason = bf.disabled_providers(force=True)["zhipu"]
        assert reason == "auto: 401 invalid or expired API key"

    def test_a_kv_failure_never_takes_the_brain_offline(self, monkeypatch) -> None:
        """Storage problems must degrade, not raise."""
        def _boom():
            raise OSError("disk gone")

        monkeypatch.setattr(bf, "_kv_connect", _boom)
        monkeypatch.setattr(bf, "_DISABLED_CACHE", ({}, 0.0))

        assert bf.disabled_providers(force=True) == {}   # no exception
        bf.set_provider_enabled("groq", False, "x")      # no exception


class TestSelection:
    def test_next_provider_skips_a_disabled_provider(self, monkeypatch) -> None:
        class _P:
            def __init__(self, pid):
                self.id, self.name, self.tier = pid, pid, "free"
                self.models, self.default_model = ["m"], "m"
                self.avg_latency_ms = 1.0
                self.health = bf.ProviderHealth.CLOSED if hasattr(bf, "ProviderHealth") else None
            @property
            def is_healthy(self):
                return True

        mgr = bf.BrainFailoverManager()
        monkeypatch.setattr(mgr, "_build_registry", lambda: None)
        mgr._providers = {"a": _P("a"), "b": _P("b")}

        bf.set_provider_enabled("a", False, "auto: 401")
        chosen = mgr.next_provider(exclude=set(), requested_model="m")

        assert chosen is not None and chosen.id == "b", (
            "a disabled provider must not be selected"
        )


# ── Which failures auto-disable, and which must NOT ─────────────────────────

class _StubProvider:
    def __init__(self, pid, base_url, models):
        self.id, self.base_url, self.models = pid, base_url, models
        self.api_key, self.tier, self.is_healthy = "k", "free", True


class _StubManager:
    def __init__(self, providers):
        self._providers = list(providers)
    def max_attempts(self): return max(len(self._providers), 1)
    def next_provider(self, *, exclude=None, requested_model=None):
        off = bf.disabled_providers()
        for p in self._providers:
            if p.id not in (exclude or set()) and p.id not in off:
                return p
        return None
    def get_providers(self): return self._providers
    def resolve_model(self, provider, requested_model): return provider.models[0]
    def record_success(self, provider_id, latency_ms=0.0): pass
    def record_failure(self, provider_id, reason, status=None): pass


@pytest.fixture
def one_provider(monkeypatch):
    def _apply(responses):
        mgr = _StubManager([_StubProvider("p1", "https://p1.test/v1", ["m1"])])
        monkeypatch.setattr(bf, "get_failover_manager", lambda: mgr)
        seq = list(responses)

        class _Client:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, url, json=None, headers=None):
                nxt = seq.pop(0)
                if isinstance(nxt, Exception):
                    raise nxt
                return nxt

        monkeypatch.setattr(httpx, "AsyncClient", _Client)
    return _apply


async def _run() -> None:
    from packages.ai.failover_client import BrainFailoverExhausted
    with pytest.raises(BrainFailoverExhausted):
        await failover_chat_completion(
            {"model": "m1", "messages": [{"role": "user", "content": "hi"}]}
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "why"),
    [
        (httpx.Response(401, json={"error": "unauthorized"}), "invalid key"),
        (httpx.Response(403, json={"error": "forbidden"}), "forbidden account"),
        (httpx.Response(402, json={"error": {"message": "Insufficient Balance"}}),
         "no credit"),
        (httpx.Response(400, json={"error": {"message":
            "Your credit balance is too low to access the Anthropic API."}}),
         "billing-shaped 400"),
    ],
)
async def test_unfixable_failures_auto_disable(one_provider, response, why) -> None:
    one_provider([response])
    await _run()

    off = bf.disabled_providers(force=True)
    assert "p1" in off, f"{why} should auto-disable the provider"
    assert off["p1"].startswith("auto:")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "why"),
    [
        (httpx.Response(429, json={"error": "rate limited"}), "quota refills"),
        (httpx.Response(500, json={"error": "server error"}), "transient"),
        (httpx.Response(503, json={"error": "unavailable"}), "transient"),
        (httpx.ConnectError("All connection attempts failed"), "may come back"),
    ],
)
async def test_transient_failures_do_not_auto_disable(
    one_provider, response, why
) -> None:
    """The critical guard: disabling on 429 would switch off every free provider."""
    one_provider([response])
    await _run()

    assert "p1" not in bf.disabled_providers(force=True), (
        f"transient failure ({why}) must NOT auto-disable — the circuit breaker "
        f"already handles it, and disabling here would take the whole free tier "
        f"offline on the first rate-limit burst"
    )

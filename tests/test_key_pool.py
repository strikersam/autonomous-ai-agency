"""Tests for packages/ai/key_pool.py — per-provider API key rotation.

Rotation is the only lever in this codebase that *adds* capacity. Distribution
spreads a fixed budget, pacing meters it, backoff waits for it; none of them
raise the ceiling. Free tiers are limited per key, so a second key on a provider
is a second budget — and the provider only needs cooling once every key is spent.

The behaviour that must never regress: with a single key configured (the default
for every provider today), the pool is a pass-through and the brain chain behaves
exactly as it did before rotation existed.
"""

from __future__ import annotations

import time
from typing import Iterator

import pytest

from packages.ai import key_pool as kp
from packages.ai.key_pool import KeyPool, api_keys_for


@pytest.fixture(autouse=True)
def _clean_pool() -> Iterator[None]:
    kp.reset()
    yield
    kp.reset()


# ---------------------------------------------------------------------------
# key discovery
# ---------------------------------------------------------------------------

class TestApiKeysFor:
    @pytest.fixture(autouse=True)
    def _opt_in(self, monkeypatch):
        """Rotation is off by default; these tests exercise the enabled path."""
        monkeypatch.setenv("GROQ_KEY_ROTATION", "true")
        monkeypatch.setenv("NOPE_KEY_ROTATION", "true")
        yield

    def test_single_key_is_the_common_case(self, monkeypatch) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "one")
        monkeypatch.delenv("GROQ_API_KEY_2", raising=False)
        assert api_keys_for("groq", "GROQ_API_KEY") == ["one"]

    def test_numbered_suffixes_extend_the_pool(self, monkeypatch) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "one")
        monkeypatch.setenv("GROQ_API_KEY_2", "two")
        monkeypatch.setenv("GROQ_API_KEY_3", "three")
        monkeypatch.delenv("GROQ_API_KEY_4", raising=False)
        assert api_keys_for("groq", "GROQ_API_KEY") == ["one", "two", "three"]

    def test_scan_stops_at_the_first_gap(self, monkeypatch) -> None:
        """A typo'd `_4` must not silently promote itself into the `_2` slot —
        the operator would believe three keys are live when two are."""
        monkeypatch.setenv("GROQ_API_KEY", "one")
        monkeypatch.delenv("GROQ_API_KEY_2", raising=False)
        monkeypatch.setenv("GROQ_API_KEY_4", "four")
        assert api_keys_for("groq", "GROQ_API_KEY") == ["one"]

    def test_duplicate_keys_are_collapsed(self, monkeypatch) -> None:
        """The same key twice is one budget, not two. Counting it twice would
        advertise capacity that does not exist and halve the real cooldown."""
        monkeypatch.setenv("GROQ_API_KEY", "same")
        monkeypatch.setenv("GROQ_API_KEY_2", "same")
        monkeypatch.delenv("GROQ_API_KEY_3", raising=False)
        assert api_keys_for("groq", "GROQ_API_KEY") == ["same"]

    def test_unset_returns_empty(self, monkeypatch) -> None:
        monkeypatch.delenv("NOPE_API_KEY", raising=False)
        monkeypatch.delenv("NOPE_API_KEY_2", raising=False)
        assert api_keys_for("nope", "NOPE_API_KEY") == []

    def test_whitespace_only_reads_as_unset(self, monkeypatch) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "   ")
        monkeypatch.delenv("GROQ_API_KEY_2", raising=False)
        assert api_keys_for("groq", "GROQ_API_KEY") == []

    def test_absent_primary_never_promotes_a_sibling(self, monkeypatch) -> None:
        """The first-gap rule has to start at the first slot or it is not a gap
        rule. Otherwise clearing `<BASE>` to switch a provider off would
        silently promote a leftover `<BASE>_2` and keep dispatching on it."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.setenv("GROQ_API_KEY_2", "orphan")
        assert api_keys_for("groq", "GROQ_API_KEY") == []

    def test_blank_primary_never_promotes_a_sibling(self, monkeypatch) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "   ")
        monkeypatch.setenv("GROQ_API_KEY_2", "orphan")
        assert api_keys_for("groq", "GROQ_API_KEY") == []


# ---------------------------------------------------------------------------
# rotation
# ---------------------------------------------------------------------------

class TestRotation:
    def test_single_key_is_a_pass_through(self) -> None:
        """The default configuration must be untouched by rotation."""
        pool = KeyPool()
        for _ in range(5):
            assert pool.next_key("groq", ["only"]) == "only"

    def test_single_key_is_returned_even_while_cooling(self) -> None:
        """With no sibling to fall back to, withholding the key would convert a
        provider cooldown the caller already handles into a hard outage."""
        pool = KeyPool()
        pool.mark_rate_limited("groq", "only")
        assert pool.next_key("groq", ["only"]) == "only"

    def test_keys_are_used_round_robin(self) -> None:
        pool = KeyPool()
        keys = ["a", "b", "c"]
        picked = [pool.next_key("groq", keys) for _ in range(6)]
        assert picked == ["a", "b", "c", "a", "b", "c"]

    def test_a_rate_limited_key_is_skipped_for_its_siblings(self) -> None:
        """The capacity property: one spent key does not stop the provider."""
        pool = KeyPool()
        keys = ["a", "b", "c"]
        pool.mark_rate_limited("groq", "b")
        picked = {pool.next_key("groq", keys) for _ in range(6)}
        assert picked == {"a", "c"}
        assert "b" not in picked

    def test_next_key_is_none_only_when_every_key_is_cooling(self) -> None:
        pool = KeyPool()
        keys = ["a", "b"]
        pool.mark_rate_limited("groq", "a")
        assert pool.next_key("groq", keys) == "b"
        pool.mark_rate_limited("groq", "b")
        assert pool.next_key("groq", keys) is None

    def test_a_key_returns_to_service_when_its_rest_expires(self) -> None:
        pool = KeyPool()
        keys = ["a", "b"]
        pool.mark_rate_limited("groq", "a")
        pool.mark_rate_limited("groq", "b")
        assert pool.next_key("groq", keys) is None
        for state in pool._pools["groq"].keys.values():
            state.cooling_until = time.monotonic() - 1
        assert pool.next_key("groq", keys) in keys

    def test_pools_are_isolated_per_provider(self) -> None:
        pool = KeyPool()
        pool.mark_rate_limited("groq", "shared")
        assert pool.next_key("nvidia", ["shared", "other"]) is not None

    def test_no_keys_returns_none(self) -> None:
        assert KeyPool().next_key("groq", []) is None


# ---------------------------------------------------------------------------
# provider-level cooling decision
# ---------------------------------------------------------------------------

class TestAllCooling:
    def test_single_key_always_reports_cooling(self) -> None:
        """So the caller falls straight through to the provider-level cooldown —
        byte-for-byte the pre-rotation path."""
        pool = KeyPool()
        assert pool.all_cooling("groq", ["only"]) is True
        assert pool.all_cooling("groq", []) is True

    def test_false_while_a_sibling_is_available(self) -> None:
        pool = KeyPool()
        pool.mark_rate_limited("groq", "a")
        assert pool.all_cooling("groq", ["a", "b"]) is False

    def test_true_once_every_key_is_spent(self) -> None:
        pool = KeyPool()
        for key in ("a", "b"):
            pool.mark_rate_limited("groq", key)
        assert pool.all_cooling("groq", ["a", "b"]) is True

    def test_retry_after_is_honoured_but_clamped(self) -> None:
        """A hostile or malformed Retry-After must not park a key indefinitely."""
        pool = KeyPool()
        pool.mark_rate_limited("groq", "a", retry_after_sec=99_999.0)
        rest = pool._pools["groq"].keys["a"].cooling_until - time.monotonic()
        assert rest <= kp._MAX_KEY_COOLDOWN_SEC + 1


# ---------------------------------------------------------------------------
# diagnostics must never leak key material
# ---------------------------------------------------------------------------

class TestSnapshotLeaksNothing:
    def test_snapshot_contains_no_key_material(self) -> None:
        secret = "gsk_super_secret_value_12345"
        pool = KeyPool()
        pool.next_key("groq", [secret, "other_secret_value"])
        pool.mark_rate_limited("groq", secret)
        blob = repr(pool.snapshot())
        assert secret not in blob
        assert "other_secret_value" not in blob
        # Not even a fragment: a leading slice of an API key identifies the
        # account for several providers.
        assert secret[:8] not in blob
        assert secret[-8:] not in blob

    def test_snapshot_still_reports_useful_counts(self) -> None:
        pool = KeyPool()
        pool.next_key("groq", ["a", "b"])
        pool.mark_rate_limited("groq", "a")
        snap = pool.snapshot()["groq"]
        assert snap["resting"] == 1
        assert snap["keys"] >= 1
        assert all(len(d["id"]) == 8 for d in snap["detail"])

    def test_digest_is_stable_and_not_reversible(self) -> None:
        assert kp._digest("abc") == kp._digest("abc")
        assert kp._digest("abc") != kp._digest("abd")
        assert "abc" not in kp._digest("abc")


# ---------------------------------------------------------------------------
# brain-chain integration
# ---------------------------------------------------------------------------

class TestBrainChainIntegration:
    def test_provider_record_carries_its_key_env(self) -> None:
        """Rotation needs the variable the key came from. Deriving it from the
        provider id would silently mean 'no extra keys' for any id that does not
        round-trip."""
        from services.brain_failover import _PROVIDER_REGISTRY, ProviderInfo

        assert "key_env" in ProviderInfo.__dataclass_fields__
        for spec in _PROVIDER_REGISTRY:
            if spec["tier"] != "local":
                assert spec.get("key_env"), f"{spec['id']} has no key_env"

    def test_build_request_uses_the_rotated_key(self) -> None:
        from packages.ai.failover_client import _build_request

        class _P:
            id = "groq"
            base_url = "https://api.groq.com/openai/v1"
            api_key = "record_key"

        _url, headers, _ = _build_request(_P(), api_key="rotated_key")
        assert headers["Authorization"] == "Bearer rotated_key"

    def test_build_request_falls_back_to_the_record_key(self) -> None:
        """No pool configured — the pre-rotation path, unchanged."""
        from packages.ai.failover_client import _build_request

        class _P:
            id = "groq"
            base_url = "https://api.groq.com/openai/v1"
            api_key = "record_key"

        _url, headers, _ = _build_request(_P())
        assert headers["Authorization"] == "Bearer record_key"

    def test_anthropic_native_also_rotates(self) -> None:
        """Anthropic uses x-api-key, not Bearer — the override must reach it."""
        from packages.ai.failover_client import _build_request

        class _P:
            id = "anthropic"
            base_url = "https://api.anthropic.com"
            api_key = "record_key"

        _url, headers, is_native = _build_request(_P(), api_key="rotated_key")
        assert is_native is True
        assert headers.get("x-api-key") == "rotated_key"

    def test_provider_keys_returns_empty_without_key_env(self) -> None:
        from packages.ai.failover_client import _provider_keys

        class _P:
            id = "mystery"

        assert _provider_keys(_P()) == []


# ---------------------------------------------------------------------------
# rotation is opt-in per provider (provider terms-of-use gate)
# ---------------------------------------------------------------------------

class TestRotationIsOptIn:
    """Sibling keys must be ignored until the operator explicitly opts in.

    Several providers' acceptable-use policies prohibit registering extra
    accounts to exceed published limits. Discovering `<KEY>_2` and silently
    using it would let the platform commit a terms violation on the operator's
    behalf from nothing more than an env var being present.
    """

    def test_siblings_ignored_without_the_gate(self, monkeypatch) -> None:
        monkeypatch.delenv("GROQ_KEY_ROTATION", raising=False)
        monkeypatch.setenv("GROQ_API_KEY", "one")
        monkeypatch.setenv("GROQ_API_KEY_2", "two")
        assert api_keys_for("groq", "GROQ_API_KEY") == ["one"]

    def test_siblings_used_once_opted_in(self, monkeypatch) -> None:
        monkeypatch.setenv("GROQ_KEY_ROTATION", "true")
        monkeypatch.setenv("GROQ_API_KEY", "one")
        monkeypatch.setenv("GROQ_API_KEY_2", "two")
        monkeypatch.delenv("GROQ_API_KEY_3", raising=False)
        assert api_keys_for("groq", "GROQ_API_KEY") == ["one", "two"]

    @pytest.mark.parametrize("value", ["false", "0", "no", "off", "", "maybe"])
    def test_only_explicit_truthy_values_enable_it(self, monkeypatch, value) -> None:
        monkeypatch.setenv("GROQ_KEY_ROTATION", value)
        monkeypatch.setenv("GROQ_API_KEY", "one")
        monkeypatch.setenv("GROQ_API_KEY_2", "two")
        assert api_keys_for("groq", "GROQ_API_KEY") == ["one"]

    def test_gate_is_per_provider(self, monkeypatch) -> None:
        monkeypatch.setenv("GROQ_KEY_ROTATION", "true")
        monkeypatch.delenv("ZAI_KEY_ROTATION", raising=False)
        monkeypatch.setenv("ZAI_API_KEY", "one")
        monkeypatch.setenv("ZAI_API_KEY_2", "two")
        assert api_keys_for("zai", "ZAI_API_KEY") == ["one"]


# ---------------------------------------------------------------------------
# an exhausted pool must never fall back to the resting primary key
# ---------------------------------------------------------------------------

class TestExhaustedPoolDoesNotReusePrimary:
    @pytest.mark.anyio
    async def test_no_request_is_sent_when_every_key_is_resting(
        self, monkeypatch
    ) -> None:
        """`next_key` returns None once all keys cool. Passing that to
        `_build_request` hits its `api_key or provider.api_key` fallback and
        sends the primary key — the one that is supposed to be resting. That is
        reachable with shipped defaults: a 30s provider cooldown expires while
        the 60s key cooldowns are still running."""
        from packages.ai import failover_client as fc

        class _P:
            id = "groq"
            base_url = "https://api.groq.com/openai/v1"
            api_key = "PRIMARY"
            key_env = "GROQ_API_KEY"

        sent: list[str] = []

        async def _boom(*args: object, **kwargs: object) -> None:
            sent.append("dispatched")
            raise AssertionError("a request was sent on a resting key")

        monkeypatch.setattr(fc, "_provider_keys", lambda p: ["PRIMARY", "SECOND"])
        pool = fc._key_pool()
        pool.mark_rate_limited("groq", "PRIMARY")
        pool.mark_rate_limited("groq", "SECOND")
        monkeypatch.setattr(fc, "_build_request", _boom)

        result, error = await fc._try_provider(
            _P(), {"model": "m"}, object(), [], 5.0, fc._Budget(3, 60.0)
        )
        assert result is None
        assert sent == [], "the exhausted pool still dispatched a request"
        assert "key(s) rate-limited" in error

    def test_single_key_provider_is_unaffected(self) -> None:
        """One key must still be returned while cooling — there is no sibling to
        fall back to, and withholding it would turn a provider cooldown the
        caller already handles into a hard outage."""
        pool = KeyPool()
        pool.mark_rate_limited("solo", "only")
        assert pool.next_key("solo", ["only"]) == "only"


# ---------------------------------------------------------------------------
# digests must not be a stable cross-process fingerprint
# ---------------------------------------------------------------------------

class TestDigestIsKeyed:
    def test_digest_is_not_a_bare_hash_of_the_key(self) -> None:
        """An unsalted sha256 prefix is a permanent fingerprint: the same key
        yields the same label in every deployment forever, so a label from a log
        can be matched against a candidate key offline."""
        import hashlib

        key = "gsk_example_key"
        assert kp._digest(key) != hashlib.sha256(key.encode()).hexdigest()[:8]
        assert kp._digest(key) != hashlib.blake2b(key.encode(), digest_size=4).hexdigest()

    def test_digest_changes_with_the_process_salt(self, monkeypatch) -> None:
        before = kp._digest("same-key")
        monkeypatch.setattr(kp, "_DIGEST_SALT", b"a-different-salt-value-32-bytes!!")
        assert kp._digest("same-key") != before

    def test_digest_is_stable_within_a_process(self) -> None:
        assert kp._digest("k") == kp._digest("k")

"""A stale model catalogue must not be mistaken for a dead account.

``config/models.yaml`` lists ``qwen-3-coder-480b``, ``llama-3.3-70b`` and
``llama-3.1-8b`` for Cerebras. An account whose key serves none of those — a
routine situation, since providers archive models and tiers differ — gets every
candidate rejected as unknown, and ``_try_provider`` then concluded "no
accessible model (404 model_not_found)" and threw the provider's kill switch.
The key was valid the whole time; only the catalogue was wrong.

These tests pin the correction: ask the provider what its key actually serves
before believing the account is at fault, and use that answer on the next call.
"""
from __future__ import annotations

import httpx
import pytest

from packages.ai import model_discovery as md
from packages.ai.failover_client import (
    _disable_unless_key_serves_other_models,
    _looks_unknown_model,
    _models_to_try,
)


class _StubProvider:
    def __init__(self, pid="cerebras", base_url="https://api.cerebras.ai",
                 models=None, api_key="k"):
        self.id = pid
        self.base_url = base_url
        self.models = models or ["qwen-3-coder-480b", "llama-3.3-70b", "llama-3.1-8b"]
        self.api_key = api_key
        self.tier = "free"
        self.is_healthy = True


@pytest.fixture(autouse=True)
def _clear_cache():
    """Discovery caches in a module global — never leak it between tests."""
    md.reset_cache()
    yield
    md.reset_cache()


@pytest.fixture
def disabled(monkeypatch):
    """Record auto-disable calls instead of writing operator state."""
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "packages.ai.failover_client._auto_disable",
        lambda pid, reason: calls.append((pid, reason)),
    )
    return calls


def _mock_get(monkeypatch, handler) -> None:
    monkeypatch.setattr(
        httpx.AsyncClient, "get", lambda self, url, **kw: handler(url, kw)
    )


def _ok(payload):
    async def _handler(url, kw):
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))
    return _handler


class TestParsing:
    def test_it_reads_the_ids_in_provider_order(self) -> None:
        ids = md._parse_ids({"data": [{"id": "a"}, {"id": "b"}]})
        assert ids == ["a", "b"], "provider ordering is a preference worth keeping"

    def test_duplicates_collapse(self) -> None:
        assert md._parse_ids({"data": [{"id": "a"}, {"id": "a"}]}) == ["a"]

    @pytest.mark.parametrize(
        "body",
        [None, [], {}, {"data": None}, {"data": [{"name": "a"}]}, {"data": [{"id": 7}]}],
    )
    def test_unusable_bodies_yield_nothing(self, body) -> None:
        """A malformed listing must never be read as "the key serves nothing"."""
        assert md._parse_ids(body) == []


class TestModelsUrl:
    def test_openai_compatible_provider(self) -> None:
        url, headers = md._models_url(_StubProvider())
        assert url == "https://api.cerebras.ai/v1/models"
        assert headers["Authorization"] == "Bearer k"

    def test_it_does_not_double_the_version_prefix(self) -> None:
        url, _ = md._models_url(_StubProvider(base_url="https://api.groq.com/openai/v1"))
        assert url == "https://api.groq.com/openai/v1/models"

    def test_anthropic_native_uses_its_own_auth(self) -> None:
        """Bearer auth is rejected by Anthropic, so discovery must not send it."""
        _, headers = md._models_url(
            _StubProvider(pid="anthropic", base_url="https://api.anthropic.com")
        )
        assert "Authorization" not in headers
        assert headers.get("x-api-key") == "k"


class TestDiscovery:
    @pytest.mark.asyncio
    async def test_it_returns_what_the_key_serves(self, monkeypatch) -> None:
        _mock_get(monkeypatch, _ok({"data": [{"id": "gpt-oss-120b"}, {"id": "x"}]}))
        assert await md.discover_models(_StubProvider()) == ["gpt-oss-120b", "x"]

    @pytest.mark.asyncio
    async def test_the_answer_is_cached(self, monkeypatch) -> None:
        calls = {"n": 0}

        async def _handler(url, kw):
            calls["n"] += 1
            return httpx.Response(
                200, json={"data": [{"id": "a"}]}, request=httpx.Request("GET", url)
            )

        _mock_get(monkeypatch, _handler)
        await md.discover_models(_StubProvider())
        await md.discover_models(_StubProvider())
        assert calls["n"] == 1, "discovery runs on the failure path — do not repeat it"

    @pytest.mark.asyncio
    async def test_an_error_status_is_unknown_not_empty(self, monkeypatch) -> None:
        """None means "could not find out" and must not read as "no models"."""
        async def _handler(url, kw):
            return httpx.Response(404, request=httpx.Request("GET", url))

        _mock_get(monkeypatch, _handler)
        assert await md.discover_models(_StubProvider()) is None

    @pytest.mark.asyncio
    async def test_a_network_failure_never_propagates(self, monkeypatch) -> None:
        async def _handler(url, kw):
            raise httpx.ConnectError("dns")

        _mock_get(monkeypatch, _handler)
        assert await md.discover_models(_StubProvider()) is None

    @pytest.mark.asyncio
    async def test_a_failure_is_cached_too(self, monkeypatch) -> None:
        """Otherwise every failed call re-asks a provider that is already down."""
        calls = {"n": 0}

        async def _handler(url, kw):
            calls["n"] += 1
            raise httpx.ConnectError("dns")

        _mock_get(monkeypatch, _handler)
        await md.discover_models(_StubProvider())
        await md.discover_models(_StubProvider())
        assert calls["n"] == 1

    def test_the_hot_path_reader_never_blocks(self) -> None:
        """``cached_models`` is sync by contract — a chat call must not wait."""
        assert md.cached_models("cerebras") is None


class TestModelOrdering:
    def test_without_discovery_the_static_list_is_unchanged(self) -> None:
        provider = _StubProvider()
        assert _models_to_try(provider, "qwen-3-coder-480b") == [
            "qwen-3-coder-480b", "llama-3.3-70b", "llama-3.1-8b"
        ]

    def test_models_the_key_cannot_use_are_dropped(self) -> None:
        md._CACHE["cerebras"] = (2**31, ["llama-3.1-8b", "gpt-oss-120b"])
        order = _models_to_try(_StubProvider(), "qwen-3-coder-480b")
        assert "qwen-3-coder-480b" not in order, (
            "attempting a model the key cannot use burns the attempt budget"
        )

    def test_served_models_missing_from_the_catalogue_are_added(self) -> None:
        md._CACHE["cerebras"] = (2**31, ["gpt-oss-120b"])
        assert _models_to_try(_StubProvider(), "qwen-3-coder-480b") == ["gpt-oss-120b"]

    def test_a_catalogue_hit_keeps_its_priority(self) -> None:
        md._CACHE["cerebras"] = (2**31, ["gpt-oss-120b", "llama-3.3-70b"])
        order = _models_to_try(_StubProvider(), "llama-3.3-70b")
        assert order[0] == "llama-3.3-70b", "the resolved model stays first"

    def test_an_empty_discovery_falls_back_to_the_catalogue(self) -> None:
        """A provider that lists nothing must not leave the chain with no model."""
        md._CACHE["cerebras"] = (2**31, [])
        assert _models_to_try(_StubProvider(), "llama-3.3-70b") != []


class TestUnknownModelDetection:
    @pytest.mark.parametrize(
        "err",
        ["cerebras 404: model_not_found", "the model `x` does not exist"],
    )
    def test_it_recognises_a_rejected_model_id(self, err) -> None:
        assert _looks_unknown_model(err) is True

    @pytest.mark.parametrize("err", ["", None, "cerebras 429 rate-limited"])
    def test_other_failures_are_not_model_problems(self, err) -> None:
        assert _looks_unknown_model(err) is False


class TestDisableGate:
    @pytest.mark.asyncio
    async def test_a_stale_catalogue_no_longer_kills_the_provider(
        self, monkeypatch, disabled
    ) -> None:
        """The reported defect, end to end.

        The catalogue's three Cerebras models are all rejected, but the key
        serves four others. That is a config problem, and disabling the provider
        makes an operator undo it by hand for no reason.
        """
        _mock_get(monkeypatch, _ok({"data": [
            {"id": "gemma-4-31b"}, {"id": "zai-glm-4.7"},
            {"id": "gpt-oss-120b"}, {"id": "llama3.1-8b"},
        ]}))
        provider = _StubProvider()

        await _disable_unless_key_serves_other_models(provider, provider.models)

        assert disabled == [], (
            "a valid key with a stale catalogue must stay enabled"
        )

    @pytest.mark.asyncio
    async def test_the_key_serving_nothing_new_still_disables(
        self, monkeypatch, disabled
    ) -> None:
        """The genuine case the kill switch exists for must keep working."""
        _mock_get(monkeypatch, _ok({"data": [{"id": "llama-3.3-70b"}]}))
        provider = _StubProvider()

        await _disable_unless_key_serves_other_models(provider, provider.models)

        assert [pid for pid, _ in disabled] == ["cerebras"]

    @pytest.mark.asyncio
    async def test_unavailable_discovery_preserves_the_old_behaviour(
        self, monkeypatch, disabled
    ) -> None:
        """No evidence either way is not a reason to change what we always did."""
        async def _handler(url, kw):
            raise httpx.ConnectError("dns")

        _mock_get(monkeypatch, _handler)
        provider = _StubProvider()

        await _disable_unless_key_serves_other_models(provider, provider.models)

        assert [pid for pid, _ in disabled] == ["cerebras"]

    @pytest.mark.asyncio
    async def test_the_reprieve_is_granted_only_once(
        self, monkeypatch, disabled
    ) -> None:
        """Without this the provider would retry a broken account forever.

        Round one learns the real list and skips the kill switch. If the very
        models the key advertises then fail too, the account really is unusable
        and the switch must throw.
        """
        _mock_get(monkeypatch, _ok({"data": [{"id": "gpt-oss-120b"}]}))
        provider = _StubProvider()

        await _disable_unless_key_serves_other_models(provider, provider.models)
        assert disabled == []

        # Round two: the corrected list was used and still failed.
        await _disable_unless_key_serves_other_models(provider, ["gpt-oss-120b"])
        assert [pid for pid, _ in disabled] == ["cerebras"]

    @pytest.mark.asyncio
    async def test_the_disable_reason_is_unchanged(
        self, monkeypatch, disabled
    ) -> None:
        """Doctor renders this string from a lookup table — do not reword it."""
        async def _handler(url, kw):
            raise httpx.ConnectError("dns")

        _mock_get(monkeypatch, _handler)
        await _disable_unless_key_serves_other_models(_StubProvider(), [])

        assert disabled[0][1] == "no accessible model (404 model_not_found)"

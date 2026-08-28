"""Tests for the provider routing in ``.github/scripts/implement_agent.py``.

The implementer used to carry its own six-entry NVIDIA model list and its own
failover, in defiance of CLAUDE.md rule 2. On 2026-08-27 every entry in that
list was dead — four ``410 Gone`` (two retired the previous morning) and one
``404`` — so the loop exhausted all candidates on turn 1 and the agency stopped
producing work entirely.

Routing through ``ProviderRouter`` fixes it, but introduces a hazard worth
pinning: the router rewrites the outbound payload for three provider types, and
none of those converters carry a ``tools`` field. Sending a tool-calling turn to
one would not raise — it would drop every tool and leave the agent narrating
edits it can no longer make. That is the failure mode this file exists to block.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GITHUB_SCRIPTS = REPO_ROOT / ".github" / "scripts"
SOURCE = (GITHUB_SCRIPTS / "implement_agent.py").read_text(encoding="utf-8")

# Verbatim from the 2026-08-27 run that produced no diff and reported success.
DEAD_MODEL_IDS = [
    "qwen/qwen3-coder-480b-a35b-instruct",
    "nvidia/llama-3.1-nemotron-ultra-253b-v1",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "meta/llama-3.3-70b-instruct",
    "qwen/qwen2.5-coder-32b-instruct",
]


@pytest.fixture(scope="module")
def agent():
    sys.path.insert(0, str(GITHUB_SCRIPTS))
    sys.modules.pop("implement_agent", None)
    module = importlib.import_module("implement_agent")
    yield module
    if str(GITHUB_SCRIPTS) in sys.path:
        sys.path.remove(str(GITHUB_SCRIPTS))


class _Recorder:
    """Stands in for ProviderRouter and captures what it was handed."""

    def __init__(self, body: dict | None = None, provider_id: str = "cerebras") -> None:
        self.payload: dict | None = None
        self.kwargs: dict | None = None
        self._body = body or {"model": "stub", "choices": [{"message": {}}]}
        self.providers = [SimpleNamespace(provider_id=provider_id)]

    async def chat_completion(self, payload, **kwargs):
        self.payload = payload
        self.kwargs = kwargs
        return SimpleNamespace(
            response=SimpleNamespace(json=lambda: self._body),
            provider=SimpleNamespace(provider_id="stub-provider"),
        )


class TestOnlyToolCapableProvidersAreUsed:
    """The type filter is a correctness guard, not a preference."""

    def test_converting_provider_types_are_excluded(self, agent, monkeypatch):
        from packages.ai.router import ProviderConfig, ProviderRouter

        mixed = [
            ProviderConfig(provider_id="cerebras", type="openai-compatible", base_url="https://a"),
            ProviderConfig(provider_id="anthropic", type="anthropic", base_url="https://b"),
            ProviderConfig(provider_id="bedrock", type="bedrock", base_url="https://c"),
            ProviderConfig(provider_id="ollama-local", type="ollama", base_url="http://d"),
            ProviderConfig(provider_id="groq", type="openai-compatible", base_url="https://e"),
        ]
        monkeypatch.setattr(
            ProviderRouter, "from_env",
            classmethod(lambda cls, *a, **k: ProviderRouter(mixed)),
        )
        router = agent.build_tool_calling_router()
        assert [p.provider_id for p in router.providers] == ["cerebras", "groq"], (
            "anthropic/bedrock/ollama rewrite the payload through converters "
            "with no tools field — a tool call sent there vanishes silently"
        )

    def test_returns_none_when_nothing_can_carry_tools(self, agent, monkeypatch):
        from packages.ai.router import ProviderConfig, ProviderRouter

        only_converting = [
            ProviderConfig(provider_id="anthropic", type="anthropic", base_url="https://b"),
        ]
        monkeypatch.setattr(
            ProviderRouter, "from_env",
            classmethod(lambda cls, *a, **k: ProviderRouter(only_converting)),
        )
        assert agent.build_tool_calling_router() is None, (
            "reporting 'no usable provider' beats silently running toolless"
        )


class TestTurnPayload:
    """What the loop sends, and just as importantly what it does not."""

    def test_tools_are_sent(self, agent):
        recorder = _Recorder()
        agent.router_turn(recorder, [{"role": "user", "content": "hi"}])
        assert recorder.payload["tools"] == agent.TOOLS
        assert recorder.payload["tool_choice"] == "auto"

    def test_no_model_is_named_for_a_non_nvidia_provider(self, agent):
        """Anything but NVIDIA resolves its own default_model."""
        recorder = _Recorder(provider_id="cerebras")
        agent.router_turn(recorder, [{"role": "user", "content": "hi"}])
        assert not recorder.payload.get("model")
        assert recorder.kwargs["model_fallbacks"] == []

    def test_no_zero_temperature(self, agent):
        """response_cache keys on (model, messages, temperature, max_tokens,
        stop) — not on tools — and engages only at temperature == 0. A hit here
        would replay a stale tool call into a live agent loop."""
        recorder = _Recorder()
        agent.router_turn(recorder, [{"role": "user", "content": "hi"}])
        assert recorder.payload.get("temperature") != 0

    def test_never_escalates_to_a_paid_provider(self, agent):
        recorder = _Recorder()
        agent.router_turn(recorder, [{"role": "user", "content": "hi"}])
        assert recorder.kwargs["allow_commercial_fallback"] is False, (
            "this loop must not burn paid credits behind the operator's back"
        )

    def test_returns_the_raw_openai_body_and_the_answering_provider(self, agent):
        body = {"model": "m", "choices": [{"message": {"content": "hello"}}]}
        assert agent.router_turn(_Recorder(body), []) == (body, "stub-provider")


class TestNoHardcodedModels:
    """The regression itself: a model id baked into this script."""

    @pytest.mark.parametrize("model_id", DEAD_MODEL_IDS)
    def test_dead_model_is_gone(self, model_id: str) -> None:
        assert model_id not in SOURCE, (
            f"{model_id} was end-of-lifed and returned 410; reintroducing a "
            "hardcoded id rebuilds the outage"
        )

    def test_no_candidate_model_list_remains(self) -> None:
        assert "CANDIDATE_MODELS" not in SOURCE

    def test_provider_endpoint_is_not_hardcoded(self) -> None:
        assert "integrate.api.nvidia.com" not in SOURCE, (
            "provider endpoints belong to the router (rule 2)"
        )


class TestToolCallsSurviveTheDictShape:
    """The router hands back parsed JSON, not SDK objects.

    Rewriting the loop for ``ProviderRouter`` meant every ``tc.id`` /
    ``tc.function.name`` had to become a dict lookup. One survived the first
    pass and would have raised ``AttributeError`` on the first turn any model
    actually called a tool — every real run — while the payload tests above
    still passed, because none of them return a tool call. This drives one.
    """

    @staticmethod
    def _turn(agent, tool_calls):
        recorder = _Recorder({
            "model": "stub",
            "choices": [{"message": {"content": None, "tool_calls": tool_calls}}],
        })
        body, _provider = agent.router_turn(recorder, [])
        return body

    def test_a_tool_call_round_trips(self, agent):
        raw = [{
            "id": "call_1",
            "type": "function",
            "function": {"name": "bash", "arguments": '{"cmd": "pytest -x"}'},
        }]
        body = self._turn(agent, raw)
        message = body["choices"][0]["message"]
        returned = message["tool_calls"]

        # Exactly the accesses the loop performs on each tool call.
        assert returned[0].get("id") == "call_1"
        function = returned[0].get("function") or {}
        assert function.get("name") == "bash"
        assert json.loads(function.get("arguments") or "{}") == {"cmd": "pytest -x"}

    def test_serialisation_uses_dict_access_only(self):
        """Guards the specific slip: attribute access on a parsed-JSON dict."""
        loop = SOURCE.split("assistant_entry: dict")[1].split("messages.append")[0]
        assert "tc.id" not in loop
        assert "tc.function" not in loop
        assert 'tc.get("id")' in loop

    def test_a_malformed_tool_call_does_not_crash_the_loop(self, agent):
        """A provider that omits `function` must not take the run down."""
        body = self._turn(agent, [{"id": "call_2"}])
        call = body["choices"][0]["message"]["tool_calls"][0]
        assert (call.get("function") or {}).get("name") is None
        assert json.loads((call.get("function") or {}).get("arguments") or "{}") == {}


class TestNoPaidProviderIsEverReached:
    """Codex review, #1369: `allow_commercial_fallback=False` is not enough.

    `chat_completion` guards with ``if not first_eligible and
    is_commercial_provider(...)``, so the *first* eligible provider is used
    whatever it costs. On a host whose only openai-compatible key is a paid one,
    the flag alone would bill the operator on the very first turn.
    """

    def test_commercial_providers_are_filtered_out(self, agent, monkeypatch):
        from packages.ai import router as router_mod
        from packages.ai.router import ProviderConfig, ProviderRouter

        free = ProviderConfig(provider_id="cerebras", type="openai-compatible", base_url="https://a")
        paid = ProviderConfig(provider_id="openrouter", type="openai-compatible", base_url="https://b")
        monkeypatch.setattr(
            ProviderRouter, "from_env",
            classmethod(lambda cls, *a, **k: ProviderRouter([paid, free])),
        )
        monkeypatch.setattr(
            router_mod, "is_commercial_provider",
            lambda p: getattr(p, "provider_id", "") == "openrouter",
        )
        router = agent.build_tool_calling_router()
        assert [p.provider_id for p in router.providers] == ["cerebras"]

    def test_a_paid_only_host_gets_nothing_rather_than_a_bill(self, agent, monkeypatch):
        from packages.ai import router as router_mod
        from packages.ai.router import ProviderConfig, ProviderRouter

        paid = ProviderConfig(provider_id="openrouter", type="openai-compatible", base_url="https://b")
        monkeypatch.setattr(
            ProviderRouter, "from_env",
            classmethod(lambda cls, *a, **k: ProviderRouter([paid])),
        )
        monkeypatch.setattr(router_mod, "is_commercial_provider", lambda p: True)
        assert agent.build_tool_calling_router() is None


class TestFailoverOffABadResponder:
    """Codex review, #1369: retrying the same payload reaches the same provider.

    The router is priority-ordered and stateless between calls, so popping the
    assistant turn and retrying draws the identical malformed reply. The
    provider has to be dropped explicitly, which is what the old explicit
    model-advance achieved.
    """

    def test_router_without_drops_only_the_named_provider(self, agent):
        from packages.ai.router import ProviderConfig, ProviderRouter

        router = ProviderRouter([
            ProviderConfig(provider_id="a", type="openai-compatible", base_url="https://a"),
            ProviderConfig(provider_id="b", type="openai-compatible", base_url="https://b"),
        ])
        assert [p.provider_id for p in agent.router_without(router, "a").providers] == ["b"]

    def test_dropping_the_last_provider_yields_none(self, agent):
        from packages.ai.router import ProviderConfig, ProviderRouter

        router = ProviderRouter([
            ProviderConfig(provider_id="only", type="openai-compatible", base_url="https://a"),
        ])
        assert agent.router_without(router, "only") is None, (
            "the loop must stop, not spin on an empty router"
        )

    def test_the_loop_fails_over_rather_than_retrying(self):
        """The regression Codex named: a retry that cannot change the outcome."""
        quirk = SOURCE.split("<tool_call>")[1].split("# Execute tool calls")[0]
        assert "router_without(router, answering_provider)" in quirk


class TestNvidiaGetsMoreThanOneCandidate:
    """Codex review, #1369 (P1): naming no model is not safe for NVIDIA.

    ``ProviderRouter``'s NVIDIA entry defaults to ``meta/llama-3.3-70b-instruct``
    (router.py:702), which reached end-of-life on 2026-08-26 and answers ``410``.
    With no model named, ``_candidate_models`` returns that one dead id, so an
    NVIDIA-only runner exhausts the provider on turn 1 — reproducing the very
    outage this change exists to prevent.
    """

    def test_the_router_default_is_a_model_we_know_is_dead(self):
        """Pins the premise, so this guard cannot quietly stop applying."""
        router_src = (REPO_ROOT / "packages/ai/router.py").read_text(encoding="utf-8")
        assert '"meta/llama-3.3-70b-instruct"' in router_src
        assert "meta/llama-3.3-70b-instruct" in DEAD_MODEL_IDS

    def test_nvidia_first_gets_the_curated_list(self, agent):
        recorder = _Recorder(provider_id="nvidia-nim")
        agent.router_turn(recorder, [{"role": "user", "content": "hi"}])

        sys.path.insert(0, str(GITHUB_SCRIPTS))
        from nvidia_models import NVIDIA_MODEL_IDS

        assert recorder.payload["model"] == NVIDIA_MODEL_IDS[0]
        assert recorder.kwargs["model_fallbacks"] == list(NVIDIA_MODEL_IDS[1:])
        assert len(NVIDIA_MODEL_IDS) > 1, (
            "one candidate is what the outage looked like"
        )

    def test_curated_ids_are_not_invented_here(self):
        """Every id handed to the router comes from the repo's curated list."""
        assert "nvidia_models" in SOURCE
        for model_id in DEAD_MODEL_IDS:
            assert model_id not in SOURCE

"""Tests for `.github/scripts/nvidia_models.py` — live model discovery.

The static list in this module has now been wrong four times. Models were
"live-verified 2026-06-14"; by 2026-08-27 two of the three answered `410 Gone`,
having reached end-of-life on 2026-05-12, 2026-06-11 and 2026-08-26. Each time
the agency stopped, and each time the fix was to hand-edit ids that would rot
again.

NVIDIA's own documentation says to find the model id by querying the models
endpoint. So the list is now discovered from the provider and ranked, with the
static entries kept only for when discovery cannot run. No id in this repo has
to be correct for the agency to find a working model.

Nothing here asserts a particular model is live — that is exactly the claim
that kept going stale. These test the ranking and the failure behaviour.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / ".github" / "scripts"


@pytest.fixture(autouse=True)
def _clear_cache(nm):
    """resolve_model_ids memoises; a cached value would leak across tests."""
    nm.reset_cache()
    yield
    nm.reset_cache()


@pytest.fixture(scope="module")
def nm():
    sys.path.insert(0, str(SCRIPTS))
    sys.modules.pop("nvidia_models", None)
    import nvidia_models

    yield nvidia_models
    if str(SCRIPTS) in sys.path:
        sys.path.remove(str(SCRIPTS))


class TestRanking:
    """Nemotron first, as asked; then other instruct models."""

    def test_nemotron_outranks_everything_else(self, nm) -> None:
        ranked = nm.rank_models([
            "meta/llama-3.1-8b-instruct",
            "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        ])
        assert ranked[0].startswith("nvidia/") and "nemotron" in ranked[0]

    def test_larger_nemotron_outranks_smaller(self, nm) -> None:
        ranked = nm.rank_models([
            "nvidia/nemotron-nano-9b-v2",
            "nvidia/llama-3.3-nemotron-super-49b-v1.5",
            "nvidia/llama-3.1-nemotron-ultra-253b-v1",
        ])
        assert "ultra" in ranked[0] or "253b" in ranked[0]

    def test_non_chat_models_are_dropped(self, nm) -> None:
        """Embedding, rerank, OCR, guard and vision models cannot drive the loop."""
        ranked = nm.rank_models([
            "nvidia/nv-embedqa-e5-v5",
            "nvidia/llama-3.2-nv-rerankqa-1b-v2",
            "nvidia/nemotron-ocr-v2",
            "nvidia/llama-3.1-nemoguard-8b-content-safety",
            "nvidia/nemotron-3-content-safety",
            "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        ])
        assert ranked == ["nvidia/llama-3.3-nemotron-super-49b-v1.5"]

    def test_order_is_stable_and_deduplicated(self, nm) -> None:
        ranked = nm.rank_models([
            "meta/llama-3.3-70b-instruct",
            "meta/llama-3.3-70b-instruct",
        ])
        assert ranked == ["meta/llama-3.3-70b-instruct"]

    def test_empty_input_gives_empty_output(self, nm) -> None:
        assert nm.rank_models([]) == []


class TestDiscovery:
    """Reads the provider's own catalogue; never raises into the caller."""

    def test_parses_an_openai_shaped_model_list(self, nm, monkeypatch) -> None:
        payload = {"data": [
            {"id": "nvidia/llama-3.3-nemotron-super-49b-v1.5"},
            {"id": "nvidia/nv-embedqa-e5-v5"},
        ]}
        monkeypatch.setattr(nm, "_fetch_models_json", lambda *a, **k: payload)
        assert nm.live_model_ids("key") == ["nvidia/llama-3.3-nemotron-super-49b-v1.5"]

    def test_no_key_means_no_call(self, nm, monkeypatch) -> None:
        def _boom(*a, **k):
            raise AssertionError("must not call the API without a key")

        monkeypatch.setattr(nm, "_fetch_models_json", _boom)
        assert nm.live_model_ids("") == []

    def test_a_failure_degrades_to_empty(self, nm, monkeypatch) -> None:
        """Discovery must never be the reason a run dies."""
        def _raise(*a, **k):
            raise RuntimeError("network is down")

        monkeypatch.setattr(nm, "_fetch_models_json", _raise)
        assert nm.live_model_ids("key") == []

    def test_malformed_payload_degrades_to_empty(self, nm, monkeypatch) -> None:
        monkeypatch.setattr(nm, "_fetch_models_json", lambda *a, **k: {"unexpected": 1})
        assert nm.live_model_ids("key") == []


class TestResolution:
    """What callers actually use: live ids when available, static otherwise."""

    def test_live_ids_win(self, nm, monkeypatch) -> None:
        monkeypatch.setattr(nm, "live_model_ids", lambda *a, **k: ["nvidia/discovered-instruct"])
        assert nm.resolve_model_ids("key") == ["nvidia/discovered-instruct"]

    def test_falls_back_to_the_static_list(self, nm, monkeypatch) -> None:
        monkeypatch.setattr(nm, "live_model_ids", lambda *a, **k: [])
        assert nm.resolve_model_ids("key") == nm.NVIDIA_MODEL_IDS

    def test_the_static_list_carries_no_retired_id(self, nm) -> None:
        """Every id that answered 410 on 2026-08-27 must be gone from it."""
        retired = {
            "nvidia/llama-3.3-nemotron-super-49b-v1.5",
            "meta/llama-3.3-70b-instruct",
            "qwen/qwen3-coder-480b-a35b-instruct",
            "qwen/qwen2.5-coder-32b-instruct",
            "nvidia/llama-3.1-nemotron-ultra-253b-v1",
        }
        assert not (set(nm.NVIDIA_MODEL_IDS) & retired)

    def test_shapes_still_agree(self, nm) -> None:
        assert nm.NVIDIA_MODEL_IDS == [m for m, _ in nm.NVIDIA_CANDIDATE_MODELS]


class TestFailureIsAudible:
    """Silent degradation is the defect this whole module exists to end.

    `live_model_ids()` swallows every exception and returns `[]`, and
    `resolve_model_ids()` then falls back to a one-entry static floor. Without a
    log line, an unreachable provider or a bad key looks exactly like a healthy
    run that simply had nothing to discover — the operator learns only when the
    agent exhausts its single candidate and the whole issue fails.
    """

    def test_a_discovery_failure_is_logged(self, nm, monkeypatch, caplog) -> None:
        def _raise(*a, **k):
            raise RuntimeError("connection refused")

        monkeypatch.setattr(nm, "_fetch_models_json", _raise)
        with caplog.at_level("WARNING"):
            assert nm.live_model_ids("key") == []
        assert any("connection refused" in r.getMessage() for r in caplog.records), (
            "the reason discovery failed must reach the log, not vanish"
        )

    def test_falling_back_to_the_floor_is_logged(self, nm, monkeypatch, caplog) -> None:
        monkeypatch.setattr(nm, "live_model_ids", lambda *a, **k: [])
        with caplog.at_level("WARNING"):
            nm.resolve_model_ids("key")
        assert any(
            "static" in r.getMessage().lower() or "fallback" in r.getMessage().lower()
            for r in caplog.records
        ), "running on the floor must be visible, not assumed"

    def test_a_successful_discovery_says_what_it_found(self, nm, monkeypatch, caplog) -> None:
        monkeypatch.setattr(nm, "live_model_ids", lambda *a, **k: ["nvidia/x-instruct"])
        with caplog.at_level("INFO"):
            nm.resolve_model_ids("key")
        assert any("nvidia/x-instruct" in r.getMessage() for r in caplog.records)

"""tests/test_daily_automation_2026_11_02.py — Daily automation 2026-11-02.

Changes shipped today:
- **Mistral Large 4 promoted to GA; context window expanded to 1 M** (2026-11-02).
  Mistral went generally available on 2026-11-01 and simultaneously released open
  weights to HuggingFace (``mistralai/Mistral-Large-4-0-Instruct``). The Preview API
  had a 131,072-token ceiling that the GA API lifts to the model's full 1,048,576-token
  context. The max-output limit rises from 4,096 to 32,768 tokens at GA.  The list
  price ($1.36/$4.18 per MTok) is unchanged from Preview; the 50 % launch discount
  had already expired.

  ``config/llm/models.yaml``: ``context_window`` updated from 131072 to 1048576,
  ``max_output_tokens`` from 4096 to 32768; comment updated to "GA" with open-weights
  note and new source URL.

  ``packages/ai/cost_tracker.py``: comment updated to reflect GA status; pricing
  entry ``"mistral-large-4-0": (1.36, 4.18)`` is unchanged.

  Sources: mistral.ai/news/mistral-large-4-ga, huggingface.co/mistralai/
  Mistral-Large-4-0-Instruct, openrouter.ai/mistralai/mistral-large-4-0,
  2026-11-01.

Files changed:
  ``config/llm/models.yaml``,
  ``packages/ai/cost_tracker.py``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_11_02.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

MISTRAL_LARGE_4_ID = "mistral-large-4-0"
MISTRAL_LARGE_4_INPUT_COST = 1.36
MISTRAL_LARGE_4_OUTPUT_COST = 4.18
MISTRAL_LARGE_4_CONTEXT_WINDOW_GA = 1_048_576  # 1 M — unlocked at GA
MISTRAL_LARGE_4_MAX_OUTPUT_GA = 32_768
MISTRAL_LARGE_4_CONTEXT_WINDOW_PREVIEW = 131_072  # Preview ceiling — must not remain


@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_11_02",
        REPO_ROOT / "packages" / "ai" / "cost_tracker.py",
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(scope="module")
def models_yaml():
    path = REPO_ROOT / "config" / "llm" / "models.yaml"
    with path.open() as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Cost-tracker: Mistral Large 4 pricing unchanged at GA
# ---------------------------------------------------------------------------

class TestMistralLarge4CostEntry:
    def test_id_present_in_cost_table(self, ct):
        table = ct._DEFAULT_COST_TABLE
        assert MISTRAL_LARGE_4_ID in table, (
            f"{MISTRAL_LARGE_4_ID} must have an entry in _DEFAULT_COST_TABLE"
        )

    def test_input_cost(self, ct):
        cost = ct.cost_for_tokens(MISTRAL_LARGE_4_ID, 1_000_000, 0)
        assert cost == pytest.approx(MISTRAL_LARGE_4_INPUT_COST), (
            f"{MISTRAL_LARGE_4_ID} input cost must be ${MISTRAL_LARGE_4_INPUT_COST}/MTok"
        )

    def test_output_cost(self, ct):
        cost = ct.cost_for_tokens(MISTRAL_LARGE_4_ID, 0, 1_000_000)
        assert cost == pytest.approx(MISTRAL_LARGE_4_OUTPUT_COST), (
            f"{MISTRAL_LARGE_4_ID} output cost must be ${MISTRAL_LARGE_4_OUTPUT_COST}/MTok"
        )

    def test_combined_cost(self, ct):
        """$1.36 input + $4.18 output = $5.54 per MTok each."""
        cost = ct.cost_for_tokens(MISTRAL_LARGE_4_ID, 1_000_000, 1_000_000)
        assert cost == pytest.approx(MISTRAL_LARGE_4_INPUT_COST + MISTRAL_LARGE_4_OUTPUT_COST)


# ---------------------------------------------------------------------------
# models.yaml: GA context-window and max-output corrections
# ---------------------------------------------------------------------------

class TestMistralLarge4ModelsYaml:
    @pytest.fixture(autouse=True)
    def entry(self, models_yaml):
        models = models_yaml.get("models", {})
        self._entry = models.get(MISTRAL_LARGE_4_ID)

    def test_entry_present(self):
        assert self._entry is not None, (
            f"{MISTRAL_LARGE_4_ID} must be declared in config/llm/models.yaml"
        )

    def test_context_window_is_1m(self):
        """GA context window must be 1,048,576 — not the Preview ceiling of 131,072."""
        cw = self._entry["context_window"]
        assert cw == MISTRAL_LARGE_4_CONTEXT_WINDOW_GA, (
            f"context_window should be {MISTRAL_LARGE_4_CONTEXT_WINDOW_GA} (GA); "
            f"got {cw} — still the Preview API limit?"
        )

    def test_context_window_not_preview_value(self):
        """Confirm the 131,072 Preview ceiling has been removed."""
        cw = self._entry["context_window"]
        assert cw != MISTRAL_LARGE_4_CONTEXT_WINDOW_PREVIEW, (
            f"context_window is still {MISTRAL_LARGE_4_CONTEXT_WINDOW_PREVIEW}; "
            "the GA entry must use the full 1 M context."
        )

    def test_max_output_tokens_ga(self):
        """GA output limit is 32,768; Preview was 4,096."""
        mot = self._entry["max_output_tokens"]
        assert mot == MISTRAL_LARGE_4_MAX_OUTPUT_GA, (
            f"max_output_tokens should be {MISTRAL_LARGE_4_MAX_OUTPUT_GA} (GA); got {mot}"
        )

    def test_provider(self):
        assert self._entry["provider"] == "mistral"

    def test_supports_tools(self):
        assert self._entry["supports_tools"] is True

    def test_supports_function_calling(self):
        assert self._entry["supports_function_calling"] is True

    def test_supports_json(self):
        assert self._entry["supports_json"] is True

    def test_supports_streaming(self):
        assert self._entry["supports_streaming"] is True

    def test_priority_unchanged(self):
        """Priority 62 is unchanged — model already in routing candidates."""
        assert self._entry["priority"] == 62


# ---------------------------------------------------------------------------
# Catalogue-count guard (no IDs accidentally dropped)
# ---------------------------------------------------------------------------

class TestCatalogueIntegrity:
    def test_catalogue_count_at_least_88(self, models_yaml):
        """88 IDs were in config/llm/models.yaml before this session; count must not decrease."""
        models = models_yaml.get("models", {})
        assert len(models) >= 88, (
            f"Expected ≥88 model IDs in config/llm/models.yaml; found {len(models)}."
        )

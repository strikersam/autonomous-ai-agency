"""tests/test_daily_automation_2026_09_21.py — Daily automation tests (2026-09-21).

Covers the cost-tracker gap fill applied today:

  Nine model IDs were present in ``config/llm/models.yaml`` but absent from
  ``packages/ai/cost_tracker.py``.  An absent entry means every call to
  ``cost_for_tokens()`` for that model returns 0.0 and the operator-facing
  spending dashboard never accounts for those tokens — even for paid models.

  1. ``claude-sonnet-4-5`` — paid Anthropic model ($3/$15 per MTok, same tier
     as claude-sonnet-4-6).  Was in the llm catalog with pricing declared but
     missing from cost_tracker.

  2. ``text-embedding-3-small`` — OpenAI embedding model ($0.02/MTok input, no
     output cost).  Was in the llm catalog with pricing declared but missing
     from cost_tracker.

  3. ``openai/gpt-oss-120b`` and ``openai/gpt-oss-20b`` — free models served on
     both NVIDIA NIM and Groq (``providers: [nvidia, groq]`` in the catalog).
     Free-tier: priced at (0.0, 0.0).

  4. ``mistralai/mistral-nemotron`` and ``nvidia/nemotron-3-ultra-550b-a55b`` —
     free NVIDIA NIM models added to the llm catalog on 2026-09-19 but not yet
     added to cost_tracker in that same session.

  5. ``deepseek-r1:32b``, ``qwen3-coder:30b``, ``nomic-embed-text`` — local
     Ollama models.  No network cost; priced at (0.0, 0.0).

  Invariant test: every model declared in ``config/llm/models.yaml`` with a
  non-zero ``input_cost_per_1m`` must have a corresponding entry in
  ``packages/ai/cost_tracker.py`` so billing attribution is never silently zero
  for a paid call.

Sandbox note: ``packages.ai.brain_config`` and ``packages.ai.cost_tracker``
require pydantic / backend deps not available here.  Tests verify the YAML and
source text directly — the same approach used in the 2026-09-18 and 2026-09-19
automation tests.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent


def _llm_catalog() -> dict[str, dict]:
    """Parse config/llm/models.yaml models dict."""
    data = yaml.safe_load((_ROOT / "config" / "llm" / "models.yaml").read_text())
    return dict(data.get("models") or {})


def _cost_tracker_src() -> str:
    """Read cost_tracker.py source text."""
    return (_ROOT / "packages" / "ai" / "cost_tracker.py").read_text()


# ── claude-sonnet-4-5 ────────────────────────────────────────────────────


class TestClaudeSonnet45CostEntry:
    """claude-sonnet-4-5 is a paid model ($3/$15/MTok) and must be tracked."""

    MODEL = "claude-sonnet-4-5"

    def test_in_llm_catalog(self):
        assert self.MODEL in _llm_catalog(), (
            f"{self.MODEL} missing from config/llm/models.yaml"
        )

    def test_catalog_declares_paid_pricing(self):
        entry = _llm_catalog()[self.MODEL]
        assert entry.get("input_cost_per_1m", 0) > 0, (
            f"{self.MODEL} catalog entry should declare a non-zero input cost"
        )

    def test_in_cost_tracker(self):
        assert self.MODEL in _cost_tracker_src(), (
            f"{self.MODEL} missing from packages/ai/cost_tracker.py; "
            "billing attribution for this paid model would silently return 0"
        )

    def test_cost_tracker_entry_is_paid(self):
        src = _cost_tracker_src()
        # Find the line containing this model id and assert it has a non-zero value
        for line in src.splitlines():
            if self.MODEL in line and "(" in line and "," in line:
                # Extract first number from tuple like (3.0, 15.0)
                parts = line.split("(")[1].split(",")
                try:
                    input_cost = float(parts[0].strip())
                    assert input_cost > 0, (
                        f"{self.MODEL} cost_tracker entry shows 0 input cost; "
                        "expected $3.0 per MTok"
                    )
                    return
                except (ValueError, IndexError):
                    continue
        raise AssertionError(f"Could not parse cost tuple for {self.MODEL} in cost_tracker")


# ── text-embedding-3-small ───────────────────────────────────────────────


class TestTextEmbeddingSmallCostEntry:
    """OpenAI text-embedding-3-small has a $0.02/MTok input cost and must be tracked."""

    MODEL = "text-embedding-3-small"

    def test_in_llm_catalog(self):
        assert self.MODEL in _llm_catalog()

    def test_catalog_declares_cost(self):
        entry = _llm_catalog()[self.MODEL]
        assert entry.get("input_cost_per_1m", 0) > 0

    def test_in_cost_tracker(self):
        assert self.MODEL in _cost_tracker_src(), (
            f"{self.MODEL} missing from cost_tracker; embedding calls would "
            "never be attributed to the billing dashboard"
        )


# ── GPT-OSS multi-provider models ────────────────────────────────────────


class TestGptOssMultiProviderCostEntries:
    """openai/gpt-oss-120b and openai/gpt-oss-20b appear in both NVIDIA and Groq
    candidates and must be in cost_tracker (free-tier, $0)."""

    MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]

    def test_in_llm_catalog(self):
        catalog = _llm_catalog()
        for m in self.MODELS:
            assert m in catalog, f"{m} missing from config/llm/models.yaml"

    def test_in_cost_tracker(self):
        src = _cost_tracker_src()
        for m in self.MODELS:
            assert m in src, (
                f"{m} missing from cost_tracker; would return 0 without this "
                "entry, which happens to be correct for free-tier but the entry "
                "is needed so the model appears in the stats dict at all"
            )


# ── NVIDIA NIM free-tier additions ──────────────────────────────────────


class TestNvidiaNimFreeTierCostEntries:
    """mistralai/mistral-nemotron and nvidia/nemotron-3-ultra-550b-a55b are
    NVIDIA NIM free-tier models; they were added to the llm catalog on 2026-09-19
    but their cost_tracker rows were missing until today."""

    MODELS = [
        "mistralai/mistral-nemotron",
        "nvidia/nemotron-3-ultra-550b-a55b",
    ]

    def test_in_llm_catalog(self):
        catalog = _llm_catalog()
        for m in self.MODELS:
            assert m in catalog, f"{m} missing from config/llm/models.yaml"

    def test_in_cost_tracker(self):
        src = _cost_tracker_src()
        for m in self.MODELS:
            assert m in src, f"{m} missing from packages/ai/cost_tracker.py"


# ── Ollama local models ──────────────────────────────────────────────────


class TestOllamaLocalCostEntries:
    """deepseek-r1:32b, qwen3-coder:30b, nomic-embed-text are local Ollama models
    (no network cost) that needed cost_tracker rows for completeness."""

    MODELS = [
        "deepseek-r1:32b",
        "qwen3-coder:30b",
        "nomic-embed-text",
    ]

    def test_in_llm_catalog(self):
        catalog = _llm_catalog()
        for m in self.MODELS:
            assert m in catalog, f"{m} missing from config/llm/models.yaml"

    def test_in_cost_tracker(self):
        src = _cost_tracker_src()
        for m in self.MODELS:
            assert m in src, f"{m} missing from packages/ai/cost_tracker.py"


# ── Invariant: every paid catalog model has a cost_tracker entry ─────────


class TestPaidModelsCostTrackerCoverage:
    """Every model in config/llm/models.yaml that declares a non-zero
    input_cost_per_1m must appear in packages/ai/cost_tracker.py.

    This test prevents a silent billing gap where a paid model is added to the
    routing catalog with accurate pricing, but cost_for_tokens() returns 0
    for every call to it because the cost_tracker was never updated.
    """

    def test_no_paid_model_missing_from_cost_tracker(self):
        catalog = _llm_catalog()
        src = _cost_tracker_src()
        missing = []
        for mid, info in catalog.items():
            if not isinstance(info, dict):
                continue
            if info.get("input_cost_per_1m", 0) > 0:
                if mid not in src:
                    missing.append((mid, info["input_cost_per_1m"]))
        assert not missing, (
            "The following paid models are declared in config/llm/models.yaml "
            "but have no entry in packages/ai/cost_tracker.py — "
            "cost_for_tokens() will return 0 for every call to them:\n"
            + "\n".join(f"  {m}  (${c}/MTok input)" for m, c in sorted(missing))
        )

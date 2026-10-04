"""tests/test_daily_automation_2026_10_04.py — Daily automation 2026-10-04.

Changes shipped today:
- **GPT-5.5 and GPT-5.5-pro cost entries added** (``gpt-5.5``, ``gpt-5.5-pro``).
  OpenAI GPT-5.5 released May 2026 — 1,050,000-token context, 128K output.
  Pricing: $5.00/$30.00 per MTok (gpt-5.5), $30.00/$180.00 per MTok (gpt-5.5-pro).
  Not yet on NVIDIA NIM; entries cover direct-OpenAI or proxied usage.
  Source: platform.openai.com/docs/models, openrouter.ai/openai/gpt-5.5, 2026-10-04.

- **GPT-Realtime-2.1 and GPT-Realtime-2.1-mini cost entries added**.
  OpenAI's second-generation realtime voice/text models (announced October 2026).
  Support text + audio inputs over WebRTC/WebSocket/SIP. Text-token pricing:
  ``gpt-realtime-2.1``: $4.00/$24.00 per MTok.
  ``gpt-realtime-2.1-mini``: $0.60/$2.40 per MTok.
  Context: 128K tokens; max output: 32K tokens.
  Source: developers.openai.com/api/docs/models, 2026-10-04.

- **Groq Llama 4 Scout 17B 16E declared** (``meta-llama/llama-4-scout-17b-16e-instruct``).
  Distinct from NVIDIA NIM's free ``meta/llama-4-scout-17b-16e-instruct`` entry.
  Groq's LPU inference at 594–750 tok/s; 128K context window (Preview tier, 30 RPM).
  Vision inputs supported (up to 20 MB); tool calling confirmed on Groq.
  Pricing: $0.11/$0.34 per MTok. Priority 99 (explicit-only; not in routing
  candidates until probed on this account).
  Source: pricepertoken.com, console.groq.com, 2026-10-04.

Files changed:
  ``packages/ai/cost_tracker.py``, ``config/llm/models.yaml``,
  ``CHANGELOG.md``, ``docs/changelog.md``,
  ``tests/test_daily_automation_2026_10_04.py`` (this file).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ct():
    spec = importlib.util.spec_from_file_location(
        "cost_tracker_2026_10_04",
        REPO_ROOT / "packages" / "ai" / "cost_tracker.py",
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(scope="module")
def llm_models():
    return yaml.safe_load(
        (REPO_ROOT / "config" / "llm" / "models.yaml").read_text()
    )


# ---------------------------------------------------------------------------
# GPT-5.5 cost entries
# ---------------------------------------------------------------------------

class TestGPT55CostEntries:
    def test_gpt55_input_cost(self, ct):
        cost = ct.cost_for_tokens("gpt-5.5", 1_000_000, 0)
        assert cost == pytest.approx(5.0), "gpt-5.5 input cost must be $5.00/MTok"

    def test_gpt55_output_cost(self, ct):
        cost = ct.cost_for_tokens("gpt-5.5", 0, 1_000_000)
        assert cost == pytest.approx(30.0), "gpt-5.5 output cost must be $30.00/MTok"

    def test_gpt55_pro_input_cost(self, ct):
        cost = ct.cost_for_tokens("gpt-5.5-pro", 1_000_000, 0)
        assert cost == pytest.approx(30.0), "gpt-5.5-pro input cost must be $30.00/MTok"

    def test_gpt55_pro_output_cost(self, ct):
        cost = ct.cost_for_tokens("gpt-5.5-pro", 0, 1_000_000)
        assert cost == pytest.approx(180.0), "gpt-5.5-pro output cost must be $180.00/MTok"

    def test_gpt55_cheaper_than_pro(self, ct):
        base_in = ct.cost_for_tokens("gpt-5.5", 1_000_000, 0)
        pro_in = ct.cost_for_tokens("gpt-5.5-pro", 1_000_000, 0)
        assert base_in < pro_in, "gpt-5.5 should be cheaper than gpt-5.5-pro"

    def test_gpt55_returns_nonzero(self, ct):
        """Sanity: gpt-5.5 is a paid model, not free."""
        cost = ct.cost_for_tokens("gpt-5.5", 100, 100)
        assert cost > 0.0


# ---------------------------------------------------------------------------
# GPT-Realtime-2.1 cost entries
# ---------------------------------------------------------------------------

class TestGPTRealtime21CostEntries:
    def test_realtime21_input_cost(self, ct):
        cost = ct.cost_for_tokens("gpt-realtime-2.1", 1_000_000, 0)
        assert cost == pytest.approx(4.0), "gpt-realtime-2.1 text input cost must be $4.00/MTok"

    def test_realtime21_output_cost(self, ct):
        cost = ct.cost_for_tokens("gpt-realtime-2.1", 0, 1_000_000)
        assert cost == pytest.approx(24.0), "gpt-realtime-2.1 text output cost must be $24.00/MTok"

    def test_realtime21_mini_input_cost(self, ct):
        cost = ct.cost_for_tokens("gpt-realtime-2.1-mini", 1_000_000, 0)
        assert cost == pytest.approx(0.60), "gpt-realtime-2.1-mini text input cost must be $0.60/MTok"

    def test_realtime21_mini_output_cost(self, ct):
        cost = ct.cost_for_tokens("gpt-realtime-2.1-mini", 0, 1_000_000)
        assert cost == pytest.approx(2.40), "gpt-realtime-2.1-mini text output cost must be $2.40/MTok"

    def test_mini_cheaper_than_full_input(self, ct):
        mini = ct.cost_for_tokens("gpt-realtime-2.1-mini", 1_000_000, 0)
        full = ct.cost_for_tokens("gpt-realtime-2.1", 1_000_000, 0)
        assert mini < full, "gpt-realtime-2.1-mini must be cheaper than gpt-realtime-2.1"

    def test_mini_cheaper_than_full_output(self, ct):
        mini = ct.cost_for_tokens("gpt-realtime-2.1-mini", 0, 1_000_000)
        full = ct.cost_for_tokens("gpt-realtime-2.1", 0, 1_000_000)
        assert mini < full


# ---------------------------------------------------------------------------
# Groq Llama 4 Scout cost entry
# ---------------------------------------------------------------------------

class TestGroqLlama4ScoutCostEntry:
    GROQ_ID = "meta-llama/llama-4-scout-17b-16e-instruct"
    NVIDIA_ID = "meta/llama-4-scout-17b-16e-instruct"

    def test_groq_input_cost(self, ct):
        cost = ct.cost_for_tokens(self.GROQ_ID, 1_000_000, 0)
        assert cost == pytest.approx(0.11), "Groq Llama 4 Scout input cost must be $0.11/MTok"

    def test_groq_output_cost(self, ct):
        cost = ct.cost_for_tokens(self.GROQ_ID, 0, 1_000_000)
        assert cost == pytest.approx(0.34), "Groq Llama 4 Scout output cost must be $0.34/MTok"

    def test_nvidia_free_entry_still_zero(self, ct):
        """NVIDIA NIM free entry must remain at $0/$0 — must not be removed or repriced."""
        cost = ct.cost_for_tokens(self.NVIDIA_ID, 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.0), (
            f"NVIDIA NIM free entry {self.NVIDIA_ID!r} must remain $0/$0"
        )

    def test_groq_more_expensive_than_nvidia(self, ct):
        groq = ct.cost_for_tokens(self.GROQ_ID, 1_000_000, 0)
        nvidia = ct.cost_for_tokens(self.NVIDIA_ID, 1_000_000, 0)
        assert groq > nvidia, "Groq (paid) must cost more than NVIDIA NIM (free)"


# ---------------------------------------------------------------------------
# Groq Llama 4 Scout models.yaml entry
# ---------------------------------------------------------------------------

class TestGroqLlama4ScoutModelDeclaration:
    MODEL_KEY = "meta-llama/llama-4-scout-17b-16e-instruct"

    def test_model_declared(self, llm_models):
        assert self.MODEL_KEY in llm_models["models"], (
            f"{self.MODEL_KEY!r} must be declared in config/llm/models.yaml"
        )

    def test_provider_is_groq(self, llm_models):
        m = llm_models["models"][self.MODEL_KEY]
        assert m.get("provider") == "groq"

    def test_context_window(self, llm_models):
        m = llm_models["models"][self.MODEL_KEY]
        assert m.get("context_window") == 131072, "128K (131072) context window expected"

    def test_supports_images(self, llm_models):
        m = llm_models["models"][self.MODEL_KEY]
        assert m.get("supports_images") is True, "Llama 4 Scout supports vision inputs"

    def test_supports_tools(self, llm_models):
        m = llm_models["models"][self.MODEL_KEY]
        assert m.get("supports_tools") is True, "Tool calling confirmed on Groq"

    def test_explicit_only_priority(self, llm_models):
        m = llm_models["models"][self.MODEL_KEY]
        assert m.get("priority", 0) >= 90, (
            "Unprobed Groq model must have priority >= 90 (explicit-only)"
        )

    def test_input_cost_in_yaml(self, llm_models):
        m = llm_models["models"][self.MODEL_KEY]
        assert m.get("input_cost_per_1m") == pytest.approx(0.11)

    def test_output_cost_in_yaml(self, llm_models):
        m = llm_models["models"][self.MODEL_KEY]
        assert m.get("output_cost_per_1m") == pytest.approx(0.34)


# ---------------------------------------------------------------------------
# Changelog parity guard
# ---------------------------------------------------------------------------

class TestChangelogParity:
    def test_changelog_mentions_gpt55(self):
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text()
        assert "gpt-5.5" in changelog, "CHANGELOG.md must mention gpt-5.5"

    def test_changelog_mentions_realtime21(self):
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text()
        assert "gpt-realtime-2.1" in changelog, "CHANGELOG.md must mention gpt-realtime-2.1"

    def test_changelog_mentions_llama4_scout_groq(self):
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text()
        assert "meta-llama/llama-4-scout" in changelog or "Llama 4 Scout" in changelog

    def test_docs_changelog_has_date(self):
        docs = (REPO_ROOT / "docs" / "changelog.md").read_text()
        assert "2026-10-04" in docs, "docs/changelog.md must have a 2026-10-04 entry"

    def test_root_changelog_has_date(self):
        root = (REPO_ROOT / "CHANGELOG.md").read_text()
        assert "2026-10-04" in root, "CHANGELOG.md must have a 2026-10-04 entry"

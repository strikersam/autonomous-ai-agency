"""tests/test_daily_automation_2026_08_06.py — Daily automation (2026-08-06).

Covers the model-catalog improvements applied today:

  1. Claude 5 family (claude-opus-5, claude-sonnet-5, claude-fable-5,
     claude-opus-4-8) added to config/llm/models.yaml so the new LLM
     router can route to them with correct capability metadata — these
     models were added to config/models.yaml and brain_config.py on
     2026-08-03 but the llm/models.yaml parity was missed.

  2. Deprecated Groq Llama 4 Maverick (llama-4-maverick-17b-128e-instruct)
     removed from config/llm/models.yaml — deprecated on Groq since March
     2026; removed from brain_config.py candidates on 2026-08-03 but the
     llm/models.yaml entry was not cleaned up at the same time.
"""
from __future__ import annotations

import os
import yaml

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
LLM_MODELS_YAML = os.path.join(REPO_ROOT, "config", "llm", "models.yaml")


def _load_yaml() -> dict:
    with open(LLM_MODELS_YAML, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ── Claude 5 family present ──────────────────────────────────────────────────

CLAUDE5_MODELS = [
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-fable-5",
    "claude-opus-4-8",
]


def test_claude5_models_in_llm_models_yaml():
    cfg = _load_yaml()
    models = cfg.get("models", {})
    missing = [m for m in CLAUDE5_MODELS if m not in models]
    assert not missing, f"Missing Claude 5 models in config/llm/models.yaml: {missing}"


def test_claude_opus5_provider_is_anthropic():
    cfg = _load_yaml()
    assert cfg["models"]["claude-opus-5"]["provider"] == "anthropic"


def test_claude_sonnet5_provider_is_anthropic():
    cfg = _load_yaml()
    assert cfg["models"]["claude-sonnet-5"]["provider"] == "anthropic"


def test_claude_fable5_provider_is_anthropic():
    cfg = _load_yaml()
    assert cfg["models"]["claude-fable-5"]["provider"] == "anthropic"


def test_claude_opus48_provider_is_anthropic():
    cfg = _load_yaml()
    assert cfg["models"]["claude-opus-4-8"]["provider"] == "anthropic"


def test_claude_opus5_context_window():
    cfg = _load_yaml()
    assert cfg["models"]["claude-opus-5"]["context_window"] == 200000


def test_claude_sonnet5_context_window():
    cfg = _load_yaml()
    assert cfg["models"]["claude-sonnet-5"]["context_window"] == 200000


def test_claude_fable5_context_window():
    cfg = _load_yaml()
    assert cfg["models"]["claude-fable-5"]["context_window"] == 200000


def test_claude_opus48_context_window():
    cfg = _load_yaml()
    assert cfg["models"]["claude-opus-4-8"]["context_window"] == 200000


def test_claude5_models_support_tools():
    cfg = _load_yaml()
    for mid in CLAUDE5_MODELS:
        assert cfg["models"][mid].get("supports_tools") is True, \
            f"{mid} must have supports_tools: true"


def test_claude5_models_support_streaming():
    cfg = _load_yaml()
    for mid in CLAUDE5_MODELS:
        assert cfg["models"][mid].get("supports_streaming") is True, \
            f"{mid} must have supports_streaming: true"


def test_claude5_models_support_reasoning():
    cfg = _load_yaml()
    for mid in CLAUDE5_MODELS:
        assert cfg["models"][mid].get("supports_reasoning") is True, \
            f"{mid} must have supports_reasoning: true"


def test_claude_opus5_is_paid():
    cfg = _load_yaml()
    m = cfg["models"]["claude-opus-5"]
    assert m.get("input_cost_per_1m", 0) > 0, "claude-opus-5 should declare a non-zero input cost"
    assert m.get("output_cost_per_1m", 0) > 0, "claude-opus-5 should declare a non-zero output cost"


def test_claude_sonnet5_has_expected_max_output():
    cfg = _load_yaml()
    assert cfg["models"]["claude-sonnet-5"]["max_output_tokens"] >= 16000


def test_claude_fable5_aliases_include_mythos():
    cfg = _load_yaml()
    aliases = cfg["models"]["claude-fable-5"].get("aliases", [])
    assert "claude-mythos-5" in aliases, \
        f"claude-fable-5 should alias claude-mythos-5 (provider code also uses that name); got {aliases}"


def test_claude5_priorities_are_distinct():
    cfg = _load_yaml()
    priorities = [cfg["models"][m]["priority"] for m in CLAUDE5_MODELS]
    assert len(priorities) == len(set(priorities)), \
        f"Claude 5 model priorities must be unique; got {dict(zip(CLAUDE5_MODELS, priorities))}"


# ── Deprecated Groq Llama 4 removed ─────────────────────────────────────────

DEPRECATED_GROQ_MODELS = [
    "llama-4-maverick-17b-128e-instruct",
    "llama-4-scout-17b-16e-instruct",
]


def test_deprecated_groq_llama4_not_in_llm_models_yaml():
    cfg = _load_yaml()
    models = cfg.get("models", {})
    still_present = [
        m for m in DEPRECATED_GROQ_MODELS
        if m in models and models[m].get("provider") == "groq"
    ]
    assert not still_present, (
        f"Deprecated Groq Llama 4 models still in config/llm/models.yaml: {still_present}. "
        "These were deprecated on Groq in March 2026 and should be removed."
    )


# ── Parity: Claude 5 models present in BOTH catalog files ───────────────────

def test_claude5_models_in_main_catalog():
    """The Claude 5 models added to config/llm/models.yaml today should also
    be present as candidates in config/models.yaml (the legacy brain catalog).
    Verified against the update made on 2026-08-03.
    """
    import yaml as _yaml
    main_yaml_path = os.path.join(REPO_ROOT, "config", "models.yaml")
    with open(main_yaml_path, encoding="utf-8") as fh:
        main_cfg = _yaml.safe_load(fh)

    main_candidates: set[str] = set()
    for provider_data in (main_cfg.get("providers") or {}).values():
        for cand in provider_data.get("candidates") or []:
            main_candidates.add(cand)

    missing_from_main = [m for m in CLAUDE5_MODELS if m not in main_candidates]
    assert not missing_from_main, (
        f"Claude 5 models missing from config/models.yaml anthropic candidates: {missing_from_main}. "
        "config/models.yaml was updated 2026-08-03 and should already have these."
    )

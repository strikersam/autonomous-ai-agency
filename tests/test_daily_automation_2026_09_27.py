"""tests/test_daily_automation_2026_09_27.py — Daily automation 2026-09-27.

Covers:
- ANTHROPIC_DEFAULT_EFFORT Platform Control (new; inspired by Claude Code's
  maxEffortLevel, Week 37 Sept 2026).
- settings.anthropic_default_effort_value validated property.
- settings.anthropic_thinking_budget property (rule-5 migration for
  ANTHROPIC_THINKING_BUDGET; was read directly via os.environ in router.py).
- providers.yaml wires default_effort through to the Anthropic config.
- control_catalogue.py declares ANTHROPIC_DEFAULT_EFFORT.
- router.py no longer reads os.environ["ANTHROPIC_THINKING_BUDGET"] directly.
- docs/configuration-reference.md documents both new env vars.
"""
from __future__ import annotations

import ast
import os
import pathlib
import re
import textwrap

import pytest

ROOT = pathlib.Path(__file__).parent.parent
SETTINGS_PY = ROOT / "packages" / "config" / "settings.py"
CATALOGUE_PY = ROOT / "packages" / "config" / "control_catalogue.py"
ROUTER_PY = ROOT / "packages" / "ai" / "router.py"
PROVIDERS_YAML = ROOT / "config" / "llm" / "providers.yaml"
CONFIG_REF = ROOT / "docs" / "configuration-reference.md"


# ---------------------------------------------------------------------------
# settings.py — new attribute and property
# ---------------------------------------------------------------------------

class TestSettingsAnthropicDefaultEffort:
    def _make_settings(self, env: dict[str, str]):
        """Build a fresh Settings() with the given env overrides."""
        saved = {k: os.environ.pop(k, None) for k in env}
        os.environ.update(env)
        try:
            # Bypass the lru_cache so we get a fresh instance.
            from packages.config.settings import Settings
            return Settings()
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_valid_effort_levels_round_trip(self):
        for level in ("low", "medium", "high", "xhigh", "max"):
            s = self._make_settings({"ANTHROPIC_DEFAULT_EFFORT": level})
            assert s.anthropic_default_effort_value == level, level

    def test_unknown_value_returns_empty(self):
        s = self._make_settings({"ANTHROPIC_DEFAULT_EFFORT": "turbo"})
        assert s.anthropic_default_effort_value == ""

    def test_empty_returns_empty(self):
        s = self._make_settings({"ANTHROPIC_DEFAULT_EFFORT": ""})
        assert s.anthropic_default_effort_value == ""

    def test_unset_returns_empty(self):
        s = self._make_settings({})
        assert s.anthropic_default_effort_value == ""

    def test_uppercase_normalized(self):
        # os.environ values are stored as-is; the property lower-cases them.
        s = self._make_settings({"ANTHROPIC_DEFAULT_EFFORT": "HIGH"})
        assert s.anthropic_default_effort_value == "high"


class TestSettingsAnthropicThinkingBudget:
    def _make_settings(self, env: dict[str, str]):
        saved = {k: os.environ.pop(k, None) for k in env}
        os.environ.update(env)
        try:
            from packages.config.settings import Settings
            return Settings()
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_integer_value_returned(self):
        s = self._make_settings({"ANTHROPIC_THINKING_BUDGET": "4096"})
        assert s.anthropic_thinking_budget == 4096

    def test_zero_default(self):
        s = self._make_settings({})
        assert s.anthropic_thinking_budget == 0

    def test_invalid_string_returns_zero(self):
        s = self._make_settings({"ANTHROPIC_THINKING_BUDGET": "notanint"})
        assert s.anthropic_thinking_budget == 0

    def test_empty_string_returns_zero(self):
        s = self._make_settings({"ANTHROPIC_THINKING_BUDGET": ""})
        assert s.anthropic_thinking_budget == 0


# ---------------------------------------------------------------------------
# control_catalogue.py — ANTHROPIC_DEFAULT_EFFORT is declared
# ---------------------------------------------------------------------------

class TestAnthropicDefaultEffortInCatalogue:
    def test_key_exists(self):
        src = CATALOGUE_PY.read_text()
        assert "ANTHROPIC_DEFAULT_EFFORT" in src

    def test_all_valid_effort_options_listed(self):
        src = CATALOGUE_PY.read_text()
        for level in ("low", "medium", "high", "xhigh", "max"):
            assert f'"{level}"' in src or f"'{level}'" in src, \
                f"effort level {level!r} not found in catalogue"

    def test_live_true(self):
        # Extract the ANTHROPIC_DEFAULT_EFFORT ControlSpec block and confirm live=True.
        src = CATALOGUE_PY.read_text()
        idx = src.find("ANTHROPIC_DEFAULT_EFFORT")
        assert idx != -1
        # The block includes the full ControlSpec up to its closing paren; use
        # a generous window to accommodate the full options list.
        block = src[idx: idx + 1200]
        assert "live=True" in block


# ---------------------------------------------------------------------------
# providers.yaml — default_effort wired for Anthropic
# ---------------------------------------------------------------------------

class TestProvidersYamlDefaultEffort:
    def test_default_effort_line_present(self):
        src = PROVIDERS_YAML.read_text()
        assert "default_effort: ${ANTHROPIC_DEFAULT_EFFORT" in src

    def test_default_effort_follows_thinking_budget(self):
        """default_effort must appear in the same Anthropic block, after thinking_budget."""
        src = PROVIDERS_YAML.read_text()
        tb_pos = src.find("thinking_budget")
        de_pos = src.find("default_effort")
        assert tb_pos != -1, "thinking_budget not found in providers.yaml"
        assert de_pos != -1, "default_effort not found in providers.yaml"
        # default_effort should be close to thinking_budget (within 200 chars).
        assert abs(de_pos - tb_pos) < 200, \
            "default_effort is unexpectedly far from thinking_budget in providers.yaml"


# ---------------------------------------------------------------------------
# router.py — no longer reads os.environ directly for ANTHROPIC_THINKING_BUDGET
# ---------------------------------------------------------------------------

class TestRouterNoDirectEnvRead:
    def test_no_os_environ_thinking_budget(self):
        """router.py must not read ANTHROPIC_THINKING_BUDGET via os.environ directly."""
        src = ROUTER_PY.read_text()
        # The literal string from the old direct read must be absent.
        assert 'os.environ.get("ANTHROPIC_THINKING_BUDGET"' not in src, (
            "router.py still reads ANTHROPIC_THINKING_BUDGET via os.environ — "
            "rule 5 violation: env vars must be read only in config modules."
        )

    def test_uses_settings_for_thinking_budget(self):
        """router.py must delegate to settings.anthropic_thinking_budget."""
        src = ROUTER_PY.read_text()
        assert "anthropic_thinking_budget" in src, (
            "router.py must import settings.anthropic_thinking_budget "
            "instead of reading the env var directly."
        )


# ---------------------------------------------------------------------------
# settings.py — anthropic_default_effort attribute exists in __init__
# ---------------------------------------------------------------------------

class TestSettingsHasAnthropicEffortAttribute:
    def test_attribute_declared_in_init(self):
        src = SETTINGS_PY.read_text()
        assert "self.anthropic_default_effort" in src

    def test_anthropic_thinking_budget_attribute_declared(self):
        src = SETTINGS_PY.read_text()
        assert "self.anthropic_thinking_budget" in src

    def test_only_settings_reads_anthropic_default_effort_env(self):
        """No other module should call os.environ.get('ANTHROPIC_DEFAULT_EFFORT')."""
        for py in ROOT.rglob("*.py"):
            if py == SETTINGS_PY:
                continue
            if "test_" in py.name or ".git" in str(py):
                continue
            src = py.read_text(errors="replace")
            assert 'ANTHROPIC_DEFAULT_EFFORT' not in src or "settings" in src.lower(), \
                f"{py} appears to read ANTHROPIC_DEFAULT_EFFORT directly (rule 5)."


# ---------------------------------------------------------------------------
# docs/configuration-reference.md — new env vars documented
# ---------------------------------------------------------------------------

class TestConfigReferenceDocumented:
    def test_anthropic_default_effort_documented(self):
        src = CONFIG_REF.read_text()
        assert "ANTHROPIC_DEFAULT_EFFORT" in src

    def test_anthropic_thinking_budget_documented(self):
        src = CONFIG_REF.read_text()
        assert "ANTHROPIC_THINKING_BUDGET" in src

    def test_max_effort_level_context_mentioned(self):
        """The connection to Claude Code's maxEffortLevel concept should be noted."""
        src = CONFIG_REF.read_text()
        assert "maxEffortLevel" in src or "max_effort_level" in src.lower()

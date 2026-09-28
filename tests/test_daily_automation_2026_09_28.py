"""tests/test_daily_automation_2026_09_28.py — Daily automation 2026-09-28.

Covers three items from the 2026-W40 routine backlog (issue #1611):

1. Prompt-cache billing bug fix (item 2 in backlog):
   - cost_for_tokens() now accepts cached_tokens and prices them at the
     provider's documented cache-read discount rate.
   - record_usage() accepts cached_tokens and passes it through.
   - packages/llm/budget.py mirrors cached_tokens to cost_tracker.
   - packages/ai/router.py passes cache_read_input_tokens to record_usage.

2. X-Claude-Code-Prompt-Id forwarding into Langfuse (item 1 in backlog):
   - emit_chat_observation() accepts prompt_id.
   - A present prompt_id is added as a prompt:<id> tag.
   - An absent prompt_id is a no-op (backward compatible).

3. Prompt-audit script (item 4 in backlog):
   - scripts/prompt_audit.py exists and is importable.
   - It flags a non-existent file path.
   - It flags a model id that isn't in config/models.yaml.
   - It passes cleanly on valid input.
"""
from __future__ import annotations

import inspect
import pathlib
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

ROOT = pathlib.Path(__file__).parent.parent
COST_TRACKER = ROOT / "packages" / "ai" / "cost_tracker.py"
LANGFUSE_OBS = ROOT / "langfuse_obs.py"
CHAT_HANDLERS = ROOT / "chat_handlers.py"
ANTHROPIC_COMPAT = ROOT / "handlers" / "anthropic_compat.py"
PROXY_PY = ROOT / "proxy.py"
BUDGET_PY = ROOT / "packages" / "llm" / "budget.py"
ROUTER_PY = ROOT / "packages" / "ai" / "router.py"
PROMPT_AUDIT = ROOT / "scripts" / "prompt_audit.py"


# ── Item 2: Prompt-cache billing fix ────────────────────────────────────────

class TestCacheReadBilling:
    """cost_for_tokens prices cached tokens at the provider's discount rate."""

    def _ct(self) -> types.ModuleType:
        import packages.ai.cost_tracker as ct
        return ct

    def test_cached_tokens_lower_cost_for_anthropic(self):
        ct = self._ct()
        model = "claude-sonnet-5"
        full_cost = ct.cost_for_tokens(model, 10_000, 500, cached_tokens=0)
        cached_cost = ct.cost_for_tokens(model, 10_000, 500, cached_tokens=8_000)
        assert cached_cost < full_cost, (
            "8 000 cached tokens should reduce cost vs. 0 cached tokens"
        )

    def test_cached_tokens_anthropic_discount_is_10_pct(self):
        ct = self._ct()
        model = "claude-sonnet-5"
        # 1M prompt tokens, all cached, no completions.
        full_cost = ct.cost_for_tokens(model, 1_000_000, 0, cached_tokens=0)
        all_cached = ct.cost_for_tokens(model, 1_000_000, 0, cached_tokens=1_000_000)
        assert abs(all_cached - full_cost * 0.1) < 1e-9, (
            f"Anthropic cache-read should cost 10% of full input; "
            f"full={full_cost:.6f} all_cached={all_cached:.6f}"
        )

    def test_cached_tokens_gemini_discount_is_25_pct(self):
        ct = self._ct()
        model = "gemini-2.5-pro"
        full_cost = ct.cost_for_tokens(model, 1_000_000, 0, cached_tokens=0)
        all_cached = ct.cost_for_tokens(model, 1_000_000, 0, cached_tokens=1_000_000)
        assert abs(all_cached - full_cost * 0.25) < 1e-9, (
            "Gemini cache-read should cost 25% of full input"
        )

    def test_cached_tokens_zero_for_free_models(self):
        ct = self._ct()
        model = "nvidia/nemotron-3-super-120b-a12b"
        # Free model: cost is 0 regardless of caching.
        assert ct.cost_for_tokens(model, 1_000_000, 1_000_000, cached_tokens=500_000) == 0.0

    def test_cached_tokens_capped_at_prompt_tokens(self):
        ct = self._ct()
        model = "claude-sonnet-5"
        # cached_tokens > prompt_tokens should be silently clamped.
        cost_clamped = ct.cost_for_tokens(model, 1_000, 100, cached_tokens=5_000)
        cost_all = ct.cost_for_tokens(model, 1_000, 100, cached_tokens=1_000)
        assert cost_clamped == cost_all, (
            "cached_tokens > prompt_tokens should be clamped to prompt_tokens"
        )

    def test_zero_cached_tokens_is_backward_compatible(self):
        ct = self._ct()
        model = "claude-opus-5-5"
        old_cost = ct.cost_for_tokens(model, 1_000, 100)
        new_cost = ct.cost_for_tokens(model, 1_000, 100, cached_tokens=0)
        assert old_cost == new_cost

    def test_record_usage_accepts_cached_tokens(self):
        ct = self._ct()
        sig = inspect.signature(ct.record_usage)
        assert "cached_tokens" in sig.parameters, (
            "record_usage() should accept cached_tokens kwarg"
        )

    def test_budget_mirror_passes_cached_tokens(self):
        src = BUDGET_PY.read_text()
        assert "cached_tokens=usage.cached_tokens" in src, (
            "budget.py _mirror_to_cost_tracker should pass cached_tokens"
        )

    def test_router_passes_cache_read_input_tokens(self):
        src = ROUTER_PY.read_text()
        assert "cache_read_input_tokens" in src
        assert "cached_tokens=_cached" in src, (
            "router.py should extract cache_read_input_tokens and pass as "
            "cached_tokens to record_usage"
        )


# ── Item 1: X-Claude-Code-Prompt-Id forwarding ──────────────────────────────

class TestPromptIdForwarding:
    """emit_chat_observation accepts prompt_id and emits it as a tag."""

    def test_emit_chat_observation_signature_has_prompt_id(self):
        import langfuse_obs
        sig = inspect.signature(langfuse_obs.emit_chat_observation)
        assert "prompt_id" in sig.parameters, (
            "emit_chat_observation should accept prompt_id kwarg"
        )

    def test_langfuse_http_sync_signature_has_prompt_id(self):
        src = LANGFUSE_OBS.read_text()
        assert "prompt_id: str | None = None" in src

    def test_prompt_tag_added_when_present(self):
        """prompt_id is forwarded to the HTTP emitter when provided."""
        import langfuse_obs

        captured: dict = {}

        def fake_http(**kwargs):
            captured.update(kwargs)

        def fake_env_val(key: str) -> str:
            return "1" if key == "LANGFUSE_USE_HTTP_ONLY" else ""

        with patch.object(langfuse_obs, "_langfuse_enabled", return_value=True), \
             patch.object(langfuse_obs, "_env_val", side_effect=fake_env_val), \
             patch.object(langfuse_obs, "_emit_langfuse_http", fake_http):
            langfuse_obs.emit_chat_observation(
                email="test@example.com",
                department="eng",
                key_id=None,
                model="claude-sonnet-5",
                messages=[],
                output_text="hi",
                prompt_tokens=10,
                completion_tokens=5,
                prompt_id="pid-abc123",
            )

        # HTTP-only path: verify prompt_id was forwarded to the emitter.
        assert captured.get("prompt_id") == "pid-abc123", (
            f"prompt_id should be forwarded to the HTTP emitter; captured={captured}"
        )

    def test_no_prompt_tag_when_absent(self):
        """Absent prompt_id is backward compatible — no prompt_id forwarded."""
        import langfuse_obs

        captured: dict = {}

        def fake_http(**kwargs):
            captured.update(kwargs)

        def fake_env_val(key: str) -> str:
            return "1" if key == "LANGFUSE_USE_HTTP_ONLY" else ""

        with patch.object(langfuse_obs, "_langfuse_enabled", return_value=True), \
             patch.object(langfuse_obs, "_env_val", side_effect=fake_env_val), \
             patch.object(langfuse_obs, "_emit_langfuse_http", fake_http):
            langfuse_obs.emit_chat_observation(
                email="test@example.com",
                department="eng",
                key_id=None,
                model="claude-sonnet-5",
                messages=[],
                output_text="hi",
                prompt_tokens=10,
                completion_tokens=5,
            )

        assert captured.get("prompt_id") is None, (
            "prompt_id should be None when not supplied"
        )

    def test_chat_handlers_extracts_prompt_id(self):
        src = CHAT_HANDLERS.read_text()
        assert 'request.headers.get("x-claude-code-prompt-id")' in src

    def test_anthropic_compat_extracts_prompt_id(self):
        src = ANTHROPIC_COMPAT.read_text()
        assert 'request.headers.get("x-claude-code-prompt-id")' in src

    def test_proxy_extracts_prompt_id(self):
        src = PROXY_PY.read_text()
        assert 'request.headers.get("x-claude-code-prompt-id")' in src


# ── Item 4: Prompt audit script ─────────────────────────────────────────────

class TestPromptAuditScript:
    """scripts/prompt_audit.py flags stale paths and unknown model IDs."""

    def _load_audit(self) -> types.ModuleType:
        import importlib.util
        spec = importlib.util.spec_from_file_location("prompt_audit", PROMPT_AUDIT)
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    def test_script_exists(self):
        assert PROMPT_AUDIT.exists(), "scripts/prompt_audit.py must exist"

    def test_flags_nonexistent_path(self, tmp_path):
        audit_mod = self._load_audit()
        md = tmp_path / "TEST.md"
        md.write_text("`packages/nonexistent/file.py`\n")
        findings = audit_mod._check_file_paths(md.read_text(), "TEST.md")
        assert any("nonexistent/file.py" in f for f in findings), (
            "Should flag a path that does not exist in the repo"
        )

    def test_no_finding_for_existing_path(self, tmp_path):
        audit_mod = self._load_audit()
        md = tmp_path / "TEST.md"
        # Use a path we know exists.
        md.write_text("`packages/ai/cost_tracker.py`\n")
        findings = audit_mod._check_file_paths(md.read_text(), "TEST.md")
        assert not findings, "Should not flag an existing file path"

    def test_flags_unknown_model_id(self, tmp_path):
        audit_mod = self._load_audit()
        known_ids = {"claude-sonnet-5", "gemini-2.5-pro"}
        md = tmp_path / "TEST.md"
        md.write_text("`nvidia/made-up-model-99b`\n")
        findings = audit_mod._check_model_ids(md.read_text(), "TEST.md", known_ids)
        assert any("made-up-model-99b" in f for f in findings), (
            "Should flag a model id not in known_ids"
        )

    def test_no_finding_for_known_model(self, tmp_path):
        audit_mod = self._load_audit()
        known_ids = {"claude-sonnet-5", "gemini-2.5-pro"}
        md = tmp_path / "TEST.md"
        md.write_text("`claude-sonnet-5`\n")
        findings = audit_mod._check_model_ids(md.read_text(), "TEST.md", known_ids)
        assert not findings, "Should not flag a known model id"

    def test_audit_exits_0_always(self, tmp_path):
        audit_mod = self._load_audit()
        # Even with findings, audit() returns 0.
        md = tmp_path / "FAKE.md"
        md.write_text("`packages/does-not-exist/foo.py`\n")
        result = audit_mod.audit([md])
        assert result == 0, "audit() should always exit 0 (non-blocking)"

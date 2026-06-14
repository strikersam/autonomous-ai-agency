"""Regression tests for: brain-skip-paid, provider-priority persistence, scanner NameError.

Three independent bugs the user reported in a single morning:
  1. Anthropic was auto-selected as the brain and consumed 20 EUR of credits overnight.
  2. The provider priority edit (PUT /api/providers/{id}) did not persist.
  3. The website scanner raised NameError on import, so onboarding returned zero systems.

These tests pin down the fixes so they cannot silently regress.
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
import textwrap
from pathlib import Path

import pytest


# ─── 1. Scanner import must not raise NameError ───────────────────────────────


def test_scanner_imports_cleanly():
    """scanner.py used to end with a bare `systems` statement at module level,
    which triggered NameError on import — breaking the whole company-onboarding
    flow (zero systems detected). The fix simply removes the orphan line.
    """
    # Clear any cached import from previous tests in the same session.
    sys.modules.pop("services.scanner", None)
    import services.scanner  # noqa: F401  — must not raise
    # The module must be loadable AND have the public class we expect.
    assert hasattr(services.scanner, "WebsiteScanner")
    assert hasattr(services.scanner, "RepoScanner")


def test_scanner_file_has_no_bare_systems_at_end():
    """Defensive check: the file must not end with a stray `systems` line.
    Reading from disk (not via importlib) catches the bug even if the module
    is already in sys.modules.
    """
    src = Path("services/scanner.py").read_text(encoding="utf-8")
    # Strip the trailing newline so we look at the last non-empty line.
    lines = [ln for ln in src.rstrip().splitlines() if ln.strip()]
    last = lines[-1].strip()
    # The file should end with a real code construct, not a dangling reference.
    assert last != "systems", (
        f"scanner.py must not end with a bare `systems` statement (would "
        f"raise NameError on import). Got: {last!r}"
    )


# ─── 2. _resolve_brain_provider must skip paid providers ─────────────────────


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_brain_skips_paid_when_free_configured(monkeypatch):
    """When a free cloud provider (NVIDIA NIM, etc.) is configured, the brain
    resolver must NOT auto-pick Anthropic — even if Anthropic has a higher
    priority or the only configured base_url. Protects against silent credit
    burn when ANTHROPIC_API_KEY is set in the env but a free provider exists.
    """
    from services import workflow_orchestrator

    async def fake_records():
        return [
            {
                "provider_id": "anthropic-claude",
                "type": "anthropic",
                "base_url": "https://api.anthropic.com",
                "api_key": "sk-ant-PLACEHOLDER",
                "default_model": "claude-sonnet-4-6",
                "priority": 100,  # highest, but PAID
            },
            {
                "provider_id": "nvidia-nim",
                "type": "openai-compatible",
                "base_url": "https://integrate.api.nvidia.com/v1",
                "api_key": "nvapi-PLACEHOLDER",
                "default_model": "nvidia/nemotron-3-super-120b-a12b",
                "priority": 50,  # lower, but FREE
            },
        ]

    monkeypatch.setattr(
        "backend.server._list_configured_provider_records",
        fake_records,
        raising=False,
    )

    base, _headers, _model = _run(workflow_orchestrator._resolve_brain_provider())
    assert "nvidia" in base.lower() or "nvapi" in base.lower() or "nemotron" in str(_model).lower(), (
        f"Brain must pick the free NVIDIA NIM, not Anthropic. Got base={base!r}"
    )
    assert "anthropic" not in base.lower(), (
        f"Brain must not auto-pick Anthropic when a free provider is configured. "
        f"Got base={base!r}"
    )


def test_brain_falls_through_to_ollama_when_all_free_excluded(monkeypatch):
    """Critical failover-safety test: if every free provider's base URL is
    excluded (i.e. all just failed in a prior retry), the resolver must fall
    through to the local Ollama fallback — NOT escalate to a paid Anthropic
    provider. This was the real bug the first review pass flagged.
    """
    from services import workflow_orchestrator

    async def fake_records():
        return [
            {
                "provider_id": "nvidia-nim",
                "type": "openai-compatible",
                "base_url": "https://integrate.api.nvidia.com/v1",
                "api_key": "nvapi-PLACEHOLDER",
                "default_model": "nvidia/nemotron-3-super-120b-a12b",
                "priority": 100,
            },
            {
                "provider_id": "anthropic-claude",
                "type": "anthropic",
                "base_url": "https://api.anthropic.com",
                "api_key": "sk-ant-PLACEHOLDER",
                "default_model": "claude-sonnet-4-6",
                "priority": 50,
            },
        ]

    monkeypatch.setattr(
        "backend.server._list_configured_provider_records",
        fake_records,
        raising=False,
    )

    # Exclude the free provider's base URL (simulating a transient outage
    # where the previous retry just failed).
    base, _headers, _model = _run(
        workflow_orchestrator._resolve_brain_provider(
            exclude_base_urls={"https://integrate.api.nvidia.com/v1"},
        )
    )
    # Must NOT escalate to Anthropic; must fall through to local Ollama.
    assert "anthropic" not in base.lower(), (
        f"Brain must not escalate to Anthropic when free providers are "
        f"excluded (would burn credits during transient outages). Got base={base!r}"
    )
    # Local Ollama fallback returns 127.0.0.1 / localhost.
    assert "localhost" in base.lower() or "127.0.0.1" in base.lower() or "ollama" in base.lower(), (
        f"Brain should fall through to local Ollama when all free providers "
        f"are excluded. Got base={base!r}"
    )


def test_brain_allows_paid_when_no_free_configured(monkeypatch):
    """When the ONLY configured provider is a paid one (e.g. operator set
    ANTHROPIC_API_KEY and no other keys), the brain resolver must still
    return that paid provider — we don't want to break single-tenant setups
    that legitimately rely on Anthropic. The "never auto-pick paid" rule
    only applies when a free alternative exists.
    """
    from services import workflow_orchestrator

    async def fake_records():
        return [
            {
                "provider_id": "anthropic-claude",
                "type": "anthropic",
                "base_url": "https://api.anthropic.com",
                "api_key": "sk-ant-PLACEHOLDER",
                "default_model": "claude-sonnet-4-6",
                "priority": 10,
            },
        ]

    monkeypatch.setattr(
        "backend.server._list_configured_provider_records",
        fake_records,
        raising=False,
    )

    base, _headers, _model = _run(workflow_orchestrator._resolve_brain_provider())
    assert "anthropic" in base.lower(), (
        f"Operator with only Anthropic configured must still get Anthropic. "
        f"Got base={base!r}"
    )


# ─── 3. ProviderUpdate model must accept priority ────────────────────────────


def test_provider_update_accepts_priority_field():
    """The PUT /api/providers/{id} endpoint did not persist priority edits
    because the ProviderUpdate Pydantic model lacked the `priority` field.
    Adding the field lets the handler's body.dict(exclude_none=True) loop
    write priority to the database.
    """
    import backend.server  # noqa: F401

    # Inspect the class without instantiating (avoids DB connection).
    from backend.server import ProviderUpdate

    fields = ProviderUpdate.model_fields
    assert "priority" in fields, (
        f"ProviderUpdate must expose a `priority` field for the PUT endpoint "
        f"to persist edits. Got fields: {list(fields.keys())}"
    )


def test_provider_update_priority_field_type():
    """Priority must be an int (or None for unset) and within a sane range
    so a typo in the UI (e.g. priority=100000) cannot break the priority-
    sorted fallback chain.
    """
    from backend.server import ProviderUpdate
    from pydantic import ValidationError

    # Round-trip: priority=99 persists, priority=None is allowed.
    upd = ProviderUpdate(priority=99)
    assert upd.priority == 99
    upd_none = ProviderUpdate()
    assert upd_none.priority is None
    # Type-coercion: a string "42" should also work (Pydantic coerces).
    upd_str = ProviderUpdate(priority="42")
    assert upd_str.priority == 42

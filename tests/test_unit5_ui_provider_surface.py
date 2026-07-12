"""tests/test_unit5_ui_provider_surface.py — UNIT 5 regression tests.

Verifies that:
  1. ``_brain_provider_status()`` returns ALL 15 providers from the
     ``BrainProvider`` Literal (not just the original 4).
  2. Each provider entry has the new fields: ``display_name``, ``tier``,
     ``candidates`` (in addition to the existing ``key_present``,
     ``key_env_var``, ``base_url``, ``presets``).
  3. The server-driven UI can render a provider that was previously
     filtered out (e.g. ``mistral``, ``deepseek``, ``aerolink``).
  4. The frontend ``BrainCard.jsx`` no longer has a hardcoded
     ``PROVIDER_LABELS`` map limited to 4 entries — the file uses a
     ``providerLabel(p)`` helper that prefers the server-supplied
     ``display_name`` and falls back to a small fallback map only for
     the loading window.

This is the regression gate for the "adding a provider to the catalog
automatically surfaces it in the UI" contract.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from packages.ai.brain_config import all_provider_ids


BRAINCARD_PATH = Path(__file__).resolve().parent.parent / "frontend" / "src" / "v5" / "components" / "BrainCard.jsx"


# ── 1. Backend returns all 15 providers ────────────────────────────────────


def test_brain_provider_status_returns_all_literal_providers(app_client):
    """The GET endpoint response must list every BrainProvider Literal entry.

    Before UNIT 5, ``_brain_provider_status()`` iterated a hardcoded
    4-element tuple ("cerebras", "groq", "nvidia", "ollama"). Adding a
    provider to the catalog silently dropped it from the UI. UNIT 5 makes
    the iteration server-driven via ``all_provider_ids()`` — this test
    pins that contract.
    """
    r = app_client.get("/admin/api/policy/brain")
    assert r.status_code == 200
    body = r.json()
    actual_ids = {p["provider_id"] for p in body["providers"]}
    expected_ids = set(all_provider_ids())
    assert actual_ids == expected_ids
    assert len(actual_ids) == 15


def test_brain_provider_status_includes_previously_filtered_providers(app_client):
    """Providers that were filtered out before UNIT 5 are now present.

    ``mistral``, ``deepseek``, ``aerolink``, ``anthropic`` were all in
    the BrainProvider Literal but were missing from the UI's 4-element
    tuple. They must now appear in the response.
    """
    r = app_client.get("/admin/api/policy/brain")
    body = r.json()
    ids = {p["provider_id"] for p in body["providers"]}
    for previously_missing in ("mistral", "deepseek", "aerolink", "anthropic"):
        assert previously_missing in ids, (
            f"provider {previously_missing!r} should be in the response"
        )


# ── 2. New fields are present ──────────────────────────────────────────────


def test_brain_provider_status_has_display_name_per_provider(app_client):
    r = app_client.get("/admin/api/policy/brain")
    for p in r.json()["providers"]:
        assert isinstance(p.get("display_name"), str)
        assert p["display_name"].strip()


def test_brain_provider_status_has_tier_per_provider(app_client):
    r = app_client.get("/admin/api/policy/brain")
    for p in r.json()["providers"]:
        assert p.get("tier") in ("free", "paid", "local", "unknown")


def test_brain_provider_status_has_candidates_per_provider(app_client):
    r = app_client.get("/admin/api/policy/brain")
    for p in r.json()["providers"]:
        assert isinstance(p.get("candidates"), list)
        assert p["candidates"], f"provider {p['provider_id']} has empty candidates"


def test_brain_provider_status_paid_tier_is_paid(app_client):
    """A known paid provider is reported as tier=paid (was filtered before)."""
    r = app_client.get("/admin/api/policy/brain")
    aerolink = next(p for p in r.json()["providers"] if p["provider_id"] == "aerolink")
    assert aerolink["tier"] == "paid"


def test_brain_provider_status_local_tier_is_local(app_client):
    r = app_client.get("/admin/api/policy/brain")
    ollama = next(p for p in r.json()["providers"] if p["provider_id"] == "ollama")
    assert ollama["tier"] == "local"


# ── 3. BrainCard.jsx uses server-driven labels ─────────────────────────────


def test_brain_card_jsx_uses_provider_label_helper():
    """The component must call ``providerLabel(p)`` rather than indexing a
    4-entry ``PROVIDER_LABELS`` map.

    Before UNIT 5, ``BrainCard.jsx`` had::

        const PROVIDER_LABELS = {
          cerebras: 'Cerebras (fast, free tier)',
          groq:     'Groq (fast, free tier)',
          nvidia:   'NVIDIA NIM (free, broad catalogue)',
          ollama:   'Local Ollama (no key, private)',
        };

    and used ``PROVIDER_LABELS[p.provider_id] || p.provider_id``. After
    UNIT 5, it calls ``providerLabel(p)`` which prefers the
    server-supplied ``display_name`` and falls back to a 14-entry map.
    """
    src = BRAINCARD_PATH.read_text(encoding="utf-8")
    # The old hardcoded 4-entry PROVIDER_LABELS map is gone.
    assert "const PROVIDER_LABELS = {" not in src, (
        "BrainCard.jsx still has the old hardcoded PROVIDER_LABELS map"
    )
    # The new helper exists.
    assert "function providerLabel(p)" in src
    # The dropdown uses providerLabel(p), not PROVIDER_LABELS[p.provider_id].
    assert "providerLabel(p)" in src
    # The fallback map has all 15 providers (so a slow server response
    # doesn't show a bare provider_id in the dropdown).
    fallback_match = re.search(
        r"const PROVIDER_LABEL_FALLBACK = \{([^}]+)\}",
        src,
        re.DOTALL,
    )
    assert fallback_match, "PROVIDER_LABEL_FALLBACK map not found"
    fallback_body = fallback_match.group(1)
    for pid in all_provider_ids():
        assert pid in fallback_body, (
            f"provider {pid!r} missing from PROVIDER_LABEL_FALLBACK"
        )


def test_brain_card_jsx_renders_tier_badge_in_dropdown():
    """The dropdown shows a [free]/[paid]/[local] tier tag so the operator
    can tell which providers cost money without leaving the page."""
    src = BRAINCARD_PATH.read_text(encoding="utf-8")
    assert "tierBadge" in src
    assert "function tierBadge" in src


def test_brain_card_jsx_dropdown_renders_provider_label():
    """The <option> tag uses providerLabel(p), not PROVIDER_LABELS[]."""
    src = BRAINCARD_PATH.read_text(encoding="utf-8")
    # Find the dropdown option block.
    assert "const label = providerLabel(p)" in src
    assert "{label}{tierTag}{keyTag}" in src

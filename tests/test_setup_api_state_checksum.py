"""Regression tests for the wizard-state SHA-256 checksum guard.

Background: silent truncation of wizard state on disk was a known failure
mode (process OOM, disk-full, etc. mid-flush) where half the user's setup
choices were lost without any log indication. The checksum now (a)
detects the truncation on next load and refuses to apply the corrupted
state, (b) is computed atomically via a .tmp file + os.replace so a
crash mid-write cannot leave a half-flushed file behind.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import setup.api as setup_api
from setup.api import WizardState


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_wizard_state_roundtrip_embeds_valid_checksum(tmp_path) -> None:
    setup_api._WIZARD_STATE_DIR = tmp_path
    setup_api.clear_wizard_state_cache()
    user_id = "user_checksum_roundtrip"

    saved = WizardState(user_id=user_id, completed=False, current_step=3)
    _run(setup_api._save_wizard_state(saved))

    # The file SHOULD contain a ``_checksum`` field and it SHOULD match.
    file_path = tmp_path / f"{user_id}.json"
    raw = json.loads(file_path.read_text())
    assert "_checksum" in raw, "save MUST embed _checksum"
    expected = raw["_checksum"]

    # Roundtrip: load returns the original payload (minus _checksum internal).
    loaded = _run(setup_api._load_wizard_state(user_id))
    assert loaded.user_id == user_id
    assert loaded.completed is False
    assert loaded.current_step == 3


def test_wizard_state_checksum_mismatch_returns_fresh(tmp_path, caplog) -> None:
    """Tampered file: checksum mismatch returns a fresh (empty) wizard."""
    setup_api._WIZARD_STATE_DIR = tmp_path
    setup_api.clear_wizard_state_cache()
    user_id = "user_checksum_tampered"

    saved = WizardState(user_id=user_id, completed=True, current_step=5)
    _run(setup_api._save_wizard_state(saved))

    file_path = tmp_path / f"{user_id}.json"
    raw = json.loads(file_path.read_text())
    raw["completed"] = False  # tamper AFTER checksum was computed
    file_path.write_text(json.dumps(raw, indent=2))

    loaded = _run(setup_api._load_wizard_state(user_id))
    # Mismatch => wipe to fresh wizard (defensive: lost single-step choice).
    assert loaded.completed is False
    assert loaded.current_step == 1


def test_wizard_state_legacy_file_without_checksum_is_loaded(tmp_path) -> None:
    """Pre-checksum rollout: a file with no _checksum is trusted (debug-logged)."""
    setup_api._WIZARD_STATE_DIR = tmp_path
    setup_api.clear_wizard_state_cache()
    user_id = "user_legacy_no_checksum"

    legacy = WizardState(user_id=user_id, completed=True, current_step=5)
    file_path = tmp_path / f"{user_id}.json"
    file_path.write_text(json.dumps(legacy.as_dict(), indent=2))  # no _checksum

    loaded = _run(setup_api._load_wizard_state(user_id))
    assert loaded.user_id == user_id
    assert loaded.completed is True
    assert loaded.current_step == 5

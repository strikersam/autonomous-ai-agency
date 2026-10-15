"""Vendor tokens glued to other text with "_" are redacted; ordinary words are not.

``\\b`` treats "_" as a word character, so the old patterns missed
``f_ghp_…`` and ``KEY_sk-…`` (found by the independent verifier on #1765).
"""
from __future__ import annotations

import pytest

from packages.security.redact import redact_secrets

GH = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
SK = "sk-" + "A1b2C3d4E5" * 3
AWS = "AKIA" + "ABCDEFGHIJ123456"


@pytest.mark.parametrize("text,secret", [
    (f"path/f_{GH}.py", GH),
    (f"OPENAI_KEY_{SK}", SK),
    (f"creds_{AWS}_x", AWS),
    (f"x {GH} y", GH),          # still redacted when separated
    (f"{SK}", SK),
])
def test_glued_vendor_tokens_are_redacted(text, secret):
    assert secret not in redact_secrets(text)


@pytest.mark.parametrize("text", [
    "the disk-usage-report-for-2026-10 is attached",   # 'sk-' after a letter
    "task-scheduler-component-name-xyz",
    "flask-sqlalchemy-integration-module",
])
def test_ordinary_words_are_not_redacted(text):
    assert redact_secrets(text) == text

"""The self-heal escalation Telegram message must be self-contained & actionable.

Regression for the operator pain point: the old escalation page was just an
opaque heal id + title, so a human had to relay it to an agent to understand
what to do. The message must now carry the failure context inline and clickable
links (built from GITHUB_REPOSITORY / PUBLIC_URL) so it can be acted on directly.

Also pins the hardened pytest send-guard (``"pytest" in sys.modules``) that
closes the background-thread gap which re-paged the operator.
"""
from __future__ import annotations

import datetime

from agent.self_healing import HealingEvent, SelfHealingAgent
from telegram_service import _telegram_sends_suppressed


def _event(**over) -> HealingEvent:
    base = dict(
        event_id="he_abc123",
        source="ci",
        title="CI failure: test_router in ci",
        description=(
            "Test `test_router` failed in workflow `ci`.\n\n"
            "**Failure category:** test_failure\n"
            "**Suggested fix:** Investigate the failing assertion and fix the code.\n"
            "**File:** `router/model_router.py`"
        ),
        severity="high",
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        signature="537d3aa5deadbeef",
        attempts=3,
    )
    base.update(over)
    return HealingEvent(**base)


def test_message_carries_inline_context_and_ids():
    msg = SelfHealingAgent._format_escalation(_event())
    assert "Self-heal escalation" in msg
    assert "CI failure: test_router" in msg          # the title
    assert "severity: high" in msg and "source: ci" in msg
    assert "attempts: 3/" in msg
    assert "Suggested fix" in msg                      # context lifted from description
    assert "he_abc123" in msg and "537d3aa5" in msg    # ids still present


def test_message_includes_links_when_env_set(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "strikersam/autonomous-ai-agency")
    monkeypatch.setenv("PUBLIC_URL", "https://example.dev/")
    msg = SelfHealingAgent._format_escalation(_event())
    assert "https://github.com/strikersam/autonomous-ai-agency/issues?q=" in msg
    assert "https://github.com/strikersam/autonomous-ai-agency/actions" in msg  # source=ci
    assert "https://example.dev/admin" in msg


def test_message_degrades_without_env(monkeypatch):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    msg = SelfHealingAgent._format_escalation(_event())
    assert "🔗" not in msg          # no links fabricated
    assert "he_abc123" in msg        # still self-describing


def test_code_fences_stripped_for_telegram_markdown():
    ev = _event(description="boom\n```\nTraceback...\n```\nmore")
    msg = SelfHealingAgent._format_escalation(ev)
    assert "```" not in msg


def test_send_guard_holds_under_pytest():
    # pytest is always in sys.modules during the suite → suppressed regardless of
    # whether PYTEST_CURRENT_TEST is set (covers background-thread escalations).
    assert _telegram_sends_suppressed() is True


def test_send_guard_opt_in_override(monkeypatch):
    monkeypatch.setenv("ALLOW_TEST_TELEGRAM", "1")
    assert _telegram_sends_suppressed() is False

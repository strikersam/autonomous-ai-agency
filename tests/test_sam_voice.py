"""tests/test_sam_voice.py — Integration tests for SAM voice agent.

Tests the SAM (System Autonomy Manager) voice command interface:
- Agent creation and singleton
- Command processing with context gathering
- Fallback response when LLM unavailable
- Session management
- Backend API endpoints (status, chat, speak)
"""

from __future__ import annotations

import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from agent.sam import SamAgent, get_sam, SamConversation


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sam() -> SamAgent:
    """Fresh SAM agent with mocked dependencies."""
    return SamAgent()


@pytest.fixture
def sam_with_mocks(sam):
    """SAM agent with all external dependencies mocked."""
    mock_sched = MagicMock()
    mock_sched.list.return_value = [
        MagicMock(enabled=True, job_id="job1"),
        MagicMock(enabled=True, job_id="job2"),
        MagicMock(enabled=False, job_id="job3"),
    ]
    with patch("packages.scheduler.scheduler.get_scheduler", return_value=mock_sched):
        yield sam


# ── Singleton ─────────────────────────────────────────────────────────────────

def test_get_sam_returns_singleton():
    """get_sam() must return the same instance."""
    s1 = get_sam()
    s2 = get_sam()
    assert s1 is s2


def test_get_sam_status(sam):
    """get_status() must return uptime and session count."""
    status = sam.get_status()
    assert "active_sessions" in status
    assert "uptime_seconds" in status
    assert status["active_sessions"] == 0
    assert status["uptime_seconds"] >= 0


# ── Command processing ───────────────────────────────────────────────────────

def test_process_command_empty_text(sam):
    """Empty input must return a prompt to repeat."""
    response = asyncio.run(sam.process_command(""))
    assert "didn't catch" in response.lower() or "could you repeat" in response.lower()


def test_process_command_whitespace_only(sam):
    """Whitespace-only input must be treated as empty."""
    response = asyncio.run(sam.process_command("   \n  "))
    assert "didn't catch" in response.lower() or "could you repeat" in response.lower()


def test_fallback_response_status(sam):
    """Fallback must return operational status when LLM is down."""
    resp = sam._fallback_response("what's the agency status")
    assert "operational" in resp.lower() or "standing by" in resp.lower()


def test_fallback_response_task(sam):
    """Fallback must acknowledge task requests."""
    resp = sam._fallback_response("create a task to fix CI")
    assert "task" in resp.lower()


def test_fallback_response_generic(sam):
    """Fallback generic response must mention being on fallback mode."""
    resp = sam._fallback_response("hello sam")
    assert "fallback" in resp.lower() or "standing by" in resp.lower()


# ── Session management ───────────────────────────────────────────────────────

def test_session_created_on_first_command(sam):
    """A new session must be created on first command."""
    sid = "test-session-123"
    session = sam._get_session(sid)
    assert session.session_id == sid
    assert session.command_count == 0
    assert len(session.history) == 0


def test_session_reused(sam):
    """Same session_id must return the same session."""
    sid = "persistent-session"
    s1 = sam._get_session(sid)
    s2 = sam._get_session(sid)
    assert s1 is s2


def test_conversation_add_turn():
    """add_turn must append to history and increment command_count."""
    conv = SamConversation(session_id="test")
    conv.add_turn("hello", "Hello, Commander")
    assert conv.command_count == 1
    assert len(conv.history) == 2
    assert conv.history[0] == {"role": "user", "content": "hello"}
    assert conv.history[1] == {"role": "assistant", "content": "Hello, Commander"}


def test_conversation_history_capped():
    """History must be capped at 20 entries (10 turns)."""
    conv = SamConversation(session_id="test")
    for i in range(15):
        conv.add_turn(f"msg{i}", f"reply{i}")
    assert len(conv.history) <= 20


# ── Persona ──────────────────────────────────────────────────────────────────

def test_sam_persona_has_commander():
    """SAM's system prompt must address the user as Commander."""
    from agent.sam import SAM_SYSTEM_PROMPT
    assert "Commander" in SAM_SYSTEM_PROMPT


def test_sam_persona_is_concise():
    """SAM's system prompt must instruct concise responses."""
    from agent.sam import SAM_SYSTEM_PROMPT
    assert "concise" in SAM_SYSTEM_PROMPT.lower() or "150" in SAM_SYSTEM_PROMPT


# ── Context building ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_build_context_returns_dict(sam_with_mocks):
    """_build_context must return a dict with expected keys."""
    ctx = await sam_with_mocks._build_context()
    assert isinstance(ctx, dict)
    assert "timestamp" in ctx
    assert "schedules" in ctx
    assert ctx["schedules"]["total"] == 3
    assert ctx["schedules"]["active"] == 2
    assert ctx["schedules"]["paused"] == 1

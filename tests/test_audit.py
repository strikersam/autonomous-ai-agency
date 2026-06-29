"""Tests for audit session management."""

from __future__ import annotations

import time
from packages.shared.audit import AuditSession, create_session, delete_session, get_session, list_sessions


def test_create_and_get_session():
    """Test creating and retrieving an audit session."""
    session_id = "test-session-1"
    metadata = {"user": "tester"}

    session = create_session(session_id, metadata)
    assert session.session_id == session_id
    assert session.metadata == metadata

    retrieved = get_session(session_id)
    assert retrieved is not None
    assert retrieved.session_id == session_id
    assert retrieved.metadata == metadata


def test_create_duplicate_session_raises():
    """Test that creating a duplicate session raises ValueError."""
    session_id = "duplicate-session"
    create_session(session_id)

    try:
        create_session(session_id)
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "already exists" in str(e)


def test_get_nonexistent_session_returns_none():
    """Test that getting a nonexistent session returns None."""
    assert get_session("nonexistent") is None


def test_add_message():
    """Test adding messages to a session."""
    session_id = "msg-test"
    session = create_session(session_id)

    session.add_message("user", "Hello")
    session.add_message("assistant", "Hi there")

    assert len(session.messages) == 2
    assert session.messages[0].role == "user"
    assert session.messages[0].content == "Hello"
    assert session.messages[1].role == "assistant"
    assert session.messages[1].content == "Hi there"

    # Check timestamps are set and increasing
    assert session.messages[0].timestamp <= session.messages[1].timestamp


def test_get_conversation():
    """Test getting conversation in OpenAI format."""
    session_id = "conv-test"
    session = create_session(session_id)

    session.add_message("user", "Question")
    session.add_message("assistant", "Answer")

    conv = session.get_conversation()
    assert conv == [
        {"role": "user", "content": "Question"},
        {"role": "assistant", "content": "Answer"},
    ]


def test_rollback():
    """Test rolling back a session."""
    session_id = "rollback-test"
    session = create_session(session_id)

    session.add_message("user", "Msg1")
    session.add_message("assistant", "Msg2")
    session.add_message("user", "Msg3")

    assert len(session.messages) == 3

    # Rollback to index 1 (keep first two messages)
    session.rollback(1)
    assert len(session.messages) == 2
    assert session.messages[0].content == "Msg1"
    assert session.messages[1].content == "Msg2"

    # Rollback to index 0 (keep first message)
    session.rollback(0)
    assert len(session.messages) == 1
    assert session.messages[0].content == "Msg1"

    # Rollback to same index (no change)
    session.rollback(0)
    assert len(session.messages) == 1


def test_rollback_out_of_range():
    """Test that rolling back out of range raises ValueError."""
    session_id = "oor-test"
    session = create_session(session_id)
    session.add_message("user", "Only message")

    try:
        session.rollback(5)
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "out of range" in str(e)

    try:
        session.rollback(-1)
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "out of range" in str(e)


def test_clear():
    """Test clearing a session."""
    session_id = "clear-test"
    session = create_session(session_id)

    session.add_message("user", "Msg1")
    session.add_message("assistant", "Msg2")
    assert len(session.messages) == 2

    session.clear()
    assert len(session.messages) == 0


def test_delete_session():
    """Test deleting a session."""
    session_id = "delete-test"
    create_session(session_id)

    assert session_id in list_sessions()
    assert get_session(session_id) is not None

    deleted = delete_session(session_id)
    assert deleted is True
    assert session_id not in list_sessions()
    assert get_session(session_id) is None

    # Deleting again returns False
    assert delete_session(session_id) is False


def test_list_sessions():
    """Test listing session IDs."""
    # Start with clean slate
    for sid in list_sessions():
        delete_session(sid)

    assert list_sessions() == []

    create_session("session-a")
    create_session("session-b")
    create_session("session-c")

    sessions = set(list_sessions())
    assert sessions == {"session-a", "session-b", "session-c"}

    delete_session("session-b")
    assert set(list_sessions()) == {"session-a", "session-c"}
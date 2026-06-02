"""Tests for agents.cowork_session — Claude Cowork."""

from __future__ import annotations

import importlib.util
import sys

import pytest

# Load the module directly to bypass agents/__init__.py dependency chain
_COWORK_SPEC = importlib.util.spec_from_file_location(
    "cowork_session", "agents/cowork_session.py"
)
_cowork = importlib.util.module_from_spec(_COWORK_SPEC)
sys.modules["cowork_session"] = _cowork
_COWORK_SPEC.loader.exec_module(_cowork)

CollaborationContext = _cowork.CollaborationContext
ContributorState = _cowork.ContributorState
CoworkSession = _cowork.CoworkSession
SessionPhase = _cowork.SessionPhase
SessionRole = _cowork.SessionRole
SyncAgent = _cowork.SyncAgent


# ── CollaborationContext ──────────────────────────────────────────────────────

class TestCollaborationContext:
    def test_add_file(self):
        ctx = CollaborationContext()
        ctx.add_file("foo.py")
        ctx.add_file("bar.py")
        ctx.add_file("foo.py")  # duplicate
        assert ctx.file_count == 2
        assert "foo.py" in ctx.active_files

    def test_remove_file(self):
        ctx = CollaborationContext()
        ctx.add_file("foo.py")
        ctx.remove_file("foo.py")
        assert ctx.file_count == 0

    def test_remove_file_noop_when_not_present(self):
        ctx = CollaborationContext()
        ctx.remove_file("nonexistent.py")
        assert ctx.file_count == 0

    def test_add_message_caps_at_50(self):
        ctx = CollaborationContext()
        for i in range(60):
            ctx.add_message(f"msg_{i}")
        assert ctx.message_count == 50
        assert ctx.recent_messages[0] == "msg_10"

    def test_snapshot_shape(self):
        ctx = CollaborationContext(
            current_task="build feature X",
            git_branch="main",
            git_last_commit="abc123",
        )
        ctx.add_file("main.py")
        snap = ctx.snapshot()
        assert snap["current_task"] == "build feature X"
        assert snap["file_count"] == 1
        assert "main.py" in snap["active_files"]


# ── CoworkSession ─────────────────────────────────────────────────────────────

class TestCoworkSession:
    def test_host_added_on_creation(self):
        session = CoworkSession(session_id="s1", host_user_id="host1")
        assert session.host_user_id == "host1"
        assert "host1" in session.contributors
        assert session.contributors["host1"].role == SessionRole.HOST

    def test_add_contributor(self):
        session = CoworkSession(session_id="s1", host_user_id="host1")
        session.add_contributor("user2")
        assert "user2" in session.contributors
        assert session.contributors["user2"].role == SessionRole.PARTICIPANT

    def test_add_contributor_no_duplicate(self):
        session = CoworkSession(session_id="s1", host_user_id="host1")
        session.add_contributor("user2")
        session.add_contributor("user2")
        assert session.contributor_count == 2  # host + user2

    def test_remove_contributor(self):
        session = CoworkSession(session_id="s1", host_user_id="host1")
        session.add_contributor("user2")
        session.remove_contributor("user2")
        assert "user2" not in session.contributors

    def test_cannot_remove_host(self):
        session = CoworkSession(session_id="s1", host_user_id="host1")
        session.remove_contributor("host1")
        assert "host1" in session.contributors

    def test_set_role(self):
        session = CoworkSession(session_id="s1", host_user_id="host1")
        session.add_contributor("user2")
        assert session.set_role("user2", SessionRole.OBSERVER) is True
        assert session.contributors["user2"].role == SessionRole.OBSERVER

    def test_set_role_unknown_user(self):
        session = CoworkSession(session_id="s1", host_user_id="host1")
        assert session.set_role("unknown", SessionRole.OBSERVER) is False

    def test_active_contributors(self):
        session = CoworkSession(session_id="s1", host_user_id="host1")
        session.add_contributor("user2")
        session.contributors["user2"].is_active = False
        assert len(session.active_contributors) == 1  # only host

    def test_host_can_always_request_edit(self):
        session = CoworkSession(session_id="s1", host_user_id="host1")
        session.add_contributor("user2")
        session.request_edit("user2")
        # Host takes over
        assert session.request_edit("host1") is True
        assert session.active_editor == "host1"

    def test_participant_blocked_by_active_editor(self):
        session = CoworkSession(session_id="s1", host_user_id="host1")
        session.add_contributor("user2")
        session.add_contributor("user3")
        # user2 gets control
        assert session.request_edit("user2") is True
        # user3 should be blocked (user2 just touched)
        assert session.request_edit("user3") is False

    def test_release_edit(self):
        session = CoworkSession(session_id="s1", host_user_id="host1")
        session.request_edit("host1")
        assert session.active_editor == "host1"
        session.release_edit("host1")
        assert session.active_editor is None

    def test_kick_inactive_editor(self):
        session = CoworkSession(session_id="s1", host_user_id="host1")
        session.request_edit("host1")
        # Artificially age the last_action_at
        from datetime import datetime, timedelta
        session.contributors["host1"].last_action_at = datetime.now() - timedelta(seconds=60)
        kicked = session.kick_inactive_editor()
        assert kicked == "host1"
        assert session.active_editor is None

    def test_kick_inactive_editor_not_active(self):
        session = CoworkSession(session_id="s1", host_user_id="host1")
        kicked = session.kick_inactive_editor()
        assert kicked is None

    def test_sync_context_message(self):
        session = CoworkSession(session_id="s1", host_user_id="host1")
        session.add_contributor("user2")
        session.sync_context("user2", {"message": "hello"})
        assert session.context.message_count == 1

    def test_sync_context_only_editor_can_modify_files(self):
        session = CoworkSession(session_id="s1", host_user_id="host1")
        session.add_contributor("user2")
        session.sync_context("user2", {"add_file": "secret.py"})
        assert session.context.file_count == 0  # user2 is not editor

    def test_summary_shape(self):
        session = CoworkSession(session_id="s1", host_user_id="host1")
        s = session.summary()
        assert s["session_id"] == "s1"
        assert s["host"] == "host1"
        assert "context" in s


# ── SyncAgent ─────────────────────────────────────────────────────────────────

class TestSyncAgent:
    def test_register_and_get_session(self):
        sa = SyncAgent()
        session = CoworkSession(session_id="s1", host_user_id="host1")
        sa.register_session(session)
        assert sa.get_session("s1") is session

    def test_unregister_session(self):
        sa = SyncAgent()
        sa.register_session(CoworkSession(session_id="s1", host_user_id="host1"))
        sa.unregister_session("s1")
        assert sa.get_session("s1") is None

    def test_tick_kicks_inactive_editors(self):
        sa = SyncAgent()
        session = CoworkSession(session_id="s1", host_user_id="host1")
        session.request_edit("host1")
        from datetime import datetime, timedelta
        session.contributors["host1"].last_action_at = datetime.now() - timedelta(seconds=60)
        sa.register_session(session)
        result = sa.tick()
        assert "host1" in result["editors_kicked"].get("s1", "")

    def test_summary_shape(self):
        sa = SyncAgent()
        sa.register_session(CoworkSession(session_id="s1", host_user_id="host1"))
        s = sa.summary()
        assert s["total_sessions"] == 1
        assert len(s["sessions"]) == 1

"""
Claude Cowork — shared AI coding sessions with real-time sync.

Enables multiple developers to share an AI pair-programming session
with context propagation, turn-taking, and collaborative state management.

Quick-Note Issue: #261
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SessionRole(str, Enum):
    """Role within a cowork session."""

    HOST = "host"
    PARTICIPANT = "participant"
    OBSERVER = "observer"


class SessionPhase(str, Enum):
    """Current phase of a cowork session."""

    IDLE = "idle"
    BRAINSTORMING = "brainstorming"
    CODING = "coding"
    REVIEWING = "reviewing"
    WRAPPING_UP = "wrapping_up"


@dataclass
class ContributorState:
    """State of a single contributor within a session."""

    user_id: str
    role: SessionRole = SessionRole.PARTICIPANT
    is_active: bool = True
    cursor_file: str = ""
    cursor_line: int = 0
    last_action_at: datetime = field(default_factory=datetime.now)

    def touch(self) -> None:
        self.last_action_at = datetime.now()

    @property
    def is_idle(self) -> bool:
        idle_seconds = (datetime.now() - self.last_action_at).total_seconds()
        return idle_seconds > 300  # 5 minutes


@dataclass
class CollaborationContext:
    """
    Shared context blob propagated to all session participants.

    Carries the active file set, current task, recent messages,
    and git state so every participant sees the same workspace view.
    """

    active_files: list[str] = field(default_factory=list)
    current_task: str = ""
    recent_messages: list[str] = field(default_factory=list)
    git_branch: str = ""
    git_last_commit: str = ""
    updated_at: datetime = field(default_factory=datetime.now)

    def add_file(self, path: str) -> None:
        if path not in self.active_files:
            self.active_files.append(path)
        self.updated_at = datetime.now()

    def remove_file(self, path: str) -> None:
        if path in self.active_files:
            self.active_files.remove(path)
        self.updated_at = datetime.now()

    def add_message(self, msg: str) -> None:
        self.recent_messages.append(msg)
        if len(self.recent_messages) > 50:
            self.recent_messages = self.recent_messages[-50:]
        self.updated_at = datetime.now()

    @property
    def file_count(self) -> int:
        return len(self.active_files)

    @property
    def message_count(self) -> int:
        return len(self.recent_messages)

    def snapshot(self) -> dict:
        return {
            "active_files": list(self.active_files),
            "current_task": self.current_task,
            "git_branch": self.git_branch,
            "git_last_commit": self.git_last_commit,
            "file_count": self.file_count,
            "message_count": self.message_count,
        }


@dataclass
class CoworkSession:
    """
    A shared AI coding session with multiple human contributors.

    Manages turn-taking, role assignment, phase transitions,
    and context propagation across participants.

    Turns:
        Only one participant can be the *active editor* at a time.
        Others are in observe/read mode until they request control.
    """

    session_id: str
    host_user_id: str
    created_at: datetime = field(default_factory=datetime.now)
    phase: SessionPhase = SessionPhase.IDLE
    contributors: dict[str, ContributorState] = field(default_factory=dict)
    context: CollaborationContext = field(default_factory=CollaborationContext)
    active_editor: Optional[str] = None

    def __post_init__(self) -> None:
        # Host always joins on creation
        if self.host_user_id not in self.contributors:
            self.contributors[self.host_user_id] = ContributorState(
                user_id=self.host_user_id,
                role=SessionRole.HOST,
            )

    # ── Contributor management ────────────────────────────────────────────

    def add_contributor(
        self, user_id: str, role: SessionRole = SessionRole.PARTICIPANT
    ) -> None:
        if user_id in self.contributors:
            return
        self.contributors[user_id] = ContributorState(
            user_id=user_id,
            role=role,
        )

    def remove_contributor(self, user_id: str) -> None:
        if user_id == self.host_user_id:
            return  # Host cannot be removed
        self.contributors.pop(user_id, None)
        if self.active_editor == user_id:
            self.active_editor = None

    def set_role(self, user_id: str, role: SessionRole) -> bool:
        contributor = self.contributors.get(user_id)
        if contributor is None:
            return False
        contributor.role = role
        return True

    @property
    def active_contributors(self) -> list[ContributorState]:
        return [c for c in self.contributors.values() if c.is_active]

    @property
    def contributor_count(self) -> int:
        return len(self.contributors)

    # ── Phase management ──────────────────────────────────────────────────

    def set_phase(self, phase: SessionPhase) -> None:
        self.phase = phase

    # ── Turn management ───────────────────────────────────────────────────

    def request_edit(self, user_id: str) -> bool:
        """
        Request editing control. Returns True if granted.

        Grant rules:
          - Host can always take control.
          - Participant must wait if someone else is actively editing
            (their last action within 30 seconds).
          - Observer can only request during IDLE or BRAINSTORMING.
        """
        contributor = self.contributors.get(user_id)
        if contributor is None:
            return False

        if contributor.role == SessionRole.HOST:
            self.active_editor = user_id
            contributor.touch()
            return True

        if contributor.role == SessionRole.OBSERVER:
            if self.phase not in (SessionPhase.IDLE, SessionPhase.BRAINSTORMING):
                return False

        # Check if current editor is still active
        if self.active_editor and self.active_editor != user_id:
            current = self.contributors.get(self.active_editor)
            if current:
                idle_secs = (datetime.now() - current.last_action_at).total_seconds()
                if idle_secs < 30:
                    return False

        self.active_editor = user_id
        contributor.touch()
        return True

    def release_edit(self, user_id: str) -> None:
        if self.active_editor == user_id:
            self.active_editor = None

    def kick_inactive_editor(self) -> Optional[str]:
        """Release control if the active editor is idle > 30s."""
        if self.active_editor is None:
            return None
        contributor = self.contributors.get(self.active_editor)
        if contributor is None:
            self.active_editor = None
            return None
        idle_secs = (datetime.now() - contributor.last_action_at).total_seconds()
        if idle_secs > 30:
            kicked = self.active_editor
            self.active_editor = None
            return kicked
        return None

    # ── Context sync ──────────────────────────────────────────────────────

    def sync_context(self, user_id: str, updates: dict) -> None:
        """
        Apply context updates from a contributor.

        Only the active editor can modify files/phase; anyone can add messages.
        """
        if user_id not in self.contributors:
            return

        if "message" in updates:
            self.context.add_message(updates["message"])

        if self.active_editor == user_id:
            if "current_task" in updates:
                self.context.current_task = updates["current_task"]
            if "add_file" in updates:
                self.context.add_file(updates["add_file"])
            if "remove_file" in updates:
                self.context.remove_file(updates["remove_file"])
            if "git_branch" in updates:
                self.context.git_branch = updates["git_branch"]
            if "git_last_commit" in updates:
                self.context.git_last_commit = updates["git_last_commit"]

        contributor = self.contributors[user_id]
        contributor.touch()

    # ── Summary ───────────────────────────────────────────────────────────

    def summary(self) -> dict:
        return {
            "session_id": self.session_id,
            "host": self.host_user_id,
            "phase": self.phase.value,
            "contributor_count": self.contributor_count,
            "active_editor": self.active_editor,
            "context": self.context.snapshot(),
        }


@dataclass
class SyncAgent:
    """
    Background agent that periodically syncs session state across contributors.

    Detects stale sessions, resolves edit conflicts, and broadcasts
    context updates to all participants.
    """

    sessions: dict[str, CoworkSession] = field(default_factory=dict)

    def register_session(self, session: CoworkSession) -> None:
        self.sessions[session.session_id] = session

    def unregister_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)

    def get_session(self, session_id: str) -> Optional[CoworkSession]:
        return self.sessions.get(session_id)

    @property
    def active_sessions(self) -> list[CoworkSession]:
        return list(self.sessions.values())

    def tick(self) -> dict:
        """
        Run one sync tick across all sessions.

        Actions taken:
          - Kick idle active editors (>30s inactivity).
          - Return a diff of changes made.
        """
        kicked: dict[str, str] = {}
        for sid, session in self.sessions.items():
            evicted = session.kick_inactive_editor()
            if evicted:
                kicked[sid] = evicted
        return {
            "sessions_scanned": len(self.sessions),
            "editors_kicked": kicked,
        }

    def summary(self) -> dict:
        return {
            "total_sessions": len(self.sessions),
            "active_sessions": len(self.active_sessions),
            "sessions": [s.summary() for s in self.sessions.values()],
        }

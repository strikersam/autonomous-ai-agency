"""Audit session management for multi-turn conversations.

This module provides in-memory storage of audit sessions, enabling
multi-turn conversations to be stored, retrieved, rolled back, and scored.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

log = logging.getLogger("qwen-proxy")


@dataclass
class AuditMessage:
    """A single message in an audit session."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=lambda: __import__('time').time())


@dataclass
class AuditSession:
    """An audit session storing a multi-turn conversation."""
    session_id: str
    messages: List[AuditMessage] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the session."""
        self.messages.append(AuditMessage(role=role, content=content))
        log.debug(f"Added message to audit session {self.session_id}: {role}")

    def get_conversation(self) -> List[Dict[str, str]]:
        """Get the conversation as a list of dicts for compatibility with OpenAI format."""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.messages
        ]

    def rollback(self, index: int) -> None:
        """Rollback the session to a specific message index (inclusive)."""
        if index < 0 or index >= len(self.messages):
            raise ValueError(f"Index {index} out of range for session with {len(self.messages)} messages")
        self.messages = self.messages[:index + 1]
        log.info(f"Rolled back audit session {self.session_id} to index {index}")

    def clear(self) -> None:
        """Clear all messages in the session."""
        self.messages.clear()
        log.info(f"Cleared audit session {self.session_id}")


# In-memory store for audit sessions
_audit_sessions: Dict[str, AuditSession] = {}


def create_session(session_id: str, metadata: Optional[Dict[str, Any]] = None) -> AuditSession:
    """Create a new audit session."""
    if session_id in _audit_sessions:
        raise ValueError(f"Audit session {session_id} already exists")
    session = AuditSession(session_id=session_id, metadata=metadata or {})
    _audit_sessions[session_id] = session
    log.info(f"Created audit session {session_id}")
    return session


def get_session(session_id: str) -> Optional[AuditSession]:
    """Retrieve an audit session by ID."""
    return _audit_sessions.get(session_id)


def delete_session(session_id: str) -> bool:
    """Delete an audit session. Returns True if session existed."""
    if session_id in _audit_sessions:
        del _audit_sessions[session_id]
        log.info(f"Deleted audit session {session_id}")
        return True
    return False


def list_sessions() -> List[str]:
    """List all audit session IDs."""
    return list(_audit_sessions.keys())
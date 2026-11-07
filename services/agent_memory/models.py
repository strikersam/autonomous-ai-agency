"""Data model for per-agent memory: notes (what an agent knows) and episodes (what happened).

The split follows Anthropic's "The components of agent memory" (2026-11): an
agent writes notes in-session from its own judgment of salience, while the raw
record of each run is kept as an episode — the ground truth an offline
dreaming pass checks notes against.
"""
from __future__ import annotations

import secrets
import time
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


def _to_epoch(value: Any) -> Any:
    """Accept ISO-8601 strings too: the SQLite backend rewrites ``updated_at`` that way."""
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).timestamp()
        except ValueError:
            return value
    return value


class NoteKind(str, Enum):
    RULE = "rule"            # a tested way of doing something
    FACT = "fact"            # something true about the environment
    TRAP = "trap"            # a mistake to avoid
    PLAN = "plan"            # current goal / next steps
    PREFERENCE = "preference"  # how the owner wants things done


class NoteStatus(str, Enum):
    UNVERIFIED = "unverified"  # written in-session, not yet checked
    VERIFIED = "verified"      # backed by an episode that passed verification
    REFUTED = "refuted"        # contradicted by an episode; kept out of prompts


class NoteLayer(str, Enum):
    INDEX = "index"  # always loaded into the agent's context (kept small)
    STORE = "store"  # recalled only when relevant to the task


MAX_NOTE_CHARS = 500


class MemoryNote(BaseModel):
    """One thing an agent learned and expects to need again."""

    note_id: str = Field(default_factory=lambda: f"mem_{secrets.token_hex(6)}")
    memory_key: str                       # agent_id, or "role:<role>" for CEO specialists
    kind: NoteKind = NoteKind.FACT
    text: str = Field(..., min_length=1, max_length=MAX_NOTE_CHARS)
    evidence: str = Field(default="", max_length=MAX_NOTE_CHARS)  # how it is known
    status: NoteStatus = NoteStatus.UNVERIFIED
    layer: NoteLayer = NoteLayer.STORE
    source_task_ids: list[str] = Field(default_factory=list)
    access_count: int = 0
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    last_accessed_at: float | None = None

    _epochs = field_validator("created_at", "updated_at", "last_accessed_at", mode="before")(
        classmethod(lambda cls, v: _to_epoch(v)))


class Episode(BaseModel):
    """The record of one task run: what was asked, what came out, how it was judged."""

    episode_id: str = Field(default_factory=lambda: f"ep_{secrets.token_hex(6)}")
    memory_key: str
    task_id: str
    title: str = Field(default="", max_length=300)
    success: bool
    verdict: str | None = None            # PASS / PASS+NOTES / FAIL, when a verifier ran
    outcome_excerpt: str = Field(default="", max_length=2000)
    notes_written: list[str] = Field(default_factory=list)
    dreamed: bool = False
    created_at: float = Field(default_factory=time.time)

    _epochs = field_validator("created_at", mode="before")(classmethod(lambda cls, v: _to_epoch(v)))

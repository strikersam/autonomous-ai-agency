"""In-session memory capture: the agent decides what is worth remembering.

An agent marks a note by writing a line in its final reply::

    REMEMBER: <what future tasks should know>
    REMEMBER(trap): <a mistake to avoid> | evidence: <how you know>

The article this implements found that strong models judge salience better
than fixed rules ("record only failures" cut the gain from memory), so the
protocol says what memory is for and leaves the choice of content to the
agent. Every run is also recorded as an episode, whether or not it wrote a
note, so dreaming has the ground truth to check notes against.
"""
from __future__ import annotations

import logging
import re
import time

from services.agent_memory.models import MAX_NOTE_CHARS, Episode, MemoryNote, NoteKind
from services.agent_memory.store import AgentMemoryStore

log = logging.getLogger("qwen-proxy")

_REMEMBER_RE = re.compile(
    r"^[ \t>*\-]*REMEMBER(?:\s*\(\s*([a-zA-Z]+)\s*\))?\s*:\s*(.+?)\s*$",
    re.MULTILINE,
)
_MAX_NOTES_PER_RUN = 5
_DUPLICATE_JACCARD = 0.8


def parse_remember_lines(text: str) -> list[tuple[NoteKind, str, str]]:
    """Return ``(kind, text, evidence)`` for each REMEMBER line, capped per run."""
    found: list[tuple[NoteKind, str, str]] = []
    for kind_raw, body in _REMEMBER_RE.findall(text or ""):
        note_text, _, evidence = body.partition("| evidence:")
        note_text = note_text.strip()[:MAX_NOTE_CHARS]
        if not note_text:
            continue
        try:
            kind = NoteKind((kind_raw or "fact").lower())
        except ValueError:
            kind = NoteKind.FACT
        found.append((kind, note_text, evidence.strip()[:MAX_NOTE_CHARS]))
        if len(found) >= _MAX_NOTES_PER_RUN:
            break
    return found


def strip_remember_lines(text: str) -> str:
    return _REMEMBER_RE.sub("", text or "").strip()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def similarity(a: str, b: str) -> float:
    """Jaccard similarity of word sets — cheap duplicate detection."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


async def capture_notes(
    store: AgentMemoryStore, memory_key: str, task_id: str, output: str,
) -> list[str]:
    """Write the run's REMEMBER lines; a near-duplicate reinforces the existing note."""
    parsed = parse_remember_lines(output)
    if not parsed:
        return []
    existing = await store.list_notes(memory_key)
    written: list[str] = []
    for kind, text, evidence in parsed:
        match = next((n for n in existing if similarity(n.text, text) >= _DUPLICATE_JACCARD), None)
        if match is not None:
            if task_id not in match.source_task_ids:
                match.source_task_ids.append(task_id)
            match.updated_at = time.time()
            await store.save_note(match)
            written.append(match.note_id)
            continue
        note = MemoryNote(memory_key=memory_key, kind=kind, text=text, evidence=evidence,
                          source_task_ids=[task_id])
        await store.save_note(note)
        existing.append(note)
        written.append(note.note_id)
    return written


async def record_episode(
    store: AgentMemoryStore,
    memory_key: str,
    *,
    task_id: str,
    title: str,
    success: bool,
    output: str,
    verdict: str | None = None,
) -> Episode:
    """Record one run and any notes the agent chose to keep from it."""
    notes = await capture_notes(store, memory_key, task_id, output)
    episode = Episode(
        memory_key=memory_key,
        task_id=task_id,
        title=(title or "")[:300],
        success=success,
        verdict=verdict,
        outcome_excerpt=strip_remember_lines(output)[:2000],
        notes_written=notes,
    )
    await store.add_episode(episode)
    log.info("agent_memory: episode %s for %s (notes=%d, success=%s)",
             episode.episode_id, memory_key, len(notes), success)
    return episode

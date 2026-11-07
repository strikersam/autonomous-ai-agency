"""Load an agent's memory into its task instruction.

Two layers, as in the memory hierarchy the article describes: a small index
that is loaded into every task (capped, because injected notes cost tokens on
every run and long instruction blocks reduce adherence), and a deeper store
from which only the notes relevant to this task are pulled. Refuted notes are
never shown.
"""
from __future__ import annotations

import re
import time

from services.agent_memory.models import MemoryNote, NoteLayer, NoteStatus
from services.agent_memory.store import AgentMemoryStore

MAX_BLOCK_CHARS = 6000

GUIDANCE = (
    "To keep something for future tasks, add a line to your final reply: "
    "`REMEMBER(kind): <note> | evidence: <how you know>` where kind is rule, fact, "
    "trap, plan or preference. Memory is for what a future task will need and could "
    "not read off the environment directly: tested rules, traps you hit, the owner's "
    "preferences. Write one only when something is clearly worth remembering."
)


_STOPWORDS = frozenset(
    "the and for with that this from into are was were has have not but you your our "
    "task tasks when what which then than also only".split()
)


def _tokens(text: str) -> set[str]:
    """Lower-cased content words with a plural 's' dropped, so 'webhooks' meets 'webhook'."""
    words = (t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2 and t not in _STOPWORDS)
    return {w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in words}


def _relevance(note: MemoryNote, query_tokens: set[str]) -> float:
    """Shared content words over the smaller side, so a short note or query is not penalised."""
    note_tokens = _tokens(note.text)
    if not note_tokens or not query_tokens:
        return 0.0
    return len(note_tokens & query_tokens) / min(len(note_tokens), len(query_tokens))


def _line(note: MemoryNote) -> str:
    mark = "verified" if note.status == NoteStatus.VERIFIED else "unverified"
    return f"- [{note.kind.value}, {mark}] {note.text} ({note.note_id})"


def select_notes(
    notes: list[MemoryNote], query: str, *, index_lines: int, recall_k: int,
) -> tuple[list[MemoryNote], list[MemoryNote]]:
    """Split live notes into (index layer, relevant store notes) for one task."""
    live = [n for n in notes if n.status != NoteStatus.REFUTED]
    index = sorted((n for n in live if n.layer == NoteLayer.INDEX),
                   key=lambda n: (n.status != NoteStatus.VERIFIED, -n.access_count))[:index_lines]
    q = _tokens(query)
    scored = [(_relevance(n, q), n) for n in live if n.layer == NoteLayer.STORE]
    scored = [(s, n) for s, n in scored if s >= 0.25]
    scored.sort(key=lambda sn: (-sn[0], sn[1].status != NoteStatus.VERIFIED))
    return index, [n for _, n in scored[:recall_k]]


def render_block(index: list[MemoryNote], relevant: list[MemoryNote]) -> str:
    """Markdown memory block for the instruction; guidance only when memory is empty."""
    parts = ["## Your memory"]
    if index or relevant:
        parts.append(
            "Notes you kept from earlier tasks. They can be wrong or out of date: check an "
            "unverified note before relying on it, and if this task shows a note is wrong, "
            "say which one (by id) and what is true instead."
        )
    if index:
        parts.append("Always-loaded index:\n" + "\n".join(_line(n) for n in index))
    if relevant:
        parts.append("Possibly relevant to this task:\n" + "\n".join(_line(n) for n in relevant))
    parts.append(GUIDANCE)
    return "\n\n".join(parts)[:MAX_BLOCK_CHARS]


async def build_memory_block(
    store: AgentMemoryStore, memory_key: str, query: str, *, index_lines: int, recall_k: int,
) -> str:
    """Select, render and record access for the notes shown to this task."""
    notes = await store.list_notes(memory_key)
    index, relevant = select_notes(notes, query, index_lines=index_lines, recall_k=recall_k)
    now = time.time()
    for note in (*index, *relevant):
        note.access_count += 1
        note.last_accessed_at = now
        await store.save_note(note)
    return render_block(index, relevant)

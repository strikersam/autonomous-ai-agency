"""Dreaming: offline reorganisation of an agent's memory.

Between tasks, a model replays an agent's recent episodes against its notes
and returns edit operations: verify or refute a note against what actually
happened, rewrite a wrong one, merge duplicates, add a pattern no single run
could see, and promote or demote notes between the always-loaded index and the
searchable store. A deterministic pass then enforces the index cap, so the
injected layer stays small whatever the model proposes.

Dreaming is focused on the agent's job: the brief carries the agent's role and
system prompt, so memory grows around what that agent is for.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Awaitable, Callable

from services.agent_memory.models import (
    MAX_NOTE_CHARS, Episode, MemoryNote, NoteKind, NoteLayer, NoteStatus,
)
from services.agent_memory.store import AgentMemoryStore

log = logging.getLogger("qwen-proxy")

LLM = Callable[[str, str], Awaitable[str]]
_MAX_NOTES_IN_BRIEF = 120
_MAX_EPISODES_IN_BRIEF = 30
_MAX_ADDS_PER_DREAM = 5

DREAM_SYSTEM = """You maintain the long-term memory of one AI agent.
Memory exists so this agent's future tasks go better. Worth keeping: rules it
tested, traps it hit, facts it could not read off the environment, its owner's
preferences, its current plan. Not worth keeping: anything a future task can
look up directly, one-off details, untested guesses.

You get the agent's notes and its recent episodes (what each task asked, whether
it succeeded, the verifier's verdict, an excerpt of the output). Episodes are the
ground truth. Check notes against them:
- verify a note an episode confirms; refute one an episode contradicts
- rewrite a note that is partly wrong, stating what is true
- merge notes that say the same thing
- add a note for a pattern visible across several episodes but in no single note
- delete notes that are redundant or not useful for this agent's job
- promote the most broadly useful verified notes to the index (loaded into every
  task, at most {cap} notes); demote detail back to the store
Cite the episode ids that justify each change in "evidence".

Reply with JSON only: {{"ops": [ ... ]}} where each op is one of
{{"op":"verify","note_id":"...","evidence":"..."}}
{{"op":"refute","note_id":"...","evidence":"..."}}
{{"op":"rewrite","note_id":"...","text":"...","evidence":"..."}}
{{"op":"merge","note_ids":["...","..."],"text":"...","kind":"rule|fact|trap|plan|preference"}}
{{"op":"add","kind":"...","text":"...","evidence":"..."}}
{{"op":"delete","note_id":"..."}}
{{"op":"promote","note_id":"..."}}
{{"op":"demote","note_id":"..."}}
Return {{"ops": []}} when nothing needs to change."""


def build_brief(agent_context: str, notes: list[MemoryNote], episodes: list[Episode]) -> str:
    """The user message for one dreaming pass."""
    note_lines = [
        f"{n.note_id} [{n.kind.value}, {n.status.value}, {n.layer.value}, used {n.access_count}x, "
        f"tasks {','.join(n.source_task_ids[-3:])}] {n.text}"
        + (f" | evidence: {n.evidence}" if n.evidence else "")
        for n in notes[:_MAX_NOTES_IN_BRIEF]
    ]
    ep_lines = [
        f"{e.episode_id} task={e.task_id} success={e.success} verdict={e.verdict or 'none'} "
        f"notes={','.join(e.notes_written) or '-'}\n  title: {e.title}\n  output: {e.outcome_excerpt[:600]}"
        for e in episodes[:_MAX_EPISODES_IN_BRIEF]
    ]
    return (
        f"Agent:\n{agent_context}\n\nNotes ({len(notes)}):\n" + ("\n".join(note_lines) or "(none)")
        + f"\n\nEpisodes ({len(episodes)}):\n" + ("\n".join(ep_lines) or "(none)")
    )


def parse_ops(text: str) -> list[dict[str, Any]] | None:
    """The op list from a model reply, or None when the reply is not usable JSON."""
    start, end = (text or "").find("{"), (text or "").rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    ops = data.get("ops") if isinstance(data, dict) else None
    return [op for op in ops if isinstance(op, dict)] if isinstance(ops, list) else None


def _clip(value: Any) -> str:
    return str(value or "").strip()[:MAX_NOTE_CHARS]


def _kind(value: Any) -> NoteKind:
    try:
        return NoteKind(str(value or "fact").lower())
    except ValueError:
        return NoteKind.FACT


def _apply_one(op: dict[str, Any], by_id: dict[str, MemoryNote], memory_key: str,
               deleted: set[str], added: list[MemoryNote]) -> bool:
    """Apply one op in place. Returns False for an op that names no known note."""
    kind = op.get("op")
    if kind == "add":
        if len(added) >= _MAX_ADDS_PER_DREAM or not _clip(op.get("text")):
            return False
        note = MemoryNote(memory_key=memory_key, kind=_kind(op.get("kind")), text=_clip(op.get("text")),
                          evidence=_clip(op.get("evidence")), status=NoteStatus.VERIFIED)
        by_id[note.note_id] = note
        added.append(note)
        return True
    if kind == "merge":
        ids = [i for i in op.get("note_ids") or [] if i in by_id and i not in deleted]
        if len(ids) < 2 or not _clip(op.get("text")):
            return False
        keep = by_id[ids[0]]
        keep.text, keep.kind = _clip(op.get("text")), _kind(op.get("kind") or keep.kind.value)
        for other in ids[1:]:
            keep.source_task_ids = list(dict.fromkeys(keep.source_task_ids + by_id[other].source_task_ids))
            keep.access_count += by_id[other].access_count
            deleted.add(other)
        return True
    note = by_id.get(str(op.get("note_id") or ""))
    if note is None or note.note_id in deleted:
        return False
    return _apply_note_op(kind, op, note, deleted)


def _apply_note_op(kind: Any, op: dict[str, Any], note: MemoryNote, deleted: set[str]) -> bool:
    if kind == "verify":
        note.status, note.evidence = NoteStatus.VERIFIED, _clip(op.get("evidence")) or note.evidence
    elif kind == "refute":
        note.status, note.layer = NoteStatus.REFUTED, NoteLayer.STORE
        note.evidence = _clip(op.get("evidence")) or note.evidence
    elif kind == "rewrite" and _clip(op.get("text")):
        note.text, note.status = _clip(op.get("text")), NoteStatus.VERIFIED
        note.evidence = _clip(op.get("evidence")) or note.evidence
    elif kind == "delete":
        deleted.add(note.note_id)
    elif kind == "promote" and note.status != NoteStatus.REFUTED:
        note.layer = NoteLayer.INDEX
    elif kind == "demote":
        note.layer = NoteLayer.STORE
    else:
        return False
    return True


def enforce_index_cap(notes: list[MemoryNote], cap: int) -> int:
    """Demote the least useful index notes until at most *cap* remain. Returns demotions."""
    for note in notes:
        if note.status == NoteStatus.REFUTED and note.layer == NoteLayer.INDEX:
            note.layer = NoteLayer.STORE
    index = [n for n in notes if n.layer == NoteLayer.INDEX]
    if len(index) <= cap:
        return 0
    index.sort(key=lambda n: (n.status == NoteStatus.VERIFIED, n.access_count, n.updated_at))
    excess = index[: len(index) - cap]
    for note in excess:
        note.layer = NoteLayer.STORE
    return len(excess)


async def dream_agent(
    store: AgentMemoryStore, memory_key: str, agent_context: str, *, llm: LLM, index_cap: int,
) -> dict[str, Any]:
    """One dreaming pass over one agent's memory. Episodes stay undreamed if the model fails."""
    notes = await store.list_notes(memory_key)
    episodes = await store.list_episodes(memory_key, undreamed_only=True)
    if not episodes:
        return {"memory_key": memory_key, "status": "nothing_new"}
    reply = await llm(DREAM_SYSTEM.format(cap=index_cap), build_brief(agent_context, notes, episodes))
    ops = parse_ops(reply)
    if ops is None:
        log.warning("agent_memory: dream for %s returned no usable ops", memory_key)
        return {"memory_key": memory_key, "status": "no_usable_reply"}
    by_id = {n.note_id: n for n in notes}
    deleted: set[str] = set()
    added: list[MemoryNote] = []
    applied = sum(1 for op in ops if _apply_one(op, by_id, memory_key, deleted, added))
    survivors = [n for i, n in by_id.items() if i not in deleted]
    demoted = enforce_index_cap(survivors, index_cap)
    now = time.time()
    for note in survivors:
        note.updated_at = now
        await store.save_note(note)
    for note_id in deleted:
        await store.delete_note(memory_key, note_id)
    await store.mark_dreamed(episodes)
    return {"memory_key": memory_key, "status": "dreamed", "episodes": len(episodes),
            "ops_proposed": len(ops), "ops_applied": applied, "added": len(added),
            "deleted": len(deleted), "demoted_for_cap": demoted}

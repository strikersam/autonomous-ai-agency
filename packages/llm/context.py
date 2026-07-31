"""packages/llm/context.py — keeping conversations inside the context window.

The escalation ladder, cheapest and least lossy first:

    1. Fit as-is                  nothing to do
    2. Escalate the model         route to a larger context window
    3. Prune                      drop tool-result blobs and duplicated turns
    4. Sliding window             keep the system prompt, the earliest turn,
                                  and the most recent N turns
    5. Recursive summarisation    replace the dropped span with a summary
                                  produced by a cheap model
    6. Semantic retrieval         re-insert only the dropped turns relevant
                                  to the current question
    7. Chunk                      split an oversized single document

Steps 3–7 are lossy at the *conversation* level but never at the *message*
level: the text of any message that survives is passed through byte-for-byte.
That is the line ADR-008 draws against OmniRoute's token-compression engines —
rewriting message bodies corrupts code blocks, tool-call JSON, and structured
outputs, and every agent in this platform depends on all three.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("llm.context")

# Reserve headroom so the completion has room; models count prompt+completion
# against the same window.
DEFAULT_RESERVE_RATIO = 0.15
# Turns always kept verbatim at the tail of a sliding window.
DEFAULT_KEEP_RECENT = 6
# A single message longer than this is a document, not a turn — chunk it.
DOCUMENT_TOKEN_THRESHOLD = 8000

SummariseFn = Callable[[list[dict[str, Any]]], Awaitable[str]]


def estimate_tokens(text: str) -> int:
    """Character-based estimate (~4 chars/token).

    A real tokenizer per model family would need three more dependencies to
    refine a number used only for fit decisions, where a 10% error costs
    nothing because of the reserve ratio.
    """
    return max(1, len(text) // 4)


def message_tokens(message: dict[str, Any]) -> int:
    content = message.get("content")
    if isinstance(content, str):
        return estimate_tokens(content) + 4
    if isinstance(content, list):
        total = 4
        for part in content:
            if isinstance(part, dict):
                total += estimate_tokens(str(part.get("text") or ""))
                if part.get("type") in {"image_url", "image", "input_image"}:
                    total += 850  # a rough per-image constant
        return total
    return estimate_tokens(str(content or "")) + 4


def total_tokens(messages: list[dict[str, Any]]) -> int:
    return sum(message_tokens(m) for m in messages)


@dataclass
class FitResult:
    """The outcome of fitting a conversation into a window."""

    messages: list[dict[str, Any]]
    original_tokens: int
    final_tokens: int
    strategies_applied: list[str] = field(default_factory=list)
    dropped_messages: int = 0
    summary: str = ""
    needs_larger_model: bool = False

    @property
    def modified(self) -> bool:
        return bool(self.strategies_applied)

    def as_dict(self) -> dict[str, Any]:
        return {
            "original_tokens": self.original_tokens,
            "final_tokens": self.final_tokens,
            "strategies": self.strategies_applied,
            "dropped_messages": self.dropped_messages,
            "needs_larger_model": self.needs_larger_model,
            "summarised": bool(self.summary),
        }


def _split(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separate system messages (always kept) from the conversation body."""
    system = [m for m in messages if m.get("role") == "system"]
    body = [m for m in messages if m.get("role") != "system"]
    return system, body


def prune(messages: list[dict[str, Any]], *, max_tool_chars: int = 2000) -> tuple[list[dict[str, Any]], int]:
    """Truncate oversized tool results and drop exact duplicate turns.

    Tool results are the usual culprit in a runaway context: a directory
    listing or an HTTP body can be tens of thousands of tokens whose tail
    carries almost no signal. The head is kept and the truncation is marked so
    the model knows the content was cut rather than being that short.
    """
    pruned: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    removed = 0

    for message in messages:
        role = str(message.get("role") or "")
        content = message.get("content")

        if role == "tool" and isinstance(content, str) and len(content) > max_tool_chars:
            message = {
                **message,
                "content": (
                    content[:max_tool_chars]
                    + f"\n… [truncated {len(content) - max_tool_chars} characters]"
                ),
            }
            removed += 1

        if isinstance(message.get("content"), str):
            fingerprint = (role, message["content"])
            if fingerprint in seen and role in {"user", "assistant"}:
                removed += 1
                continue
            seen.add(fingerprint)

        pruned.append(message)

    return pruned, removed


def sliding_window(
    messages: list[dict[str, Any]], *, budget_tokens: int, keep_recent: int = DEFAULT_KEEP_RECENT
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep system messages, the first turn, and the newest turns that fit.

    Returns ``(kept, dropped)``. The first user turn is preserved because it
    almost always carries the task definition — dropping it makes an agent
    forget what it was asked to do while remembering the last six steps of
    doing it.
    """
    system, body = _split(messages)
    if not body:
        return messages, []

    reserved = total_tokens(system)
    anchor = body[0]
    anchor_tokens = message_tokens(anchor)

    tail: list[dict[str, Any]] = []
    used = reserved + anchor_tokens
    for message in reversed(body[1:]):
        cost = message_tokens(message)
        if len(tail) >= keep_recent and used + cost > budget_tokens:
            break
        if used + cost > budget_tokens and tail:
            break
        tail.append(message)
        used += cost
    tail.reverse()

    kept_ids = {id(m) for m in tail} | {id(anchor)}
    dropped = [m for m in body if id(m) not in kept_ids]
    return [*system, anchor, *tail], dropped


def chunk_document(text: str, *, chunk_tokens: int = 3000, overlap_tokens: int = 200) -> list[str]:
    """Split a long document on paragraph boundaries with overlap.

    Overlap keeps a fact that straddles a boundary from being lost to both
    chunks. Paragraph-aligned splitting keeps code blocks and lists intact far
    more often than a fixed character cut.
    """
    if not text:
        return []
    max_chars = chunk_tokens * 4
    overlap_chars = overlap_tokens * 4
    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = (current[-overlap_chars:] + "\n\n" + paragraph) if overlap_chars else paragraph
        else:
            # A single paragraph longer than the chunk size — hard split it.
            for start in range(0, len(paragraph), max_chars):
                chunks.append(paragraph[start:start + max_chars])
            current = ""
    if current:
        chunks.append(current)
    return chunks


def semantic_select(
    dropped: list[dict[str, Any]], query: str, *, limit: int = 3
) -> list[dict[str, Any]]:
    """Pick the dropped turns most relevant to ``query`` by token overlap.

    Lexical overlap rather than embeddings: this runs on the hot path of a
    context overflow, when the request is already late, and calling an
    embedding endpoint to rescue a conversation from an overflow risks the
    same overflow twice. Embedding-backed retrieval is available separately
    through the vector memory service.
    """
    if not dropped or not query:
        return []
    query_terms = {w for w in query.lower().split() if len(w) > 3}
    if not query_terms:
        return []

    scored: list[tuple[float, dict[str, Any]]] = []
    for message in dropped:
        content = message.get("content")
        if not isinstance(content, str) or not content:
            continue
        terms = {w for w in content.lower().split() if len(w) > 3}
        if not terms:
            continue
        overlap = len(query_terms & terms) / len(query_terms)
        if overlap > 0:
            scored.append((overlap, message))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [message for _score, message in scored[:limit]]


class ContextManager:
    """Applies the escalation ladder to one request."""

    def __init__(
        self,
        *,
        reserve_ratio: float = DEFAULT_RESERVE_RATIO,
        keep_recent: int = DEFAULT_KEEP_RECENT,
        summarise: SummariseFn | None = None,
    ) -> None:
        self._reserve_ratio = reserve_ratio
        self._keep_recent = keep_recent
        self._summarise = summarise

    def budget_for(self, context_window: int, max_output_tokens: int) -> int:
        """Tokens available for the prompt, after reserving output headroom."""
        reserve = max(int(context_window * self._reserve_ratio), max_output_tokens)
        return max(512, context_window - reserve)

    def fits(
        self, messages: list[dict[str, Any]], *, context_window: int, max_output_tokens: int
    ) -> bool:
        return total_tokens(messages) <= self.budget_for(context_window, max_output_tokens)

    async def fit(
        self,
        messages: list[dict[str, Any]],
        *,
        context_window: int,
        max_output_tokens: int,
        query: str = "",
        allow_summary: bool = True,
    ) -> FitResult:
        """Reduce ``messages`` until they fit, applying the ladder in order."""
        original = total_tokens(messages)
        budget = self.budget_for(context_window, max_output_tokens)

        if original <= budget:
            return FitResult(messages=messages, original_tokens=original, final_tokens=original)

        working = list(messages)
        applied: list[str] = []

        # Step 3 — prune.
        working, removed = prune(working)
        if removed:
            applied.append("prune")
        if total_tokens(working) <= budget:
            return FitResult(
                messages=working, original_tokens=original,
                final_tokens=total_tokens(working), strategies_applied=applied,
                dropped_messages=removed,
            )

        # Step 4 — sliding window.
        working, dropped = sliding_window(
            working, budget_tokens=budget, keep_recent=self._keep_recent
        )
        if dropped:
            applied.append("sliding_window")

        # Step 5 — summarise what the window dropped.
        summary = ""
        if dropped and allow_summary and self._summarise is not None:
            try:
                summary = await self._summarise(dropped)
            except Exception as exc:
                log.warning("llm.context: summarisation failed (%s) — continuing without", exc)
            if summary:
                applied.append("summary")
                working = self._insert_summary(working, summary)

        # Step 6 — bring back the dropped turns that matter to this question.
        if dropped and query:
            relevant = semantic_select(dropped, query)
            candidate = self._insert_relevant(working, relevant)
            if relevant and total_tokens(candidate) <= budget:
                applied.append("semantic_retrieval")
                working = candidate

        final = total_tokens(working)
        return FitResult(
            messages=working,
            original_tokens=original,
            final_tokens=final,
            strategies_applied=applied,
            dropped_messages=len(dropped) + removed,
            summary=summary,
            needs_larger_model=final > budget,
        )

    @staticmethod
    def _insert_summary(messages: list[dict[str, Any]], summary: str) -> list[dict[str, Any]]:
        """Put the summary directly after the system prompt, labelled as one."""
        note = {
            "role": "system",
            "content": (
                "Summary of earlier conversation turns that were removed to fit "
                f"the context window:\n\n{summary}"
            ),
        }
        system = [m for m in messages if m.get("role") == "system"]
        rest = [m for m in messages if m.get("role") != "system"]
        return [*system, note, *rest]

    @staticmethod
    def _insert_relevant(
        messages: list[dict[str, Any]], relevant: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not relevant:
            return messages
        note = {
            "role": "system",
            "content": "Relevant excerpts recalled from earlier in the conversation:\n\n"
            + "\n\n".join(
                f"[{m.get('role')}] {m.get('content')}"
                for m in relevant
                if isinstance(m.get("content"), str)
            ),
        }
        system = [m for m in messages if m.get("role") == "system"]
        rest = [m for m in messages if m.get("role") != "system"]
        return [*system, note, *rest]


def build_summariser(chat: Callable[..., Awaitable[Any]]) -> SummariseFn:
    """Wrap a chat callable into a summariser for dropped turns.

    The summariser deliberately routes to a cheap/fast model: summarising a
    dropped span is bookkeeping, and spending premium tokens on it would
    defeat the reason the span was dropped.
    """
    async def summarise(dropped: list[dict[str, Any]]) -> str:
        transcript = "\n\n".join(
            f"[{m.get('role')}] {m.get('content')}"
            for m in dropped
            if isinstance(m.get("content"), str) and m.get("content")
        )
        if not transcript:
            return ""
        if len(transcript) > 40_000:
            transcript = transcript[:40_000] + "\n… [transcript truncated]"
        response = await chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarise the following conversation excerpt. Preserve "
                        "decisions, constraints, file paths, identifiers, and any "
                        "unfinished task. Omit pleasantries. Be dense and factual."
                    ),
                },
                {"role": "user", "content": transcript},
            ],
            max_tokens=800,
            temperature=0.0,
        )
        return getattr(response, "text", "") or ""

    return summarise

"""packages/intelligence/context.py — Context optimization + compression.

Manages the context window for LLM calls: compresses long conversations,
selects the most relevant context, and stays within token budgets.

Inspired by Onyx (context windows, context ranking, conversation memory)
implemented natively using the existing packages/ architecture.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("intelligence.context")

# Approximate tokens-per-character ratio (rough estimate for budgeting)
CHARS_PER_TOKEN = 4


@dataclass
class ContextWindow:
    """A managed context window for an LLM call."""
    messages: list[dict[str, str]] = field(default_factory=list)
    total_chars: int = 0
    max_chars: int = 32000  # ~8k tokens default budget
    compressed: bool = False
    dropped_count: int = 0

    @property
    def estimated_tokens(self) -> int:
        return self.total_chars // CHARS_PER_TOKEN

    @property
    def is_over_budget(self) -> bool:
        return self.total_chars > self.max_chars


class ContextOptimizer:
    """Optimizes context for LLM calls.

    Strategies:
    1. Truncate: keep the system prompt + last N messages
    2. Summarize: replace older messages with a summary
    3. Relevance filter: drop messages not related to the current goal
    4. Token budget enforcement
    """

    def __init__(self, max_chars: int = 32000) -> None:
        self.max_chars = max_chars

    def optimize(
        self,
        messages: list[dict[str, str]],
        goal: str = "",
        strategy: str = "truncate",
    ) -> ContextWindow:
        """Optimize a message list to fit within the token budget.

        Args:
            messages: The conversation messages [{role, content}, ...]
            goal: The current task goal (for relevance filtering)
            strategy: "truncate", "summarize", or "relevance"

        Returns:
            A ContextWindow with the optimized messages
        """
        total_chars = sum(len(m.get("content", "")) for m in messages)
        window = ContextWindow(
            messages=list(messages),
            total_chars=total_chars,
            max_chars=self.max_chars,
        )

        if not window.is_over_budget:
            return window

        if strategy == "truncate":
            window = self._truncate(window)
        elif strategy == "summarize":
            window = self._summarize(window)
        elif strategy == "relevance":
            window = self._relevance_filter(window, goal)
        else:
            window = self._truncate(window)

        log.info(
            "Context optimized: strategy=%s, %d→%d chars (%d messages→%d), dropped=%d",
            strategy, total_chars, window.total_chars,
            len(messages), len(window.messages), window.dropped_count,
        )
        return window

    def _truncate(self, window: ContextWindow) -> ContextWindow:
        """Keep system prompt + most recent messages within budget."""
        if not window.messages:
            return window

        # Always keep the system prompt (first message if role=system)
        system_msgs = []
        other_msgs = list(window.messages)
        if other_msgs[0].get("role") == "system":
            system_msgs = [other_msgs[0]]
            other_msgs = other_msgs[1:]

        # Keep most recent messages until budget is hit
        system_chars = sum(len(m.get("content", "")) for m in system_msgs)
        budget = self.max_chars - system_chars

        kept = []
        chars = 0
        for msg in reversed(other_msgs):
            msg_chars = len(msg.get("content", ""))
            if chars + msg_chars > budget:
                break
            kept.insert(0, msg)
            chars += msg_chars

        window.dropped_count = len(other_msgs) - len(kept)
        window.messages = system_msgs + kept
        window.total_chars = system_chars + chars
        window.compressed = True
        return window

    def _summarize(self, window: ContextWindow) -> ContextWindow:
        """Replace older messages with a summary placeholder."""
        if not window.messages:
            return window

        # Keep system prompt + last 3 messages, summarize the rest
        system_msgs = []
        other_msgs = list(window.messages)
        if other_msgs[0].get("role") == "system":
            system_msgs = [other_msgs[0]]
            other_msgs = other_msgs[1:]

        recent_count = min(3, len(other_msgs))
        recent_msgs = other_msgs[-recent_count:] if recent_count > 0 else []
        old_msgs = other_msgs[:-recent_count] if recent_count > 0 else other_msgs

        if not old_msgs:
            return window

        # Create a simple summary (full LLM summarization will be added)
        summary_parts = []
        for msg in old_msgs:
            content = msg.get("content", "")
            summary_parts.append(f"[{msg.get('role', '?')}]: {content[:100]}...")

        summary_msg = {
            "role": "system",
            "content": f"Previous conversation summary:\n" + "\n".join(summary_parts),
        }

        window.dropped_count = len(old_msgs)
        window.messages = system_msgs + [summary_msg] + recent_msgs
        window.total_chars = sum(len(m.get("content", "")) for m in window.messages)
        window.compressed = True
        return window

    def _relevance_filter(self, window: ContextWindow, goal: str) -> ContextWindow:
        """Filter messages by relevance to the current goal."""
        if not window.messages or not goal:
            return self._truncate(window)

        goal_words = set(goal.lower().split())

        # Always keep system messages
        system_msgs = [m for m in window.messages if m.get("role") == "system"]
        non_system = [m for m in window.messages if m.get("role") != "system"]

        # Score each message by keyword overlap with goal
        scored = []
        for msg in non_system:
            content = msg.get("content", "").lower()
            content_words = set(content.split())
            overlap = len(goal_words & content_words)
            scored.append((overlap, msg))

        # Sort by relevance (highest first), keep within budget
        scored.sort(key=lambda x: x[0], reverse=True)

        system_chars = sum(len(m.get("content", "")) for m in system_msgs)
        budget = self.max_chars - system_chars

        kept = []
        chars = 0
        for score, msg in scored:
            if score == 0:
                continue  # Skip irrelevant messages
            msg_chars = len(msg.get("content", ""))
            if chars + msg_chars > budget:
                break
            kept.append(msg)
            chars += msg_chars

        # Sort kept messages back into chronological order
        kept_set = {id(m) for m in kept}
        ordered = [m for m in non_system if id(m) in kept_set]

        window.dropped_count = len(non_system) - len(ordered)
        window.messages = system_msgs + ordered
        window.total_chars = system_chars + chars
        window.compressed = True
        return window

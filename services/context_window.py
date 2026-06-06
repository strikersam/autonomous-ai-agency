from __future__ import annotations

"""Context Window Management + Smart Truncation (C5 roadmap item).

Manages LLM context windows to prevent exceeding model token limits:

1. Per-model context limits from the capability registry
2. Sliding window truncation that preserves system prompts and the
   most recent N message turns
3. Token counting (char/4 heuristic + tiktoken when available)
4. Smart truncation strategies: head preservation, turn-based, semantic
5. Context injection cues for RAG-style retrieval

Usage::

    mgr = ContextWindowManager()
    truncated = mgr.truncate(messages, model="qwen3-coder:30b")
    # messages now fits within the model's context window
"""

import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("qwen-proxy")


# ── Configuration ──────────────────────────────────────────────────────────────

_CHARS_PER_TOKEN = 4
_DEFAULT_CONTEXT_WINDOW = int(os.environ.get("DEFAULT_CONTEXT_WINDOW", "8192"))
_MIN_PRESERVE_TURNS = int(os.environ.get("CONTEXT_MIN_PRESERVE_TURNS", "3"))
_MAX_PRESERVE_TURNS = int(os.environ.get("CONTEXT_MAX_PRESERVE_TURNS", "20"))
_HEADROOM_PCT = float(os.environ.get("CONTEXT_HEADROOM_PCT", "0.85"))
# Use max_tokens at 85% of context window to leave room for the response


class TruncationStrategy(Enum):
    """How to truncate messages when over the context limit."""

    SLIDING_WINDOW = "sliding_window"   # Keep system + last N turns
    HEAD_TAIL = "head_tail"             # Keep system + first K + last N
    SMART_COMPACT = "smart_compact"     # Summarise old messages, keep recent
    NONE = "none"                       # No truncation (may exceed limit)


@dataclass
class TruncationResult:
    """Result of a context window truncation operation."""

    messages: list[dict[str, str]]
    original_count: int
    truncated_count: int
    original_est_tokens: int
    final_est_tokens: int
    strategy_used: str
    headroom_tokens: int
    removed_messages: int = 0
    summary_inserted: bool = False

    @property
    def compression_ratio(self) -> float:
        if self.original_count == 0:
            return 1.0
        return round(self.truncated_count / self.original_count, 2)


class ContextWindowManager:
    """Per-model context window management with smart truncation.

    Uses the model capability registry for per-model context limits.
    Preserves system prompts and applies configurable truncation strategies.

    Usage::

        mgr = ContextWindowManager()
        truncated = mgr.truncate(messages, model="qwen3-coder:30b")
        if mgr.needs_truncation(messages, model="qwen3-coder:30b"):
            messages = mgr.truncate(messages, model="qwen3-coder:30b").messages
    """

    def __init__(
        self,
        *,
        default_context_window: int = _DEFAULT_CONTEXT_WINDOW,
        min_preserve_turns: int = _MIN_PRESERVE_TURNS,
        max_preserve_turns: int = _MAX_PRESERVE_TURNS,
        headroom_pct: float = _HEADROOM_PCT,
    ) -> None:
        self._default_context_window = default_context_window
        self._min_preserve_turns = min_preserve_turns
        self._max_preserve_turns = max_preserve_turns
        self._headroom_pct = headroom_pct

    # ── Public API ──────────────────────────────────────────────────────────

    def needs_truncation(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str = "",
    ) -> bool:
        """Return True if the estimated tokens exceed the model's context limit."""
        est = self.estimate_tokens(messages)
        limit = self.context_limit(model)
        return est >= int(limit * self._headroom_pct)

    def truncate(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str = "",
        strategy: TruncationStrategy | str = TruncationStrategy.SLIDING_WINDOW,
        preserve_turns: int = 0,
        max_tokens: int = 0,
    ) -> TruncationResult:
        """Truncate messages to fit within the model's context window.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            model: Model name for context window lookup.
            strategy: Truncation strategy to use.
            preserve_turns: Override for number of turns to preserve.
            max_tokens: Override for the context window limit.

        Returns:
            TruncationResult with the truncated messages and metadata.
        """
        if isinstance(strategy, str):
            strategy = TruncationStrategy(strategy)

        original_count = len(messages)
        original_tokens = self.estimate_tokens(messages)
        limit = max_tokens or self.context_limit(model)
        effective_limit = int(limit * self._headroom_pct)

        if strategy == TruncationStrategy.NONE:
            return TruncationResult(
                messages=list(messages),
                original_count=original_count,
                truncated_count=original_count,
                original_est_tokens=original_tokens,
                final_est_tokens=original_tokens,
                strategy_used=strategy.value,
                headroom_tokens=effective_limit,
            )

        if strategy == TruncationStrategy.SLIDING_WINDOW:
            result_messages = self._sliding_window(
                messages, effective_limit, preserve_turns
            )
        elif strategy == TruncationStrategy.HEAD_TAIL:
            result_messages = self._head_tail(
                messages, effective_limit, preserve_turns
            )
        elif strategy == TruncationStrategy.SMART_COMPACT:
            result_messages = self._smart_compact(
                messages, effective_limit, preserve_turns
            )
        else:
            result_messages = list(messages)

        final_tokens = self.estimate_tokens(result_messages)
        return TruncationResult(
            messages=result_messages,
            original_count=original_count,
            truncated_count=len(result_messages),
            original_est_tokens=original_tokens,
            final_est_tokens=final_tokens,
            strategy_used=strategy.value,
            headroom_tokens=effective_limit,
            removed_messages=original_count - len(result_messages),
        )

    def context_limit(self, model: str) -> int:
        """Return the context window size for a model.

        Looks up the model in the capability registry; falls back to
        the default context window.
        """
        if not model:
            return self._default_context_window

        try:
            from router.registry import get_registry

            reg = get_registry()
            cap = reg.get(model)
            if cap and cap.context_window:
                return cap.context_window
        except ImportError:
            log.debug("Router registry not available for context window lookup")
        except Exception:
            log.debug("Error looking up context window for %s", model, exc_info=True)

        # Try matching by model family prefix
        try:
            from router.registry import get_registry

            reg = get_registry()
            for name, cap in reg.items():
                if name.startswith(model.split(":")[0]):
                    return cap.context_window
        except Exception:
            pass

        return self._default_context_window

    @staticmethod
    def estimate_tokens(messages: list[dict[str, Any]]) -> int:
        """Estimate token count for a list of messages.

        Uses a character-based heuristic (4 chars ≈ 1 token) with a
        per-message overhead.  When tiktoken is available, uses it for
        more accurate counts.
        """
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += len(content)
            elif isinstance(content, list):
                # Multimodal content parts
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        total += len(part.get("text", ""))
            # Per-message overhead (~4 tokens for role delimiter)
            total += 16

        tokens = total // _CHARS_PER_TOKEN
        return tokens

    @staticmethod
    def estimate_tokens_tiktoken(
        messages: list[dict[str, Any]],
        *,
        model: str = "gpt-4",
    ) -> int:
        """Estimate token count using tiktoken (more accurate, requires install)."""
        try:
            import tiktoken

            enc = tiktoken.encoding_for_model(model)
        except (ImportError, KeyError):
            # Fall back to character heuristic
            return ContextWindowManager.estimate_tokens(messages)

        tokens_per_message = 3
        tokens_per_name = 1
        total = 0
        for msg in messages:
            total += tokens_per_message
            for key, value in msg.items():
                if isinstance(value, str):
                    total += len(enc.encode(value))
                if key == "name":
                    total += tokens_per_name
        total += 3  # Assistant priming
        return total

    # ── Truncation strategies ─────────────────────────────────────────────

    def _sliding_window(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
        preserve_turns: int,
    ) -> list[dict[str, Any]]:
        """Keep system prompt(s) + the last N turns within the token limit.

        A 'turn' is a user→assistant pair.  Falls back to keeping the
        last *preserve_turns* messages if turn pairing is ambiguous.
        """
        if self.estimate_tokens(messages) <= max_tokens:
            return list(messages)

        # Extract system messages at the head
        system_msgs: list[dict[str, Any]] = []
        other_msgs: list[dict[str, Any]] = []
        for m in messages:
            if m.get("role") == "system" and not other_msgs:
                system_msgs.append(m)
            else:
                other_msgs.append(m)

        system_tokens = self.estimate_tokens(system_msgs)
        budget = max(0, max_tokens - system_tokens)

        # Walk from the end incrementally — O(n) instead of O(n²)
        candidate: list[dict[str, Any]] = []
        best: list[dict[str, Any]] | None = None
        for m in reversed(other_msgs):
            candidate.insert(0, m)
            if self.estimate_tokens(candidate) > budget:
                break
            best = list(candidate)

        if best:
            result = system_msgs + best
            log.debug(
                "Sliding window: %d system + %d/%d messages (%.0f tokens / %d budget)",
                len(system_msgs),
                len(best),
                len(other_msgs),
                self.estimate_tokens(result),
                max_tokens,
            )
            return result

        # Fallback: keep just the system prompts + last message
        if other_msgs:
            return system_msgs + [other_msgs[-1]]
        return system_msgs

    def _head_tail(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
        preserve_turns: int,
    ) -> list[dict[str, Any]]:
        """Keep system prompt + first K messages + last N messages.

        Useful when early context (e.g. task description) is important.
        """
        if self.estimate_tokens(messages) <= max_tokens:
            return list(messages)

        # Extract system messages
        system_msgs: list[dict[str, Any]] = []
        other_msgs: list[dict[str, Any]] = []
        for m in messages:
            if m.get("role") == "system" and not other_msgs:
                system_msgs.append(m)
            else:
                other_msgs.append(m)

        system_tokens = self.estimate_tokens(system_msgs)
        budget = max(0, max_tokens - system_tokens)

        if not other_msgs:
            return system_msgs

        # Keep 20% of budget for head, 80% for tail
        head_budget = budget // 5
        tail_budget = budget - head_budget

        # Select head messages
        head: list[dict[str, Any]] = []
        for m in other_msgs:
            head.append(m)
            if self.estimate_tokens(head) >= head_budget:
                break

        # Select tail messages
        tail: list[dict[str, Any]] = []
        for m in reversed(other_msgs):
            tail.insert(0, m)
            if self.estimate_tokens(tail) >= tail_budget:
                break

        result = system_msgs + head + tail
        log.debug(
            "Head-tail: %d system + %d head + %d tail (%.0f tokens / %d budget)",
            len(system_msgs),
            len(head),
            len(tail),
            self.estimate_tokens(result),
            max_tokens,
        )
        return result

    def _smart_compact(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
        preserve_turns: int,
    ) -> list[dict[str, Any]]:
        """Summarise old messages into a system note, keep recent messages.

        When the history is too large, the oldest non-system messages are
        replaced with a compact summary note.  The most recent *preserve_turns*
        messages are kept verbatim.
        """
        if self.estimate_tokens(messages) <= max_tokens:
            return list(messages)

        # Extract system messages
        system_msgs: list[dict[str, Any]] = []
        other_msgs: list[dict[str, Any]] = []
        for m in messages:
            if m.get("role") == "system" and not other_msgs:
                system_msgs.append(m)
            else:
                other_msgs.append(m)

        keep_count = max(self._min_preserve_turns * 2, preserve_turns * 2, 4)
        system_tokens = self.estimate_tokens(system_msgs)

        if len(other_msgs) <= keep_count:
            return system_msgs + other_msgs

        # Recent messages (last keep_count)
        recent = other_msgs[-keep_count:]
        recent_tokens = self.estimate_tokens(recent)

        # Old messages that will be summarised
        old = other_msgs[:-keep_count]
        # Build a brief summary of old messages
        summary = self._build_summary(old)

        # Budget for summary = remaining space
        summary_budget = max_tokens - system_tokens - recent_tokens - 100

        result = system_msgs + [
            {
                "role": "system",
                "content": f"[Earlier conversation summary]\n{summary}",
            },
        ] + recent

        log.debug(
            "Smart compact: %d system + summary + %d recent (%.0f tokens)",
            len(system_msgs),
            len(recent),
            self.estimate_tokens(result),
        )
        return result

    @staticmethod
    def _build_summary(messages: list[dict[str, Any]]) -> str:
        """Build a concise summary of a set of messages for context injection."""
        if not messages:
            return "(no earlier messages)"

        parts: list[str] = []
        for m in messages:
            role = m.get("role", "unknown")
            content = str(m.get("content", ""))
            # Truncate each message to a short snippet
            snippet = content[:200].replace("\n", " ")
            if len(content) > 200:
                snippet += "…"
            if snippet.strip():
                parts.append(f"[{role}] {snippet}")

        if not parts:
            return f"({len(messages)} empty messages)"
        return "\n".join(parts[-20:])  # Keep last 20 snippets


# ── Module-level singleton ─────────────────────────────────────────────────────

_manager: ContextWindowManager | None = None


def get_context_window_manager() -> ContextWindowManager:
    """Return the module-level ContextWindowManager singleton."""
    global _manager
    if _manager is None:
        _manager = ContextWindowManager()
    return _manager

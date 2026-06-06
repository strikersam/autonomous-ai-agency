from __future__ import annotations

import logging
import re
import time
from typing import Any

log = logging.getLogger("qwen-agent")

# Default token budgets (chars ≈ tokens * 4 for rough estimation without tiktoken)
_DEFAULT_USER_BUDGET = 50_000 * 4   # 50k tokens ≈ 200k chars
_DEFAULT_ASSISTANT_BUDGET = 20_000 * 4  # 20k tokens ≈ 80k chars
# Trigger pruning when total estimated tokens exceed this
_DEFAULT_PRUNE_AFTER_TOKENS = 80_000
# Minimum interval (seconds) between prune operations to avoid thrashing
_DEFAULT_CACHE_TTL = 300  # 5 minutes

_THINK_PATTERN = re.compile(r"<think>[\s\S]*?(?:</think>|$)", re.IGNORECASE)


class ContextPruner:
    """3-phase context window management middleware.

    Phase 1 — Truncate: Strips ``<think>`` tags and summarises oversized tool outputs.
    Phase 2 — Backward walk: Enforces per-role token budgets by walking backward.
    Phase 3 — XML wrap: Older evicted turns become ``<historical_memory_only>`` XML.

    Designed to be called before every LLM API call in the agent loop:
    ``messages = pruner.prune(messages)`` right inside ``_chat_text()``.

    Integrates with the existing ``ContextManager`` which handles observation masking
    and JIT retrieval hints — the pruner is the *API-level* token-budget enforcer.
    """

    def __init__(
        self,
        *,
        user_budget: int = _DEFAULT_USER_BUDGET,
        assistant_budget: int = _DEFAULT_ASSISTANT_BUDGET,
        prune_after_tokens: int = _DEFAULT_PRUNE_AFTER_TOKENS,
        cache_ttl: int = _DEFAULT_CACHE_TTL,
    ) -> None:
        self.user_budget = user_budget
        self.assistant_budget = assistant_budget
        self.prune_after_tokens = prune_after_tokens
        self.cache_ttl = cache_ttl
        self._last_pruned: float = 0.0

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def prune(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply 3-phase pruning if the context is over budget or cache expired.

        Returns the pruned message list (may be unchanged if within budget).
        """
        if not messages:
            return messages

        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        estimated_tokens = total_chars // 4
        cache_expired = (time.time() - self._last_pruned) > self.cache_ttl

        if estimated_tokens < self.prune_after_tokens and not cache_expired:
            return messages

        log.debug(
            "context_pruner: triggering prune (tokens≈%d, budget=%d, cache_expired=%s)",
            estimated_tokens, self.prune_after_tokens, cache_expired,
        )

        # Phase 1: Strip think tags and truncate large tool outputs
        messages = self._phase1_truncate(messages)

        # Phase 2: Backward-walk with per-role budgets
        kept, evicted = self._phase2_backward_walk(messages)

        # Phase 3: XML-wrap evicted turns into historical memory
        result = self._phase3_xml_wrap(kept, evicted)

        self._last_pruned = time.time()
        log.debug(
            "context_pruner: %d messages → %d kept + %d evicted (wrapped)",
            len(messages), len(kept), len(evicted),
        )
        return result

    # ------------------------------------------------------------------
    # Phase 1: Truncate think tags + oversized tool outputs
    # ------------------------------------------------------------------

    def _phase1_truncate(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Strip ``<think>`` blocks and truncate oversized assistant/tool outputs."""
        result: list[dict[str, Any]] = []
        for msg in messages:
            content = msg.get("content", "")
            if not isinstance(content, str):
                result.append(msg)
                continue

            # Strip <think>...</think> blocks (costly reasoning verbatim, no model value)
            stripped = _THINK_PATTERN.sub("", content).strip()

            # Truncate oversized tool outputs (keep first ~2k chars)
            role = msg.get("role", "")
            if role in ("tool", "function") and len(stripped) > 2000:
                stripped = stripped[:2000] + " … [tool output truncated by context_pruner]"

            if stripped != content:
                msg = dict(msg)
                msg["content"] = stripped
            result.append(msg)

        return result

    # ------------------------------------------------------------------
    # Phase 2: Backward walk with per-role token budgets
    # ------------------------------------------------------------------

    def _phase2_backward_walk(
        self, messages: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Walk messages backward, accumulating per-role char counts.

        Returns (kept_messages, evicted_messages) where kept messages fit
        within their role budgets and evicted ones are the overflow.
        The system message is always preserved.
        """
        user_chars = 0
        assistant_chars = 0
        kept: list[dict[str, Any]] = []
        evicted: list[dict[str, Any]] = []

        # Always keep the first system message
        system_idx = -1
        for i, msg in enumerate(messages):
            if msg.get("role") == "system":
                system_idx = i
                break

        # Walk backward from the end, collecting until budgets are exceeded
        for msg in reversed(messages):
            role = msg.get("role", "user")
            content = str(msg.get("content", ""))
            chars = len(content)

            # System message: always keep (but count toward budget)
            if role == "system":
                kept.insert(0, msg)
                continue

            if role == "user":
                if user_chars + chars <= self.user_budget:
                    kept.insert(0, msg)
                    user_chars += chars
                else:
                    evicted.insert(0, msg)
            else:
                if assistant_chars + chars <= self.assistant_budget:
                    kept.insert(0, msg)
                    assistant_chars += chars
                else:
                    evicted.insert(0, msg)

        return kept, evicted

    # ------------------------------------------------------------------
    # Phase 3: XML historical-memory wrap
    # ------------------------------------------------------------------

    def _phase3_xml_wrap(
        self,
        kept: list[dict[str, Any]],
        evicted: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Wrap evicted messages into ``<historical_memory_only>`` XML.

        The XML block is injected into the first system message (or prepended
        as a new system message if none exists).  This keeps the older context
        available for reference but outside the live message window, so the
        model's attention is focused on recent turns.
        """
        if not evicted:
            return kept

        history_lines: list[str] = []
        for msg in evicted:
            role = msg.get("role", "unknown")
            content = str(msg.get("content", ""))[:1500]
            history_lines.append(f"<turn role=\"{role}\">\n{content}\n</turn>")

        history_block = (
            "<historical_memory_only>\n"
            + "\n".join(history_lines)
            + "\n</historical_memory_only>"
        )

        # Inject into first system message or prepend new one
        result = list(kept)
        for i, msg in enumerate(result):
            if msg.get("role") == "system":
                existing = str(msg.get("content", ""))
                result[i] = {
                    "role": "system",
                    "content": f"{history_block}\n\n{existing}",
                }
                return result

        # No system message found — prepend one
        return [{"role": "system", "content": history_block}] + result

    # ------------------------------------------------------------------
    # Utility: force-clear the cache timer (used after deploy/restart)
    # ------------------------------------------------------------------

    def touch(self) -> None:
        """Reset the prune timer so the next call always runs the pipeline."""
        self._last_pruned = 0.0

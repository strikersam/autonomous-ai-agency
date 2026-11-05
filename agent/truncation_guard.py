"""Detect a model response that the provider cut off at its output limit.

A reply that stopped at ``max_tokens`` is a partial answer; treating it as complete
yields half a JSON plan or a half-written file. The guard is a pure function over
the provider's ``finish_reason`` so callers can fail loudly instead of parsing it.
"""

from __future__ import annotations

from typing import Any

# OpenAI-style "length", Anthropic-style "max_tokens", Gemini-style "MAX_TOKENS".
_TRUNCATED_REASONS = frozenset({"length", "max_tokens", "max_output_tokens"})


class TruncatedResponseError(RuntimeError):
    """Raised when a response ended because it hit the output-token limit."""


def is_truncated(finish_reason: Any) -> bool:
    """True when ``finish_reason`` says the provider stopped at its output limit."""
    if not isinstance(finish_reason, str):
        return False
    return finish_reason.strip().lower() in _TRUNCATED_REASONS


def require_complete(finish_reason: Any) -> None:
    """Raise ``TruncatedResponseError`` if the response was cut off at the limit."""
    if is_truncated(finish_reason):
        raise TruncatedResponseError(
            f"response truncated by provider (finish_reason={finish_reason!r})"
        )

"""packages/gateway/messages.py — text access over OpenAI-style chat messages.

Shared by the prompt policy and the sanitiser. A message's ``content`` is either
a string or a list of parts; only ``{"type": "text", "text": ...}`` parts carry
prompt text, every other part (images, tool payloads) is left alone.
"""

from __future__ import annotations

from typing import Any, Callable, Iterator


def iter_texts(messages: Any) -> Iterator[str]:
    """Yield every prompt-text string in *messages*."""
    if not isinstance(messages, list):
        return
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            yield content
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                    yield part["text"]


def _map_content(content: Any, fn: Callable[[str], str]) -> Any:
    if isinstance(content, str):
        return fn(content)
    if not isinstance(content, list):
        return content
    out: list[Any] = []
    for part in content:
        if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
            part = {**part, "text": fn(part["text"])}
        out.append(part)
    return out


def map_texts(messages: Any, fn: Callable[[str], str]) -> Any:
    """Return *messages* with *fn* applied to every text; inputs are never mutated."""
    if not isinstance(messages, list):
        return messages
    out: list[Any] = []
    for message in messages:
        if isinstance(message, dict) and "content" in message:
            message = {**message, "content": _map_content(message["content"], fn)}
        out.append(message)
    return out

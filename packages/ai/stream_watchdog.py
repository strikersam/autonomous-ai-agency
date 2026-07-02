"""packages/ai/stream_watchdog.py — Idle-timeout guard for streaming LLM responses.

Providers can silently stall mid-stream (TCP timeout without RST, ECONNRESET that
httpx swallows, upstream provider hang under load). Without a watchdog the streaming
generator never raises — the caller blocks indefinitely and an autonomous loop slot
is stuck until the server restarts.

Usage (in any provider adapter's stream() method):

    from packages.ai.stream_watchdog import guarded_stream

    async def stream(self, messages, **kwargs):
        async def _raw():
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream("POST", url, ...) as resp:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: ") and line != "data: [DONE]":
                            chunk = json.loads(line[6:])
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            if delta.get("content"):
                                yield delta["content"]

        async for chunk in guarded_stream(_raw(), idle_timeout=STREAM_IDLE_TIMEOUT):
            yield chunk

The default idle timeout is 5 minutes (300 s), matching the Claude Code proxy
internal default confirmed in production (v2.1.185 release, July 2026).
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

log = logging.getLogger(__name__)

# Default: 5 minutes between chunks before declaring a stall.
# Override via STREAM_IDLE_TIMEOUT_SEC env var (checked at import time).
import os as _os
STREAM_IDLE_TIMEOUT: float = float(_os.environ.get("STREAM_IDLE_TIMEOUT_SEC", "300"))


class StreamStallError(RuntimeError):
    """Raised when no chunk arrives within the idle timeout window."""


async def guarded_stream(
    source: AsyncGenerator[str, None],
    idle_timeout: float = STREAM_IDLE_TIMEOUT,
) -> AsyncGenerator[str, None]:
    """Wrap *source* so that a stall (no chunk for *idle_timeout* seconds) raises.

    Args:
        source: Any async generator that yields string chunks.
        idle_timeout: Seconds of silence before raising StreamStallError.
                      ≤0 disables the guard (pass-through).

    Yields:
        Chunks from *source* unchanged.

    Raises:
        StreamStallError: When no chunk arrives within *idle_timeout* seconds.
    """
    if idle_timeout <= 0:
        async for chunk in source:
            yield chunk
        return

    aiter = source.__aiter__()

    async def _anext() -> str | None:
        try:
            return await aiter.__anext__()
        except StopAsyncIteration:
            return None

    while True:
        try:
            value = await asyncio.wait_for(_anext(), timeout=idle_timeout)
        except asyncio.TimeoutError:
            msg = f"Stream stalled: no chunk received for {idle_timeout:.0f}s"
            log.warning(msg)
            raise StreamStallError(msg)

        if value is None:
            return
        yield value

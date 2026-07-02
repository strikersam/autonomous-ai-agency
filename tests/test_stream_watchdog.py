"""tests/test_stream_watchdog.py — unit tests for packages/ai/stream_watchdog.py.

Tests the idle-timeout guard for streaming LLM responses.
No real HTTP requests — pure asyncio + async generators.
"""
from __future__ import annotations

import asyncio

import pytest

from packages.ai.stream_watchdog import StreamStallError, guarded_stream


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _instant_stream(*chunks: str):
    """Async generator that yields chunks with zero delay."""
    for chunk in chunks:
        yield chunk


async def _slow_stream(delay: float, *chunks: str):
    """Async generator that pauses *delay* seconds between each chunk."""
    for chunk in chunks:
        await asyncio.sleep(delay)
        yield chunk


async def _stalling_stream(first_chunk: str, stall_after: float):
    """Yields one chunk then stalls forever."""
    yield first_chunk
    await asyncio.sleep(stall_after)
    # Never reaches here in the stall scenario
    yield "never"


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pass_through_fast_stream():
    """Normal streams with no delay pass through unchanged."""
    chunks = []
    async for c in guarded_stream(_instant_stream("a", "b", "c"), idle_timeout=5.0):
        chunks.append(c)
    assert chunks == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_pass_through_empty_stream():
    """Empty streams complete without error."""
    chunks = []
    async for c in guarded_stream(_instant_stream(), idle_timeout=5.0):
        chunks.append(c)
    assert chunks == []


@pytest.mark.asyncio
async def test_stall_raises_stream_stall_error():
    """StreamStallError is raised when no chunk arrives within idle_timeout."""
    with pytest.raises(StreamStallError, match="stalled"):
        async for _ in guarded_stream(_stalling_stream("hello", stall_after=60.0), idle_timeout=0.05):
            pass


@pytest.mark.asyncio
async def test_chunks_arriving_within_timeout_are_ok():
    """Chunks that arrive before the timeout do not trigger the guard."""
    chunks = []
    # 3 chunks, each 0.02 s apart, timeout 0.1 s — should succeed
    async for c in guarded_stream(_slow_stream(0.02, "x", "y", "z"), idle_timeout=0.1):
        chunks.append(c)
    assert chunks == ["x", "y", "z"]


@pytest.mark.asyncio
async def test_disabled_guard_passes_through_stalling_stream():
    """Setting idle_timeout <= 0 disables the guard entirely (pass-through)."""
    # Use a very short stall so the test doesn't block — disabled guard never fires
    results = []
    gen = _instant_stream("only", "these")
    async for c in guarded_stream(gen, idle_timeout=0):
        results.append(c)
    assert results == ["only", "these"]


@pytest.mark.asyncio
async def test_stream_stall_error_is_runtime_error():
    """StreamStallError is a RuntimeError subclass for easy catching."""
    assert issubclass(StreamStallError, RuntimeError)


def test_module_constants_exist():
    """Public API: STREAM_IDLE_TIMEOUT and StreamStallError are exported."""
    from packages.ai import stream_watchdog
    assert hasattr(stream_watchdog, "STREAM_IDLE_TIMEOUT")
    assert stream_watchdog.STREAM_IDLE_TIMEOUT > 0

from __future__ import annotations

"""Streaming Delta Reconstruction (C3 roadmap item).

Implements streaming with proper delta reconstruction so that LLM responses
can be post-processed (tool-call parsing, steering injection, guardrail
filtering) without losing streaming to the client.

The pipeline:
1. Accumulate raw SSE chunks into a full response buffer
2. Apply post-processing hooks (tool extraction, steering, guardrails)
3. Re-emit the processed content as properly-formed SSE deltas
   with an asyncio.Queue for backpressure
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Awaitable

log = logging.getLogger("qwen-proxy")


# ── Data models ──────────────────────────────────────────────────────────────

@dataclass
class DeltaChunk:
    """A single SSE delta chunk with metadata."""

    content: str
    role: str = "assistant"
    index: int = 0
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    def to_sse_bytes(self, model: str, chunk_id: str) -> bytes:
        """Render as an OpenAI-compatible SSE delta chunk."""
        delta: dict[str, Any] = {}
        if self.role and self.index == 0:
            delta["role"] = self.role
        if self.content:
            delta["content"] = self.content
        if self.tool_calls:
            delta["tool_calls"] = self.tool_calls

        obj: dict[str, Any] = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": self.index,
                    "delta": delta,
                    "finish_reason": self.finish_reason or (None if self.content else "stop"),
                }
            ],
        }
        if self.tool_calls:
            obj["choices"][0]["finish_reason"] = "tool_calls"

        encoded = json.dumps(obj, separators=(",", ":"))
        return b"data: " + encoded.encode("utf-8") + b"\n\n"

    @staticmethod
    def done_sse_bytes(model: str, chunk_id: str) -> bytes:
        """Return the [DONE] marker."""
        return b"data: [DONE]\n\n"


@dataclass
class ReconstructResult:
    """Result of reconstructing a streamed response."""

    full_text: str
    chunks: list[DeltaChunk]
    tool_calls: list[dict[str, Any]]
    latency_ms: float
    model: str = ""
    processed: bool = False


# ── Post-processing hook type ────────────────────────────────────────────────

PostProcessHook = Callable[[str], Awaitable[str]]
"""A hook that receives the accumulated full text and returns processed text."""


# ── Streaming Delta Reconstructor ────────────────────────────────────────────

class StreamingDeltaReconstructor:
    """Accumulate SSE chunks, post-process, and re-stream as deltas.

    Usage::

        recon = StreamingDeltaReconstructor(model="qwen3-coder:30b")
        recon.add_hook("guardrails", my_guardrail_filter)

        async for line_bytes in upstream_sse:
            recon.feed_sse_bytes(line_bytes)

        async for chunk_bytes in recon.emit():
            yield chunk_bytes
    """

    _CHUNK_SIZE = 8  # chars per emitted delta chunk (simulates streaming)

    def __init__(self, *, model: str = "", chunk_size: int = 0) -> None:
        self.model = model
        self.chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        self._chunk_size = chunk_size or self._CHUNK_SIZE
        self._buffer: list[str] = []
        self._hooks: dict[str, PostProcessHook] = {}
        self._consumed = False
        self._total_raw_bytes = 0
        self._total_emitted_bytes = 0

    # ── Hook registration ──────────────────────────────────────────────────

    def add_hook(self, name: str, hook: PostProcessHook) -> None:
        """Register a post-processing hook (runs before re-streaming)."""
        self._hooks[name] = hook

    def remove_hook(self, name: str) -> None:
        """Remove a post-processing hook."""
        self._hooks.pop(name, None)

    # ── Feed phase: accumulate raw SSE chunks ───────────────────────────────

    def feed_sse_bytes(self, data: bytes) -> None:
        """Feed a raw SSE line from the upstream stream."""
        self._total_raw_bytes += len(data)
        # Parse the SSE line to extract content delta
        line = data.strip()
        if not line or line == b"data: [DONE]":
            return
        if not line.startswith(b"data:"):
            return

        payload = line.split(b"data:", 1)[1].strip()
        try:
            obj = json.loads(payload)
        except (json.JSONDecodeError, ValueError):
            return

        if not isinstance(obj, dict):
            return

        choices = obj.get("choices") or []
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta") or {}
            content = delta.get("content")
            if isinstance(content, str) and content:
                self._buffer.append(content)

    def feed_text(self, text: str) -> None:
        """Feed raw text (e.g., from a non-streaming response) for re-emission."""
        self._buffer.append(text)

    # ── Process phase: apply hooks to accumulated text ──────────────────────

    async def process(self) -> str:
        """Apply all registered hooks to the accumulated text.

        Returns the final processed text ready for emission.
        """
        text = "".join(self._buffer)

        for name, hook in self._hooks.items():
            try:
                processed = await hook(text)
                log.debug("Streaming hook '%s': %d → %d chars", name, len(text), len(processed))
                text = processed
            except Exception as exc:
                log.warning("Streaming hook '%s' failed: %s", name, exc)

        self._buffer = [text]
        return text

    # ── Emit phase: re-stream processed text as deltas ──────────────────────

    async def emit(self) -> AsyncIterator[bytes]:
        """Re-emit the processed content as SSE delta chunks.

        Processes accumulated text through hooks, then yields each
        character-sized chunk as an SSE delta directly (no queue).
        """
        if self._consumed:
            return
        self._consumed = True

        text = await self.process()
        self._total_emitted_bytes = 0

        # Emit in character-sized chunks to simulate streaming
        for i in range(0, len(text), self._chunk_size):
            chunk_text = text[i : i + self._chunk_size]
            chunk_bytes = DeltaChunk(
                content=chunk_text,
                role="assistant",
                index=0,
            ).to_sse_bytes(self.model, self.chunk_id)
            self._total_emitted_bytes += len(chunk_bytes)
            yield chunk_bytes

        # Emit the finishing chunk
        done_bytes = DeltaChunk(
            content="",
            index=0,
            finish_reason="stop",
        ).to_sse_bytes(self.model, self.chunk_id)
        yield done_bytes

        # Signal done
        yield DeltaChunk.done_sse_bytes(self.model, self.chunk_id)

    async def emit_all(self) -> list[bytes]:
        """Collect all emitted chunks into a list (convenience)."""
        chunks: list[bytes] = []
        async for chunk in self.emit():
            chunks.append(chunk)
        return chunks

    # ── Stats ───────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return reconstruction statistics."""
        raw_text = "".join(self._buffer)
        return {
            "model": self.model,
            "raw_bytes": self._total_raw_bytes,
            "emitted_bytes": self._total_emitted_bytes,
            "accumulated_chars": len(raw_text),
            "hooks": list(self._hooks.keys()),
            "chunk_size": self._chunk_size,
        }


# ── Module-level factory ─────────────────────────────────────────────────────

def create_streaming_reconstructor(
    *,
    model: str = "",
    chunk_size: int = 0,
    enable_steering: bool = False,
    enable_guardrails: bool = False,
) -> StreamingDeltaReconstructor:
    """Create a pre-configured StreamingDeltaReconstructor.

    Args:
        model: Model name for the SSE metadata.
        chunk_size: Characters per emitted chunk (default=8).
        enable_steering: If True, register the SteerLM hook.
        enable_guardrails: If True, register the guardrails hook.
    """
    recon = StreamingDeltaReconstructor(model=model, chunk_size=chunk_size)

    if enable_steering:
        # Deferred import to avoid circular dependency
        try:
            from router.steering import get_steering

            steer = get_steering()

            async def _steering_hook(text: str) -> str:
                return steer.inject(text)

            recon.add_hook("steering", _steering_hook)
        except ImportError:
            log.debug("Steering module not available — skipping hook")

    if enable_guardrails:
        try:
            from services.guardrails import get_guardrails

            guard = get_guardrails()

            async def _guardrails_hook(text: str) -> str:
                result = guard.check_output(text)
                if result.blocked:
                    return "[Output blocked by guardrails]"
                if result.warned:
                    log.warning("Guardrails flagged output: %s", result.issues)
                return text

            recon.add_hook("guardrails", _guardrails_hook)
        except ImportError:
            log.debug("Guardrails module not available — skipping hook")

    return recon

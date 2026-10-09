from __future__ import annotations

"""Lossless tool-output offload.

Observation masking (``context_manager.py``) and the ReAct scratchpad
(``react_loop.py``) shorten tool results to keep the prompt lean. Without this
store the cut text is gone for good. The store keeps the full result under an
unguessable ref so the model can page it back in with ``read_tool_output``.

In-process, bounded (entries and total characters, LRU) and TTL-limited. A ref
is generated with ``secrets`` and never derived from the content. Each entry is
also bound to an *owner* (one agent run); a read from a different owner is
refused, so a ref leaked into another run's context is useless there.
"""

import hashlib
import json
import logging
import secrets
import threading
import time
from collections import OrderedDict
from typing import Any, Callable

log = logging.getLogger("qwen-proxy")

MAX_ENTRIES = 256
MAX_TOTAL_CHARS = 8_000_000
TTL_SECONDS = 3600.0
DEFAULT_READ_LIMIT = 4000
MAX_READ_LIMIT = 8000

_REF_PREFIX = "out_"


def offload_enabled() -> bool:
    """Read AGENT_TOOL_OUTPUT_OFFLOAD at call time so a Platform Controls override is live."""
    try:
        from packages.config import settings

        return settings.agent_tool_output_offload
    except Exception as exc:  # noqa: BLE001 - a broken settings read keeps the shipped default
        log.debug("AGENT_TOOL_OUTPUT_OFFLOAD unreadable, keeping offload on: %s", exc)
        return True


def stringify(result: Any) -> str:
    """Stable text form of a tool result (JSON for containers, str otherwise)."""
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, indent=2, default=str)
    except (TypeError, ValueError):
        return str(result)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def hint_for(ref: str) -> str:
    """Suffix appended to a shortened observation so the model can recover it."""
    return f" [full output: ref={ref} — call read_tool_output to page it in]"


class ToolOutputStore:
    """Thread-safe LRU of full tool outputs keyed by an unguessable ref."""

    def __init__(
        self,
        *,
        max_entries: int = MAX_ENTRIES,
        max_total_chars: int = MAX_TOTAL_CHARS,
        ttl_seconds: float = TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_entries = max_entries
        self.max_total_chars = max_total_chars
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._items: OrderedDict[str, tuple[float, str, str | None]] = OrderedDict()
        self._by_digest: dict[tuple[str | None, str], str] = {}
        self._total = 0

    def _drop(self, ref: str) -> None:
        _, text, owner = self._items.pop(ref)
        self._total -= len(text)
        self._by_digest.pop((owner, _digest(text)), None)

    def _evict(self) -> None:
        now = self._clock()
        for ref in [r for r, (ts, _, _o) in self._items.items() if now - ts > self.ttl_seconds]:
            self._drop(ref)
        while self._items and (
            len(self._items) > self.max_entries or self._total > self.max_total_chars
        ):
            self._drop(next(iter(self._items)))

    def offload(self, result: Any, owner: str | None = None) -> str | None:
        """Store the full stringified *result* for *owner* and return its ref.

        Identical text offloaded again by the same owner while still live
        returns the same ref (masking re-runs every tool iteration over the
        same history). Returns None, storing nothing and evicting nothing, when
        the text alone exceeds the total-size cap.
        """
        text = stringify(result)
        if len(text) > self.max_total_chars:
            return None
        key = (owner, _digest(text))
        with self._lock:
            self._evict()
            existing = self._by_digest.get(key)
            if existing is not None and existing in self._items:
                self._items.move_to_end(existing)
                return existing
            ref = _REF_PREFIX + secrets.token_urlsafe(16)
            self._items[ref] = (self._clock(), text, owner)
            self._by_digest[key] = ref
            self._total += len(text)
            self._evict()
        return ref

    def read(
        self,
        ref: str,
        offset: int = 0,
        limit: int = DEFAULT_READ_LIMIT,
        owner: str | None = None,
    ) -> dict[str, Any]:
        """Return a slice of a stored output. Never raises.

        A ref held by a different *owner* reads as unknown.
        """
        try:
            offset = max(0, int(offset))
            limit = min(max(1, int(limit)), MAX_READ_LIMIT)
        except (TypeError, ValueError, OverflowError):
            return {"ok": False, "error": "offset and limit must be integers"}
        with self._lock:
            self._evict()
            entry = self._items.get(ref) if isinstance(ref, str) else None
            if entry is None or entry[2] != owner:
                return {
                    "ok": False,
                    "error": "unknown or expired ref — the output is no longer available",
                }
            self._items.move_to_end(ref)
            text = entry[1]
        end = offset + limit
        return {
            "ok": True,
            "ref": ref,
            "content": text[offset:end],
            "offset": offset,
            "total_length": len(text),
            "next_offset": end if end < len(text) else None,
        }

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


_store: ToolOutputStore | None = None
_store_lock = threading.Lock()


def get_tool_output_store() -> ToolOutputStore:
    """Process-wide singleton."""
    global _store
    with _store_lock:
        if _store is None:
            _store = ToolOutputStore()
        return _store


def reset_store() -> None:
    """Drop the singleton (tests)."""
    global _store
    with _store_lock:
        _store = None


def offload_hint(result: Any, shown_len: int, owner: str | None = None) -> str:
    """Offload *result* and return the hint suffix, or '' when not worthwhile.

    Offloads only when the feature is on and the full text is longer than what
    the caller keeps (*shown_len*). Fails soft: any error, or an entry too big
    for the store, yields ''.
    """
    try:
        if not offload_enabled():
            return ""
        text = stringify(result)
        if len(text) <= shown_len:
            return ""
        ref = get_tool_output_store().offload(text, owner)
        return hint_for(ref) if ref else ""
    except Exception as exc:  # noqa: BLE001 - offload must never break the loop
        log.debug("tool output offload failed: %s", exc)
        return ""

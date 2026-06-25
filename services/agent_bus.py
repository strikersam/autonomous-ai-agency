from __future__ import annotations

"""Inter-Agent Message Bus (A5 roadmap item).

A lightweight pub/sub message bus that allows agents to subscribe to topics
and broadcast events, reducing tight coupling between agents (Planner,
Executor, Verifier, etc.).

Features:
- Topic-based publish/subscribe
- Pattern-matched subscriptions (e.g. ``agent.*.done`` matches ``agent.planner.done``)
- In-memory event bus with optional async dispatch
- Event history with configurable retention
- Wildcard topic matching (``*`` and ``**``)

Usage::

    bus = get_agent_bus()

    # Subscribe to agent lifecycle events
    @bus.subscribe("agent.*.done")
    async def on_agent_done(topic: str, event: dict) -> None:
        print(f"Agent finished: {event}")

    # Broadcast an event
    await bus.publish("agent.planner.done", {"plan": plan.model_dump()})
"""

import asyncio
import fnmatch
import logging
import time
from collections import defaultdict
from typing import Any, Callable, Awaitable

log = logging.getLogger("qwen-proxy")

# How many events to retain in history per topic (for late subscribers)
_HISTORY_LIMIT = int(__import__("os").environ.get("AGENT_BUS_HISTORY_LIMIT", "100"))


class AgentMessageBus:
    """Pub/sub message bus for inter-agent communication.

    Agents subscribe to topics (e.g. ``agent.planner.done``) and receive
    events broadcast by other agents.  Topics are dot-separated strings
    with ``*`` (single segment) and ``**`` (multi-segment) wildcards.
    """

    def __init__(self) -> None:
        # topic → list of (callback, pattern) tuples
        self._subscribers: dict[str, list[tuple[Callable[[str, dict], Awaitable[None]], str]]] = defaultdict(list)
        # pattern → list of callbacks (for wildcard lookup)
        self._pattern_subscribers: dict[str, list[Callable[[str, dict], Awaitable[None]]]] = defaultdict(list)
        # topic → list of events (history)
        self._history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._event_count = 0
        self._started_at = time.monotonic()

    # ── Subscribe ────────────────────────────────────────────────────────────

    def subscribe(
        self,
        topic_pattern: str,
        receive_history: bool = True,
    ) -> Callable:
        """Decorator: subscribe a callback to a topic pattern.

        Supports ``*`` (single segment) and ``**`` (multi-segment) wildcards.

        Usage::

            @bus.subscribe("agent.*.done")
            async def on_done(topic: str, event: dict) -> None: ...
        """
        def decorator(
            callback: Callable[[str, dict], Awaitable[None]],
        ) -> Callable[[str, dict], Awaitable[None]]:
            # Store for pattern matching
            self._pattern_subscribers[topic_pattern].append(callback)
            # Also index exact topics for fast lookup
            if "*" not in topic_pattern:
                self._subscribers[topic_pattern].append((callback, topic_pattern))

            # Replay history for late subscribers
            if receive_history:
                if "*" in topic_pattern:
                    for topic, events in self._history.items():
                        if self._topic_matches(topic, topic_pattern):
                            for event in events[-10:]:  # limit history replay
                                asyncio.create_task(self._safe_call(callback, topic, event))
                elif topic_pattern in self._history:
                    for event in self._history[topic_pattern][-10:]:
                        asyncio.create_task(self._safe_call(callback, topic_pattern, event))

            return callback
        return decorator

    def unsubscribe(
        self,
        callback: Callable[[str, dict], Awaitable[None]],
        topic_pattern: str | None = None,
    ) -> None:
        """Remove a subscription."""
        if topic_pattern:
            subs = self._pattern_subscribers.get(topic_pattern, [])
            if callback in subs:
                subs.remove(callback)
            if not subs:
                self._pattern_subscribers.pop(topic_pattern, None)
            if "*" not in topic_pattern:
                subs = self._subscribers.get(topic_pattern, [])
                self._subscribers[topic_pattern] = [
                    (cb, pat) for cb, pat in subs if cb is not callback
                ]
        else:
            for pat in list(self._pattern_subscribers):
                subs = self._pattern_subscribers[pat]
                if callback in subs:
                    subs.remove(callback)
                if not subs:
                    self._pattern_subscribers.pop(pat, None)
            for topic in list(self._subscribers):
                self._subscribers[topic] = [
                    (cb, pat) for cb, pat in self._subscribers[topic] if cb is not callback
                ]

    # ── Publish ──────────────────────────────────────────────────────────────

    async def publish(self, topic: str, event: dict[str, Any]) -> int:
        """Broadcast an event to all matching subscribers.

        Returns the number of callbacks invoked.
        """
        count = 0
        timestamp = time.monotonic()

        # Store in history
        event_with_ts = {"_timestamp": timestamp, "_topic": topic, **event}
        history = self._history[topic]
        history.append(event_with_ts)
        if len(history) > _HISTORY_LIMIT:
            history.pop(0)
        self._event_count += 1

        # Notify exact-match subscribers
        for callback, _pat in self._subscribers.get(topic, []):
            await self._safe_call(callback, topic, event)
            count += 1

        # Notify pattern subscribers
        for pattern, callbacks in list(self._pattern_subscribers.items()):
            if "*" in pattern and self._topic_matches(topic, pattern):
                for callback in callbacks:
                    await self._safe_call(callback, topic, event)
                    count += 1

        if count > 0:
            log.debug("Published to topic=%s (%d subscribers)", topic, count)
        return count

    def publish_nowait(self, topic: str, event: dict[str, Any]) -> asyncio.Task[int]:
        """Fire-and-forget publish. Creates a background task.

        Returns the asyncio.Task so callers can await or cancel it.
        """
        return asyncio.create_task(self.publish(topic, event))

    # ── Query ────────────────────────────────────────────────────────────────

    def get_history(self, topic: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent events for a topic."""
        return self._history.get(topic, [])[-limit:]

    def get_topics(self) -> list[str]:
        """Return all topics that have history."""
        return sorted(self._history.keys())

    def stats(self) -> dict[str, Any]:
        """Return bus statistics."""
        return {
            "event_count": self._event_count,
            "topics": len(self._history),
            "subscribers": sum(len(v) for v in self._pattern_subscribers.values()),
            "uptime_s": time.monotonic() - self._started_at,
        }

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _topic_matches(topic: str, pattern: str) -> bool:
        """Check if a topic matches a pattern with * and ** wildcards."""
        if "**" in pattern:
            parts = pattern.split("**")
            if len(parts) > 2:
                return False  # only one ** allowed
            prefix, suffix = parts[0].rstrip("."), parts[1].lstrip(".") if len(parts) > 1 else ""
            if prefix and not topic.startswith(prefix):
                return False
            if suffix and not topic.endswith(suffix):
                return False
            return True
        return fnmatch.fnmatch(topic, pattern)

    @staticmethod
    async def _safe_call(
        callback: Callable[[str, dict], Awaitable[None]],
        topic: str,
        event: dict,
    ) -> None:
        try:
            await callback(topic, event)
        except Exception as exc:
            log.debug("Subscriber callback error (topic=%s): %s", topic, exc)


# ── Module-level singleton ─────────────────────────────────────────────────────

_agent_bus: AgentMessageBus | None = None


def get_agent_bus() -> AgentMessageBus:
    """Return the module-level AgentMessageBus singleton."""
    global _agent_bus
    if _agent_bus is None:
        _agent_bus = AgentMessageBus()
    return _agent_bus

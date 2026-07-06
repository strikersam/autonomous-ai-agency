"""packages/events/bus.py — In-process event bus.

Loosely couples components via pub/sub. No module calls another module
directly — it publishes an event, and subscribers react.

Usage:
    from packages.events import bus
    
    # Publish
    await bus.publish(Event(type="task_created", data={"task_id": "..."}))
    
    # Subscribe
    bus.subscribe("task_created", handle_task_created)
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

log = logging.getLogger("events")

@dataclass
class Event:
    """An event published on the bus."""
    type: str
    data: dict[str, Any] = field(default_factory=dict)


# Event type constants (use these instead of string literals)
TASK_CREATED = "task_created"
TASK_STARTED = "task_started"
TASK_COMPLETED = "task_completed"
TASK_FAILED = "task_failed"
TASK_CANCELLED = "task_cancelled"
PROVIDER_UNAVAILABLE = "provider_unavailable"
PROVIDER_RECOVERED = "provider_recovered"
BRAIN_SWITCHED = "brain_switched"
SCHEDULE_FIRED = "schedule_fired"
AGENT_STARTED = "agent_started"
AGENT_COMPLETED = "agent_completed"


_subscribers: dict[str, list[Callable]] = {}


def subscribe(event_type: str, handler: Callable[[Event], Awaitable[None] | None]) -> None:
    """Subscribe to an event type."""
    _subscribers.setdefault(event_type, []).append(handler)
    log.debug("Subscribed %s to %s", handler.__name__, event_type)


async def publish(event: Event) -> None:
    """Publish an event to all subscribers."""
    handlers = _subscribers.get(event.type, [])
    for handler in handlers:
        try:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            log.warning("Event handler %s failed for %s: %s", handler.__name__, event.type, exc)

"""Internal async event bus for broadcasting state changes and protocol events."""

import asyncio
import logging
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

EventHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[EventHandler]] = {}
        self._global_subscribers: list[EventHandler] = []

    def subscribe(self, event_type: str, handler: EventHandler):
        self._subscribers.setdefault(event_type, []).append(handler)

    def subscribe_all(self, handler: EventHandler):
        self._global_subscribers.append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler):
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                h for h in self._subscribers[event_type] if h != handler
            ]

    def unsubscribe_all(self, handler: EventHandler):
        self._global_subscribers = [
            h for h in self._global_subscribers if h != handler
        ]

    async def emit(self, event_type: str, data: dict[str, Any]):
        event = {"type": event_type, **data}
        handlers = self._subscribers.get(event_type, []) + self._global_subscribers
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception("Error in event handler for %s", event_type)


# Global singleton
event_bus = EventBus()

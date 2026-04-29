from __future__ import annotations

import queue
import threading
from typing import Any

from .common import utc_now_iso


class EventBroker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: set[queue.Queue[dict[str, Any]]] = set()

    def subscribe(self) -> queue.Queue[dict[str, Any]]:
        subscriber: queue.Queue[dict[str, Any]] = queue.Queue()
        with self._lock:
            self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: queue.Queue[dict[str, Any]]) -> None:
        with self._lock:
            self._subscribers.discard(subscriber)

    def publish(self, event_type: str, data: Any) -> None:
        event = {
            "type": event_type,
            "timestamp": utc_now_iso(),
            "data": data,
        }
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            subscriber.put(event)

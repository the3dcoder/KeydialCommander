"""In-process pub/sub for driver events (socket stream now, WebSocket in Phase 2)."""
import asyncio
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self):
        self._queues: List[asyncio.Queue] = []

    def subscribe(self, maxsize: int = 64) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._queues.append(q)
        return q

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        try:
            self._queues.remove(queue)
        except ValueError:
            pass

    def publish(self, event: Dict[str, Any]) -> None:
        """Non-blocking publish; a full subscriber queue drops its oldest item."""
        for q in list(self._queues):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()            # drop oldest
                    q.put_nowait(event)
                except Exception:
                    pass

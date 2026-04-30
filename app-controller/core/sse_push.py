import asyncio
import logging
import time
import json
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field

logger = logging.getLogger("ai_controller.sse_push")


@dataclass
class SSEEvent:
    event_type: str
    category: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    event_id: Optional[str] = None

    def to_sse_message(self) -> str:
        parts = []
        if self.event_id:
            parts.append(f"id: {self.event_id}")
        parts.append(f"event: {self.category}")
        parts.append(f"data: {json.dumps(self.data, ensure_ascii=False)}")
        return "\n".join(parts) + "\n\n"


class SSEPushManager:

    def __init__(self):
        self._connections: Dict[str, List[asyncio.Queue]] = {}
        self._event_history: Dict[str, List[SSEEvent]] = {}
        self._max_history_per_category = 50
        self._event_counter = 0

    def subscribe(self, category: str) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=100)
        if category not in self._connections:
            self._connections[category] = []
        self._connections[category].append(queue)

        if category in self._event_history:
            for event in self._event_history[category][-5:]:
                try:
                    queue.put_nowait(event.to_sse_message())
                except asyncio.QueueFull:
                    pass

        logger.info("SSE client subscribed to category: %s", category)
        return queue

    def unsubscribe(self, category: str, queue: asyncio.Queue):
        if category in self._connections:
            try:
                self._connections[category].remove(queue)
            except ValueError:
                pass
            if not self._connections[category]:
                del self._connections[category]
        logger.info("SSE client unsubscribed from category: %s", category)

    def push_event(self, category: str, data: Dict[str, Any], event_type: str = "update") -> int:
        self._event_counter += 1
        event = SSEEvent(
            event_type=event_type,
            category=category,
            data=data,
            event_id=str(self._event_counter),
        )

        if category not in self._event_history:
            self._event_history[category] = []
        self._event_history[category].append(event)
        if len(self._event_history[category]) > self._max_history_per_category:
            self._event_history[category] = self._event_history[category][-self._max_history_per_category:]

        message = event.to_sse_message()
        sent = 0
        queues = self._connections.get(category, [])
        dead_queues = []
        for queue in queues:
            try:
                queue.put_nowait(message)
                sent += 1
            except asyncio.QueueFull:
                dead_queues.append(queue)

        for dq in dead_queues:
            try:
                self._connections[category].remove(dq)
            except (ValueError, KeyError):
                pass

        if category == "all" or category == "global":
            for cat, cat_queues in self._connections.items():
                if cat == category:
                    continue
                for queue in cat_queues:
                    try:
                        queue.put_nowait(message)
                    except asyncio.QueueFull:
                        pass

        logger.debug("SSE event pushed to category %s, sent=%d", category, sent)
        return sent

    def push_to_all(self, data: Dict[str, Any], event_type: str = "update"):
        self.push_event("all", data, event_type)

    def get_categories(self) -> List[str]:
        return list(self._connections.keys())

    def get_connection_count(self, category: Optional[str] = None) -> int:
        if category:
            return len(self._connections.get(category, []))
        return sum(len(qs) for qs in self._connections.values())

    def get_history(self, category: str, limit: int = 20) -> List[Dict]:
        events = self._event_history.get(category, [])
        return [
            {
                "event_id": e.event_id,
                "event_type": e.event_type,
                "data": e.data,
                "timestamp": e.timestamp,
            }
            for e in events[-limit:]
        ]

    def get_stats(self) -> Dict:
        return {
            "categories": self.get_categories(),
            "total_connections": self.get_connection_count(),
            "connections_by_category": {
                cat: len(queues) for cat, queues in self._connections.items()
            },
            "total_events_pushed": self._event_counter,
        }

    def cleanup(self):
        for category in list(self._connections.keys()):
            for queue in self._connections[category]:
                try:
                    queue.put_nowait("event: close\ndata: {}\n\n")
                except asyncio.QueueFull:
                    pass
        self._connections.clear()


sse_push_manager = SSEPushManager()

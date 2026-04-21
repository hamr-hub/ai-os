from fastapi import WebSocket
from typing import Dict, List, Set
import asyncio
import json
from datetime import datetime

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._background_task = None
        self._total_connections = 0
        self._connection_history: List[Dict] = []
        self._max_history_length = 100
    
    async def connect(self, websocket: WebSocket, channel: str = "default"):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(websocket)
        self._total_connections += 1
        
        self._record_connection_event("connect", channel)
    
    def disconnect(self, websocket: WebSocket, channel: str = "default"):
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)
        
        self._record_connection_event("disconnect", channel)
    
    def _record_connection_event(self, event_type: str, channel: str):
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "channel": channel,
            "active_connections": self.get_total_connection_count()
        }
        self._connection_history.append(event)
        if len(self._connection_history) > self._max_history_length:
            self._connection_history = self._connection_history[-self._max_history_length:]
    
    async def broadcast(self, message: dict, channel: str = "default"):
        if channel not in self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.active_connections[channel].discard(conn)
    
    async def broadcast_status(self, gpu_summary: dict, model_status: dict):
        message = {
            "type": "status_update",
            "timestamp": datetime.now().isoformat(),
            "gpu": {
                "status": gpu_summary.get("status", "unavailable"),
                "current": gpu_summary.get("current"),
                "history": gpu_summary.get("history", [])
            },
            "models": model_status
        }
        await self.broadcast(message, channel="monitor")
    
    def get_connection_count(self, channel: str = "default") -> int:
        if channel in self.active_connections:
            return len(self.active_connections[channel])
        return 0
    
    def get_total_connection_count(self) -> int:
        return sum(len(connections) for connections in self.active_connections.values())
    
    def get_active_channels(self) -> List[str]:
        return [channel for channel, connections in self.active_connections.items() if connections]
    
    def get_connection_stats(self) -> Dict:
        channel_stats = {}
        for channel, connections in self.active_connections.items():
            channel_stats[channel] = len(connections)
        
        return {
            "total_connections": self.get_total_connection_count(),
            "channels": channel_stats,
            "active_channels": self.get_active_channels(),
            "total_connections_since_start": self._total_connections,
            "history": self._connection_history,
            "timestamp": datetime.now().isoformat()
        }
    
    def set_max_history_length(self, length: int):
        if length > 0:
            self._max_history_length = length
            if len(self._connection_history) > self._max_history_length:
                self._connection_history = self._connection_history[-self._max_history_length:]
    
    def get_max_history_length(self) -> int:
        return self._max_history_length
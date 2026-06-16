import asyncio
import json
from typing import Dict, List
from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections per job_id."""

    def __init__(self):
        # job_id -> list of connected WebSocket clients
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # job_id -> list of buffered messages (for clients that connect late)
        self.message_buffer: Dict[str, List[dict]] = {}

    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)

        # Send buffered messages to newly connected client
        for message in self.message_buffer.get(job_id, []):
            await websocket.send_text(json.dumps(message))

    def disconnect(self, job_id: str, websocket: WebSocket):
        if job_id in self.active_connections:
            self.active_connections[job_id].remove(websocket)

    async def broadcast(self, job_id: str, message: dict):
        """Send a message to all clients watching this job, and buffer it."""
        if job_id not in self.message_buffer:
            self.message_buffer[job_id] = []
        self.message_buffer[job_id].append(message)

        if job_id in self.active_connections:
            disconnected = []
            for websocket in self.active_connections[job_id]:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception:
                    disconnected.append(websocket)
            for ws in disconnected:
                self.active_connections[job_id].remove(ws)

    def clear_buffer(self, job_id: str):
        self.message_buffer.pop(job_id, None)


# Single shared instance used across the app
manager = ConnectionManager()
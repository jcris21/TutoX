import asyncio
import logging
from typing import Dict, Optional
from uuid import uuid4

from fastapi import WebSocket

from .redis_manager import redis_manager

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and sessions"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self, websocket: WebSocket, session_id: Optional[str] = None
    ) -> str:
        """Establishes WebSocket connection and returns session ID"""
        await websocket.accept()

        async with self._lock:
            # Generate session ID if not provided
            if not session_id:
                session_id = str(uuid4())

            self.active_connections[session_id] = websocket
            logger.info(f"New connection established: {session_id}")

            # Update stats in Redis
            await redis_manager.increment_counter("active_connections")

        return session_id

    async def disconnect(self, session_id: str):
        """Removes connection and cleans up session data"""
        async with self._lock:
            if session_id in self.active_connections:
                self.active_connections.pop(session_id)
                await redis_manager.increment_counter("active_connections", -1)
                logger.info(f"Connection closed: {session_id}")

    def get_active_sessions_count(self) -> int:
        """Returns count of active connections"""
        return len(self.active_connections)

    async def send_message(self, session_id: str, message: dict):
        """Sends message to specific session"""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to {session_id}: {str(e)}")
                await self.disconnect(session_id)

    async def broadcast(self, message: dict, exclude: Optional[str] = None):
        """Broadcasts message to all connections except excluded session"""
        for session_id, websocket in self.active_connections.items():
            if session_id != exclude:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to {session_id}: {str(e)}")
                    await self.disconnect(session_id)


# Global instance
connection_manager = ConnectionManager()

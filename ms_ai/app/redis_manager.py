import json
import logging
import os
from datetime import timedelta
from typing import Any, Dict, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisManager:
    """Handle Redis connections and operations for sessions and messages"""

    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.client: Optional[redis.Redis] = None
        self.pubsub = None

    async def connect(self):
        """Establish connection to Redis"""
        try:
            self.client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,
            )
            await self.client.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise

    async def disconnect(self):
        """Close connection to Redis"""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")

    # === Session Management ===

    async def store_session(
        self, session_id: str, user_data: Dict[str, Any], ttl: int = 3600
    ):
        """Store session data with TTL (default: 1 hour)"""
        try:
            await self.client.setex(
                f"session:{session_id}", timedelta(seconds=ttl), json.dumps(user_data)
            )

        except Exception as e:
            logger.error(f"Error storing session: {str(e)}")
            raise

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data"""
        try:
            data = await self.client.get(f"session:{session_id}")
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error retrieving session: {str(e)}")
            return None

    async def update_session(self, session_id: str, updates: Dict[str, Any]):
        """Update existing session data"""
        session_data = await self.get_session(session_id)
        if session_data:
            session_data.update(updates)
            await self.store_session(session_id, session_data)

    async def delete_session(self, session_id: str):
        """Delete a session"""
        await self.client.delete(f"session:{session_id}")

    # === Message Queue ===

    async def push_message(self, session_id: str, message: Dict[str, Any]):
        """Add a message to the session queue"""
        await self.client.rpush(f"messages:{session_id}", json.dumps(message))
        # Expire queue after 1 hour of inactivity
        await self.client.expire(f"messages:{session_id}", 3600)

    async def get_messages(self, session_id: str, limit: int = 50) -> list:
        """Retrieve the last N messages from the session"""
        raw_messages = await self.client.lrange(f"messages:{session_id}", -limit, -1)

        messages = []
        for msg in raw_messages:
            if isinstance(msg, bytes):
                msg = msg.decode("utf-8")

            try:
                messages.append(json.loads(msg))
            except Exception:
                continue

        return messages
    
    async def clear_messages(self, session_id: str):
        await self.client.delete(f"messages:{session_id}")

    # === Pub/Sub for real-time notifications ===

    async def publish_event(self, channel: str, event: Dict[str, Any]):
        """Publish an event to a channel"""
        await self.client.publish(channel, json.dumps(event))

    async def subscribe_to_channel(self, channel: str):
        """Subscribe to a channel to receive events"""
        self.pubsub = self.client.pubsub()
        await self.pubsub.subscribe(channel)
        return self.pubsub

    # === Metrics and Monitoring ===

    async def increment_counter(self, key: str, amount: int = 1):
        """Increment a counter (useful for metrics)"""
        await self.client.incrby(key, amount)

    async def get_counter(self, key: str) -> int:
        """Get the value of a counter"""
        value = await self.client.get(key)
        return int(value) if value else 0

    async def record_latency(self, endpoint: str, latency_ms: float):
        """Record latency in a time series list"""
        timestamp = json.dumps(
            {
                "timestamp": int(timedelta.total_seconds(timedelta())),
                "latency": latency_ms,
            }
        )
        await self.client.lpush(f"latency:{endpoint}", timestamp)
        # Keep only last 1000 measurements
        await self.client.ltrim(f"latency:{endpoint}", 0, 999)


# Global instance
redis_manager = RedisManager()

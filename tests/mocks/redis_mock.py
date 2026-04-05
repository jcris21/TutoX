from typing import Any, Dict, Optional


class MockRedis:
    """Mock Redis for testing"""

    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.pubsub_channels = {}

    async def ping(self):
        """Mock ping"""
        return True

    async def get(self, key: str) -> Optional[str]:
        """Mock get"""
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None):
        """Mock set with optional expiration"""
        self.data[key] = value

    async def delete(self, key: str):
        """Mock delete"""
        self.data.pop(key, None)

    async def rpush(self, key: str, value: str):
        """Mock list push"""
        if key not in self.data:
            self.data[key] = []
        self.data[key].append(value)

    async def lrange(self, key: str, start: int, end: int) -> list:
        """Mock list range"""
        if key not in self.data:
            return []
        return self.data[key][start:end]

    async def incrby(self, key: str, amount: int = 1):
        """Mock increment"""
        if key not in self.data:
            self.data[key] = 0
        self.data[key] += amount
        return self.data[key]

    async def publish(self, channel: str, message: str):
        """Mock publish"""
        if channel in self.pubsub_channels:
            for callback in self.pubsub_channels[channel]:
                await callback(message)

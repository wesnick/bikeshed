import json
import redis
from typing import Any, Optional

from src.config import get_config

config = get_config()

class RedisService:
    """Service for Redis caching operations"""
    
    def __init__(self, redis_url: str = None):
        """Initialize Redis service
        
        Args:
            redis_url: Redis connection URL, defaults to config if None
        """
        redis_url = redis_url or str(config.REDIS_URL)
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self.default_ttl = 3600  # Default TTL: 1 hour
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in Redis with optional TTL
        
        Args:
            key: Redis key
            value: Value to store (will be JSON serialized)
            ttl: Time to live in seconds, uses default_ttl if None
        """
        try:
            self.redis.setex(
                key,
                ttl or self.default_ttl,
                json.dumps(value)
            )
        except Exception as e:
            print(f"Error setting Redis key {key}: {e}")
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from Redis
        
        Args:
            key: Redis key
            
        Returns:
            Deserialized value if found, None otherwise
        """
        try:
            value = self.redis.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            print(f"Error getting Redis key {key}: {e}")
        return None
    
    def set_default_ttl(self, ttl_seconds: int) -> None:
        """Set the default TTL (Time To Live) in seconds
        
        Args:
            ttl_seconds: TTL in seconds
        """
        self.default_ttl = ttl_seconds

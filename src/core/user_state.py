import json
from typing import Any, Dict, Optional

from .cache import RedisService
from src.logging import logger

class UserStateService:
    """
    Manages a simple key-value store for user-specific state persisted in Redis.
    Designed for a single-user context where authentication is not required.
    """
    _REDIS_KEY = "user_state"

    def __init__(self, redis_service: RedisService):
        self._redis = redis_service

    def _get_state(self) -> Dict[str, Any]:
        """Retrieves the entire state dictionary from Redis."""
        try:
            raw_state = self._redis.get(self._REDIS_KEY)
            if raw_state:
                # Assuming RedisService stores/retrieves as string
                if isinstance(raw_state, bytes):
                    raw_state = raw_state.decode('utf-8')
                return json.loads(raw_state)
            return {}
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from Redis key '{self._REDIS_KEY}'. Returning empty state.")
            return {}
        except Exception as e:
            logger.error(f"Error retrieving state from Redis key '{self._REDIS_KEY}': {e}. Returning empty state.")
            return {}

    def _save_state(self, state: Dict[str, Any]) -> None:
        """Saves the entire state dictionary to Redis as a JSON string."""
        try:
            json_state = json.dumps(state)
            # Set without TTL for persistence across restarts
            self._redis.set(self._REDIS_KEY, json_state, ttl=None)
        except Exception as e:
            logger.error(f"Error saving state to Redis key '{self._REDIS_KEY}': {e}")

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Gets a specific value from the user state by key."""
        state = self._get_state()
        return state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Sets a specific key-value pair in the user state."""
        state = self._get_state()
        state[key] = value
        self._save_state(state)

    def get_all(self) -> Dict[str, Any]:
        """Gets the entire user state dictionary."""
        return self._get_state()

    def delete(self, key: str) -> None:
        """Deletes a specific key from the user state."""
        state = self._get_state()
        if key in state:
            del state[key]
            self._save_state(state)

    def clear(self) -> None:
        """Clears the entire user state."""
        self._save_state({})

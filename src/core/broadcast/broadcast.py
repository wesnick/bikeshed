import asyncio
import json
import redis.asyncio as redis
from typing import Dict, Any, Optional, Type
from pydantic import BaseModel

from src.core.broadcast.broadcast_strategy import (
    BroadcastStrategy,
    MessageBroadcastStrategy,
    DialogBroadcastStrategy
)
from src.logging import logger
from src.core.models import Message, Dialog


class BroadcastService:
    """Service for broadcasting events to SSE clients"""

    def __init__(self, redis_url: str = None):
        # Store active client queues
        self.active_clients: Dict[str, asyncio.Queue] = {}
        self._strategies: Dict[Type[BaseModel], BroadcastStrategy] = {}

        # Register default strategies
        self.register_strategy(Message, MessageBroadcastStrategy())
        self.register_strategy(Dialog, DialogBroadcastStrategy())

        # Redis pub/sub setup
        self.redis_client = redis.from_url(redis_url)
        self.pubsub = None
        self.subscription_task = None

    def register_client(self, client_id: str) -> asyncio.Queue:
        """Register a new client and return its queue"""
        queue = asyncio.Queue()
        self.active_clients[client_id] = queue
        logger.info(f"Registered SSE client: {client_id}, total clients: {len(self.active_clients)}")
        return queue

    def unregister_client(self, client_id: str) -> None:
        """Unregister a client"""
        if client_id in self.active_clients:
            del self.active_clients[client_id]
            logger.info(f"Unregistered SSE client: {client_id}, remaining clients: {len(self.active_clients)}")

    async def initialize_redis(self):
        """Initialize Redis connection for pub/sub"""
        if self.redis_client:
            try:
                # Close any existing pubsub connection
                if self.pubsub:
                    await self.pubsub.unsubscribe()
                    await self.pubsub.close()

                # Cancel any existing subscription task
                if self.subscription_task:
                    self.subscription_task.cancel()
                    try:
                        await self.subscription_task
                    except asyncio.CancelledError:
                        pass

                # Create a new pubsub connection
                self.pubsub = self.redis_client.pubsub()
                await self.pubsub.subscribe("broadcast_channel")

                # Start listening in background
                self.subscription_task = asyncio.create_task(self._listen_for_redis_messages())
                logger.info("Redis pub/sub initialized for broadcast service")
            except Exception as e:
                logger.error(f"Failed to initialize Redis pub/sub: {e}")

    async def _listen_for_redis_messages(self):
        """Listen for messages from Redis and broadcast locally"""
        # Flag to track if we're currently processing a message
        processing = False

        try:
            while True:
                try:
                    # Only get a new message if we're not currently processing one
                    if not processing:
                        message = await self.pubsub.get_message(ignore_subscribe_messages=True)
                        if message and message['type'] == 'message':
                            processing = True
                            try:
                                event = json.loads(message['data'])
                                await self._local_broadcast(event['event'], event['data'])
                            except json.JSONDecodeError:
                                logger.error(f"Invalid JSON in Redis message: {message['data']}")
                            except Exception as e:
                                logger.error(f"Error processing Redis message: {e}")
                            finally:
                                processing = False

                    # Always have a small delay to prevent CPU spinning
                    await asyncio.sleep(0.01)

                except redis.RedisError as e:
                    logger.error(f"Redis error in subscription: {e}")
                    # Wait before trying again
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("Redis subscription task cancelled")
        except Exception as e:
            logger.error(f"Redis subscription error: {e}")
            # Try to reconnect after a delay
            await asyncio.sleep(5)
            if self.redis_client:
                self.subscription_task = asyncio.create_task(self._listen_for_redis_messages())

    async def broadcast(self, event_name: str, data: Any) -> None:
        """
        Send an event to all connected SSE clients and publish to Redis
        for cross-process broadcasting
        """
        if self.pubsub is not None:
            await self._local_broadcast(event_name, data)

        if self.pubsub is None:
            await self.publish_to_redis(event_name, data)

    async def _local_broadcast(self, event_name: str, data: Any) -> None:
        """Send an event to all locally connected SSE clients"""
        if not self.active_clients:
            logger.debug(f"No clients to broadcast {event_name} to")
            return

        logger.debug(f"Broadcasting {event_name} to {len(self.active_clients)} clients")

        # Format the event data for SSE
        if isinstance(data, (dict, list)):
            event_data = json.dumps(data)
        else:
            event_data = str(data)

        # Create the event message
        event_message = {
            "event": event_name,
            "data": event_data
        }

        # Send to all clients
        for client_id, queue in list(self.active_clients.items()):
            try:
                await queue.put(event_message)
            except Exception as e:
                logger.error(f"Error broadcasting to client {client_id}: {e}")
                # If we can't send to this client, remove it
                self.unregister_client(client_id)

    async def publish_to_redis(self, event_name: str, data: Any) -> None:
        """Publish an event to Redis for cross-process broadcasting"""
        if not self.redis_client:
            return

        try:
            # Prepare the message
            if isinstance(data, (dict, list)):
                data_str = json.dumps(data)
            else:
                data_str = str(data)

            message = json.dumps({
                'event': event_name,
                'data': data_str
            })

            # Publish to Redis
            await self.redis_client.publish("broadcast_channel", message)
            logger.debug(f"Published {event_name} to Redis broadcast channel")
        except Exception as e:
            logger.error(f"Failed to publish to Redis: {e}")

    def register_strategy(self, model_class: Type[BaseModel], strategy: BroadcastStrategy) -> None:
        """Register a broadcast strategy for a model class"""
        self._strategies[model_class] = strategy
        logger.debug(f"Registered broadcast strategy for {model_class.__name__}")

    async def model_update(self, model: BaseModel) -> None:
        """Broadcast updates for a model if it has an id field and a registered strategy"""
        # Skip if model doesn't have an id
        if not hasattr(model, "id"):
            return

        model_class = type(model)
        strategy = self._strategies.get(model_class)

        if not strategy:
            # No strategy registered for this model type
            return

        # Use the appropriate strategy to determine if and what to broadcast
        if strategy.should_broadcast(model):
            events = await strategy.get_events(model)

            for event_name, data in events:
                await self.broadcast(event_name, data)
                logger.debug(f"Broadcast {event_name} for {model_class.__name__} {model.id}")

    async def shutdown(self, message: Optional[str] = "Server is shutting down") -> None:
        """Send shutdown message to all clients and close connections"""
        if not self.active_clients:
            logger.info("No SSE connections to shut down")
            return

        logger.info(f"Shutting down {len(self.active_clients)} SSE connections...")

        try:
            # Broadcast shutdown message to all clients
            await self.broadcast("server_shutdown", message)

            # Give clients a moment to process the shutdown message
            await asyncio.sleep(0.2)

            # Close all connections
            for client_id, queue in list(self.active_clients.items()):
                try:
                    await queue.put(None)  # Signal to close the connection
                except Exception as e:
                    logger.error(f"Error closing connection for client {client_id}: {e}")
        except Exception as e:
            logger.error(f"Error during shutdown of SSE connections: {e}")
        finally:
            # Clear the collection
            client_count = len(self.active_clients)
            self.active_clients.clear()
            logger.info(f"Cleared {client_count} SSE connections during shutdown")

        # Clean up Redis resources
        if self.subscription_task:
            self.subscription_task.cancel()
            try:
                await self.subscription_task
            except asyncio.CancelledError:
                pass

        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()

        if self.redis_client:
            await self.redis_client.close()

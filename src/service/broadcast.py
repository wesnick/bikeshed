import asyncio
import json
from typing import Dict, Any, Optional, Type
from pydantic import BaseModel

from src.service.broadcast_strategy import (
    BroadcastStrategy,
    MessageBroadcastStrategy,
    SessionBroadcastStrategy
)
from src.service.logging import logger
from src.models.models import Message, Session


class BroadcastService:
    """Service for broadcasting events to SSE clients"""

    def __init__(self):
        # Store active client queues
        self.active_clients: Dict[str, asyncio.Queue] = {}
        self._strategies: Dict[Type[BaseModel], BroadcastStrategy] = {}

        # Register default strategies
        self.register_strategy(Message, MessageBroadcastStrategy())
        self.register_strategy(Session, SessionBroadcastStrategy())

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

    async def broadcast(self, event_name: str, data: Any) -> None:
        """Send an event to all connected SSE clients"""
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

    def register_strategy(self, model_class: Type[BaseModel], strategy: BroadcastStrategy) -> None:
        """Register a broadcast strategy for a model class"""
        self._strategies[model_class] = strategy
        logger.info(f"Registered broadcast strategy for {model_class.__name__}")

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

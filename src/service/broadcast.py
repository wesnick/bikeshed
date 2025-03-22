import asyncio
import json
import logging
from typing import Dict, Any, Optional
import uuid

logger = logging.getLogger(__name__)

class BroadcastService:
    """Service for broadcasting events to SSE clients"""
    
    def __init__(self):
        # Store active client queues
        self.active_clients: Dict[str, asyncio.Queue] = {}
        # Set to track client IDs for easier iteration
        self.client_ids: set = set()
    
    def register_client(self, client_id: str) -> asyncio.Queue:
        """Register a new client and return its queue"""
        queue = asyncio.Queue()
        self.active_clients[client_id] = queue
        self.client_ids.add(client_id)
        logger.info(f"Registered SSE client: {client_id}")
        return queue
    
    def unregister_client(self, client_id: str) -> None:
        """Unregister a client"""
        if client_id in self.active_clients:
            del self.active_clients[client_id]
            self.client_ids.discard(client_id)
            logger.info(f"Unregistered SSE client: {client_id}")
    
    async def broadcast(self, event_name: str, data: Any) -> None:
        """Send an event to all connected SSE clients"""
        logger.debug(f"Broadcasting {event_name} to {len(self.active_clients)} clients")
        for client_id in list(self.client_ids):
            try:
                queue = self.active_clients.get(client_id)
                if queue:
                    # Format the event properly for SSE
                    event_data = json.dumps(data) if isinstance(data, (dict, list)) else data
                    await queue.put({"event": event_name, "data": event_data})
            except Exception as e:
                logger.error(f"Error broadcasting to client {client_id}: {e}")
                # If we can't send to this client, remove it
                self.unregister_client(client_id)
    
    async def shutdown(self, message: Optional[str] = "Server is shutting down") -> None:
        """Send shutdown message to all clients and close connections"""
        logger.info(f"Shutting down {len(self.active_clients)} SSE connections...")
        try:
            # Broadcast shutdown message to all clients
            await self.broadcast("server_shutdown", message)
            # Give clients a moment to process the shutdown message
            await asyncio.sleep(0.2)
            # Close all connections
            for client_id in list(self.client_ids):
                try:
                    queue = self.active_clients.get(client_id)
                    if queue:
                        await queue.put(None)  # Signal to close the connection
                except Exception as e:
                    logger.error(f"Error closing connection for client {client_id}: {e}")
        except Exception as e:
            logger.error(f"Error during shutdown of SSE connections: {e}")
        finally:
            logger.info("All SSE connections have been notified of shutdown")
            # Clear the collections
            self.active_clients.clear()
            self.client_ids.clear()

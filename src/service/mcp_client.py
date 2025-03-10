from typing import Optional, Dict, Any, Union
from contextlib import AsyncExitStack
import json
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from src.service.redis_service import RedisService


class SessionData:
    def __init__(self, session: ClientSession, write, stdio):
        self.session = session
        self.write = write
        self.stdio = stdio


class MCPClient:
    def __init__(self, redis_service: Optional[RedisService] = None):
        self.sessions: Dict[str, SessionData] = {}
        self.exit_stack = AsyncExitStack()
        self._initialized = False
        self.redis_service = redis_service

    async def __aenter__(self):
        """Make MCPClient usable as an async context manager."""
        self._initialized = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources when exiting the async context."""
        await self.cleanup()

    async def connect_to_server(self, name: str, server_params: StdioServerParameters):
        """Connect to an MCP server

        Args:
            name: Name of the server, used as the key for the session dictionary.
            server_params: StdioServerParameters
        """
        if name in self.sessions:
            # If we already have a session with this name, close it first
            await self._close_session(name)
            
        try:
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            stdio, write = stdio_transport
            session: ClientSession = await self.exit_stack.enter_async_context(ClientSession(stdio, write))

            init_result: types.InitializeResult = await session.initialize()

            print(f"Connected to server with features: {init_result}")

            self.sessions[name] = SessionData(session, write, stdio)
        except Exception as e:
            print(f"Error connecting to server {name}: {e}")
            # Re-raise to allow caller to handle
            raise

    async def _close_session(self, name: str):
        """Close a specific session by name."""
        if name in self.sessions:
            # We don't need to explicitly close the session as it's managed by exit_stack
            del self.sessions[name]

    async def cleanup(self, name: Optional[str] = None):
        """Clean up resources

        Args:
            name: Optional name of the session to clean up. Cleans all if None
        """
        if name:
            await self._close_session(name)
        else:
            # Clear the sessions dictionary
            self.sessions.clear()
            # Close all resources managed by the exit stack
            await self.exit_stack.aclose()
            # Create a new exit stack for potential future use
            self.exit_stack = AsyncExitStack()

    async def get_session(self, name: str) -> Optional[ClientSession]:
        """Get the ClientSession by name.
                Args:
                    name: name of the session

                Returns:
        ClientSession if found, None otherwise.
        """
        session_data = self.sessions.get(name)
        if session_data:
            return session_data.session
        return None
        
    async def cache_result(self, server_name: str, cache_type: str, key: str, data: Any) -> None:
        """Cache result from a server session.
        
        Args:
            server_name: Name of the server session
            cache_type: Type of cache (tools, prompts, resources, resource_templates)
            key: Cache key
            data: Data to cache
        """
        if not self.redis_service:
            return
            
        cache_key = f"mcp:{server_name}:{cache_type}:{key}"
        await self.redis_service.set(cache_key, data)
            
    async def get_cached_result(self, server_name: str, cache_type: str, key: str) -> Optional[Any]:
        """Get cached result from a server session.
        
        Args:
            server_name: Name of the server session
            cache_type: Type of cache (tools, prompts, resources, resource_templates)
            key: Cache key
            
        Returns:
            Cached data if found, None otherwise
        """
        if not self.redis_service:
            return None
            
        cache_key = f"mcp:{server_name}:{cache_type}:{key}"
        return await self.redis_service.get(cache_key)


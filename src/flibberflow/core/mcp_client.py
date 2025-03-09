from typing import Optional, Dict
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client


class SessionData:
    def __init__(self, session: ClientSession, exit_stack: AsyncExitStack, write, stdio):
        self.session = session
        self.exit_stack = exit_stack
        self.write = write
        self.stdio = stdio


class MCPClient:
    def __init__(self):
        self.sessions: Dict[str, SessionData] = {}

    async def connect_to_server(self, name: str, server_params: StdioServerParameters):
        """Connect to an MCP server

        Args:
            name: Name of the server, used as the key for the session dictionary.
            server_params: StdioServerParameters
        """
        exit_stack = AsyncExitStack()
        stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport
        session = await exit_stack.enter_async_context(ClientSession(stdio, write))

        init_result: types.InitializeResult = await session.initialize()

        # List available tools
        response = await session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

        self.sessions[name] = SessionData(session, exit_stack, write, stdio)

    async def cleanup(self, name: Optional[str] = None):
        """Clean up resources

        Args:
            name: Optional name of the session to clean up. Cleans all if None
        """
        if name:
            if name in self.sessions:
                await self.sessions[name].exit_stack.aclose()
                del self.sessions[name]
        else:
            for session_data in self.sessions.values():
                await session_data.exit_stack.aclose()
            self.sessions.clear()

    async def get_session(self, name: str) -> Optional[ClientSession]:
        """Get the ClientSession by name.

                Args:
                    name: name of the session

                Returns:
        ClientSession if found, None otherwise.
        """
        session_data = self.sessions.get(name)
        if session_
            return session_data.session
        return None


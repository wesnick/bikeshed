from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client


class MCPClient:
    def __init__(self):

        self.write = None
        self.stdio = None
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()

    async def connect_to_server(self, name: str, server_params: StdioServerParameters):
        """Connect to an MCP server

        Args:
            name: Name of the server
            server_params: StdioServerParameters
        """
        # is_python = server_script_path.endswith('.py')
        # is_js = server_script_path.endswith('.js')
        # if not (is_python or is_js):
        #     raise ValueError("Server script must be a .py or .js file")
        #
        # command = "python" if is_python else "node"
        # server_params = StdioServerParameters(
        #     command=command,
        #     args=[server_script_path],
        #     env=None
        # )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        init_result: types.InitializeResult = await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

import pytest
from unittest.mock import AsyncMock

from src.core.mcp_client import MCPClient
from src.core.cache import RedisService


@pytest.mark.asyncio
async def test_mcp_client_init():
    """Test that the MCP client initializes correctly"""
    redis_mock = AsyncMock(spec=RedisService)

    async with MCPClient() as client:
        assert client._initialized is True
        assert isinstance(client.sessions, dict)


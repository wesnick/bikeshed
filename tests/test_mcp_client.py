import pytest
from unittest.mock import AsyncMock, patch

from src.service.mcp_client import MCPClient
from src.service.cache import RedisService


@pytest.mark.asyncio
async def test_mcp_client_init():
    """Test that the MCP client initializes correctly"""
    redis_mock = AsyncMock(spec=RedisService)
    
    async with MCPClient(redis_service=redis_mock) as client:
        assert client._initialized is True
        assert isinstance(client.sessions, dict)


@pytest.mark.asyncio
@patch('src.service.mcp_client.MCPClient.build_manifest')
async def test_get_manifest(mock_build_manifest):
    """Test that get_manifest calls build_manifest when cache is empty"""
    redis_mock = AsyncMock(spec=RedisService)
    redis_mock.get.return_value = None
    mock_build_manifest.return_value = {"tools": []}
    
    async with MCPClient(redis_service=redis_mock) as client:
        manifest = await client.get_manifest()
        
        assert manifest == {"tools": []}
        mock_build_manifest.assert_called_once()

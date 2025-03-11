import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from click.testing import CliRunner

from src.cli import search_mcp


@pytest.mark.asyncio
async def test_search_mcp_command():
    """Test the search_mcp CLI command"""
    runner = CliRunner()
    
    # Create a mock that returns a regular value, not a coroutine
    mock_search = MagicMock()
    
    with patch('src.cli._search_mcp', mock_search):
        # Patch asyncio.run to avoid event loop issues
        with patch('asyncio.run'):
            result = runner.invoke(search_mcp, ["test_query", "--limit", "5"])
            
            assert result.exit_code == 0
            mock_search.assert_called_once_with("test_query", 5)

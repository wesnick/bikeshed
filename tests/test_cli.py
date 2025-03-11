import pytest
from unittest.mock import patch, AsyncMock
from click.testing import CliRunner

from src.cli import search_mcp


@pytest.mark.asyncio
async def test_search_mcp_command():
    """Test the search_mcp CLI command"""
    runner = CliRunner()
    
    with patch('src.cli._search_mcp') as mock_search:
        mock_search.return_value = AsyncMock()
        result = runner.invoke(search_mcp, ["test_query", "--limit", "5"])
        
        assert result.exit_code == 0
        mock_search.assert_called_once_with("test_query", 5)

from httpx import ASGITransport, AsyncClient
from typing import AsyncGenerator
import pytest

from src.main import app

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Create an async test client for FastAPI app
    """
    host, port = "127.0.0.1", 9000
    
    # Use the ASGI app with AsyncClient
    async with AsyncClient(transport=ASGITransport(app=app, client=(host, port)), base_url="http://test") as client:
        yield client

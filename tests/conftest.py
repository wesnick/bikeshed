import pytest
from httpx import AsyncClient
from typing import AsyncGenerator
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Create an async test client for FastAPI app
    """
    # Create a TestClient first to get ASGI app
    test_client = TestClient(app)
    
    # Use the ASGI app with AsyncClient
    async with AsyncClient(app=test_client.app, base_url="http://test") as client:
        yield client

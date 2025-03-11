import pytest
from httpx import AsyncClient
from typing import AsyncGenerator

from src.main import app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Create an async test client for FastAPI app
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

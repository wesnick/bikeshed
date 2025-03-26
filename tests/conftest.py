import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from psycopg import AsyncConnection

from src.main import app
from src.dependencies import get_settings


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Create an async test client for FastAPI app
    """
    host, port = "127.0.0.1", 9000
    
    # Use the ASGI app with AsyncClient
    async with AsyncClient(transport=ASGITransport(app=app, client=(host, port)), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def db_conn() -> AsyncGenerator[AsyncConnection, None]:
    """
    Provides a database connection for a test function.
    Ensures the connection is closed afterwards.
    """
    settings = get_settings()
    conn_str = f"postgres://{settings.postgres_user}:{settings.postgres_password}@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db_test}"
    conn = None
    try:
        conn = await AsyncConnection.connect(conn_str)
        yield conn
    finally:
        if conn:
            await conn.close()


@pytest_asyncio.fixture(scope="function")
async def db_conn_clean(db_conn: AsyncConnection) -> AsyncGenerator[AsyncConnection, None]:
    """
    Provides a database connection wrapped in a transaction that rolls back.
    Ensures test isolation.
    """
    async with db_conn.transaction():
        yield db_conn
        # Transaction automatically rolls back on exit unless committed
        # We don't commit, so it rolls back.

import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from psycopg import AsyncConnection

from src.main import app
from src.dependencies import settings


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
    Ensures test isolation by truncating tables within a transaction.
    """
    # List of tables managed by the repositories being tested
    tables_to_truncate = ["messages", "dialogs", "blobs", "tags", "stashes", "roots", "root_files", "entity_tags", "entity_stashes"] # Add other tables as needed

    async with db_conn.transaction():
        async with db_conn.cursor() as cur:
            for table in tables_to_truncate:
                # Use CASCADE if there are foreign key relationships
                await cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
        yield db_conn
        # Transaction automatically rolls back on exit unless committed
        # We don't commit, so it rolls back, ensuring cleanup even if truncate fails somehow.

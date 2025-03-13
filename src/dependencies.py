from typing import AsyncGenerator, Annotated

from fastapi import Depends
from markdown2 import markdown
from sqlalchemy.ext.asyncio import  AsyncSession

from src.service.database import async_session_factory
from src.service.cache import RedisService
from src.service.mcp_client import MCPClient
from src.config import get_config


settings = get_config()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session"""
    async with async_session_factory() as session:
        yield session

async def get_cache() -> AsyncGenerator[RedisService, None]:
    yield RedisService(redis_url=str(settings.redis_url))

async def get_mcp_client(cache: Annotated[RedisService, Depends(get_cache)]) -> AsyncGenerator[MCPClient, None]:
    async with MCPClient(redis_service=cache) as client:
        yield client


def markdown2html(text: str):
    return markdown(text, extras={
        'breaks': {'on_newline': True},
        'fenced-code-blocks': {},
        'highlightjs-lang': {},
    })

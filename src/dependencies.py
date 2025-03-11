from typing import Annotated

from fastapi import Depends
from markdown2 import markdown

from service.database import async_session_factory
from service.cache import RedisService
from service.mcp_client import MCPClient
from config import get_config

settings = get_config()

async def get_db():
    """Dependency for getting async database session"""
    async with async_session_factory() as session:
        yield session

async def get_cache():
    yield RedisService(redis_url=str(settings.redis_url))

async def get_mcp_client(cache: Annotated[RedisService, Depends(get_cache)]):
    async with MCPClient(redis_service=cache) as client:
        yield client


def markdown2html(text: str):
    return markdown(text, extras={
        'breaks': {'on_newline': True},
        'fenced-code-blocks': {},
        'highlightjs-lang': {},
    })

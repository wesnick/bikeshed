from typing import AsyncGenerator, Annotated

from fastapi import Depends
from fastapi.templating import Jinja2Templates
from fasthx import Jinja
from markdown2 import markdown
from sqlalchemy.ext.asyncio import  AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.service.cache import RedisService
from src.service.mcp_client import MCPClient
from src.repository.session import SessionRepository
from src.repository.message import MessageRepository
from src.service.workflow import WorkflowService
from src.config import get_config


settings = get_config()

# Create engine with the Base metadata from models
engine = create_async_engine(
    str(settings.database_url),
    echo=settings.log_level == "DEBUG",
)

async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session"""
    async with async_session_factory() as session:
        yield session

async def get_cache() -> AsyncGenerator[RedisService, None]:
    yield RedisService(redis_url=str(settings.redis_url))

# Create the singleton instance
mcp_client = MCPClient()
_mcp_client_initialized = False

async def get_mcp_client() -> AsyncGenerator[MCPClient, None]:
    """Dependency for getting the singleton MCPClient instance"""
    global _mcp_client_initialized
    
    # Only enter the context manager once
    if not _mcp_client_initialized:
        await mcp_client.__aenter__()
        _mcp_client_initialized = True
    
    # Simply yield the singleton instance
    yield mcp_client

def markdown2html(text: str):
    from src.main import logger
    logger.debug(f"Converting markdown to html: {text}")
    return markdown(text, extras={
        'breaks': {'on_newline': True},
        'fenced-code-blocks': {},
        'highlightjs-lang': {},
    })


def get_jinja() -> Jinja:
    jinja_templates = Jinja2Templates(directory="templates")
    jinja_templates.env.filters['markdown2html'] = markdown2html

    return Jinja(jinja_templates)

async def get_workflow_service() -> AsyncGenerator[WorkflowService, None]:
    """Dependency for getting the workflow service"""
    session_repo = SessionRepository()
    message_repo = MessageRepository()
    yield WorkflowService(session_repo, message_repo)

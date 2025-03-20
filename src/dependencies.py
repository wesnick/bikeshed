from typing import AsyncGenerator, Annotated
import asyncio

from fastapi.templating import Jinja2Templates
from fasthx import Jinja
from markdown2 import markdown
from sqlalchemy.ext.asyncio import  AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.service.cache import RedisService
from src.service.mcp_client import MCPClient
from src.config import get_config
from src.core.registry import Registry
from src.core.registry_loader import RegistryBuilder
from src.core.workflow.service import WorkflowService

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

# Create the singleton Registry instance
registry = Registry()
_registry_initialized = False
_registry_lock = asyncio.Lock()

async def get_registry() -> AsyncGenerator[Registry, None]:
    """Dependency for getting the singleton Registry instance"""
    global _registry_initialized
    
    # Use a lock to prevent multiple initialization attempts
    async with _registry_lock:
        if not _registry_initialized:
            builder = RegistryBuilder(registry)
            await builder.build()
            _registry_initialized = True
    
    yield registry

# Create the singleton WorkflowService instance
_workflow_service = None
_workflow_service_lock = asyncio.Lock()

async def get_workflow_service() -> AsyncGenerator[WorkflowService, None]:
    """Dependency for getting the singleton WorkflowService instance"""
    global _workflow_service
    
    # Use a lock to prevent multiple initialization attempts
    async with _workflow_service_lock:
        if _workflow_service is None:
            # Get the registry first
            registry_instance = None
            async for reg in get_registry():
                registry_instance = reg
                break
                
            if not registry_instance:
                raise RuntimeError("Failed to get registry instance")

            # Create the WorkflowService instance with the actual registry
            _workflow_service = WorkflowService(
                async_session_factory,
                registry_instance,
                None # @TODO
            )
    
    yield _workflow_service



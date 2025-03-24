from typing import AsyncGenerator
import asyncio
import json

from arq.connections import ArqRedis, create_pool, RedisSettings
from fastapi.templating import Jinja2Templates
from fasthx import Jinja
from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncConnection
from psycopg.types.json import set_json_dumps
from pydantic import BaseModel

from src.service.cache import RedisService
from src.service.llm import FakerCompletionService, LiteLLMCompletionService, ChainedCompletionService
from src.service.mcp_client import MCPClient
from src.service.broadcast import BroadcastService
from src.config import get_config
from src.core.registry import Registry
from src.core.registry_loader import RegistryBuilder
from src.core.workflow.service import WorkflowService

settings = get_config()

# Create a connection pool for database access
db_pool = AsyncConnectionPool(
    str(settings.database_url),
    min_size=5,
    max_size=20,
    open=False
)

def pydantic_json_dumps(obj):
    if isinstance(obj, BaseModel):
        return obj.model_dump_json()
    else:
        return json.dumps(obj)

set_json_dumps(pydantic_json_dumps)

async def get_db() -> AsyncGenerator[AsyncConnection, None]:
    """Dependency for getting async database connection"""
    async with db_pool.connection() as conn:
        yield conn

async def get_cache() -> AsyncGenerator[RedisService, None]:
    yield RedisService(redis_url=str(settings.redis_url))

async def get_arq_redis() -> AsyncGenerator[ArqRedis, None]:
    """Dependency for getting ARQ Redis connection"""
    redis = await create_pool(RedisSettings.from_dsn(str(settings.redis_url)))
    try:
        yield redis
    finally:
        await redis.close()


def get_jinja() -> Jinja:
    from src.jinja_extensions import markdown2html, format_file_size, get_file_icon
    
    jinja_templates = Jinja2Templates(directory="templates")
    jinja_templates.env.filters['markdown2html'] = markdown2html
    jinja_templates.env.filters['format_file_size'] = format_file_size
    jinja_templates.env.filters['file_icon'] = get_file_icon

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

# Create the singleton BroadcastService instance
broadcast_service = BroadcastService(redis_url=str(settings.redis_url))

async def get_remote_broadcast_service() -> AsyncGenerator[BroadcastService, None]:
    """Dependency for getting the singleton BroadcastService instance"""
    global broadcast_service

    yield broadcast_service

async def get_broadcast_service() -> AsyncGenerator[BroadcastService, None]:
    """Dependency for getting the singleton BroadcastService instance"""
    global broadcast_service

    await broadcast_service.initialize_redis()

    yield broadcast_service

# Create the singleton WorkflowService instance
_workflow_service = None
_workflow_service_lock = asyncio.Lock()


async def get_completion_service() -> AsyncGenerator[ChainedCompletionService, None]:
    """Dependency for getting a CompletionService instance"""
    completion_service = ChainedCompletionService([
        FakerCompletionService(broadcast_service=broadcast_service),
        LiteLLMCompletionService(broadcast_service=broadcast_service),
    ])

    yield completion_service

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

            if not registry_instance:
                raise RuntimeError("Failed to get registry instance")

            completion_service = None
            async for cs in get_completion_service():
                completion_service = cs

            # Create the WorkflowService instance with the actual registry
            _workflow_service = WorkflowService(
                get_db=get_db,
                registry=registry_instance,
                completion_service=completion_service,
                broadcast_service=broadcast_service
            )
    
    yield _workflow_service



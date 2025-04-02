from functools import lru_cache
from typing import AsyncGenerator
import asyncio
import json

from arq.connections import ArqRedis, create_pool, RedisSettings
from fastapi import Depends
from fastapi.templating import Jinja2Templates
from fasthx import Jinja
from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncConnection
from psycopg.types.json import set_json_dumps # Re-add
from pydantic import BaseModel

from src.service.cache import RedisService
# Add this import
from src.service.user_state import UserStateService
from src.service.llm import FakerCompletionService, LiteLLMCompletionService, ChainedCompletionService
from src.service.mcp_client import MCPClient
from src.service.broadcast import BroadcastService
from src.config import get_config
from src.core.registry import Registry
from src.core.registry_loader import RegistryBuilder


settings = get_config()

# Create a connection pool for database access
db_pool = AsyncConnectionPool(
    str(settings.database_url),
    min_size=5,
    max_size=20,
    open=False
)

# Re-add pydantic_json_dumps function and set_json_dumps call
def pydantic_json_dumps(obj):
    """Custom JSON serializer for Pydantic models and other types."""
    if isinstance(obj, BaseModel):
        # Use Pydantic's recommended way to serialize, handling complex types
        return obj.model_dump_json()
    # Let psycopg handle standard types or raise an error for unsupported ones
    # We might need to add handlers for datetime etc. if psycopg doesn't cover them by default
    # For now, rely on Pydantic's serialization within model_dump_json
    return json.dumps(obj) # Fallback, might need refinement

set_json_dumps(pydantic_json_dumps)


async def get_db() -> AsyncGenerator[AsyncConnection, None]:
    """Dependency for getting async database connection"""
    async with db_pool.connection() as conn:
        yield conn

async def get_cache() -> AsyncGenerator[RedisService, None]:
    yield RedisService(redis_url=str(settings.redis_url))

# Add this new dependency function
async def get_user_state_service(cache: RedisService = Depends(get_cache)) -> UserStateService:
    """Dependency for getting the UserStateService instance."""
    # Note: This creates a new instance per request, but it operates on the
    # same underlying Redis key, effectively acting as a singleton state manager.
    return UserStateService(redis_service=cache)

async def get_arq_redis() -> AsyncGenerator[ArqRedis, None]:
    """Dependency for getting ARQ Redis connection"""
    redis = await create_pool(RedisSettings.from_dsn(str(settings.redis_url)))
    try:
        yield redis
    finally:
        await redis.close()


@lru_cache
def get_jinja(directory: str = "templates") -> Jinja:
    from src.jinja_extensions import markdown2html, quote_plus, format_file_size, get_file_icon, format_text_length, format_cost_per_million

    jinja_templates = Jinja2Templates(directory=directory)
    jinja_templates.env.filters['markdown2html'] = markdown2html
    jinja_templates.env.filters['format_file_size'] = format_file_size
    jinja_templates.env.filters['file_icon'] = get_file_icon
    jinja_templates.env.filters['format_text_length'] = format_text_length
    jinja_templates.env.filters['format_cost_per_million'] = format_cost_per_million
    jinja_templates.env.filters['quote_plus'] = quote_plus


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

async def get_workflow_service():
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
            from src.core.workflow.service import WorkflowService
            _workflow_service = WorkflowService(
                get_db=get_db,
                registry=registry_instance,
                completion_service=completion_service,
                broadcast_service=broadcast_service
            )

    yield _workflow_service

async def enqueue_job(job_name: str, **kwargs):
    """
    Enqueue a message processing job with ARQ

    Args:
        job_name: The name of the job to enqueue
        kwargs: Keyword arguments to pass to the job

    Returns:
        The job ID as a string
    """
    async for arq_redis in get_arq_redis():
        job = await arq_redis.enqueue_job(job_name, **kwargs)
        return job.job_id

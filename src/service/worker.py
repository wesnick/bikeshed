import asyncio
from typing import Any, Dict, Optional, AsyncGenerator
from arq import create_pool
from arq.connections import RedisSettings, ArqRedis
from psycopg import AsyncConnection
import uuid

from src.config import get_config
from src.models.models import Session, Message
from src.service.llm.base import CompletionService
from src.service.broadcast import BroadcastService
from src.repository.message import MessageRepository
from src.dependencies import get_db, get_completion_service, get_broadcast_service

settings = get_config()
message_repository = MessageRepository()

async def process_message_job(ctx: Dict[str, Any], session_id: uuid.UUID) -> Dict[str, Any]:
    """
    ARQ worker function to process a message asynchronously.
    
    Args:
        ctx: ARQ context
        session_id: UUID of the session to process
    
    Returns:
        Dict with job result information
    """
    # Get the session from the database
    async for db in get_db():
        # Fetch the session from the database
        from src.repository.session import SessionRepository
        session_repo = SessionRepository()
        session = await session_repo.get_by_id(db, session_id)
        
        if not session:
            return {"success": False, "error": f"Session {session_id} not found"}


    # Get services
    completion_service: CompletionService = await anext(get_completion_service())
    broadcast_service: BroadcastService = await anext(get_broadcast_service())

    try:
        # Process with Completion service
        result_message = await completion_service.complete(
            session,
            broadcast=None
        )

        # Update final message in database
        async for db in get_db():
            await message_repository.update(db, result_message.id, result_message.model_dump(exclude={"children", "parent"}))
            break  # We only need one connection

        # Notify all clients to update the session component
        await broadcast_service.broadcast("session_update", "")
        
        return {
            "success": True, 
            "message_id": str(result_message.id),
            "session_id": str(session_id)
        }
    
    except Exception as e:
        # Log the error and return failure
        from src.service.logging import logger
        logger.error(f"Error processing message for session {session_id}: {str(e)}")
        
        # Notify clients about the error
        await broadcast_service.broadcast("session_error", {
            "session_id": str(session_id),
            "error": str(e)
        })
        
        return {"success": False, "error": str(e), "session_id": str(session_id)}

class WorkerSettings:
    """ARQ Worker Settings"""
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
    functions = [process_message_job]
    job_timeout = 300  # 5 minutes
    max_jobs = 10
    poll_delay = 0.5  # seconds


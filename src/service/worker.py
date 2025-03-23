from typing import Any, Dict
from arq.connections import RedisSettings
import uuid

from src.config import get_config
from src.service.llm.base import CompletionService
from src.service.broadcast import BroadcastService
from src.repository.message import MessageRepository
from src.dependencies import get_completion_service, get_remote_broadcast_service, db_pool

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
    from src.repository.session import SessionRepository
    session_repo = SessionRepository()
    
    async with ctx['db_pool'].connection() as db:
        # Fetch the session from the database
        session = await session_repo.get_with_messages(db, session_id)
        
        if not session:
            return {"success": False, "error": f"Session {session_id} not found"}


    # Get services
    completion_service: CompletionService = await anext(get_completion_service())
    broadcast_service: BroadcastService = ctx['broadcast_service']

    try:
        # Process with Completion service
        result_message = await completion_service.complete(
            session,
            broadcast=None
        )

        # Update final message in database
        async with db_pool.connection() as db:
            await message_repository.update(db, result_message.id, result_message.model_dump(exclude={"children", "parent"}))

        # Notify all clients to update the session component
        await broadcast_service.broadcast("session_update", {
            "session_id": str(session_id),
            "message_id": str(result_message.id)
        })
        
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
    
    # Lifecycle hooks
    @staticmethod
    async def on_startup(ctx):
        """Open database pool on worker startup"""
        await db_pool.open()
        ctx['db_pool'] = db_pool
        
        # Initialize broadcast service for the worker
        broadcast_service = await anext(get_remote_broadcast_service())
        ctx['broadcast_service'] = broadcast_service
    
    @staticmethod
    async def on_shutdown(ctx):
        """Close database pool and broadcast service on worker shutdown"""
        await db_pool.close()
        
        # Clean up broadcast service if it was initialized
        if 'broadcast_service' in ctx:
            await ctx['broadcast_service'].shutdown("Worker shutting down")


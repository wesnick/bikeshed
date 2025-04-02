from typing import Any, Dict
from arq.connections import RedisSettings
import uuid

from src.config import get_config
from src.service.llm.base import CompletionService
from src.service.broadcast import BroadcastService
from src.components.repositories import message_repository
from src.dependencies import get_completion_service, get_remote_broadcast_service, db_pool
from src.service.logging import logger

settings = get_config()

async def dialog_run_workflow_job(ctx: Dict[str, Any], dialog_id: uuid.UUID) -> Dict[str, Any]:
    """
    ARQ worker function to run a workflow asynchronously.

    Args:
        ctx: ARQ context
        dialog_id: UUID of the dialog to process

    Returns:
        Dict with job result information
    """
    from src.core.workflow.service import WorkflowService
    from src.dependencies import get_workflow_service
    from src.service.logging import logger

    # Get services
    workflow_service: WorkflowService = await anext(get_workflow_service())

    try:
        # Get the dialog from the database
        dialog = await workflow_service.get_dialog(dialog_id)

        if not dialog:
            return {"success": False, "error": f"Dialog {dialog_id} not found"}

        # Run the workflow
        await workflow_service.run_workflow(dialog)

        return {
            "success": True,
            "dialog_id": str(dialog_id)
        }

    except Exception as e:
        # Log the error and return failure
        logger.error(f"Error running workflow for dialog {dialog_id}: {str(e)}")

        return {"success": False, "error": str(e), "dialog_id": str(dialog_id)}


async def process_message_job(ctx: Dict[str, Any], dialog_id: uuid.UUID) -> Dict[str, Any]:
    """
    ARQ worker function to process a message asynchronously.

    Args:
        ctx: ARQ context
        dialog_id: UUID of the dialog to process

    Returns:
        Dict with job result information
    """

    # Get the dialog from the database
    from src.components.dialog.repository import DialogRepository
    dialog_repo = DialogRepository()

    async with ctx['db_pool'].connection() as db:
        # Fetch the dialog from the database
        dialog = await dialog_repo.get_with_messages(db, dialog_id)

        if not dialog:
            return {"success": False, "error": f"Dialog {dialog_id} not found"}


    # Get services
    completion_service: CompletionService = await anext(get_completion_service())
    broadcast_service: BroadcastService = ctx['broadcast_service']

    try:
        # Process with Completion service
        result_message = await completion_service.complete(
            dialog,
            broadcast=None
        )

        # Update final message in database
        async with db_pool.connection() as db:
            await message_repository.upsert(db, result_message, ['id'])

        # Notify all clients to update the dialog component
        await broadcast_service.broadcast("dialog.update", str(dialog.id))

        return {
            "success": True,
            "message_id": str(result_message.id),
            "dialog_id": str(dialog_id)
        }

    except Exception as e:
        # Log the error and return failure
        from src.service.logging import logger
        logger.error(f"Error processing message for dialog {dialog_id}: {str(e)}")

        # Notify clients about the error
        await broadcast_service.broadcast("dialog_error", {
            "dialog_id": str(dialog_id),
            "error": str(e)
        })

        return {"success": False, "error": str(e), "dialog_id": str(dialog_id)}

async def process_root(ctx: Dict[str, Any], directory_path: str):
    from src.core.roots.scanner import FileScanner

    async with db_pool.connection() as conn:
        scanner = FileScanner(conn)
        try:
            await scanner.create_root_and_scan(directory_path)
            logger.info(f"[bold green]Successfully scanned directory '{directory_path}'[/bold green]")
        except Exception as e:
            logger.error(f"[bold red]Error:[/bold red] {str(e)}")
        finally:
            await db_pool.close()


class WorkerSettings:
    """ARQ Worker Settings"""
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
    functions = [
        process_message_job,
        dialog_run_workflow_job,
        process_root
    ]
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
        # We actually don't need to close the pool, in fact, it breaks watch
        # await db_pool.close()



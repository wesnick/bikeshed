from contextlib import asynccontextmanager
import uvicorn
import asyncio
import uuid

from fastapi import FastAPI, Request, Depends
from psycopg import AsyncConnection
from starlette.staticfiles import StaticFiles
from starlette.responses import Response
from sse_starlette.sse import EventSourceResponse


from src.core.registry import Registry
from src.service.broadcast import BroadcastService
from src.service.logging import logger, setup_logging
from src.service.shutdown_helper import shutdown_manager
from src.http.middleware import HTMXRedirectMiddleware
from src.dependencies import get_db, get_jinja, get_registry, get_broadcast_service, get_root_repository
from src.routes import api_router
# Import the new router
from src.routes import root_management as root_management_router
from src.repository import session_repository


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()

    # Store the broadcast service in app state
    from src.dependencies import broadcast_service, db_pool
    await db_pool.open()
    app.state.broadcast_service = broadcast_service

    # Use the shutdown manager's event
    app.state.shutdown_event = shutdown_manager.shutdown_event

    # Register broadcast service shutdown with the shutdown manager
    shutdown_manager.register_cleanup_hook(broadcast_service.shutdown)

    shutdown_manager.register_cleanup_hook(db_pool.close)

    # Set up signal handlers using the shutdown manager
    shutdown_manager.install_signal_handlers()

    # Boot the registry
    async for registry in get_registry():
        app.state.registry = registry
        # Register registry cleanup with shutdown manager
        shutdown_manager.register_cleanup_hook(registry.stop_watching)
        # Start watching the directory and store the task
        # @TODO
        # app.state.watcher_task = asyncio.create_task(
        #     registry.watch_directory('/home/wes/Downloads')
        # )

    yield

    logger.info("Application shutting down via lifespan exit")
    await shutdown_manager.trigger_shutdown()


app = FastAPI(title="BikeShed", lifespan=lifespan)
app.add_middleware(HTMXRedirectMiddleware)

# static asset mount
app.mount("/build", StaticFiles(directory="build"), name="build")

jinja = get_jinja()
# Include API routes
app.include_router(api_router)
app.include_router(root_management_router.router, prefix="/root") # Add prefix


@app.get("/")
@jinja.page('index.html.j2')
def index(response: Response) -> dict:
    """This route serves the index.html template with all components initialized."""
    # Return empty data to ensure all components are properly initialized
    response.headers['HX-Trigger-After-Swap'] = 'drawer.updated'
    return {}

@app.get("/settings")
@jinja.hx('components/settings.html.j2')
async def settings_component() -> dict:
    """This route serves just the settings component for htmx requests."""
    return {}


@app.get("/components/left-sidebar")
@jinja.hx('components/left_sidebar.html.j2')
async def left_sidebar_component(db: AsyncConnection = Depends(get_db), registry: Registry = Depends(get_registry)) -> dict:
    """This route serves the left sidebar component for htmx requests."""
    sessions = await session_repository.get_recent_sessions(db)

    session_templates = registry.session_templates

    return {
        "flows": [],
        "sessions": sessions,
        "tools": [],
        "prompts": [],
        "session_templates": session_templates,
    }


class PathBasedTemplateSelector:

    @staticmethod
    def parse_request_parts(request: Request):
        from urllib.parse import urlparse
        return urlparse(request.headers.get('hx-current-url')).path.strip('/').split('/')

    def get_component(self, request: Request, error: Exception | None) -> str:
        from urllib.parse import urlparse
        url_parts = urlparse(request.headers.get('hx-current-url')).path.strip('/').split('/')

        from src.service.logging import logger
        logger.warning(f"Url parts: {url_parts}")

        if len(url_parts) < 2:
            return 'components/drawer/empty.html.j2'

        # switch statement
        match url_parts[0]:
            case 'session':
                # test if uuid
                try:
                    uuid.UUID(url_parts[1])
                    return 'components/drawer/session_context.html.j2'
                except ValueError:
                    pass

        return 'components/drawer/empty.html.j2'

@app.get("/components/drawer")
@jinja.hx(PathBasedTemplateSelector())
async def right_drawer_component(request: Request, db: AsyncConnection = Depends(get_db)):
    """This route serves the right drawer component for htmx requests."""
    url_parts = PathBasedTemplateSelector.parse_request_parts(request)

    match url_parts:
        case ['session', session_id]:
            from src.repository.session import SessionRepository
            session_repo = SessionRepository()
            session = await session_repo.get_by_id(db, session_id)
            return {
                'entity_id': session.id,
                'entity_type': 'session'
            }

            from src.service.logging import logger
            logger.warning(f"session_id: {session.id}")

    return {
        'data': f"Url parts: {url_parts} \n\n"
    }


@app.get("/kitchen-sink")
@jinja.hx('components/kitchen_sink.html.j2', no_data=True)
async def kitchen_sink_component() -> None:
    """This route serves the kitchen sink component for htmx requests."""


@app.get("/sse")
async def sse(request: Request, broadcast_service: BroadcastService = Depends(get_broadcast_service)):
    """SSE endpoint for all component updates"""
    client_id = str(uuid.uuid4())
    queue = broadcast_service.register_client(client_id)

    async def event_generator():
        # Send initial connection message
        yield {
            "event": "connected",
            "data": "Connected to SSE stream"
        }

        try:
            while True:
                # Wait for the next event
                event = await queue.get()
                if event is None:  # None is our signal to stop
                    logger.info(f"Closing SSE connection for client {client_id}")
                    break

                # Yield the event for SSE
                yield event

        except asyncio.CancelledError:
            logger.warning(f"SSE connection for client {client_id} was cancelled")
            raise  # Re-raise to ensure proper cleanup
        except Exception as e:
            logger.error(f"Error in SSE connection for client {client_id}: {e}")
            raise
        finally:
            # Make sure we unregister on any exception
            broadcast_service.unregister_client(client_id)

    return EventSourceResponse(event_generator())


if __name__ == "__main__":
    # Configure uvicorn to use our logging
    uvicorn.run(app, host="0.0.0.0", port=8000)

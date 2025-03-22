from contextlib import asynccontextmanager
from random import randint
import uvicorn
import asyncio
import json
import uuid
import signal
import threading

from fastapi import FastAPI, Request, Depends, BackgroundTasks
from psycopg import AsyncConnection
from starlette.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from src.core.registry import Registry
from src.service.broadcast import BroadcastService
from src.types import MessageCreate
from src.models import Message
from src.service.logging import logger, setup_logging
from src.service.mcp_client import MCPClient
from src.http.middleware import HTMXRedirectMiddleware
from src.dependencies import get_db, get_jinja, get_registry, get_broadcast_service
from src.routes import api_router
from src.repository import session_repository

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    
    # Store the broadcast service in app state
    from src.dependencies import broadcast_service
    app.state.broadcast_service = broadcast_service

    # Create a shutdown event
    app.state.shutdown_event = asyncio.Event()
    
    # Set up signal handlers
    setup_signal_handlers()

    # Boot the registry
    async for registry in get_registry():
        app.state.registry = registry
        # Start watching the directory and store the task
        # @TODO
        # app.state.watcher_task = asyncio.create_task(
        #     registry.watch_directory('/home/wes/Downloads')
        # )

    # Create a task to monitor the shutdown event
    shutdown_monitor_task = asyncio.create_task(monitor_shutdown_event(app))
    
    try:
        yield
    finally:
        logger.info("Application shutting down via lifespan exit")
        
        # Cancel the shutdown monitor task if it's still running
        if not shutdown_monitor_task.done():
            shutdown_monitor_task.cancel()
            try:
                await shutdown_monitor_task
            except asyncio.CancelledError:
                pass
        
        # Perform cleanup
        await app.state.broadcast_service.shutdown("Server is shutting down for maintenance")
        await app.state.registry.stop_watching()

async def monitor_shutdown_event(app):
    """Monitor the shutdown event and initiate graceful shutdown when triggered"""
    try:
        await app.state.shutdown_event.wait()
        logger.info("Shutdown event detected, initiating graceful shutdown")
        # Notify clients about the shutdown
        await app.state.broadcast_service.shutdown("Server is shutting down due to signal")
    except asyncio.CancelledError:
        # Task was cancelled during normal shutdown
        pass
    except Exception as e:
        logger.error(f"Error in shutdown monitor: {e}")

app = FastAPI(title="BikeShed", lifespan=lifespan)
app.add_middleware(HTMXRedirectMiddleware)

# static asset mount
app.mount("/build", StaticFiles(directory="build"), name="build")

jinja = get_jinja()

# Include API routes
app.include_router(api_router)

# Store active session tasks
ACTIVE_SESSIONS = {}
# Store clients connected to SSE
SSE_CLIENTS = set()

# Set up signal handlers for graceful shutdown
def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown"""
    # Store original signal handlers to chain to them
    original_term_handler = signal.getsignal(signal.SIGTERM)
    original_int_handler = signal.getsignal(signal.SIGINT)
    
    # Flag to prevent multiple shutdown attempts
    shutdown_initiated = False
    
    # Create a shutdown event to signal the lifespan context manager
    shutdown_event = asyncio.Event()
    app.state.shutdown_event = shutdown_event

    def signal_handler(sig, frame):
        nonlocal shutdown_initiated
        
        # Prevent multiple shutdown attempts
        if shutdown_initiated:
            logger.warning(f"Shutdown already in progress, ignoring signal {sig}")
            return
            
        shutdown_initiated = True
        logger.warning(f"Received signal {sig}, initiating graceful shutdown...")

        # Set the shutdown event - this will be checked in the lifespan context
        # and will trigger a clean shutdown
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(lambda: asyncio.create_task(app.state.shutdown_event.set()))
            logger.info(f"Shutdown event set for signal {sig}")
        except RuntimeError:
            # No event loop running in this thread
            logger.warning(f"No event loop running, can't set shutdown event for signal {sig}")

        # Chain to the original handler directly
        # The clean shutdown will happen via the lifespan context
        if sig == signal.SIGTERM and original_term_handler and callable(original_term_handler):
            if original_term_handler != signal.SIG_DFL and original_term_handler != signal.SIG_IGN:
                original_term_handler(sig, frame)
        elif sig == signal.SIGINT and original_int_handler and callable(original_int_handler):
            if original_int_handler != signal.SIG_DFL and original_int_handler != signal.SIG_IGN:
                original_int_handler(sig, frame)

    # Register our handlers
    signal.signal(signal.SIGTERM, signal_handler)  # Signal 15, sent by uvicorn --reload
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C

    logger.info("Signal handlers registered for graceful shutdown")

# This function is replaced by BroadcastService.shutdown

# Signal handlers are now set up in the lifespan context manager


@app.get("/")
@jinja.page('index.html.j2')
def index() -> dict:
    """This route serves the index.html template with all components initialized."""
    # Return empty data to ensure all components are properly initialized
    return {}

@app.get("/settings")
@jinja.hx('components/settings.html.j2')
async def settings_component() -> dict:
    """This route serves just the settings component for htmx requests."""
    return {}


@app.get("/session/{session_id}")
@jinja.hx('components/session.html.j2')
async def session_component() -> dict:
    """This route serves just the chat component for htmx requests."""
    return {"messages": []}

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

@app.get("/components/right-drawer")
@jinja.hx('components/right_drawer.html.j2', no_data=True)
async def right_drawer_component() -> None:
    """This route serves the right drawer component for htmx requests."""

@app.get("/components/navbar-notifications")
@jinja.hx('components/navbar-notifications.html.j2')
async def navbar_component():
    """This route serves the navbar component for htmx requests."""
    return {
        'total_running': 0,
        'total_waiting': 0
    }

@app.get("/prompt/{prompt_id}")
@jinja.hx('components/prompt_form.html.j2')
async def prompt_form(request: Request, prompt_id: str) -> dict:
    """This route serves a form for a specific prompt."""
    # Split the prompt_id into server_name and prompt_name
    parts = prompt_id.split('.')
    if len(parts) != 2:
        return {"error": "Invalid prompt ID format"}

    server_name, prompt_name = parts

    # Get the MCP client from app state
    mcp_client: MCPClient = request.app.state.mcp_client

    # Get the manifest to find the prompt
    manifest = await mcp_client.get_manifest()

    # Find the prompt in the manifest
    prompt = manifest.get('prompts', {}).get(prompt_id)
    if not prompt:
        return {"error": f"Prompt {prompt_id} not found"}

        # Return the prompt data for rendering
    return {
        "prompt": prompt,
        "prompt_id": prompt_id
    }


@app.post("/prompt/{prompt_id}/interpolate")
@jinja.hx('components/session_form.html.j2')
async def interpolate_prompt(request: Request, prompt_id: str) -> dict:
    """Interpolate a prompt with the provided arguments and return the session form."""
    # Split the prompt_id into server_name and prompt_name
    parts = prompt_id.split('.')
    if len(parts) != 2:
        return {"error": "Invalid prompt ID format"}

    server_name, prompt_name = parts

    # Get the MCP client from app state
    mcp_client: MCPClient = request.app.state.mcp_client

    # Get the manifest to find the prompt
    manifest = await mcp_client.get_manifest()

    # Find the prompt in the manifest
    prompt = manifest.get('prompts', {}).get(prompt_id)
    if not prompt:
        return {"error": f"Prompt {prompt_id} not found"}

        # Parse the form data
    form_data = await request.form()

    # Get the session for this server
    session = await mcp_client.get_session(server_name)
    if not session:
        return {"error": f"Server {server_name} not connected"}

    try:
        # Call the interpolate_prompt method
        args = {k: v for k, v in form_data.items()}
        interpolated_text = await session.get_prompt(prompt_name, args)

        # Return the session form with the interpolated text
        return {"default_message": interpolated_text}
    except Exception as e:
        return {"error": f"Error interpolating prompt: {str(e)}"}

@app.get("/tool/{tool_id}")
@jinja.hx('components/tool_form.html.j2')
async def tool_form(request: Request, tool_id: str) -> dict:
    """This route serves a dynamic form for a specific tool."""
    # Split the tool_id into server_name and tool_name
    parts = tool_id.split('.')
    if len(parts) != 2:
        return {"error": "Invalid tool ID format"}

    server_name, tool_name = parts

    # Get the MCP client from app state
    mcp_client: MCPClient = request.app.state.mcp_client

    # Get the manifest to find the tool
    manifest = await mcp_client.get_manifest()

    # Find the tool in the manifest
    tool = manifest.get('tools', {}).get(tool_id)
    if not tool:
        return {"error": f"Tool {tool_id} not found"}

    # Create a dynamic form from the tool's input schema
    from models.form_models import DynamicForm

    form = DynamicForm.from_json_schema(
        schema=tool['schema'],
        form_id=f"tool-form-{tool_id.replace('.', '-')}",
        title=f"Tool: {tool['name']}",
        description=tool['description'],
        submit_label="Execute Tool"
    )

    # Return the form data for rendering
    return {
        "tool": tool,
        "tool_id": tool_id,
        "form": form.to_dict()
    }

@app.post("/tool/{tool_id}/execute")
async def execute_tool(
    request: Request,
    tool_id: str,
):
    """Execute a tool with the provided parameters."""
    # Split the tool_id into server_name and tool_name
    parts = tool_id.split('.')
    if len(parts) != 2:
        return {"error": "Invalid tool ID format"}

    server_name, tool_name = parts

    # Get the MCP client from app state
    mcp_client: MCPClient = request.app.state.mcp_client

    # Get the manifest to find the tool
    manifest = await mcp_client.get_manifest()

    # Get the session for this server
    session = await mcp_client.get_session(server_name)
    if not session:
        return {"error": f"Server {server_name} not connected"}

    # Parse the form data
    form_data = await request.form()

    # Convert form data to a dictionary for the tool
    tool_params = dict(form_data)

    logger.info(f"Executing tool: {tool_id} with params: {tool_params}")

    # @TODO: refactor with json-form htmx plugin
    # Cast data back to types it is expecting
    tool_schema = manifest['tools'][tool_id]['schema']
    for key, value in tool_params.items():
        if key in tool_schema['properties'] and isinstance(value, str):
            prop_type = tool_schema['properties'][key]['type']
            if prop_type == 'integer':
                if value == '':
                    value = 0
                tool_params[key] = int(value)
            elif prop_type == 'number':
                if value == '':
                    value = 0
                tool_params[key] = float(value)
            elif prop_type == 'boolean':
                tool_params[key] = (value.lower() == 'true' or value.lower() == 'on')


    # Process in background (non-blocking)
    asyncio.create_task(process_tool_execution(tool_id, tool_name, session, tool_params))

    # Return empty response as we'll update via SSE
    return ""

async def process_tool_execution(tool_id: str, tool_name: str, session, params: dict):
    """Process the tool execution and send response via SSE."""
    # Add user message to the database
    user_message_data = {
        "role": "user",
        "content": f"Executing tool: {tool_id} with parameters: {params}",
        "model": None,
        "extra": {"tool_id": tool_id, "params": params}
    }

    # Notify all clients to update the session component
    from src.dependencies import broadcast_service
    await broadcast_service.broadcast("session_update", "update")

    try:
        from mcp import ClientSession
        session: ClientSession

        # Execute the tool
        result = await session.call_tool(tool_name, params)

        # Add system response to the database
        system_response_data = {
            "role": "assistant",
            "content": f"Tool execution result: {result.content}",
            "model": None,
            "extra": {"tool_id": tool_id, "result": result.content}
        }
    except Exception as e:
        # Handle errors
        system_response_data = {
            "role": "assistant",
            "content": f"Error executing tool: {str(e)}",
            "model": None,
            "extra": {"tool_id": tool_id, "error": str(e)}
        }

    # Notify all clients to update the session component again
    await broadcast_service.broadcast("session_update", "update")

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

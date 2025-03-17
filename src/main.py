from contextlib import asynccontextmanager
from random import randint
import uvicorn
import asyncio
import json
import uuid
import signal
import threading

from fastapi import FastAPI, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from src.core.registry_loader import RegistryLoader
from src.types import MessageCreate
from src.models import Message
from src.service.logging import logger, setup_logging
from src.service.mcp_client import MCPClient
from src.http.middleware import HTMXRedirectMiddleware
from src.dependencies import get_db, get_jinja, get_mcp_client
from src.routes import api_router
from src.repository import session_repository

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()

    loader = RegistryLoader()
    app.state.registry = await loader.load()

    yield

    # Clean up the mcp_client when the application shuts down
    from src.dependencies import mcp_client, _mcp_client_initialized
    if _mcp_client_initialized:
        logger.info("Cleaning up MCP client...")
        await mcp_client.__aexit__(None, None, None)


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

    def signal_handler(sig, frame):
        logger.warning(f"Received signal {sig}, initiating graceful shutdown...")

        # Schedule the shutdown task without blocking
        asyncio.create_task(shutdown_sse_connections())

        # Chain to the original handler after a short delay
        # This allows our shutdown_sse_connections to start running
        def chain_to_original():
            logger.info(f"Chaining to original signal handler for {sig}")
            # Call the original handler
            if sig == signal.SIGTERM and original_term_handler and callable(original_term_handler):
                original_term_handler(sig, frame)
            elif sig == signal.SIGINT and original_int_handler and callable(original_int_handler):
                original_int_handler(sig, frame)

        # Schedule the original handler to run after a short delay
        # This gives our shutdown_sse_connections time to start
        timer = threading.Timer(0.5, chain_to_original)
        timer.daemon = True  # Make sure this doesn't block process exit
        timer.start()

    # Register our handlers
    signal.signal(signal.SIGTERM, signal_handler)  # Signal 15, sent by uvicorn --reload
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C

    logger.info("Signal handlers registered for graceful shutdown")

async def shutdown_sse_connections():
    """Send shutdown message to all SSE clients and close connections"""
    logger.info(f"Shutting down {len(ACTIVE_SESSIONS)} SSE connections...")
    try:
        # Broadcast shutdown message to all clients with more detailed information
        await broadcast_event("server_shutdown", "Server is shutting down for restart")
        # Give clients a moment to process the shutdown message
        # Use a shorter sleep time to ensure we don't block shutdown
        await asyncio.sleep(0.2)
        # Close all connections
        for client_id in list(ACTIVE_SESSIONS.keys()):
            try:
                queue = ACTIVE_SESSIONS[client_id]
                await queue.put(None)  # Signal to close the connection
            except Exception as e:
                logger.error(f"Error closing connection for client {client_id}: {e}")
    except Exception as e:
        logger.error(f"Error during shutdown of SSE connections: {e}")
    finally:
        logger.info("All SSE connections have been notified of shutdown")
        # Clear the collections to help with cleanup
        ACTIVE_SESSIONS.clear()
        SSE_CLIENTS.clear()

# Initialize signal handlers
setup_signal_handlers()


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
async def left_sidebar_component(db: AsyncSession = Depends(get_db)) -> dict:
    """This route serves the left sidebar component for htmx requests."""
    sessions = await session_repository.get_recent_sessions(db)
    
    # Get session templates from registry
    session_templates = app.state.registry.session_templates if hasattr(app.state, 'registry') else {}
    
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

@app.get("/components/navbar")
@jinja.hx('components/navbar.html.j2', no_data=True)
async def navbar_component() -> None:
    """This route serves the navbar component for htmx requests."""

@app.get("/components/session-form/{session_id}")
@jinja.hx('components/session_form.html.j2')
async def session_form_component(session_id: str):
    """This route serves the session form component for htmx requests."""
    return {"session_id": session_id}

@app.get("/session-template/{template_name}")
@jinja.hx('components/session_template_form.html.j2')
async def session_template_form(template_name: str, request: Request):
    """This route serves the session template form for creating a new session."""
    # Get the template from the registry
    template = request.app.state.registry.get_session_template(template_name)
    if not template:
        return {"error": f"Template {template_name} not found"}
    
    return {
        "template": template,
        "template_name": template_name
    }

@app.post("/session-template/{template_name}/create")
async def create_session_from_template_route(
    template_name: str, 
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Create a new session from a template and redirect to it."""
    # Get form data
    form_data = await request.form()
    description = form_data.get("description")
    goal = form_data.get("goal")
    
    # Get the template from the registry
    template = request.app.state.registry.get_session_template(template_name)
    if not template:
        return {"error": f"Template {template_name} not found"}
    
    # Create the session
    from src.service.session import create_session_from_template
    session = await create_session_from_template(
        db=db,
        template=template,
        description=description if description else None,
        goal=goal if goal else None
    )
    
    if not session:
        return {"error": "Failed to create session"}
    
    # Redirect to the session page
    from fastapi.responses import RedirectResponse
    return RedirectResponse(
        url=f"/session/{session.id}",
        status_code=303
    )


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
    await broadcast_event("session_update", "update")

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
    await broadcast_event("session_update", "update")

@app.get("/kitchen-sink")
@jinja.hx('components/kitchen_sink.html.j2', no_data=True)
async def kitchen_sink_component() -> None:
    """This route serves the kitchen sink component for htmx requests."""


@app.get("/sse")
async def sse(request: Request):
    """SSE endpoint for all component updates"""
    client_id = str(uuid.uuid4())
    queue = asyncio.Queue()
    SSE_CLIENTS.add(client_id)
    logger.info(f"New SSE connection: {client_id}")

    try:
        async def event_generator():
            # Send initial connection message
            yield {"event": "connected", "data": "Connected to SSE stream"}

            # Create a queue for this client
            ACTIVE_SESSIONS[client_id] = queue

            try:
                while True:
                    # Wait for the next event with a timeout
                    event = await queue.get()
                    if event is None:  # None is our signal to stop
                        logger.info(f"Closing SSE connection for client {client_id}")
                        break
                    yield event
            except asyncio.TimeoutError:
                # Send a keepalive ping every 30 seconds
                yield {"event": "ping", "data": ""}
            except asyncio.CancelledError:
                logger.warning(f"SSE connection for client {client_id} was cancelled")
                raise  # Re-raise to ensure proper cleanup
            except Exception as e:
                logger.error(f"Error in SSE connection for client {client_id}: {e}")

        return EventSourceResponse(event_generator())
    finally:
        # Clean up when the generator exits
        if client_id in ACTIVE_SESSIONS:
            del ACTIVE_SESSIONS[client_id]
        if client_id in SSE_CLIENTS:
            SSE_CLIENTS.remove(client_id)
        logger.info(f"Cleaned up client {client_id}")


@app.post("/session-submit", response_class=HTMLResponse)
async def session(
    message: MessageCreate,
):
    # Get model and strategy from form data
    # form_data = await request.json()
    logger.info(f"Form data: {message.model_dump()}")
    # model = form_data.get("model", "default-model")
    # strategy = form_data.get("strategy", "default-strategy")

    # Process in background (non-blocking)
    asyncio.create_task(process_message(message))

    # Return empty response as we'll update via SSE
    return ""

async def process_message(message: MessageCreate):
    """Process the message and send response via SSE"""

    # Add user message to the database
    db_message = Message(
        role=message.role,
        model=message.model,
        text=message.text,
        mime_type=message.mime_type,
        session_id=message.session_id,
        parent_id=message.parent_id,
        extra=message.extra
    )
    async for db in get_db():
        db.add(db_message)
        await db.commit()


        # Notify all clients to update the session component
        await broadcast_event("session_update", "update")

        # Simulate processing time
        await asyncio.sleep(randint(1, 5))

        # Add system response to the database
        await db.refresh(db_message)
        db_message = Message(
            role="assistant",
            model=message.model,
            text=f"Processed message using {message.model} with {message.extra} strategy: {message.text}",
            mime_type=message.mime_type,
            session_id=message.session_id,
            parent_id=db_message.id,
        )
        db.add(db_message)
        await db.commit()

        # Notify all clients to update the session component again
        await broadcast_event("session_update", "update")

async def broadcast_event(event_name, data):
    """Send an event to all connected SSE clients"""
    logger.debug(f"Broadcasting {event_name} to {len(ACTIVE_SESSIONS)} clients")
    for client_id in list(ACTIVE_SESSIONS.keys()):
        try:
            queue = ACTIVE_SESSIONS[client_id]
            # Format the event properly for SSE
            event_data = json.dumps(data) if isinstance(data, (dict, list)) else data
            await queue.put({"event": event_name, "data": event_data})
        except Exception as e:
            logger.error(f"Error broadcasting to client {client_id}: {e}")
            # If we can't send to this client, remove it
            if client_id in ACTIVE_SESSIONS:
                del ACTIVE_SESSIONS[client_id]


if __name__ == "__main__":
    # Configure uvicorn to use our logging
    uvicorn.run(app, host="0.0.0.0", port=8000)

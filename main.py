from contextlib import asynccontextmanager
from random import randint
import uvicorn
import asyncio
import json
import uuid
import signal
import threading
from fastapi import FastAPI, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from mcp import StdioServerParameters

from flibberflow.core.mcp_client import MCPClient
from flibberflow.http import HTMXRedirectMiddleware
from starlette.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from fasthx import Jinja
from sse_starlette.sse import EventSourceResponse

mcp_client = MCPClient()

@asynccontextmanager
async def lifespan(app: FastAPI):
    server = {
        "sqlite": {
          "command": "uvx",
          "args": ["mcp-server-sqlite", "--db-path", "./test.db"]
        },
        "fetch": {
          "command": "uvx",
          "args": ["mcp-server-fetch", "--ignore-robots-txt"]
        }
    }

    for name, params in server.items():
        res = await mcp_client.connect_to_server(
            name=name,
            server_params=StdioServerParameters(**params)
        )

    print("initialized")

    yield

    # Close the MCP client connections.
    await mcp_client.cleanup()


app = FastAPI(title="Flibberflow", lifespan=lifespan)
app.add_middleware(HTMXRedirectMiddleware)

# static asset mount
app.mount("/build", StaticFiles(directory="build"), name="build")

jinja_templates = Jinja2Templates(directory="templates")
jinja = Jinja(jinja_templates)

# Store active session tasks
ACTIVE_SESSIONS = {}
# Store messages for the session
MESSAGES = []
# Store clients connected to SSE
SSE_CLIENTS = set()

# Set up signal handlers for graceful shutdown
def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown"""
    # Store original signal handlers to chain to them
    original_term_handler = signal.getsignal(signal.SIGTERM)
    original_int_handler = signal.getsignal(signal.SIGINT)
    
    def signal_handler(sig, frame):
        print(f"Received signal {sig}, initiating graceful shutdown...")

        # Schedule the shutdown task without blocking
        asyncio.create_task(shutdown_sse_connections())
        
        # Chain to the original handler after a short delay
        # This allows our shutdown_sse_connections to start running
        def chain_to_original():
            print(f"Chaining to original signal handler for {sig}")
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
    
    print("Signal handlers registered for graceful shutdown")


async def shutdown_sse_connections():
    """Send shutdown message to all SSE clients and close connections"""
    print(f"Shutting down {len(ACTIVE_SESSIONS)} SSE connections...")
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
                print(f"Error closing connection for client {client_id}: {e}")
    except Exception as e:
        print(f"Error during shutdown of SSE connections: {e}")
    finally:
        print("All SSE connections have been notified of shutdown")
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
@jinja.hx('components/settings.html.j2', no_data=True)
def settings_component() -> None:
    """This route serves just the settings component for htmx requests."""

@app.get("/session")
@jinja.hx('components/session.html.j2')
def session_component() -> dict:
    """This route serves just the chat component for htmx requests."""
    return {"messages": MESSAGES}

@app.get("/components/left-sidebar")
@jinja.hx('components/left_sidebar.html.j2', no_data=True)
def left_sidebar_component() -> None:
    """This route serves the left sidebar component for htmx requests."""

@app.get("/components/right-drawer")
@jinja.hx('components/right_drawer.html.j2', no_data=True)
def right_drawer_component() -> None:
    """This route serves the right drawer component for htmx requests."""

@app.get("/components/navbar")
@jinja.hx('components/navbar.html.j2', no_data=True)
def navbar_component() -> None:
    """This route serves the navbar component for htmx requests."""

@app.get("/components/session-form")
@jinja.hx('components/session_form.html.j2', no_data=True)
def session_form_component() -> None:
    """This route serves the session form component for htmx requests."""

@app.get("/kitchen-sink")
@jinja.hx('components/kitchen_sink.html.j2', no_data=True)
def kitchen_sink_component() -> None:
    """This route serves the kitchen sink component for htmx requests."""


@app.get("/sse")
async def sse(request: Request):
    """SSE endpoint for all component updates"""
    client_id = str(uuid.uuid4())
    queue = asyncio.Queue()
    SSE_CLIENTS.add(client_id)
    print(f"New SSE connection: {client_id}")

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
                        print(f"Closing SSE connection for client {client_id}")
                        break
                    yield event
            except asyncio.TimeoutError:
                # Send a keepalive ping every 30 seconds
                yield {"event": "ping", "data": ""}
            except asyncio.CancelledError:
                print(f"SSE connection for client {client_id} was cancelled")
                raise  # Re-raise to ensure proper cleanup
            except Exception as e:
                print(f"Error in SSE connection for client {client_id}: {e}")

        return EventSourceResponse(event_generator())
    finally:
        # Clean up when the generator exits
        if client_id in ACTIVE_SESSIONS:
            del ACTIVE_SESSIONS[client_id]
        if client_id in SSE_CLIENTS:
            SSE_CLIENTS.remove(client_id)
        print(f"Cleaned up client {client_id}")


@app.post("/session-submit", response_class=HTMLResponse)
async def session(request: Request, message: str = Form(...)):
    # Get model and strategy from form data
    form_data = await request.form()
    model = form_data.get("model", "default-model")
    strategy = form_data.get("strategy", "default-strategy")

    # Process in background (non-blocking)
    asyncio.create_task(process_message(message, model, strategy))

    # Return empty response as we'll update via SSE
    return ""

async def process_message(message: str, model: str, strategy: str):
    """Process the message and send response via SSE"""
    # Add user message to the messages list
    user_message = {"role": "user", "content": message}
    MESSAGES.append(user_message)

    # Notify all clients to update the session component
    await broadcast_event("session_update", "update")


    # Simulate processing time
    await asyncio.sleep(randint(1, 5))

    # Add system response to the messages list
    system_response = {
        "role": "assistant", 
        "content": f"Processed message using {model} with {strategy} strategy: {message}"
    }
    MESSAGES.append(system_response)

    # Notify all clients to update the session component again
    await broadcast_event("session_update", "update")

async def broadcast_event(event_name, data):
    """Send an event to all connected SSE clients"""
    print(f"Broadcasting {event_name} to {len(ACTIVE_SESSIONS)} clients")
    for client_id in list(ACTIVE_SESSIONS.keys()):
        try:
            queue = ACTIVE_SESSIONS[client_id]
            # Format the event properly for SSE
            event_data = json.dumps(data) if isinstance(data, (dict, list)) else data
            await queue.put({"event": event_name, "data": event_data})
        except Exception as e:
            print(f"Error broadcasting to client {client_id}: {e}")
            # If we can't send to this client, remove it
            if client_id in ACTIVE_SESSIONS:
                del ACTIVE_SESSIONS[client_id]


if __name__ == "__main__":
    # Make sure signal handlers are set up before starting the server
    setup_signal_handlers()
    uvicorn.run(app, host="0.0.0.0", port=8000)

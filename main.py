import uvicorn
import asyncio
import json
import uuid
from fastapi import FastAPI, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from flibberflow.http import HTMXRedirectMiddleware
from starlette.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from fasthx import Jinja
from sse_starlette.sse import EventSourceResponse


app = FastAPI(title="Flibberflow")
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
                    # Wait for messages to be added to the queue
                    event = await queue.get()
                    if event is None:  # None is our signal to stop
                        break
                    yield event
            except asyncio.CancelledError:
                pass
        
        return EventSourceResponse(event_generator())
    finally:
        # Cleanup when client disconnects
        async def cleanup():
            if client_id in ACTIVE_SESSIONS:
                del ACTIVE_SESSIONS[client_id]
            if client_id in SSE_CLIENTS:
                SSE_CLIENTS.remove(client_id)
        
        asyncio.create_task(cleanup())

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
    await asyncio.sleep(1)
    
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
    uvicorn.run(app, host="0.0.0.0", port=8000)


import uvicorn
import time
import asyncio
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from flibberflow.http import HTMXRedirectMiddleware
from starlette.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from fasthx import Jinja
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

# app.add_middleware(HTMXRedirectMiddleware)

# static asset mount
app.mount("/build", StaticFiles(directory="build"), name="build")

jinja_templates = Jinja2Templates(directory="templates")
jinja = Jinja(jinja_templates)

# Store active session connections
ACTIVE_SESSIONS = {}


@app.get("/")
@jinja.page('index.html.j2')
def index() -> None:
    """This route serves the index.html template."""

@app.get("/settings")
@jinja.hx('components/settings.html.j2', no_data=True)
def session_component() -> None:
    """This route serves just the chat component for htmx requests."""

@app.get("/session")
@jinja.hx('components/session.html.j2', no_data=True)
def session_component() -> None:
    """This route serves just the chat component for htmx requests."""

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


@app.get("/session-start")
async def session_workspace(request: Request):
    """SSE endpoint for session messages"""
    client_id = str(id(request))
    
    # Create a queue for this client
    queue = asyncio.Queue()
    ACTIVE_SESSIONS[client_id] = queue
    
    async def event_generator():
        try:
            while True:
                # Wait for messages to be added to the queue
                message = await queue.get()
                if message is None:  # None is our signal to stop
                    break
                yield {"event": "message", "data": message}
        except asyncio.CancelledError:
            pass
        finally:
            # Clean up when the client disconnects
            if client_id in ACTIVE_SESSIONS:
                del ACTIVE_SESSIONS[client_id]
    
    return EventSourceResponse(event_generator())

@app.post("/session-submit", response_class=HTMLResponse)
async def session(request: Request, message: str = Form(...)):
    # Get model and strategy from form data
    form_data = await request.form()
    model = form_data.get("model", "default-model")
    strategy = form_data.get("strategy", "default-strategy")


    # Process in background (non-blocking)
    asyncio.create_task(process_message(request, message, model, strategy))


async def process_message(request: Request, message: str, model: str, strategy: str):
    """Process the message and send response via SSE"""
    # @TODO:
    pass


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)


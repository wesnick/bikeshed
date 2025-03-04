import uvicorn
import time
import asyncio
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from fasthx import Jinja
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

# static asset mount
app.mount("/build", StaticFiles(directory="build"), name="build")

jinja = Jinja(Jinja2Templates(directory="templates"))

# Store active chat connections
CHAT_CONNECTIONS = {}


@app.get("/")
@jinja.page('index.html.j2')
def index() -> None:
    """This route serves the index.html template."""


@app.get("/components/chat")
@jinja.hx('components/chat.html.j2', no_data=True)
def chat_component() -> None:
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

@app.get("/components/chat-form")
@jinja.hx('components/chat_form.html.j2', no_data=True)
def chat_form_component() -> None:
    """This route serves the chat form component for htmx requests."""


@app.get("/chatroom")
async def chatroom(request: Request):
    """SSE endpoint for chat messages"""
    client_id = str(id(request))
    
    # Create a queue for this client
    queue = asyncio.Queue()
    CHAT_CONNECTIONS[client_id] = queue
    
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
            if client_id in CHAT_CONNECTIONS:
                del CHAT_CONNECTIONS[client_id]
    
    return EventSourceResponse(event_generator())

@app.post("/chat", response_class=HTMLResponse)
async def chat(request: Request, message: str = Form(...)):
    # Get model and strategy from form data
    form_data = await request.form()
    model = form_data.get("model", "default-model")
    strategy = form_data.get("strategy", "default-strategy")
    
    # Create user message HTML
    context = {"message_type": "user", "message_content": message}
    user_message_html = await request.app.state.templates.TemplateResponse(
        "components/message.html.j2", 
        {"request": request, **context}
    ).body.decode('utf-8')
    
    # Send user message to all connected clients
    for client_queue in CHAT_CONNECTIONS.values():
        await client_queue.put(user_message_html)
    
    # Process in background (non-blocking)
    asyncio.create_task(process_message(request, message, model, strategy))
    
    # Return empty response since messages will be sent via SSE
    return ""

async def process_message(request: Request, message: str, model: str, strategy: str):
    """Process the message and send response via SSE"""
    # Simulate processing delay (remove in production)
    await asyncio.sleep(1)
    
    # For now, just echo the message back as the assistant
    # In a real implementation, this would be the LLM response
    assistant_message = f"You said: {message} (using model: {model}, strategy: {strategy})"
    
    # Use the message component template for assistant message
    assistant_message_html = await jinja.render_template(
        request, 
        "components/message.html.j2", 
        {"message_type": "assistant", "message_content": assistant_message}
    )
    
    # Add script to stop timer
    assistant_message_html += "<script>stopTimer();</script>"
    
    # Send assistant message to all connected clients
    for client_queue in CHAT_CONNECTIONS.values():
        await client_queue.put(assistant_message_html)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)


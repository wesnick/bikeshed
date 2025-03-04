import uvicorn
import time
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fasthx import Jinja

app = FastAPI()

# static asset mount
app.mount("/build", StaticFiles(directory="build"), name="build")

jinja = Jinja(Jinja2Templates(directory="templates"))


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


@app.post("/chat", response_class=HTMLResponse)
async def chat(request: Request, message: str = Form(...)):
    # Get model and strategy from form data
    form_data = await request.form()
    model = form_data.get("model", "default-model")
    strategy = form_data.get("strategy", "default-strategy")
    
    # In a real app, you would process the message with an LLM here
    # For now, we'll just echo the message and add a simulated delay
    
    # Create user message HTML with the message component
    context = {"message_type": "user", "message_content": message}
    user_message_html = await request.app.state.templates.TemplateResponse(
        "components/message.html.j2", 
        {"request": request, **context}
    ).body.decode('utf-8')
    
    # Simulate processing delay (remove in production)
    time.sleep(1)
    
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
    
    # Return both messages to be added to the chat
    return user_message_html + assistant_message_html


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)


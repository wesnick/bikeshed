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


@app.get("/chat-component")
@jinja.hx('components/chat.html.j2', no_data=True)
def chat_component() -> None:
    """This route serves just the chat component for htmx requests."""


@app.post("/chat", response_class=HTMLResponse)
async def chat(request: Request, message: str = Form(...)):
    # Get model and strategy from form data
    form_data = await request.form()
    model = form_data.get("model", "default-model")
    strategy = form_data.get("strategy", "default-strategy")
    
    # In a real app, you would process the message with an LLM here
    # For now, we'll just echo the message and add a simulated delay
    
    # Create user message HTML
    user_message_html = f"""
    <div class="message user-message">
        <p>{message}</p>
    </div>
    """
    
    # Simulate processing delay (remove in production)
    time.sleep(1)
    
    # For now, just echo the message back as the assistant
    # In a real implementation, this would be the LLM response
    assistant_message = f"You said: {message} (using model: {model}, strategy: {strategy})"
    
    assistant_message_html = f"""
    <div class="message assistant-message">
        <p>{assistant_message}</p>
    </div>
    <script>stopTimer();</script>
    """
    
    # Return both messages to be added to the chat
    return user_message_html + assistant_message_html


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)


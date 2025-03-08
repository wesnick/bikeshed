Example of using SSE with fastAPI and HTMX

Example fastapi:

```python
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import asyncio
import time
import random
import json
from datetime import datetime

app = FastAPI()

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up templates
templates = Jinja2Templates(directory="templates")

# In-memory data store for our example
tasks = [
    {"id": 1, "title": "Learn HTMX", "status": "In Progress"},
    {"id": 2, "title": "Master FastAPI", "status": "Pending"},
    {"id": 3, "title": "Build SPA-like app", "status": "Pending"}
]

notifications = []

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main page"""
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "tasks": tasks, "notifications": notifications}
    )

@app.get("/tasks", response_class=HTMLResponse)
async def get_tasks(request: Request):
    """Return just the tasks list HTML fragment"""
    return templates.TemplateResponse(
        "partials/tasks.html", 
        {"request": request, "tasks": tasks}
    )

@app.get("/notifications", response_class=HTMLResponse)
async def get_notifications(request: Request):
    """Return just the notifications HTML fragment"""
    return templates.TemplateResponse(
        "partials/notifications.html", 
        {"request": request, "notifications": notifications}
    )

@app.get("/stats", response_class=HTMLResponse)
async def get_stats(request: Request):
    """Return just the stats HTML fragment"""
    completed = sum(1 for task in tasks if task["status"] == "Completed")
    in_progress = sum(1 for task in tasks if task["status"] == "In Progress")
    pending = sum(1 for task in tasks if task["status"] == "Pending")
    
    return templates.TemplateResponse(
        "partials/stats.html", 
        {
            "request": request, 
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending,
            "total": len(tasks)
        }
    )

@app.post("/tasks/{task_id}/complete", response_class=HTMLResponse)
async def complete_task(request: Request, task_id: int):
    """Mark a task as completed and return the updated task HTML"""
    # Find and update the task
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = "Completed"
            
            # Add a notification
            notifications.insert(0, {
                "id": len(notifications) + 1,
                "message": f"Task '{task['title']}' marked as completed",
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            
            # Keep only the 5 most recent notifications
            if len(notifications) > 5:
                notifications.pop()
            
            break
    
    # Return just the updated task HTML
    return templates.TemplateResponse(
        "partials/task_row.html", 
        {"request": request, "task": task}
    )

@app.get("/sse")
async def sse(request: Request):
    """Server-Sent Events endpoint"""
    async def event_generator():
        # Initial connection message
        yield "data: Connected to SSE stream\n\n"
        
        # Keep connection alive and send updates
        while True:
            # Wait a bit
            await asyncio.sleep(1)
            
            # Send updates to different parts of the page
            if random.random() < 0.3:  # Occasionally update stats
                yield f"event: stats_update\ndata: update\n\n"
            
            if random.random() < 0.2:  # Occasionally update notifications
                yield f"event: notifications_update\ndata: update\n\n"
                
            # Keep-alive ping every 15-20 seconds
            if random.random() < 0.05:
                yield f"event: ping\ndata: {time.time()}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

Sample HTML
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FastAPI + HTMX + SSE Example</title>
    <link rel="stylesheet" href="/static/styles.css">
    <!-- Include HTMX -->
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <!-- Include SSE extension -->
    <script src="https://unpkg.com/htmx-ext-sse@2.2.2"></script>
</head>
<body hx-ext="sse" sse-connect="/sse">
    <div class="container">
        <header>
            <h1>Task Manager</h1>
            <p>A FastAPI + HTMX + SSE Example</p>
        </header>

        <div class="dashboard">
            <!-- Stats section - updated via SSE -->
            <section class="stats-section" 
                     hx-trigger="sse:stats_update" 
                     hx-get="/stats" 
                     hx-swap="innerHTML">
                {% include "partials/stats.html" %}
            </section>

            <!-- Notifications section - updated via SSE -->
            <section class="notifications-section" 
                     hx-trigger="sse:notifications_update" 
                     hx-get="/notifications" 
                     hx-swap="innerHTML">
                {% include "partials/notifications.html" %}
            </section>
        </div>

        <!-- Tasks section -->
        <section class="tasks-section">
            <h2>Tasks</h2>
            <div id="tasks-container">
                {% include "partials/tasks.html" %}
            </div>
        </section>

        <footer>
            <p>Built with FastAPI, HTMX, and Server-Sent Events</p>
        </footer>
    </div>
</body>
</html>
```
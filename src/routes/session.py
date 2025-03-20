from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.workflow.service import WorkflowService
from src.dependencies import get_db, get_jinja, get_workflow_service
from src.repository import session_repository, message_repository
from src.models import Session


router = APIRouter(prefix="/session", tags=["session"])

jinja = get_jinja()

@router.get("/")
@jinja.hx('components/session/list.html.j2')
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """List all sessions"""
    sessions = await session_repository.get_recent_sessions(db)
    return {"sessions": sessions}

@router.get("/{session_id}")
@jinja.hx('components/session.html.j2')
async def get_session(session_id: UUID,
                      workflow_service: WorkflowService = Depends(get_workflow_service),
                      db: AsyncSession = Depends(get_db)):
    """Get a specific session with its messages"""
    session = await workflow_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = await message_repository.get_by_session(db, session.id)
    session_workflow_svg = await workflow_service.create_workflow_graph(session)
    return {
        "session": session,
        "messages": messages,
        "workflow_svg": session_workflow_svg,
        "session_workflow_svg": session_workflow_svg,
    }

@router.post("/")
@jinja.hx('components/session.html.j2')
async def create_session(summary: Optional[str] = None, goal: Optional[str] = None,
                        system_prompt: Optional[str] = None, flow_id: Optional[UUID] = None,
                        db: AsyncSession = Depends(get_db)):
    """Create a new session"""
    session_data = {
        "summary": summary,
        "goal": goal,
        "system_prompt": system_prompt,
        "flow_id": flow_id
    }
    session = await session_repository.create(db, session_data)
    return {"session": session, "messages": [], "message": "Session created successfully"}


@router.get("/template-creator/{template_name}")
@jinja.hx('components/session_template_form.html.j2')
async def session_template_form(template_name: str,
                                request: Request,
                                workflow_service: WorkflowService = Depends(get_workflow_service)):
    """This route serves the session template form for creating a new session."""
    # Get the template from the registry
    template = request.app.state.registry.get_session_template(template_name)
    if not template:
        return {"error": f"Template {template_name} not found"}

    session = Session()
    session.template = template

    # Analyze workflow dependencies
    workflow_analysis = await workflow_service.analyze_workflow_dependencies(template)
    
    session_workflow_svg = await workflow_service.create_workflow_graph(session)

    return {
        "template": template,
        "template_name": template_name,
        "session_workflow_svg": session_workflow_svg,
        "workflow_analysis": workflow_analysis,
    }


@router.post("/template-creator/{template_name}/create")
async def create_session_from_template_route(
        template_name: str,
        request: Request,
        background_tasks: BackgroundTasks,
        workflow_service: WorkflowService = Depends(get_workflow_service),
):
    """Create a new session from a template and redirect to it."""
    # Get form data
    form_data = await request.form()
    description = form_data.get("description")
    goal = form_data.get("goal")
    
    # Extract workflow input variables from form data
    initial_data = {"variables": {}}
    
    # Process all form fields that start with "input_" as workflow variables
    for key, value in form_data.items():
        if key.startswith("input_") and value:  # Only include non-empty values
            var_name = key[6:]  # Remove "input_" prefix
            initial_data["variables"][var_name] = value

    # Get the template from the registry
    template = request.app.state.registry.get_session_template(template_name)
    if not template:
        return {"error": f"Template {template_name} not found"}

    # Create the session with initial data
    session = await workflow_service.create_session_from_template(
        template=template,
        description=description if description else None,
        goal=goal if goal else None,
        initial_data=initial_data
    )

    if not session:
        return {"error": "Failed to create session"}

    # @TODO: trigger htmx get rather than use redirection

    background_tasks.add_task(workflow_service.execute_next_step, session.id)

    # Redirect to the session page
    from fastapi.responses import RedirectResponse
    return RedirectResponse(
        url=f"/session/{session.id}",
        status_code=303
    )

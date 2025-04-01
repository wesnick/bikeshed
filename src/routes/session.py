from typing import Optional
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg import AsyncConnection
from starlette.responses import Response

from src.core.registry import Registry
from src.core.workflow.service import WorkflowService
from src.dependencies import get_db, get_jinja, get_workflow_service, get_registry, get_broadcast_service, \
    get_arq_redis
from src.models.models import MessageStatus
from src.repository import session_repository, message_repository
from src.models import Session, Message
from src.service.broadcast import BroadcastService
from src.custom_types import SessionTemplateCreationRequest, MessageCreate
from src.service.logging import logger

router = APIRouter(prefix="/session", tags=["session"])

jinja = get_jinja()

@router.get("/")
@jinja.hx('components/session/list.html.j2')
async def list_sessions(db: AsyncConnection = Depends(get_db)):
    """List all sessions"""
    sessions = await session_repository.get_recent_sessions(db)
    return {"sessions": sessions}


@router.post("/")
@jinja.hx('components/session/session.html.j2')
async def create_session(summary: Optional[str] = None, goal: Optional[str] = None,
                        system_prompt: Optional[str] = None, flow_id: Optional[UUID] = None,
                        db: AsyncConnection = Depends(get_db)):
    """Create a new session"""
    session_data = {
        "summary": summary,
        "goal": goal,
        "system_prompt": system_prompt,
        "flow_id": flow_id
    }
    session = Session(**session_data)
    session = await session_repository.create(db, session)
    return {
        "session": session,
        "messages": [],
        "message": "Session created successfully"
    }



@router.get("/{session_id}")
@jinja.hx('components/session/session.html.j2')
async def get_session(response: Response,
                      session_id: UUID):
    """Container for session mini-dash"""

    response.headers['HX-Trigger-After-Swap'] = "drawer.updated"

    return {
        "session_id": session_id,
    }

@router.get("/{session_id}/overview")
@jinja.hx('components/session/session_overview.html.j2', no_data=True)
async def get_session(session_id: UUID,
                      workflow_service: WorkflowService = Depends(get_workflow_service)):
    """Container for session mini-dash"""
    session = await workflow_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session": session,
        "active_step": session.get_next_step_name(),
    }

@router.get("/{session_id}/messages")
@jinja.hx('components/session/message_list.html.j2')
async def get_session_messages(session_id: UUID,
                              db: AsyncConnection = Depends(get_db)):
    """Get a specific session with its messages"""
    messages = await message_repository.get_by_session(db, session_id)

    return {
        "messages": messages,
    }


@router.get("/{session_id}/session-form")
@jinja.hx('components/session/session_form.html.j2')
async def session_form_component(session_id: UUID,
                                 workflow_service: WorkflowService = Depends(get_workflow_service)):
    """This route serves the session form component for htmx requests."""
    session = await workflow_service.get_session(session_id)

    if not session:
        return {"error": "Session not found"}

    current_step = session.get_current_step()

    return {
        "session": session,
        "current_step": current_step
    }


@router.post("/session-submit")
@jinja.hx('components/session/message_list.html.j2')
async def session_submit(response: Response,
                         message: MessageCreate,
                         workflow_service: WorkflowService = Depends(get_workflow_service),
                         db: AsyncConnection = Depends(get_db),
                         broadcast_service: BroadcastService = Depends(get_broadcast_service)):
    """This route serves the session form component for htmx requests."""

    session = await workflow_service.get_session(message.session_id)

    next_action = "continue" if message.button_pressed == "continue" else "send"
    logger.warning(f"{next_action} pressed")

    # Workflow continue
    if next_action == "continue":
        await enqueue_session_run_workflow(session.id)
        return {"session": session, "current_step": session.get_current_step()}

    user_message = Message(
        id=uuid.uuid4(),
        session_id=session.id,
        role='user',
        text=message.text,
        parent_id=session.messages[-1].id if session.messages else None,
        status=MessageStatus.PENDING
    )

    # Add user message to the database
    await message_repository.create(db, user_message)

    # Add to session for LLM processing
    session.messages.append(user_message)

    # Create assistant message placeholder
    assistant_message = Message(
        id=uuid.uuid4(),
        session_id=session.id,
        role='assistant',
        model=message.model,
        parent_id=user_message.id,
        text="",
        status=MessageStatus.CREATED
    )
    # Add to database and session
    await message_repository.create(db, assistant_message)
    session.messages.append(assistant_message)

    # Send it to the queue
    await enqueue_message_processing(session.id)

    # response.headers['HX-Target'] = "#dashboard"
    # response.headers['HX-Reswap'] = 'outerHTML'

    return {
        "session": session,
        "messages": session.messages,
        "current_step": session.get_current_step()
    }


async def enqueue_message_processing(session_id: uuid.UUID) -> str:
    """
    Enqueue a message processing job with ARQ

    Args:
        session_id: The UUID of the session to process
        arq_redis: ARQ Redis connection

    Returns:
        The job ID as a string
    """
    async for arq_redis in get_arq_redis():
        job = await arq_redis.enqueue_job('process_message_job', session_id)
        return job.job_id


@router.get("/template-creator/{template_name}")
@jinja.hx('components/session/session_template_form.html.j2')
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

    # @TODO: refactor this to not use engine directly
    await workflow_service.engine.initialize_session(session)

    return {
        "template": template,
        "template_name": template_name,
        "workflow_analysis": workflow_analysis,
    }


@router.post("/template-creator/{template_name}/create")
@jinja.hx('components/session/session.html.j2')
async def create_session_from_template_route(
        response: Response,
        template_name: str,
        session_create: SessionTemplateCreationRequest,
        workflow_service: WorkflowService = Depends(get_workflow_service),
        registry: Registry = Depends(get_registry),
):
    """Create a new session from a template and redirect to it."""
    description = session_create.description
    goal = session_create.goal

    # Extract workflow input variables from form data
    initial_data = {"variables": {}}

    # Process all form fields that start with "input_" as workflow variables
    for key, value in session_create.input.items():
        initial_data["variables"][key] = value

    # Get the template from the registry
    template = registry.get_session_template(template_name)
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


    await enqueue_session_run_workflow(session.id)

    # @TODO this might better be HX-Location
    response.headers['HX-Replace-Url'] = f"/session/{session.id}"
    response.headers['HX-Trigger'] = 'sse:session.updated'

    return {
        "session_id": session.id,
    }

async def enqueue_session_run_workflow(session_id: uuid.UUID) -> str:
    """
    Enqueue a message processing job with ARQ

    Args:
        session_id: The UUID of the session to process
        arq_redis: ARQ Redis connection

    Returns:
        The job ID as a string
    """
    async for arq_redis in get_arq_redis():
        job = await arq_redis.enqueue_job('session_run_workflow_job', session_id)
        return job.job_id


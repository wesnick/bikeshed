from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from psycopg import AsyncConnection

from src.core.registry import Registry
from src.core.workflow.service import WorkflowService
from src.dependencies import get_db, get_jinja, get_workflow_service, get_registry
from src.repository import session_repository, message_repository
from src.models import Session
from src.types import SessionTemplateCreationRequest, MessageCreate
from src.service.logging import logger

router = APIRouter(prefix="/session", tags=["session"])

jinja = get_jinja()

@router.get("/")
@jinja.hx('components/session/list.html.j2')
async def list_sessions(db: AsyncConnection = Depends(get_db)):
    """List all sessions"""
    sessions = await session_repository.get_recent_sessions(db)
    return {"sessions": sessions}

@router.get("/{session_id}")
@jinja.hx('components/session/session.html.j2')
async def get_session(session_id: UUID,
                      workflow_service: WorkflowService = Depends(get_workflow_service)):
    """Get a specific session with its messages"""
    session = await workflow_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")


    logger.warning(f"Session: {session} Message count: {len(session.messages)}")
    session_workflow_svg = await workflow_service.create_workflow_graph(session)
    return {
        "session": session,
        "messages": session.messages,
        "workflow_svg": session_workflow_svg,
        "session_workflow_svg": session_workflow_svg,
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
    session = await session_repository.create(db, session_data)
    return {"session": session, "messages": [], "message": "Session created successfully"}


@router.get("/{session_id}/session-form")
@jinja.hx('components/session/session_form.html.j2')
async def session_form_component(session_id: UUID,
                                 workflow_service: WorkflowService = Depends(get_workflow_service)):
    """This route serves the session form component for htmx requests."""
    session = await workflow_service.get_session(session_id)

    if not session:
        return {"error": "Session not found"}

    current_step = session.get_current_step()

    return {"session": session, "current_step": current_step}


@router.post("/session-submit")
@jinja.hx('components/session/session_form.html.j2')
async def session_submit(message: MessageCreate,
                        background_tasks: BackgroundTasks,
                        workflow_service: WorkflowService = Depends(get_workflow_service)):
    """This route serves the session form component for htmx requests."""

    session = await workflow_service.get_session(message.session_id)

    if message.button_pressed == "send":
        logger.warning("send pressed")
    elif message.button_pressed == "continue":
        logger.warning("continue pressed")

    # model = form_data.get("model", "default-model")
    # strategy = form_data.get("strategy", "default-strategy")

    # Process in background (non-blocking)
    background_tasks.add_task(process_message, message)

    # Return empty response as we'll update via SSE
    return {"session": session, "current_step": session.get_current_step()}

async def process_message(message: MessageCreate):
    """Process the message and send response via SSE"""
    from src.main import broadcast_event
    from src.core.llm.manager import ConversationManager, MessageContext
    from src.core.llm.middleware import (
        MessagePersistenceMiddleware,
        LLMProcessingMiddleware,
        SessionUpdateMiddleware
    )
    from src.core.llm.llm import get_llm_service

    # Get the LLM service
    llm_service = get_llm_service()

    async for db in get_db():
        # Get the session
        session = await session_repository.get_by_id(db, message.session_id)
        if not session:
            return

        # Create conversation manager with middleware chain
        manager = ConversationManager([
            MessagePersistenceMiddleware(),
            LLMProcessingMiddleware(llm_service),
            SessionUpdateMiddleware()
        ])
        
        # Process through middleware chain
        context = await manager.process(MessageContext(
            session=session,
            raw_input=message.text,
            model=message.model,
            metadata={
                "parent_id": message.parent_id,
                "extra": message.extra
            }
        ))
        
        # Extract created messages
        messages = context.metadata.get("messages", [])
        
        # Add messages to the database
        for msg in messages:
            db.add(msg)
        await db.commit()
        
        # Refresh the session to get the latest messages
        await db.refresh(session)

        # Notify all clients to update the session component
        await broadcast_event("session_update", "update")


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

    await workflow_service.engine.initialize_session(session)
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
        session_create: SessionTemplateCreationRequest,
        background_tasks: BackgroundTasks,
        workflow_service: WorkflowService = Depends(get_workflow_service),
        registry: Registry = Depends(get_registry)

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

    # @TODO: trigger htmx get rather than use redirection

    background_tasks.add_task(workflow_service.run_workflow, session)

    # Redirect to the session page
    return {"url": f"/session/{session.id}"}

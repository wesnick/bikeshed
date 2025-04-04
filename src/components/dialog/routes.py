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
from src.core.models import MessageStatus
from src.components.repositories import dialog_repository, message_repository
from src.core.models import Dialog, Message
from src.service.broadcast import BroadcastService
from src.custom_types import DialogTemplateCreationRequest, MessageCreate
from src.service.logging import logger

router = APIRouter(prefix="/dialog", tags=["dialog"])

jinja = get_jinja("src/components/dialog/templates")

@router.get("/")
@jinja.hx('list.html.j2')
async def list_dialogs(db: AsyncConnection = Depends(get_db)):
    """List all dialogs"""
    dialogs = await dialog_repository.get_recent_dialogs(db)
    return {"dialogs": dialogs}


@router.post("/")
@jinja.hx('dialog.html.j2')
async def create_dialog(summary: Optional[str] = None, goal: Optional[str] = None,
                        system_prompt: Optional[str] = None, flow_id: Optional[UUID] = None,
                        db: AsyncConnection = Depends(get_db)):
    """Create a new dialog"""
    dialog_data = {
        "summary": summary,
        "goal": goal,
        "system_prompt": system_prompt,
        "flow_id": flow_id
    }
    dialog = Dialog(**dialog_data)
    dialog = await dialog_repository.create(db, dialog)
    return {
        "dialog": dialog,
        "messages": [],
        "message": "Dialog created successfully"
    }



@router.get("/{dialog_id}")
@jinja.hx('view_dash.html.j2')
async def get_dialog(response: Response,
                      dialog_id: UUID):
    """Container for dialog mini-dash"""

    response.headers['HX-Trigger-After-Swap'] = "drawer.updated"

    return {
        "dialog_id": dialog_id,
    }

@router.get("/{dialog_id}/overview")
@jinja.hx('overview.html.j2', no_data=True)
async def get_dialog(dialog_id: UUID,
                      workflow_service: WorkflowService = Depends(get_workflow_service)):
    """Container for dialog mini-dash"""
    dialog = await workflow_service.get_dialog(dialog_id)
    if not dialog:
        raise HTTPException(status_code=404, detail="Dialog not found")

    return {
        "dialog": dialog,
        "active_step": dialog.get_next_step_name(),
    }

@router.get("/{dialog_id}/messages")
@jinja.hx('message_list.html.j2')
async def get_dialog_messages(dialog_id: UUID,
                              db: AsyncConnection = Depends(get_db)):
    """Get a specific dialog with its messages"""
    messages = await message_repository.get_by_dialog(db, dialog_id)

    return {
        "messages": messages,
    }


@router.get("/{dialog_id}/dialog-form")
@jinja.hx('dialog_form.html.j2')
async def dialog_form_component(dialog_id: UUID,
                                 workflow_service: WorkflowService = Depends(get_workflow_service)):
    """This route serves the dialog form component for htmx requests."""
    dialog = await workflow_service.get_dialog(dialog_id)

    if not dialog:
        return {"error": "Dialog not found"}

    current_step = dialog.get_current_step()

    from src.main import app
    registry = app.state.registry
    models = registry.list_models(True)

    return {
        "dialog": dialog,
        "current_step": current_step,
        "available_models": models,
    }


@router.post("/dialog-submit")
@jinja.hx('message_list.html.j2')
async def dialog_submit(response: Response,
                         message: MessageCreate,
                         workflow_service: WorkflowService = Depends(get_workflow_service),
                         db: AsyncConnection = Depends(get_db),
                         broadcast_service: BroadcastService = Depends(get_broadcast_service)):
    """This route serves the dialog form component for htmx requests."""

    dialog = await workflow_service.get_dialog(message.dialog_id)

    next_action = "continue" if message.button_pressed == "continue" else "send"
    logger.warning(f"{next_action} pressed")

    # Workflow continue
    if next_action == "continue":
        await enqueue_dialog_run_workflow(dialog.id)
        return {"dialog": dialog, "current_step": dialog.get_current_step()}

    dialog.create_user_message(message.text)
    # Create assistant message placeholder
    assistant_message = dialog.create_stub_assistant_message(dialog.model)

    # Add to database and dialog
    await message_repository.create(db, assistant_message)

    # Send it to the queue
    await enqueue_message_processing(dialog.id)

    # response.headers['HX-Target'] = "#dashboard"
    # response.headers['HX-Reswap'] = 'outerHTML'

    return {
        "dialog": dialog,
        "messages": dialog.messages,
        "current_step": dialog.get_current_step()
    }


async def enqueue_message_processing(dialog_id: uuid.UUID) -> str:
    """
    Enqueue a message processing job with ARQ

    Args:
        dialog_id: The UUID of the dialog to process
        arq_redis: ARQ Redis connection

    Returns:
        The job ID as a string
    """
    async for arq_redis in get_arq_redis():
        job = await arq_redis.enqueue_job('process_message_job', dialog_id)
        return job.job_id


@router.get("/template-creator/{template_name}")
@jinja.hx('dialog_template_form.html.j2')
async def dialog_template_form(template_name: str,
                                request: Request,
                                workflow_service: WorkflowService = Depends(get_workflow_service)):
    """This route serves the dialog template form for creating a new dialog."""
    # Get the template from the registry
    template = request.app.state.registry.get_dialog_template(template_name)
    if not template:
        return {"error": f"Template {template_name} not found"}

    dialog = Dialog()
    dialog.template = template

    # Analyze workflow dependencies
    workflow_analysis = await workflow_service.analyze_workflow_dependencies(template)

    # @TODO: refactor this to not use engine directly
    await workflow_service.engine.initialize_dialog(dialog)

    return {
        "template": template,
        "template_name": template_name,
        "workflow_analysis": workflow_analysis,
    }


@router.post("/template-creator/{template_name}/create")
@jinja.hx('view_dash.html.j2')
async def create_dialog_from_template_route(
        response: Response,
        template_name: str,
        dialog_create: DialogTemplateCreationRequest,
        workflow_service: WorkflowService = Depends(get_workflow_service),
        registry: Registry = Depends(get_registry),
):
    """Create a new dialog from a template and redirect to it."""
    description = dialog_create.description
    goal = dialog_create.goal

    # Extract workflow input variables from form data
    initial_data = {"variables": {}}

    # Process all form fields that start with "input_" as workflow variables
    for key, value in dialog_create.input.items():
        initial_data["variables"][key] = value

    # Get the template from the registry
    template = registry.get_dialog_template(template_name)
    if not template:
        return {"error": f"Template {template_name} not found"}

    # Create the dialog with initial data
    dialog = await workflow_service.create_dialog_from_template(
        template=template,
        description=description if description else None,
        goal=goal if goal else None,
        initial_data=initial_data
    )

    if not dialog:
        return {"error": "Failed to create dialog"}


    await enqueue_dialog_run_workflow(dialog.id)

    # @TODO this might better be HX-Location
    response.headers['HX-Replace-Url'] = f"/dialog/{dialog.id}"
    response.headers['HX-Trigger'] = 'sse:dialog.updated'

    return {
        "dialog_id": dialog.id,
    }

async def enqueue_dialog_run_workflow(dialog_id: uuid.UUID) -> str:
    """
    Enqueue a message processing job with ARQ

    Args:
        dialog_id: The UUID of the dialog to process
        arq_redis: ARQ Redis connection

    Returns:
        The job ID as a string
    """
    async for arq_redis in get_arq_redis():
        job = await arq_redis.enqueue_job('dialog_run_workflow_job', dialog_id)
        return job.job_id

